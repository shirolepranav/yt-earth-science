"""STAGE 8 - Audio mastering.

Two jobs:

  1. Duck background music under the narration. Music at a constant level fights
     the voice; ducking drops it automatically whenever the narrator speaks.
  2. Normalise the whole mix to about -14 LUFS, which is what YouTube targets.
     Skip this and your videos sound quieter than everything else in the feed,
     which viewers experience as "low quality" without knowing why.

Music is optional. With no music file present this still runs and just does the
loudness pass, which is the part that actually matters.

Put royalty-free tracks (YouTube Audio Library is fine and cleared for
monetisation) in assets/music/ as .mp3 or .wav.

Run it:  python -m pipeline.audio --run latest
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

from .common import ROOT, Run, log, resolve_run

MUSIC_DIR = ROOT / "assets" / "music"
TARGET_LUFS = -14.0     # YouTube's normalisation target
MUSIC_LEVEL = 0.14      # music volume before ducking


def pick_music(run_id: str) -> Path | None:
    """Choose a music bed, rotating between tracks across videos.

    Rotation is deliberate: the same bed on every upload is exactly the kind of
    template signature that reads as mass production.
    """
    if not MUSIC_DIR.exists():
        return None
    tracks = sorted(
        p for p in MUSIC_DIR.iterdir()
        if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac")
    )
    if not tracks:
        return None
    random.seed(run_id)  # same run always picks the same track
    return random.choice(tracks)


def run_ffmpeg(args: list[str], label: str) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed:\n{result.stderr[-2000:]}")


def master(run: Run) -> Path:
    narration = run.path("audio", "narration.wav")
    output = run.path("audio", "narration_mixed.wav")

    if not narration.exists():
        raise FileNotFoundError(f"{narration} not found. Run the narrate stage first.")

    music = pick_music(run.id)

    if music:
        log(f"Mixing with music bed: {music.name}")
        # sidechaincompress is the ducking: the narration (second input to the
        # filter) controls how far the music gets pushed down.
        filter_graph = (
            f"[1:a]volume={MUSIC_LEVEL},aloop=loop=-1:size=2e9[music];"
            "[music][0:a]sidechaincompress="
            "threshold=0.02:ratio=12:attack=20:release=400[ducked];"
            "[ducked][0:a]amix=inputs=2:duration=first:dropout_transition=0[mixed];"
            f"[mixed]loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11[out]"
        )
        run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(narration),
            "-i", str(music),
            "-filter_complex", filter_graph,
            "-map", "[out]",
            "-ar", "48000", "-ac", "2",
            str(output),
        ], "audio mix")
    else:
        log("No music found in assets/music/ - doing the loudness pass only")
        run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(narration),
            "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11",
            "-ar", "48000", "-ac", "2",
            str(output),
        ], "loudness normalisation")

    run.mark_done("audio")
    log(f"Mastered audio: {output}")
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mix and normalise the audio.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    master(resolve_run(args.run))
