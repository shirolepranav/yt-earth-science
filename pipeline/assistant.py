"""The thing you actually talk to.

`brain.py` works out what you meant. This module does it, and writes back.

It splits the work in two, because the jobs have wildly different runtimes:

  * **Fast intents** - status, a title change, picking a thumbnail, a question -
    are handled right here, as soon as the studio passes your message on.

  * **Slow intents** - proposing topics, writing a script, building a video,
    uploading - are only *named* here. `route()` returns the intent string and
    the studio (../yt-studio) queues tools/chat_job.py for it, so a 90-minute
    build never blocks a reply.

The other half of this module is the three gates: the messages that present
topics, the script and the finished video, each with the buttons that move the
run forward.

Run it:  python -m pipeline.assistant --text "use thumbnail b"
"""

from __future__ import annotations


import re

from . import brain, chat, footage, publish
from .common import RUNS_DIR, Run, latest_run_id, load_persona, log, resolve_run

# Where a run is, from the chat's point of view. Kept in the run's state.json
# so a background job and the app agree on it.
STAGES = ("topics", "script", "building", "review", "published", "cancelled")

# Intents this module finishes on the spot. Everything else is handed to
# tools/chat_job.py by the studio.
FAST = {"status", "question", "unclear", "pick_thumbnail", "set_title", "set_tags",
        "set_description", "set_pinned_comment", "cancel", "footage"}


def active_run() -> Run | None:
    """The run the conversation is about - always the most recent one."""
    run_id = latest_run_id()
    return resolve_run(run_id) if run_id else None


def log_path() -> str:
    """Where the studio sends background jobs' output, for error messages."""
    return str(RUNS_DIR / "job.log")


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

    # Five buttons to a row keeps them readable.
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
    # Runs from before the final check have no "unresolved": show every flag.
    unresolved = check.get("unresolved", check.get("flags", []))
    fixed = len(check.get("flags", [])) - len(unresolved)

    header = [
        f"✍️ <b>Script ready</b> — run <code>{run.id}</code>", "",
        f"<b>{chat.escape(metadata.get('title', '(no title)'))}</b>",
        f"{word_count(script_text):,} words · ~{word_count(script_text) / 150:.0f} min · "
        f"fact-check: <b>{chat.escape(check.get('verdict', 'unknown'))}</b>",
    ]
    if fixed > 0:
        header += [f"🔧 {fixed} claim(s) fixed automatically by the fact-check."]
    if unresolved:
        header += ["", f"⚠️ <b>{len(unresolved)} claim(s) need you</b> — edit them, or build anyway:"]
        header += [f"• <b>{chat.escape(f.get('problem', ''))}</b>: “{chat.escape((f.get('quote') or '')[:160])}”"
                   f" — {chat.escape((f.get('detail') or '')[:240])}" for f in unresolved[:8]]

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
# Gate 2b - the footage, before the render spends 20-40 minutes on it
# ---------------------------------------------------------------------------

def present_footage(run: Run) -> None:
    """Every shot against the script, with a swap for any piece of footage."""
    rows = footage.build(run)
    rendered = run.is_done("render")
    if not rendered:
        run.save_state(chat_stage="footage")
    chat.send_footage(
        run.path("footage.json"),
        f"🎞 <b>Footage</b> — {chat.escape(footage.summary(rows))}\n\n"
        "Open the list to see each shot next to its line of script and why it was picked. "
        "Swap any shot for other stock or an AI image, as many as you like"
        + (" — the video is re-rendered after a swap, redrawing only the changed parts." if rendered
           else ", then render."),
        buttons=None if rendered else chat.keyboard([("🎬 Render", "cmd:render")]),
    )


# ---------------------------------------------------------------------------
# Gate 3 - the finished video
# ---------------------------------------------------------------------------

def present_review(run: Run) -> None:
    """Post the video to watch here, the thumbnails and every upload detail."""
    state = run.state()
    metadata = run.read_json("metadata.json")

    # Written here as well as at upload, so the packet exists while you review.
    description = publish.build_description(run, metadata)
    run.write_text("output/description.txt", description)
    run.write_text("output/UPLOAD.md", publish.build_packet(run))

    chat.send_video(run.path("output", "video.mp4"),
                    caption=f"🎥 <b>Video ready</b> — run <code>{run.id}</code>")

    chat.send("\n".join([
        f"<b>Title:</b> {chat.escape(metadata.get('title', ''))}",
        "",
        "<b>Description:</b>",
        f"<pre>{chat.escape(description)}</pre>",
        f"<b>Tags:</b> {chat.escape(', '.join(metadata.get('tags', [])[:15]))}",
        "",
        f"<b>Pinned comment:</b> {chat.escape(metadata.get('pinned_comment') or '(none)')}",
        f"<b>Subtitles:</b> {state.get('subtitle_cues', 0):,} cues",
    ]))

    # The three thumbnails, so you can pick by eye rather than by filename.
    selected = publish.chosen_thumbnail(run).name
    for letter, filename in publish.THUMBNAIL_FILES.items():
        path = run.path("output", filename)
        if path.exists():
            mark = " ← selected" if filename == selected else ""
            chat.send_photo(path, caption=f"<b>Thumbnail {letter}</b>{mark}",
                            buttons=None if mark else chat.keyboard([(f"Use {letter}", f"thumb:{letter}")]))

    chat.send_file(run.path("output", "subtitles.srt"), caption="Subtitles")
    chat.send_file(run.path("output", "UPLOAD.md"), caption="Everything needed for a manual upload")

    run.save_state(chat_stage="review")
    chat.send(
        "Watch it, then tell me anything to change — the title, description, tags, "
        "pinned comment, thumbnail, or a stage to redo.",
        buttons=chat.keyboard(
            [("🔁 Redo thumbnail", "redo:thumbnail"), ("🎞 Footage", "cmd:footage")],
            [("✅ Accept & upload", "cmd:publish")],
        ),
    )


# ---------------------------------------------------------------------------
# The fast handlers
# ---------------------------------------------------------------------------

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
        "set_pinned_comment": ("pinned_comment", args.get("text")),
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


def do_question(run: Run | None, text: str) -> None:
    """Actually talk: answer with the run and the recent conversation in view."""
    from .llm import chat as ask

    context = ["No run in progress."]
    if run:
        state = run.state()
        context = [f"Run {run.id}, stage: {state.get('chat_stage', 'unknown')}, "
                   f"finished: {', '.join(state.get('stages_done', []))}"]
        if run.path("metadata.json").exists():
            metadata = run.read_json("metadata.json")
            context += [f"Title: {metadata.get('title', '')}",
                        f"Description: {metadata.get('description', '')}",
                        f"Tags: {', '.join(metadata.get('tags', []))}",
                        f"Pinned comment: {metadata.get('pinned_comment', '')}"]
        if run.path("thumbnails.json").exists():
            chosen = publish.chosen_thumbnail(run).name
            for t in run.read_json("thumbnails.json"):
                context.append(f"Thumbnail {t.get('file')}{' (selected)' if t.get('file') == chosen else ''}: "
                               f"text {t.get('text')!r}, image: {t.get('hero', '')}")
        if run.path("script.txt").exists():
            context.append("Script (start):\n" + " ".join(run.read_text("script.txt").split()[:1500]))

    recent = "\n".join(f"{m.get('role')}: {m.get('html', '')[:500]}"
                       for m in chat.history(20) if m.get("html"))
    system = (load_persona() + "\n\nYou are also the producer running this channel's video "
              "pipeline, chatting with the channel owner in their studio app. Answer "
              "plainly and briefly. You can't take actions from this reply - if they want "
              "a change, tell them what to say (e.g. 'change the title to ...', 'redo the footage').")
    try:
        answer = ask(system, "\n".join(context) + f"\n\nRecent chat:\n{recent}\n\nThey said: {text}",
                     label="chat answer")
    except Exception as error:  # noqa: BLE001
        answer = f"I couldn't reach the model ({error})."
    # Models write **bold** whatever you ask; show it as bold rather than asterisks.
    chat.send(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", chat.escape(answer)))


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

    Returns the whole decision - `{"intent", "args", "reply"}`. The studio
    reads the intent and decides whether to start a background job.
    """
    run = active_run()
    decision = brain.understand(text, run)
    intent, args = decision["intent"], decision.get("args", {})
    reply = decision.get("reply", "")

    # Slow intents are acknowledged by the studio, once it knows it can start them.

    if intent == "status":
        do_status(run)
    elif intent == "pick_thumbnail":
        do_pick_thumbnail(run, args)
    elif intent in ("set_title", "set_tags", "set_description", "set_pinned_comment"):
        do_edit_metadata(run, intent, args)
    elif intent == "cancel":
        do_cancel(run)
    elif intent == "footage":
        if run and run.path("storyboard.json").exists() and run.is_done("visuals"):
            present_footage(run)
        else:
            chat.send("There's no footage yet — it's ready once the build reaches the render.")
    elif intent == "question":
        do_question(run, text)
    elif intent == "unclear":
        chat.send(chat.escape(reply) or "I'm not sure what you meant — try rephrasing?")

    log(f"routed to: {intent}")
    return decision


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Handle one chat message.")
    parser.add_argument("--text", help="The message you sent.")
    parser.add_argument("--present", choices=["topics", "script", "footage", "review"],
                        help="Post a gate message instead of routing a reply.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    if args.present:
        target = resolve_run(args.run)
        {"topics": present_topics, "script": present_script, "footage": present_footage,
         "review": present_review}[args.present](target)
    elif args.text:
        decision = route(args.text)
        # The studio (yt-studio/app.py) reads this last line to decide whether
        # to queue a background job. See yt-studio/CHANNEL_CONTRACT.md.
        print(json.dumps({**decision, "slow": decision["intent"] not in FAST}))
    else:
        parser.error("Pass either --text or --present.")
