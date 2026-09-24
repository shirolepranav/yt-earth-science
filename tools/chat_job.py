"""Runs the slow half of a chat request.

`pipeline/assistant.py` answers anything quick on the spot. Anything that
takes minutes - proposing topics, writing a script, building a video, uploading
it - lands here instead, queued by the studio (../yt-studio) so the fast
replies stay fast.

One entry point for all of them:

    python tools/chat_job.py --intent approve_script --args '{}' --run latest

Every path ends the same way: it posts the next gate to the chat, so you always
know what it wants from you next.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

# Let this run as `python tools/chat_job.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import assistant, chat, publish, script, stock, visuals  # noqa: E402
from pipeline.common import load_config, log, resolve_run  # noqa: E402
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
        chat.send("🔎 Fact-checking your script…")
        run.path("script_cited.txt").unlink(missing_ok=True)
        script.recheck(run, pasted)
        run.reset_stages(keep=["choose", "research", "script"])
        chat.send("✅ Using your script, with any fixes the fact-check could make.")
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
        # New footage is shown before it's rendered; a plain re-render isn't.
        run.save_state(footage_ok=redo_stage == "render")
        chat.send(f"🔁 Redoing {redo_stage} and everything after it. "
                  "The video has to be rebuilt and re-uploaded.")
        # YouTube can't swap the file behind an existing video, so the old
        # private upload has to go before the new one arrives.
        publish.delete_video(run)
    elif not run.is_done("thumbnail"):  # not just the render left
        chat.send("🎬 Building. I'll show you every shot before the 20–40 minute render.")

    run.save_state(chat_stage="building")

    for name in BUILD_STAGES:
        if run.is_done(name):
            continue
        if name == "render" and not run.state().get("footage_ok"):
            # Pause: every shot is built, and a swap now costs no render time.
            assistant.present_footage(run)
            return
        chat.progress(name)
        run_stage(run, name)

    assistant.present_review(run)


def do_render(run_id: str) -> None:
    """The footage is approved: render it."""
    run = resolve_run(run_id)
    run.save_state(footage_ok=True)
    chat.send("🎬 Rendering. Roughly 4–8 minutes per two minutes of video that changed.")
    do_build(run_id, {})


def do_swap(run_id: str, args: dict) -> None:
    """Replace one shot's footage - a fresh library search, or a generated still -
    then show the footage list again. Nothing renders until you tap Render, so
    several swaps cost one render."""
    run = resolve_run(run_id)
    sid, to, hint = str(args.get("shot", "")), args.get("to"), (args.get("hint") or "").strip()
    if run.state().get("chat_stage") == "published":
        chat.send("This video is already public — its footage can't be changed now.")
        return
    board = run.read_json("storyboard.json")
    shot = next((s for s in board["shots"] if str(s["id"]) == sid), None)
    if not shot or shot["kind"] not in ("stock", "ai") or to not in ("stock", "ai"):
        chat.send(f"Shot {chat.escape(sid)} isn't a footage shot I can swap.")
        return
    found = run.read_json("stock.json")
    built = run.read_json("visuals.json") if run.path("visuals.json").exists() else {}

    if to == "stock":
        chat.send(f"🔎 Searching the libraries again for shot {sid}…")
        words = run.read_json("words.json")["words"]
        spoken = stock.spoken_during(words, shot["start"], shot["end"])
        current = {c["id"] for c in found.get(sid, {}).get("clips", [])}
        queries = [hint] if hint else stock.fresh_queries(spoken, shot.get("intent", ""), shot.get("queries") or [])
        if not queries:
            chat.send("I couldn't think of a new search — tell me what to look for.")
            return
        registry = json.loads(stock.USED_REGISTRY.read_text()) if stock.USED_REGISTRY.exists() else {}
        used = {c for run_id_, ids in registry.items() if run_id_ != run.id for c in ids} | current
        starts = {str(s["id"]): s["start"] for s in board["shots"]}
        claims: dict[str, list[float]] = {}  # the rest of this video's clips, so reuse rules still hold
        for other, entry in found.items():
            for clip in entry["clips"] if other != sid else []:
                claims.setdefault(clip["id"], []).append(starts.get(other, 0.0))
        target = {**shot, "queries": queries, "intent": hint or shot.get("intent", "")}
        result = stock.fetch_for_shot(run, target, words, used, threading.Lock(), claims)
        if not result:
            chat.send(f"Nothing in the libraries scored {stock.MIN_SCORE}+/10 for that. "
                      "Try other words, or ✨ AI in the footage list.")
            return
        found[sid] = result
        built.pop(sid, None)
        shot.update(kind="stock", queries=queries, intent=target["intent"])
        shot.pop("swapped_to_ai", None)
        registry[run.id] = sorted({c["id"] for entry in found.values() for c in entry["clips"]})
        stock.USED_REGISTRY.write_text(json.dumps(registry, indent=1))
    else:
        chat.send(f"✨ Generating a new image for shot {sid}…")
        if hint:
            shot.update(image_prompt=hint, intent=hint)
        elif shot.get("swapped_to_ai") or sid not in found:
            shot["angle"] = shot.get("angle", 0) + 1  # same prompt, new framing - not the cached image
        shot["swapped_to_ai"] = True
        ledger: list[float] = []
        # A still with a parallax move (~$0.04), never motion: a swap shouldn't eat the clip budget.
        asset = visuals.build_shot(run, {**shot, "kind": "ai"}, False, run.read_json("look.json"),
                                   load_config()["visuals"], ledger)
        run.save_state(visuals_spend_usd=round(run.state().get("visuals_spend_usd", 0) + sum(ledger), 2))
        if not asset:
            chat.send("The image generation failed — see the log, or try again.")
            return
        found.pop(sid, None)
        built[sid] = {**asset, "for": shot.get("image_prompt")}

    run.write_json("storyboard.json", board)
    run.write_json("stock.json", found)
    run.write_json("visuals.json", built)
    run_stage(run, "shotlist", force=True)
    # The video on disk no longer matches: render again before anything uploads.
    run.reset_stages(keep=[s for s in run.state()["stages_done"] if s != "render"])
    run.save_state(footage_ok=False)
    chat.send(f"✅ Shot {sid} swapped.")
    assistant.present_footage(run)


def do_publish(run_id: str) -> None:
    """Accept: upload with every detail filled in, make it public, post the comment."""
    run = resolve_run(run_id)
    if not run.is_done("render"):
        chat.send("The footage changed since the last render — tap 🎬 Render first.",
                  buttons=chat.keyboard([("🎬 Render", "cmd:render")]))
        return
    if not publish.have_youtube_keys():
        chat.send("YouTube isn't connected (no YOUTUBE_* keys in .env), so upload it by hand "
                  "from the packet:")
        chat.send_file(run.path("output", "UPLOAD.md"))
        return

    if not run.state().get("video_id"):
        chat.send("⬆️ Uploading to YouTube with the title, description, tags, thumbnail and subtitles…")
        publish.upload(run)
    video_id = publish.go_live(run)
    commented = publish.post_comment(run)

    chat.send(
        f"🚀 <b>Published.</b>\n\nhttps://youtu.be/{video_id}\n\n"
        + ("💬 Comment posted — open it and tap <b>Pin</b> (YouTube's API can't pin).\n\n"
           if commented else "")
        + "<i>If it still shows as private, the Google API project hasn't been audited "
        "yet — flip it public in YouTube Studio.</i>"
    )


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
    try:
        dispatch(intent, args, options.run)
    except (Exception, SystemExit) as error:  # noqa: BLE001 - die() raises SystemExit
        chat.failed(intent, str(error) or type(error).__name__, assistant.log_path())
        raise


def dispatch(intent: str, args: dict, run_id: str) -> None:
    if intent == "new":
        do_topics()
    elif intent == "pick":
        do_pick(run_id, args)
    elif intent in ("edit_script", "replace_script"):
        do_revise(run_id, intent, args)
    elif intent == "approve_script":
        do_build(run_id, args)
    elif intent == "redo":
        do_build(run_id, args, redo_stage=args.get("stage", ""))
    elif intent == "approve_footage":
        do_render(run_id)
    elif intent == "swap":
        do_swap(run_id, args)
    elif intent == "publish":
        do_publish(run_id)
    else:
        log(f"Nothing slow to do for intent '{intent}'.")


if __name__ == "__main__":
    main()
