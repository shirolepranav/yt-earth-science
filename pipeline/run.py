"""The orchestrator - one command that drives the whole pipeline.

Everything is a named stage. Stages write their output to the run folder before
the next one starts, so any stage can be re-run on its own without redoing (or
re-paying for) the ones before it.

The order:

    topics     propose 10 candidates              -> GATE 1 (you pick one)
    choose     record your pick
    research   build the sourced dossier
    script     five-pass writing chain            -> GATE 2 (you approve/edit)
    narrate    text to speech
    align      word-level timings
    storyboard plan every shot against those timings
    charts     GPT-6 Astra writes a bespoke three.js component per chart
    stock      fetch and verify the real-world clips
    visuals    AI keyframes, motion clips, depth maps (budget-capped)
    shotlist   map the plan to what was built
    audio      music ducking + loudness
    thumbnail  three thumbnails, ranked by a shrink test
    render     Remotion draws the video
    publish    upload (only if review_only is false)

Common uses:

    python -m pipeline.run topics
    python -m pipeline.run choose --run latest --pick 3
    python -m pipeline.run build --run latest        # everything after Gate 2
    python -m pipeline.run stage render --run latest # re-run one stage
"""

from __future__ import annotations

import argparse
import sys

from . import (
    align, audio, charts3d, narrate, publish, render, research, script, shotlist, stock,
    storyboard, thumbnail, topics, visuals,
)
from .common import Run, log, resolve_run

# Stage name -> the function that runs it. Each takes a Run.
STAGES = {
    "research": lambda run: research.generate(run, run.read_json("chosen_topic.json")),
    "script": script.generate,
    "narrate": narrate.generate,
    "align": align.generate,
    "storyboard": storyboard.generate,
    "charts": charts3d.build_for_run,
    "stock": stock.build_for_run,
    "visuals": visuals.build_for_run,
    "shotlist": shotlist.build,
    "audio": audio.master,
    "thumbnail": thumbnail.generate,
    "render": render.render,
    "publish": publish.upload,
}

# Everything that happens after the human approves the script at Gate 2.
BUILD_STAGES = [
    "narrate", "align", "storyboard", "charts", "stock", "visuals", "shotlist",
    "audio", "thumbnail", "render", "publish",
]


def run_stage(run: Run, name: str, force: bool = False) -> None:
    if not force and run.is_done(name):
        log(f"== {name}: already done, skipping (use --force to redo it)")
        return

    log(f"== {name}")
    STAGES[name](run)


def cmd_topics(args) -> None:
    active = resolve_run(args.run)
    log(f"Run id: {active.id}")
    result = topics.generate(active)
    print()
    print(topics.format_for_humans(result))
    print(f"\nRUN_ID={active.id}")


def cmd_choose(args) -> None:
    active = resolve_run(args.run)
    all_topics = active.read_json("topics.json")["topics"]

    match = next((t for t in all_topics if int(t["rank"]) == args.pick), None)
    if not match:
        sys.exit(f"No topic ranked {args.pick}. There are {len(all_topics)}.")

    active.write_json("chosen_topic.json", match)
    active.mark_done("choose")
    log(f"Chose #{args.pick}: {match['title']}")


def cmd_write(args) -> None:
    """Research + script. Everything between Gate 1 and Gate 2."""
    active = resolve_run(args.run)
    run_stage(active, "research", args.force)
    run_stage(active, "script", args.force)
    print()
    print(script.format_for_humans(active))


def cmd_build(args) -> None:
    """Everything after Gate 2: audio, visuals, render, and maybe upload."""
    active = resolve_run(args.run)
    for name in BUILD_STAGES:
        run_stage(active, name, args.force)
    log("Build complete.")
    log(f"  video:     {active.path('output', 'video.mp4')}")
    log(f"  thumbnail: {active.path('output', 'thumbnail.jpg')}")


def cmd_stage(args) -> None:
    active = resolve_run(args.run)
    if args.name not in STAGES:
        sys.exit(f"Unknown stage '{args.name}'. Options: {', '.join(STAGES)}")
    run_stage(active, args.name, force=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="The Boring Docs video pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("topics", help="Propose 10 topics (Gate 1)")
    p.add_argument("--run", default=None)
    p.set_defaults(func=cmd_topics)

    p = sub.add_parser("choose", help="Record which topic you picked")
    p.add_argument("--run", default="latest")
    p.add_argument("--pick", type=int, required=True)
    p.set_defaults(func=cmd_choose)

    p = sub.add_parser("write", help="Research + script chain (Gate 2)")
    p.add_argument("--run", default="latest")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("build", help="Everything after the script is approved")
    p.add_argument("--run", default="latest")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("stage", help="Re-run one named stage")
    p.add_argument("name")
    p.add_argument("--run", default="latest")
    p.set_defaults(func=cmd_stage)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
