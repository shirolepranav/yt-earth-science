"""The thing you actually talk to.

`brain.py` works out what you meant. This module does it, and writes back.

It splits the work in two, because the jobs have wildly different runtimes:

  * **Fast intents** - status, a title change, picking a thumbnail, publishing -
    are handled right here, in the same GitHub Actions job that received your
    message. You get an answer in under a minute.

  * **Slow intents** - proposing topics, writing a script, building a video -
    are only *named* here. `route()` returns the intent string and the workflow
    starts a separate job for it, so a 90-minute build never blocks a reply.

The other half of this module is the three gates: the messages that present
topics, the script and the finished video, each with the buttons that move the
run forward.

Run it:  python -m pipeline.assistant --text "use thumbnail b"
"""

from __future__ import annotations

import os

from . import brain, chat, publish
from .common import Run, latest_run_id, log, resolve_run

# Where a run is, from the chat's point of view. Kept in the run's state.json
# so a fresh Actions job can pick up the conversation with no memory of its own.
STAGES = ("topics", "script", "building", "review", "published", "cancelled")

# Intents this module finishes on the spot. Everything else is handed to a
# dedicated job by the workflow.
FAST = {"status", "question", "unclear", "pick_thumbnail", "set_title", "set_tags",
        "set_description", "publish", "cancel"}


def active_run() -> Run | None:
    """The run the conversation is about - always the most recent one."""
    run_id = latest_run_id()
    return resolve_run(run_id) if run_id else None


def log_url() -> str:
    """A link to the job currently running, for error messages."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    return f"https://github.com/{repo}/actions/runs/{run_id}" if repo and run_id else ""


# ---------------------------------------------------------------------------
# Gate 1 - the topics
# ---------------------------------------------------------------------------

def present_topics(run: Run) -> None:
    """Post the ten proposed topics with a numbered button for each."""
    topics = run.read_json("topics.json").get("topics", [])

    lines = [f"🎬 <b>New video</b> — run <code>{run.id}</code>", "",
             "Ten topics. Tap one, or tell me what you'd rather make.", ""]
    for topic in topics:
        lines += [
            f"<b>{topic['rank']}. {chat.escape(topic['title'])}</b>",
            f"{chat.escape(topic['why_they_click'])}",
            "",
        ]

    # Telegram gets cramped past five buttons in a row.
    numbers = [str(t["rank"]) for t in topics]
    rows = [[(n, f"pick:{n}") for n in numbers[i:i + 5]] for i in range(0, len(numbers), 5)]

    run.save_state(chat_stage="topics")
    chat.send("\n".join(lines), buttons=chat.keyboard(*rows))


# ---------------------------------------------------------------------------
# Gate 2 - the script
# ---------------------------------------------------------------------------

def present_script(run: Run) -> None:
    """Post the finished script for review, with an Approve button."""
    from .script import word_count

    script_text = run.read_text("script.txt")
    metadata = run.read_json("metadata.json")
    check = run.read_json("factcheck.json")
    flags = check.get("flags", [])

    header = [
        f"✍️ <b>Script ready</b> — run <code>{run.id}</code>", "",
        f"<b>{chat.escape(metadata.get('title', '(no title)'))}</b>",
        f"{word_count(script_text):,} words · ~{word_count(script_text) / 150:.0f} min · "
        f"fact-check: <b>{chat.escape(check.get('verdict', 'unknown'))}</b>",
    ]
    if flags:
        header += ["", f"⚠️ {len(flags)} claim(s) flagged:"]
        header += [f"• {chat.escape(f.get('problem', ''))}" for f in flags[:5]]

    chat.send("\n".join(header))
    chat.send(chat.escape(script_text))

    run.save_state(chat_stage="script")
    chat.send(
        "Tell me what to change, or paste a rewritten script in a code block.\n\n"
        "<i>This gate isn't a rubber stamp — changing something is what makes "
        "this a person using AI tools rather than a content farm.</i>",
        buttons=chat.keyboard([("✅ Build it", "cmd:approve"), ("🗑 Cancel", "cmd:cancel")]),
    )


# ---------------------------------------------------------------------------
# Gate 3 - the finished video
# ---------------------------------------------------------------------------

def present_review(run: Run) -> None:
    """Post the private YouTube link, the thumbnails and the upload details."""
    state = run.state()
    metadata = run.read_json("metadata.json")
    video_url = state.get("video_url", "")

    lines = [f"🎥 <b>Video ready</b> — run <code>{run.id}</code>", ""]
    if video_url:
        lines += [f'<a href="{video_url}">Watch it on YouTube</a> (private — only you can see it)', ""]
    else:
        lines += ["The upload was skipped, so the file is in the Actions artifact for this run.", ""]

    lines += [
        f"<b>Title:</b> {chat.escape(metadata.get('title', ''))}",
        f"<b>Tags:</b> {chat.escape(', '.join(metadata.get('tags', [])[:15]))}",
        f"<b>Subtitles:</b> {state.get('subtitle_cues', 0):,} cues",
        "",
        "Watch the first 30 seconds, then tell me anything you want changed — "
        "the title, the tags, the thumbnail, or a stage to redo.",
    ]

    # Anything that quietly fell back to a lesser path during the build. The
    # video is finished either way, but you should know before you publish it.
    problems = chat.degraded()
    if problems:
        lines += ["", "⚠️ <b>Built with something degraded:</b>"]
        lines += [f"• {chat.escape(p)}" for p in problems]

    chat.send("\n".join(lines), preview=True)

    # The three thumbnails, so you can pick by eye rather than by filename.
    selected = publish.chosen_thumbnail(run).name
    for letter, filename in publish.THUMBNAIL_FILES.items():
        path = run.path("output", filename)
        if path.exists():
            mark = " ← currently selected" if filename == selected else ""
            chat.send_photo(path, caption=f"<b>Thumbnail {letter}</b>{mark}")

    chat.send_file(run.path("output", "subtitles.srt"), caption="Subtitles, ready to upload")
    chat.send_file(run.path("output", "UPLOAD.md"), caption="Everything needed for a manual upload")

    run.save_state(chat_stage="review")
    chat.send(
        "Ready?",
        buttons=chat.keyboard(
            [("🅰️", "thumb:a"), ("🅱️", "thumb:b"), ("🅲", "thumb:c")],
            [("🔁 Redo thumbnail", "redo:thumbnail"), ("🔁 Redo footage", "redo:stock")],
            [("🚀 Publish", "cmd:publish")],
        ),
    )


# ---------------------------------------------------------------------------
# The fast handlers
# ---------------------------------------------------------------------------

def resolve_retry(run: Run | None) -> tuple[str, dict]:
    """Turn "retry" into whatever actually needs re-running.

    The workflow decides which job to start from the intent alone, so "retry"
    has to become a concrete intent before it gets there. Which one depends on
    how far the run got, and the run folder already records that: each stage
    writes its output before the next begins, so the first missing file is the
    stage that failed.

    Re-running is safe. Finished stages are skipped by `run.is_done`, so a
    retry picks up where it stopped rather than paying for the whole thing
    again.
    """
    if run is None or not run.path("topics.json").exists():
        # Either nothing has ever run, or the topic engine itself failed.
        return "new", {}

    if not run.path("chosen_topic.json").exists():
        # Topics exist and are waiting on you - there's nothing to re-run.
        return "waiting_for_pick", {}

    if not run.path("script.txt").exists():
        # Research or writing fell over. Re-run it with the topic you chose.
        rank = run.read_json("chosen_topic.json").get("rank")
        return "pick", {"number": int(rank)} if rank else {}

    # The script exists, so the build is what broke. Finished stages are
    # already recorded, so this resumes rather than restarting.
    return "approve_script", {}


def do_status(run: Run | None) -> None:
    if not run:
        chat.send("Nothing in progress. Reply <code>new video</code> to start one.",
                  buttons=chat.keyboard([("🎬 New video", "cmd:new")]))
        return

    state = run.state()
    metadata = run.read_json("metadata.json") if run.path("metadata.json").exists() else {}
    done = state.get("stages_done", [])

    lines = [
        f"📊 <b>Run <code>{run.id}</code></b>",
        f"Stage: <b>{state.get('chat_stage', 'unknown')}</b>",
        f"Finished: {chat.escape(', '.join(done)) if done else 'nothing yet'}",
    ]
    if metadata.get("title"):
        lines.append(f"Title: {chat.escape(metadata['title'])}")
    if state.get("video_url"):
        lines.append(f"Video: {state['video_url']} ({state.get('video_privacy', 'private')})")
    chat.send("\n".join(lines))


def do_pick_thumbnail(run: Run | None, args: dict) -> None:
    if not run:
        chat.send("There's no run to change a thumbnail on.")
        return

    choice = str(args.get("choice", "a"))
    try:
        filename = publish.select_thumbnail(run, choice)
    except (ValueError, FileNotFoundError) as error:
        chat.send(f"⚠️ {chat.escape(str(error))}")
        return

    # If the video is already up on YouTube, change it there too. A YouTube
    # error must not lose the fact that the local choice was saved.
    try:
        note = " Updated on YouTube too." if publish.apply_thumbnail(run) else ""
    except Exception as error:  # noqa: BLE001
        note = f" YouTube refused it though: {chat.escape(str(error)[:200])}"

    chat.send(f"✅ Using <b>{filename}</b>.{note}")


def do_edit_metadata(run: Run | None, intent: str, args: dict) -> None:
    """Handle set_title / set_tags / set_description in one place."""
    if not run or not run.path("metadata.json").exists():
        chat.send("There's no metadata to edit yet.")
        return

    metadata = run.read_json("metadata.json")
    field, value = {
        "set_title": ("title", args.get("title")),
        "set_tags": ("tags", args.get("tags")),
        "set_description": ("description", args.get("description")),
    }[intent]

    if not value:
        chat.send("I didn't catch the new value — send it again with the text?")
        return

    # Tags must be a list. The model usually returns one, but a comma-separated
    # string is a common enough slip that it's worth handling rather than
    # writing a string into a field the upload expects to iterate.
    if field == "tags" and isinstance(value, str):
        value = [tag.strip() for tag in value.split(",") if tag.strip()]

    metadata[field] = value
    run.write_json("metadata.json", metadata)

    try:
        note = "\n\n<i>Updated on YouTube too.</i>" if publish.apply_metadata(run) else ""
    except Exception as error:  # noqa: BLE001
        note = f"\n\n<i>YouTube refused it: {chat.escape(str(error)[:200])}</i>"

    shown = ", ".join(value) if isinstance(value, list) else str(value)
    chat.send(f"✅ New {field}:\n\n{chat.escape(shown[:600])}{note}")


def do_publish(run: Run | None) -> None:
    if not run:
        chat.send("There's nothing to publish.")
        return
    if not run.state().get("video_id"):
        chat.send("This run has no uploaded video — upload it by hand from output/UPLOAD.md.")
        return

    try:
        video_id = publish.go_live(run)
    except Exception as error:  # noqa: BLE001
        chat.send(f"❌ Publishing failed: {chat.escape(str(error))}")
        return

    chat.send(
        f"🚀 <b>Published.</b>\n\nhttps://youtu.be/{video_id}\n\n"
        "<i>If it still shows as private, the Google API project hasn't been "
        "audited yet — flip it public in the YouTube app.</i>",
        preview=True,
    )


def do_cancel(run: Run | None) -> None:
    if not run:
        chat.send("Nothing to cancel.")
        return
    run.save_state(chat_stage="cancelled")
    chat.send(f"🗑 Run <code>{run.id}</code> abandoned. "
              "Reply <code>new video</code> when you want another.",
              buttons=chat.keyboard([("🎬 New video", "cmd:new")]))


# ---------------------------------------------------------------------------
# The entry point the workflow calls
# ---------------------------------------------------------------------------

def route(text: str) -> dict:
    """Work out what you meant, do it if it's quick, and name it either way.

    Returns the whole decision - `{"intent", "args", "reply"}`. The workflow
    reads the intent and decides whether to start a long-running job.
    """
    run = active_run()
    decision = brain.understand(text, run)
    intent, args = decision["intent"], decision.get("args", {})
    reply = decision.get("reply", "")

    # "retry" isn't a job in its own right - work out what it means here, so
    # the workflow still gates on a concrete intent.
    if intent == "retry":
        intent, args = resolve_retry(run)
        decision["intent"], decision["args"] = intent, args
        if intent == "waiting_for_pick":
            chat.send("Nothing failed — the topics are waiting for you. "
                      "Tap a number above, or send one.")
            log("routed to: waiting_for_pick")
            return decision
        reply = f"Retrying from {intent.replace('_', ' ')}."

    # Acknowledge slow work immediately - otherwise you're staring at nothing
    # for the twenty minutes a script takes.
    if intent not in FAST and reply:
        chat.send(f"👍 {chat.escape(reply)}")

    if intent == "status":
        do_status(run)
    elif intent == "pick_thumbnail":
        do_pick_thumbnail(run, args)
    elif intent in ("set_title", "set_tags", "set_description"):
        do_edit_metadata(run, intent, args)
    elif intent == "publish":
        do_publish(run)
    elif intent == "cancel":
        do_cancel(run)
    elif intent in ("question", "unclear"):
        chat.send(chat.escape(reply) or "I'm not sure what you meant — try rephrasing?")

    log(f"routed to: {intent}")
    return decision


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Handle one chat message.")
    parser.add_argument("--text", help="The message you sent.")
    parser.add_argument("--present", choices=["topics", "script", "review"],
                        help="Post a gate message instead of routing a reply.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    if args.present:
        target = resolve_run(args.run)
        {"topics": present_topics, "script": present_script,
         "review": present_review}[args.present](target)
    elif args.text:
        decision = route(args.text)

        # GitHub Actions reads these to decide which job to start next. Writing
        # them from the one decision matters: asking the model twice could give
        # two different answers and start the wrong job.
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a") as handle:
                handle.write(f"intent={decision['intent']}\n")
                handle.write(f"args={json.dumps(decision.get('args', {}))}\n")
                current = active_run()
                handle.write(f"run_id={current.id if current else ''}\n")
        print(decision["intent"])
    else:
        parser.error("Pass either --text or --present.")
