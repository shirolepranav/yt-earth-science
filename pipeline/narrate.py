"""STAGE 4 - Narration.

Turns script.txt into one narration WAV.

Long scripts have to be sent to the voice API in pieces - no provider will
synthesise ten minutes in a single call reliably. We split only at paragraph
breaks, never mid-sentence, and each piece is saved to disk as it arrives so a
failure on chunk four doesn't mean paying to regenerate chunks one to three.

Four providers are implemented. All hand back the same thing: raw 16-bit mono
PCM at 24 kHz, which we glue together with a short silence between pieces.
ElevenLabs is the default: Gemini re-rolled the voice on every call, and one
join in the 14 Sep build (2:19) sounded like a different narrator.

Run it:  python -m pipeline.narrate --run latest
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import tempfile
import wave
from pathlib import Path

import requests

from .common import Run, load_config, log, resolve_run, secret, with_retries

SAMPLE_WIDTH_BYTES = 2  # 16-bit audio
CHANNELS = 1            # mono


# ---------------------------------------------------------------------------
# Splitting the script into API-sized pieces
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split into chunks at paragraph boundaries only.

    Splitting mid-sentence is audible: the voice resets its intonation and the
    seam sounds like a stitch. Paragraph breaks are where a human reader would
    pause anyway, so the joins disappear.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph

    if current:
        chunks.append(current)
    return chunks


# ---------------------------------------------------------------------------
# Provider: Gemini TTS (the default)
# ---------------------------------------------------------------------------

def _gemini_pcm(text: str, cfg: dict) -> bytes:
    """Ask Gemini for speech. It returns base64 PCM at 24 kHz, 16-bit, mono."""
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{cfg['gemini_model']}:generateContent",
        headers={"x-goog-api-key": secret("GEMINI_API_KEY")},  # header, not URL: URLs end up in error logs
        json={
            "contents": [{"parts": [{"text": f"{cfg['gemini_style']}\n\n{text}" if cfg.get("gemini_style") else text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": cfg["gemini_voice"]}
                    }
                },
            },
        },
        timeout=600,
    )
    response.raise_for_status()
    parts = response.json()["candidates"][0]["content"]["parts"]
    audio_b64 = parts[0]["inlineData"]["data"]
    return base64.b64decode(audio_b64)


# ---------------------------------------------------------------------------
# Provider: Qwen TTS (Alibaba Model Studio, Singapore endpoint)
# ---------------------------------------------------------------------------

def _qwen_pcm(text: str, cfg: dict) -> bytes:
    """Qwen returns a URL to an audio file, which we download and convert."""
    response = requests.post(
        "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/"
        "multimodal-generation/generation",
        headers={
            "Authorization": f"Bearer {secret('QWEN_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": cfg["qwen_model"],
            "input": {
                "text": text,
                "voice": cfg["qwen_voice"],
                "language_type": "English",
            },
        },
        timeout=600,
    )
    response.raise_for_status()
    audio_url = response.json()["output"]["audio"]["url"]

    downloaded = requests.get(audio_url, timeout=300)
    downloaded.raise_for_status()

    # Convert whatever format Qwen sent into the same raw PCM the rest of this
    # module expects, so both providers are interchangeable downstream.
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as handle:
        handle.write(downloaded.content)
        temp_path = handle.name

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", temp_path,
         "-ar", str(cfg["sample_rate"]), "-ac", "1", "-f", "s16le", "-"],
        capture_output=True,
        check=True,
    )
    Path(temp_path).unlink(missing_ok=True)
    return result.stdout


# ---------------------------------------------------------------------------
# Provider: Speechify TTS (raw PCM, no conversion needed)
# ---------------------------------------------------------------------------

def _speechify_pcm(text: str, cfg: dict) -> bytes:
    """Speechify streams raw 16-bit PCM directly when asked via output_format."""
    response = requests.post(
        "https://api.speechify.ai/v1/audio/stream",
        headers={
            "Authorization": f"Bearer {secret('SPEECHIFY_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "input": text,
            "voice_id": cfg["speechify_voice"],
            "model": cfg["speechify_model"],
            "output_format": f"pcm_{cfg['sample_rate']}",
        },
        timeout=600,
    )
    response.raise_for_status()
    body = response.json()
    return base64.b64decode(body["audio_base64"]), body.get("alignment") or {}


def words_from_alignment(alignment: dict, offset: float) -> list[dict]:
    """Character times -> one entry per word, shifted to its place in the full WAV."""
    words: list[dict] = []
    letters, starts, ends = (alignment.get("characters") or [],
                             alignment.get("character_start_times_seconds") or [],
                             alignment.get("character_end_times_seconds") or [])
    current, start, end = "", 0.0, 0.0
    for letter, first, last in zip(letters, starts, ends):
        if letter.isspace():
            if current:
                words.append({"word": current, "start": round(start + offset, 3), "end": round(end + offset, 3)})
                current = ""
            continue
        if not current:
            start = first
        current, end = current + letter, last
    if current:
        words.append({"word": current, "start": round(start + offset, 3), "end": round(end + offset, 3)})
    return words


# ---------------------------------------------------------------------------
# Provider: ElevenLabs (the default - one fixed voice, stitched across chunks)
# ---------------------------------------------------------------------------

def _elevenlabs_pcm(text: str, cfg: dict, previous_text: str = "", next_text: str = "") -> tuple[bytes, dict]:
    """ElevenLabs returns raw PCM when asked, plus the exact time of every
    character it spoke - timings from the engine that made the audio, so no
    second model has to guess them back out. previous_text/next_text tell it
    what surrounds this chunk, so the delivery carries across the join; the
    fixed seed keeps a regenerated chunk close to its neighbours."""
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['elevenlabs_voice_id']}/with-timestamps",
        params={"output_format": f"pcm_{cfg['sample_rate']}"},
        headers={"xi-api-key": secret("ELEVENLABS_API_KEY"), "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": cfg["elevenlabs_model"],
            "voice_settings": {"stability": cfg["elevenlabs_stability"],
                               "similarity_boost": cfg["elevenlabs_similarity"]},
            "previous_text": previous_text[-1000:] or None,
            "next_text": next_text[:1000] or None,
            "seed": cfg.get("elevenlabs_seed", 1),
        },
        timeout=600,
    )
    response.raise_for_status()
    body = response.json()
    return base64.b64decode(body["audio_base64"]), body.get("alignment") or {}


def words_from_alignment(alignment: dict, offset: float) -> list[dict]:
    """Character times -> one entry per word, shifted to its place in the full WAV."""
    words: list[dict] = []
    letters, starts, ends = (alignment.get("characters") or [],
                             alignment.get("character_start_times_seconds") or [],
                             alignment.get("character_end_times_seconds") or [])
    current, start, end = "", 0.0, 0.0
    for letter, first, last in zip(letters, starts, ends):
        if letter.isspace():
            if current:
                words.append({"word": current, "start": round(start + offset, 3), "end": round(end + offset, 3)})
                current = ""
            continue
        if not current:
            start = first
        current, end = current + letter, last
    if current:
        words.append({"word": current, "start": round(start + offset, 3), "end": round(end + offset, 3)})
    return words


# ---------------------------------------------------------------------------
# Writing the finished WAV
# ---------------------------------------------------------------------------

def write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(CHANNELS)
        out.setsampwidth(SAMPLE_WIDTH_BYTES)
        out.setframerate(sample_rate)
        out.writeframes(pcm)


def silence(seconds: float, sample_rate: int) -> bytes:
    """A run of zero bytes - i.e. digital silence - of the given length."""
    return b"\x00" * int(seconds * sample_rate * SAMPLE_WIDTH_BYTES * CHANNELS)


# ---------------------------------------------------------------------------
# Voice drift - why the same voice sounded like two narrators
# ---------------------------------------------------------------------------

MAX_PITCH_DRIFT = 0.08   # measured: good chunks sit within ~5% of each other,
DRIFT_RETRIES = 2        # the "second narrator" chunks were 20-27% higher


def median_pitch(pcm: bytes, sample_rate: int) -> float:
    """Median fundamental frequency (Hz) of voiced speech, by autocorrelation.

    Every chunk is a separate TTS call, and the voice drifts between calls: in
    the 14 Sep 2026 runs chunks alternated between ~116 Hz and ~148 Hz - enough
    to sound like two people taking turns. This is the number that catches it.
    """
    import numpy as np  # installed with faster-whisper

    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    frame, lo, hi = int(0.04 * sample_rate), int(sample_rate / 300), int(sample_rate / 60)
    pitches = []
    for start in range(0, len(samples) - frame, frame * 2):
        window = samples[start:start + frame]
        if np.sqrt((window ** 2).mean()) < 500:  # silence
            continue
        window = window - window.mean()
        corr = np.correlate(window, window, "full")[frame - 1:]
        lag = lo + int(np.argmax(corr[lo:hi]))
        if corr[lag] > 0.3 * corr[0]:  # clearly voiced
            pitches.append(sample_rate / lag)
    return float(np.median(pitches)) if pitches else 0.0


def synth_consistent(synth, chunk: str, cfg: dict, reference: float | None, label: str) -> bytes:
    """Synthesise a chunk, regenerating it if its pitch drifts from the first chunk's."""
    best, best_drift = b"", float("inf")
    for attempt in range(1 + (DRIFT_RETRIES if reference else 0)):
        pcm = with_retries(lambda: synth(chunk, cfg), label=label)
        if not reference:
            return pcm
        drift = abs(median_pitch(pcm, cfg["sample_rate"]) - reference) / reference
        if drift < best_drift:
            best, best_drift = pcm, drift
        if drift <= MAX_PITCH_DRIFT:
            break
        if attempt < DRIFT_RETRIES:
            log(f"    voice drifted {drift:.0%} from the first chunk - regenerating ({attempt + 1}/{DRIFT_RETRIES})")
    if best_drift > MAX_PITCH_DRIFT:
        log(f"    kept the closest take ({best_drift:.0%} drift) - listen to this join")
    return best


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(run: Run) -> Path:
    cfg = load_config()["models"]["tts"]
    provider = cfg["provider"]
    sample_rate = cfg["sample_rate"]

    script = run.read_text("script.txt")
    chunks = chunk_text(script, cfg.get(f"{provider}_max_chars", cfg["max_chars_per_call"]))
    log(f"Narrating with {provider}: {len(chunks)} chunk(s), "
        f"{len(script):,} characters total")

    synth = {"gemini": _gemini_pcm, "qwen": _qwen_pcm, "speechify": _speechify_pcm}.get(provider)
    gap = silence(cfg["pause_seconds"], sample_rate)
    pieces: list[bytes] = []
    reference: float | None = None  # the first chunk's pitch; every later chunk must match it

    words: list[dict] = []
    spoken_seconds = 0.0  # where the next chunk starts in the finished WAV
    for index, chunk in enumerate(chunks, 1):
        chunk_path = run.path("audio", f"chunk{index:02d}.wav")
        align_path = run.path("audio", f"chunk{index:02d}.align.json")

        # Skip anything already generated - this is what makes a re-run cheap.
        if chunk_path.exists():
            log(f"  chunk {index}/{len(chunks)}: already done, skipping")
            with wave.open(str(chunk_path), "rb") as existing:
                pieces.append(existing.readframes(existing.getnframes()))
        else:
            log(f"  chunk {index}/{len(chunks)}: {len(chunk):,} chars...")
            call = synth
            if provider == "elevenlabs":
                before, after = "\n\n".join(chunks[:index - 1]), "\n\n".join(chunks[index:])
                # Keep each take's timings; synth_consistent may regenerate and keep an earlier one.
                alignments: dict[bytes, dict] = {}

                def call(text, c, before=before, after=after, alignments=alignments):  # noqa: E731
                    pcm, alignment = _elevenlabs_pcm(text, c, before, after)
                    alignments[hashlib.sha256(pcm).digest()] = alignment
                    return pcm

            pcm = synth_consistent(call, chunk, cfg, reference, f"tts chunk {index}")
            write_wav(chunk_path, pcm, sample_rate)
            if provider == "elevenlabs":
                align_path.write_text(json.dumps(alignments.get(hashlib.sha256(pcm).digest(), {})))
            pieces.append(pcm)
        if reference is None:
            reference = median_pitch(pieces[-1], sample_rate) or None

        if align_path.exists():
            words += words_from_alignment(json.loads(align_path.read_text()), spoken_seconds)
        spoken_seconds += len(pieces[-1]) / (sample_rate * SAMPLE_WIDTH_BYTES * CHANNELS) + cfg["pause_seconds"]
        pieces.append(gap)

    full = b"".join(pieces)
    output_path = run.path("audio", "narration.wav")
    write_wav(output_path, full, sample_rate)

    duration = len(full) / (sample_rate * SAMPLE_WIDTH_BYTES * CHANNELS)
    # The engine's own character timings beat transcribing the audio back with
    # whisper: they are exact, and the align stage uses them when they are here.
    if words:
        run.write_json("words.json", {"method": "elevenlabs", "duration": duration, "words": words})
        log(f"  wrote exact timings for {len(words):,} words from the voice engine")
    run.save_state(narration_seconds=round(duration, 2))
    run.mark_done("narrate")

    log(f"Narration written: {output_path} ({duration / 60:.1f} minutes)")
    if len(chunks) > 1:
        joins = ", ".join(
            f"{sum(len(p) for p in pieces[:i * 2]) / (sample_rate * 2) / 60:.1f}min"
            for i in range(1, len(chunks))
        )
        log(f"  Chunk joins (each checked for pitch drift): {joins}")
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Narrate the approved script.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    generate(resolve_run(args.run))
