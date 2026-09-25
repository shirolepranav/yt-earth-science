"""STAGE 10 - Render.

Hands the shot list to Remotion, which draws every frame in a headless browser
and encodes the result to MP4.

This is the entire editing step. There is no timeline to drag clips around in -
every cut, hold and transition was decided earlier, in the shot list. If a cut
feels wrong, the fix is in the shot list logic or the polish prompt, not in a
video editor.

One mechanical detail: a browser can only load files that the dev server is
serving, so this copies the run's clips, stills and audio into
remotion/public/current/ and rewrites the shot list to use those short names.

Run it:  python -m pipeline.render --run latest
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

from .common import ROOT, Run, log, resolve_run

REMOTION_DIR = ROOT / "remotion"
PUBLIC_DIR = REMOTION_DIR / "public" / "current"
COMPOSITION = "MainVideo"
# Render in 2-minute segments. Remotion's GPU (angle) renderer leaks memory on
# long renders - a 13-minute render died at frame 5144 - and a failed segment
# only costs that segment on the next run, not the whole video.
SEGMENT_FRAMES = 3600


def stage_assets(run: Run) -> Path:
    """Copy this run's assets where the browser can reach them.

    Returns the path to the rewritten props file.
    """
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir(parents=True)

    shot_list = run.read_json("shotlist.json")

    # GPT-6 Astra's chart components are source code, so they go into the
    # bundle (src/generated/) rather than public/. A missing file falls back to
    # the built-in chart instead of failing the render.
    from .charts3d import stage as stage_charts
    components = {}
    for shot in shot_list["shots"]:
        key = shot.get("component")
        if key:
            source = run.path("assets", "charts", f"{key}.tsx")
            if source.exists():
                components[key] = source
            else:
                shot["component"] = None
    stage_charts(components)

    # Audio
    audio_source = Path(shot_list["audioFile"])
    if not audio_source.exists():
        raise FileNotFoundError(f"{audio_source} not found. Run the audio stage first.")
    shutil.copy2(audio_source, PUBLIC_DIR / "narration.wav")
    shot_list["audioFile"] = "current/narration.wav"

    # Clips, stills, depth maps and card plates. Charts, numbers and evidence
    # pages are drawn from data and need no files. Names are content hashes or
    # unique stock ids, so nothing collides in the flat public folder.
    for shot in shot_list["shots"]:
        for key in ("src", "depth"):
            source = shot.get(key)
            if not source:
                continue
            source_path = Path(source)
            if not source_path.exists():
                log(f"  missing {key} for a {shot['type']} shot: {source_path.name}")
                shot[key] = None
                continue
            shutil.copy2(source_path, PUBLIC_DIR / source_path.name)
            shot[key] = f"current/{source_path.name}"

    # A still without its depth map still renders (plain push-in); anything
    # else that lost its file is dropped, and the previous shot holds.
    kept: list[dict] = []
    for shot in shot_list["shots"]:
        if shot["type"] in ("clip", "still", "card") and not shot.get("src"):
            if kept:
                kept[-1]["end"] = shot["end"]
            continue
        kept.append(shot)
    shot_list["shots"] = kept

    props_path = PUBLIC_DIR.parent / "props.json"
    props_path.write_text(json.dumps(shot_list, indent=2))
    return props_path


def code_hash() -> str:
    """Every file the render draws with: a changed component invalidates every segment."""
    digest = hashlib.sha256()
    for path in sorted((REMOTION_DIR / "src").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(REMOTION_DIR).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def segment_keys(shot_list: dict, total_frames: int, code: str) -> list[str]:
    """One key per SEGMENT_FRAMES segment, from everything outside the shots,
    the shots that overlap it and - for the outro's segment - the last shot,
    which the outro freezes. Asset names are content hashes or unique stock
    ids, so a swapped file changes its shot's src."""
    fps, shots = shot_list["fps"], shot_list["shots"]
    shared = json.dumps({k: v for k, v in shot_list.items() if k != "shots"}, sort_keys=True) + code
    outro_from = total_frames - math.ceil(shot_list.get("outroSeconds", 0) * fps)
    keys = []
    for start in range(0, total_frames, SEGMENT_FRAMES):
        end = min(total_frames, start + SEGMENT_FRAMES) - 1
        drawn = [s for s in shots if round(s["start"] * fps) <= end and round(s["end"] * fps) > start]
        if end >= outro_from and shots:
            drawn.append(shots[-1])
        blob = shared + json.dumps(drawn, sort_keys=True)
        keys.append(hashlib.sha256(blob.encode()).hexdigest()[:12])
    return keys


def ensure_dependencies() -> None:
    if not (REMOTION_DIR / "node_modules").exists():
        log("Installing Remotion (first run only, takes a few minutes)...")
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"],
                       cwd=REMOTION_DIR, check=True)


def render(run: Run, output_name: str = "video.mp4") -> Path:
    ensure_dependencies()
    props_path = stage_assets(run)
    output_path = run.path("output", output_name)
    shot_list = json.loads(props_path.read_text())
    total_frames = math.ceil(shot_list["durationSeconds"] * shot_list["fps"])

    # Each segment is named by what it draws, so swapping one shot re-renders
    # only the segment(s) it plays in, and a Remotion code change re-renders all.
    keys = segment_keys(shot_list, total_frames, code_hash())
    fingerprint = hashlib.sha256("".join(keys).encode()).hexdigest()[:12]
    parts_dir = run.path("output", "parts")
    parts_dir.mkdir(exist_ok=True)

    base_command = [
        f"--props={props_path}",
        # Half the cores: each worker is a browser tab, and past that they fight for memory.
        f"--concurrency={os.getenv('REMOTION_CONCURRENCY', str(max(2, (os.cpu_count() or 4) // 2)))}",
        # WebGL backend for the three.js charts and parallax stills: "angle" uses
        # the GPU (a Mac); "swangle" is software rendering for GPU-less CI.
        f"--gl={os.getenv('REMOTION_GL', 'angle')}",
        # Tabs busy decoding clips and drawing WebGL can take well over the
        # 30s default to load textures.
        "--timeout=120000",
        "--muted",  # the narration is muxed in once at the end, sample-accurate
        # "error" hid Remotion's own frame counter, which left a multi-hour
        # render with no way to tell "slow" from "stuck" - not in the chat, and
        # not even in the CI log. "info" prints the frame progress that makes
        # the render rate measurable.
        f"--log={os.getenv('REMOTION_LOG', 'info')}",
    ]
    # Some environments already have a Chromium installed. Pointing Remotion at
    # it skips a ~150 MB download on every fresh machine.
    browser = os.getenv("REMOTION_BROWSER_EXECUTABLE")
    if browser:
        base_command.append(f"--browser-executable={browser}")

    from . import chat  # late import: rendering must work with no chat configured

    parts = []
    starts = list(range(0, total_frames, SEGMENT_FRAMES))
    log(f"Rendering {total_frames / shot_list['fps'] / 60:.1f} min in {len(starts)} segments "
        "(the slow part - roughly 4-8 minutes per segment on a Mac)...")
    chat.send(
        f"🎞 <b>Rendering</b> — {total_frames / shot_list['fps'] / 60:.0f} minutes of video "
        f"in {len(starts)} segments.\n\n"
        "<i>This is the long one. I'll report after each segment with an estimate.</i>"
    )

    # Timing only the segments actually rendered in this job. A restored
    # segment costs nothing, so counting it would flatter the estimate.
    rendered = 0
    spent = 0.0

    for number, start in enumerate(starts, 1):
        end = min(total_frames, start + SEGMENT_FRAMES) - 1
        part = parts_dir / f"{keys[number - 1]}_{start:06d}.mp4"
        parts.append(part)
        if part.exists():
            log(f"  segment {number}/{len(starts)}: already rendered")
            continue
        log(f"  segment {number}/{len(starts)}: frames {start}-{end}")
        tmp = part.with_name(part.stem + ".partial.mp4")

        began = time.monotonic()
        subprocess.run(["npx", "remotion", "render", COMPOSITION, str(tmp),
                        f"--frames={start}-{end}", *base_command], cwd=REMOTION_DIR, check=True)
        tmp.replace(part)

        rendered += 1
        spent += time.monotonic() - began

        # How many are genuinely left - a segment already on disk is not work.
        left = sum(1 for later, other in enumerate(starts[number:], number + 1)
                   if not (parts_dir / f"{fingerprint}_{other:06d}.mp4").exists())
        each = spent / rendered
        log(f"    {each / 60:.1f} min for that segment; {left} left")

        if left:
            chat.send(f"🎞 Segment <b>{number}/{len(starts)}</b> done — "
                      f"about <b>{left * each / 60:.0f} min</b> left "
                      f"({each / 60:.1f} min per segment)")
        else:
            chat.send(f"🎞 Segment <b>{number}/{len(starts)}</b> done — stitching the audio on now.")

    concat_list = parts_dir / f"{fingerprint}.txt"
    concat_list.write_text("".join(f"file '{p.name}'\n" for p in parts))
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(REMOTION_DIR / "public" / shot_list["audioFile"]),
        # Silence under the outro. Padding with silence leaves the -14 LUFS
        # integrated loudness from the audio stage unchanged (gated measure).
        "-map", "0:v", "-map", "1:a", "-af", "apad", "-t", f"{total_frames / shot_list['fps']:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(output_path),
    ], check=True)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    run.save_state(video_path=str(output_path))
    run.mark_done("render")
    log(f"Rendered: {output_path} ({size_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Render the video with Remotion.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    render(resolve_run(args.run))
