"""Runs the slow half of a chat request.

`pipeline/assistant.py` answers anything quick inside the job that received
your message. Anything that takes minutes - proposing topics, writing a script,
building a video - lands here instead, started by its own job in
.github/workflows/chat.yml so the fast replies stay fast.

One entry point for all of them, so the workflow stays a thin wrapper:

    python tools/chat_job.py --intent approve_script --args '{}' --run latest

Every path ends the same way: it posts the next gate to Telegram, so you always
know what it wants from you next.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Let this run as `python tools/chat_job.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import assistant, chat, publish, script  # noqa: E402
from pipeline.common import log, resolve_run  # noqa: E402
from pipeline.run import BUILD_STAGES, run_stage  # noqa: E402

# Re-running one of these changes the thumbnail or the subtitle track but NOT
# the video file, so the private upload can stay where it is and just have the
# one thing swapped. Anything else means a re-render and a fresh upload,
# because YouTube can't replace the file behind an existing video.
SIDECAR_STAGES = {"thumbnail", "captions"}


def do_topics() -> None:
    """Start a new run and present ten topics."""
    from pipeline import topics

    run = resolve_run(None)  # None means "make a new run"
    log(f"Run id: {run.id}")
    chat.send(f"🔎 Looking for topics… (run <code>{run.id}</code>)")

    topics.generate(run)
    assistant.present_topics(run)

    # The workflow reads this to know what to commit.
    print(f"RUN_ID={run.id}")


def do_pick(run_id: str, args: dict) -> None:
    """Record the topic you chose, then research and write the script."""
    number = args.get("number")
    if not number:
        chat.send("I didn't catch which number you meant — send just the digit?")
        return

    run = resolve_run(run_id)
    all_topics = run.read_json("topics.json")["topics"]
    match = next((t for t in all_topics if int(t["rank"]) == int(number)), None)
    if not match:
        chat.send(f"There's no topic {number} — the list has {len(all_topics)}.")
        return

    run.write_json("chosen_topic.json", match)
    run.mark_done("choose")
    chat.send(f"📚 Researching <b>{chat.escape(match['title'])}</b>. "
              "This takes about twenty minutes — I'll send the script when it's done.")

    run_stage(run, "research")
    run_stage(run, "script")
    assistant.present_script(run)


def do_revise(run_id: str, intent: str, args: dict) -> None:
    """Apply an edit to the script and show it again."""
    run = resolve_run(run_id)

    if intent == "replace_script":
        pasted = (args.get("script") or "").strip()
        if len(pasted) < 200:
            chat.send("That looked too short to be a whole script — paste it in a code block?")
            return
        run.write_text("script.txt", pasted)
        run.reset_stages(keep=["choose", "research", "script"])
        chat.send("✅ Using your script as written.")
    else:
        instruction = args.get("instruction") or ""
        if not instruction:
            chat.send("Tell me what to change and I'll do it.")
            return
        chat.send("✍️ Rewriting…")
        summary = script.revise(run, instruction)
        chat.send(f"✅ {chat.escape(summary)}")

    assistant.present_script(run)


def do_build(run_id: str, args: dict, redo_stage: str = "") -> None:
    """Build the video, or redo one stage of it, then upload privately."""
    run = resolve_run(run_id)

    if redo_stage:
        if redo_stage not in BUILD_STAGES:
            chat.send(f"I can't redo '{chat.escape(redo_stage)}'.")
            return

        # A sidecar only needs itself re-run. Anything else invalidates every
        # stage after it, because they were all cut against what it produced.
        if redo_stage in SIDECAR_STAGES:
            chat.send(f"🔁 Redoing the {redo_stage}…")
            run_stage(run, redo_stage, force=True)
            if redo_stage == "thumbnail":
                publish.apply_thumbnail(run)
            else:
                publish.apply_metadata(run)
            assistant.present_review(run)
            return

        start = BUILD_STAGES.index(redo_stage)
        run.reset_stages(keep=["choose", "research", "script"] + BUILD_STAGES[:start])
        chat.send(f"🔁 Redoing {redo_stage} and everything after it. "
                  "The video has to be rebuilt and re-uploaded.")
        # YouTube can't swap the file behind an existing video, so the old
        # private upload has to go before the new one arrives.
        publish.delete_video(run)
    else:
        chat.send("🎬 Building. This takes 30–90 minutes — I'll send the link when it's ready.")

    run.save_state(chat_stage="building")

    for name in BUILD_STAGES:
        if run.is_done(name):
            continue
        chat.progress(name)
        run_stage(run, name)

    assistant.present_review(run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the slow half of a chat request.")
    parser.add_argument("--intent", required=True)
    parser.add_argument("--args", default="{}", help="JSON from the router.")
    parser.add_argument("--run", default="latest")
    options = parser.parse_args()

    try:
        args = json.loads(options.args or "{}")
    except json.JSONDecodeError:
        args = {}

    intent = options.intent
    if intent == "new":
        do_topics()
    elif intent == "pick":
        do_pick(options.run, args)
    elif intent in ("edit_script", "replace_script"):
        do_revise(options.run, intent, args)
    elif intent == "approve_script":
        do_build(options.run, args)
    elif intent == "redo":
        do_build(options.run, args, redo_stage=args.get("stage", ""))
    else:
        log(f"Nothing slow to do for intent '{intent}'.")


if __name__ == "__main__":
    main()
