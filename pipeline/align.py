"""STAGE 5 - Word-level timing.

Produces a JSON file listing every spoken word with the exact second it starts
and ends.

With ElevenLabs the narrate stage already wrote words.json from the engine's own
character timings - exact, free, and nothing to re-derive - so this stage just
checks it covers the script. Any other voice provider means transcribing the
audio back with faster-whisper.

Every shot in the video is cut against these timings - a new visual every two
to six seconds, a chart landing on the number, a card landing on the question.
So there is no fallback: estimated timings drift a second or more within a
minute, which at this cutting pace means every visual lands on the wrong words.
If faster-whisper is missing, the build stops here and says how to fix it.

faster-whisper rather than WhisperX: same word-level output, no PyTorch or
pyannote, a ~200 MB install rather than ~2.5 GB.

Run it:  python -m pipeline.align --run latest
"""

from __future__ import annotations

import re
import wave
from pathlib import Path

from .common import Run, log, resolve_run

MODEL_SIZE = "base.en"  # small, fast, and accurate enough for timing


def audio_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


# ---------------------------------------------------------------------------
# Transcription with word timestamps
# ---------------------------------------------------------------------------

def transcribe_with_whisper(audio_path: Path) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper is not installed, and shots can't be timed without it. "
            "Install it with: pip install -r requirements.txt"
        ) from None

    log(f"  transcribing with faster-whisper ({MODEL_SIZE})...")
    # int8 on CPU is roughly 4x faster than float32 with no meaningful accuracy
    # loss for timing purposes, which is all we need it for.
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    segments, _info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        vad_filter=True,          # skip silence, which improves timing accuracy
        beam_size=5,
    )

    words: list[dict] = []
    for segment in segments:
        for word in (segment.words or []):
            words.append({
                "word": word.word.strip(),
                "start": round(word.start, 3),
                "end": round(word.end, 3),
            })
    return words


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(run: Run) -> list[dict]:
    audio_path = run.path("audio", "narration.wav")
    if not audio_path.exists():
        raise FileNotFoundError(f"{audio_path} not found. Run the narrate stage first.")

    duration = audio_duration_seconds(audio_path)
    log(f"Aligning {duration / 60:.1f} minutes of narration")

    # Timings the voice engine already gave us, if the script is all there:
    # a missing tail would mean cutting the last minutes against nothing.
    if run.path("words.json").exists():
        existing = run.read_json("words.json")
        words = existing.get("words") or []
        spoken = len(" ".join(w["word"] for w in words))
        script = len(re.sub(r"\s+", " ", run.read_text("script.txt")).strip())
        if existing.get("method") == "elevenlabs" and words and spoken > 0.9 * script:
            log(f"  using the voice engine's own timings for {len(words):,} words")
            run.mark_done("align")
            return words
        if existing.get("method") == "elevenlabs":
            log(f"  voice-engine timings cover only {spoken}/{script} characters - transcribing instead")

    words = transcribe_with_whisper(audio_path)
    if not words:
        raise RuntimeError(f"faster-whisper found no words in {audio_path}.")
    method = "faster-whisper"

    run.write_json("words.json", {"method": method, "duration": duration, "words": words})
    run.save_state(alignment_method=method, narration_seconds=round(duration, 2))
    run.mark_done("align")

    log(f"Wrote timings for {len(words):,} words ({method})")
    return words


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Produce word-level timings.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    generate(resolve_run(args.run))
