"""Turning what you typed into something the pipeline can do.

You shouldn't have to remember commands. "make the title punchier", "use the
second thumbnail", "redo the footage, it's too generic" and "ship it" should
all just work. This module takes your message plus where the run currently is,
and returns one of a fixed list of intents.

How it decides, in order:

  1. Buttons and obvious literals ("approve", "3", "publish") are matched by
     plain string rules. Free, instant, no API call, can't be misread.
  2. Anything else goes to DeepSeek with the run's current state as context,
     and comes back as JSON. Costs about $0.00002 a message.
  3. If that call fails, we fall back to `unclear` and ask you to rephrase -
     never to a guess, because a wrong guess here can spend money or publish
     a video.

Run it:  python -m pipeline.brain --text "use thumbnail b" --run latest
"""

from __future__ import annotations

import json
import re

from .common import Run, log

# Every intent the system understands. The studio routes on these strings: anything
# not in assistant.FAST is run as a background job by tools/chat_job.py.
INTENTS = {
    "new":             "Start a new video - propose ten topics",
    "pick":            "Choose topic number N from the list",
    "approve_script":  "The script is good - build the video",
    "edit_script":     "Change something about the script, described in words",
    "replace_script":  "Use this pasted text as the script verbatim",
    "set_title":       "Change the video title",
    "set_tags":        "Change the tags",
    "set_description": "Change the description",
    "set_pinned_comment": "Change the pinned comment",
    "pick_thumbnail":  "Use thumbnail a, b or c",
    "redo":            "Re-run one stage (thumbnail, stock, visuals, narrate, render)",
    "publish":         "Accept the video - upload it to YouTube and make it public",
    "status":          "Where is the current run up to?",
    "cancel":          "Abandon the current run",
    "question":        "A question or remark that needs an answer, not an action",
    "unclear":         "Could not tell what was meant",
}

# Stage names `redo` is allowed to re-run. Deliberately not the whole list:
# re-running research or script from here would throw away your approved text.
REDOABLE = ["narrate", "captions", "storyboard", "charts", "stock", "visuals",
            "audio", "thumbnail", "render"]


# ---------------------------------------------------------------------------
# Step 1: the rules that never need a model
# ---------------------------------------------------------------------------

def match_literally(text: str) -> dict | None:
    """Catch the handful of messages that have exactly one possible meaning."""
    clean = text.strip().lower()

    # Button taps arrive as "cmd:new", "pick:3", "thumb:b" - see pipeline/chat.py.
    if ":" in clean and " " not in clean:
        prefix, _, value = clean.partition(":")
        mapping = {
            "cmd": {"new": "new", "status": "status", "cancel": "cancel",
                    "approve": "approve_script", "publish": "publish"},
        }
        if prefix == "pick" and value.isdigit():
            return {"intent": "pick", "args": {"number": int(value)}}
        if prefix == "thumb" and value in ("a", "b", "c"):
            return {"intent": "pick_thumbnail", "args": {"choice": value}}
        if prefix == "redo" and value in REDOABLE:
            return {"intent": "redo", "args": {"stage": value}}
        if prefix in mapping and value in mapping[prefix]:
            return {"intent": mapping[prefix][value], "args": {}}

    # A bare number at the topic gate means "that one".
    if clean.isdigit():
        return {"intent": "pick", "args": {"number": int(clean)}}

    exact = {
        "approve": "approve_script", "approved": "approve_script", "ok": "approve_script",
        "yes": "approve_script", "go": "approve_script", "build it": "approve_script",
        "publish": "publish", "ship it": "publish", "go live": "publish", "accept": "publish",
        "status": "status", "where are we": "status", "?": "status",
        "cancel": "cancel", "stop": "cancel", "abandon": "cancel",
        "new": "new", "new video": "new", "start": "new", "make a video": "new",
    }
    if clean in exact:
        return {"intent": exact[clean], "args": {}}

    # "thumbnail b" / "use thumbnail c" / "thumb a"
    thumbnail = re.fullmatch(r"(?:use\s+)?thumb(?:nail)?\s*([abc])", clean)
    if thumbnail:
        return {"intent": "pick_thumbnail", "args": {"choice": thumbnail.group(1)}}

    # A fenced code block is a pasted replacement script, never an instruction.
    pasted = extract_fenced_script(text)
    if pasted:
        return {"intent": "replace_script", "args": {"script": pasted}}

    return None


# A real script runs to 1,400+ words. Anything shorter in a code block is a
# quoted paragraph or a stray snippet, not a replacement - so it falls through
# to the model, which will read it as an edit instruction instead.
MIN_SCRIPT_WORDS = 200


def extract_fenced_script(text: str) -> str | None:
    """Pull a pasted script out of a ``` code block, if there is one.

    Takes the longest block, because people quote a line above the script they
    actually mean. Handles ```text and ```markdown language markers.
    """
    blocks = re.findall(r"```(?:\w+)?\s*\n(.*?)```", text, re.DOTALL)
    if not blocks:
        return None

    longest = max(blocks, key=len).strip()
    return longest if len(longest.split()) >= MIN_SCRIPT_WORDS else None


# ---------------------------------------------------------------------------
# Step 2: ask the model about everything else
# ---------------------------------------------------------------------------

SYSTEM = (
    "You route messages for a YouTube video pipeline. The user is the channel "
    "owner, talking to you from their studio app. Reply with JSON only."
)

TEMPLATE = """The user sent this message:

\"\"\"{text}\"\"\"

The video they're talking about is at this point:

- stage: {stage}
- run id: {run_id}
- title: {title}

Decide which ONE of these they meant:

{intents}

Rules:
- "pick" needs args.number (the topic number they chose).
- "pick_thumbnail" needs args.choice, one of "a", "b", "c".
- "redo" needs args.stage, one of: {redoable}.
- "set_title" needs args.title; "set_tags" needs args.tags (a list);
  "set_description" needs args.description; "set_pinned_comment" needs args.text.
- "edit_script" needs args.instruction - their change, in their own words.
- If they are asking something rather than instructing, use "question" and put
  the answer in "reply".
- If you genuinely cannot tell, use "unclear". Never guess at an intent that
  spends money ("approve_script", "redo") or publishes ("publish").

Also write "reply": one short, friendly sentence confirming what you're about
to do, as if you were texting them back. No preamble, no emoji spam.

Reply with JSON only:
{{"intent": "...", "args": {{}}, "reply": "..."}}"""


def ask_model(text: str, run: Run | None) -> dict:
    """Send the message to DeepSeek and get a structured intent back."""
    from .llm import chat_json  # imported late: keeps `match_literally` dependency-free

    state = run.state() if run else {}
    metadata = {}
    if run and run.path("metadata.json").exists():
        metadata = run.read_json("metadata.json")

    prompt = TEMPLATE.format(
        text=text[:4000],
        stage=state.get("chat_stage", "no run in progress"),
        run_id=run.id if run else "none",
        title=metadata.get("title", "(not written yet)"),
        intents="\n".join(f"- {name}: {description}" for name, description in INTENTS.items()),
        redoable=", ".join(REDOABLE),
    )

    result = chat_json(SYSTEM, prompt, label="chat routing")
    if not isinstance(result, dict) or result.get("intent") not in INTENTS:
        raise ValueError(f"Model returned an unusable intent: {result}")
    result.setdefault("args", {})
    result.setdefault("reply", "")
    return result


# ---------------------------------------------------------------------------
# The one function the workflow calls
# ---------------------------------------------------------------------------

def understand(text: str, run: Run | None = None) -> dict:
    """Message in, `{"intent", "args", "reply"}` out. Never raises."""
    literal = match_literally(text)
    if literal:
        literal.setdefault("reply", "")
        log(f"  intent (rule): {literal['intent']}")
        return literal

    try:
        result = ask_model(text, run)
        log(f"  intent (model): {result['intent']}")
        return result
    except Exception as error:  # noqa: BLE001
        log(f"  intent routing failed: {error}")
        return {
            "intent": "unclear",
            "args": {},
            "reply": "I couldn't work out what you meant there - try rephrasing it?",
        }


if __name__ == "__main__":
    import argparse

    from .common import resolve_run

    parser = argparse.ArgumentParser(description="Work out what a message means.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--run", default=None)
    args = parser.parse_args()

    active = resolve_run(args.run) if args.run else None
    print(json.dumps(understand(args.text, active), indent=2))
