"""Talking to you in the local studio app.

Everything the pipeline says to you goes through here. Each message is one JSON
line appended to `runs/chat.jsonl`; the studio (../yt-studio) serves that file
to the page in your browser, which polls it every two seconds. So a 90-minute
build running in a background process talks to you the same way a quick reply
does - it appends a line.

Buttons are `(label, code)` pairs. Tapping one sends the code back as if you
had typed it ("cmd:approve", "pick:3", "thumb:b"), and `brain.py` reads it.

Nothing here ever raises: a chat message failing must not take a video build
down with it.
"""

from __future__ import annotations

import html
import json
import os
import time
from pathlib import Path

from .common import ROOT, RUNS_DIR, log

LOG_FILE = RUNS_DIR / "chat.jsonl"


def enabled() -> bool:
    """Always on - the chat is a local file. Kept so callers needn't change."""
    return True


def _append(record: dict) -> str:
    """Write one message as one line. O_APPEND keeps concurrent writers whole."""
    record.setdefault("id", str(time.time_ns()))
    record.setdefault("ts", time.time())
    record.setdefault("role", "ai")
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(record) + "\n").encode()
        fd = os.open(LOG_FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except Exception as error:  # noqa: BLE001
        log(f"  chat write failed: {error}")
    return record["id"]


def _web_path(path: Path) -> str | None:
    """A file under runs/ as the URL the page loads it from, cache-busted by mtime
    so a redone thumbnail with the same name shows the new image."""
    path = Path(path).resolve()
    if not path.exists():
        return None
    return f"/{path.relative_to(ROOT).as_posix()}?v={int(path.stat().st_mtime)}"


def history(limit: int = 20) -> list[dict]:
    """The last few messages, for giving the model conversational context."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text().splitlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def escape(text: str) -> str:
    """Make text safe to show as HTML. Messages use <b>, <i>, <code> and <a>."""
    return html.escape(str(text), quote=False)


def keyboard(*rows: list[tuple[str, str]]) -> list[list[list[str]]]:
    """Rows of buttons under a message, each a `(label, code)` pair."""
    return [[[label, code] for label, code in row] for row in rows]


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send(text: str, *, buttons=None, preview: bool = False) -> str:
    """Send a message. Returns its id so it can be edited later."""
    return _append({"html": text, "buttons": buttons})


def edit(message_id: str, text: str, *, buttons=None) -> None:
    """Rewrite a message already on screen - the page replaces it in place."""
    _append({"edit": message_id, "html": text, "buttons": buttons})


def send_photo(path: Path, caption: str = "", buttons=None) -> None:
    if (url := _web_path(path)):
        _append({"html": caption, "image": url, "buttons": buttons})


def send_video(path: Path, caption: str = "") -> None:
    if (url := _web_path(path)):
        _append({"html": caption, "video": url})


def send_file(path: Path, caption: str = "") -> None:
    if (url := _web_path(path)):
        _append({"html": caption, "file": url, "name": Path(path).name})


def send_footage(path: Path, caption: str, buttons=None) -> None:
    """The footage list - the studio shows it as a panel, one row per shot."""
    if (url := _web_path(path)):
        _append({"html": caption, "footage": url, "buttons": buttons})


def progress(stage: str, detail: str = "") -> None:
    """A one-line 'still working' note. Called between build stages."""
    send(f"⚙️ <b>{escape(stage)}</b>{(' — ' + escape(detail)) if detail else ''}")


# ---------------------------------------------------------------------------
# Degraded, but not failed
#
# Several stages are deliberately built to carry on when a provider won't
# answer: a chart falls back to the built-in component, a vision check falls
# back to the other provider. That's the right behaviour - a video should never
# be lost over one chart - but it used to be invisible. An empty OpenAI balance
# produced a finished video with plainer charts and not a word about why, with
# the only trace in an Actions log nobody reads.
#
# Stages record it here instead, and the review message lists it. The whole
# build runs in one process, so a plain list is all this needs.
# ---------------------------------------------------------------------------

_degraded: list[str] = []


def note_degraded(what: str) -> None:
    """Record that something fell back to a lesser path. Deduplicated, because
    eight charts failing for one reason is one problem, not eight."""
    if what not in _degraded:
        _degraded.append(what)
        log(f"  degraded: {what}")


def degraded() -> list[str]:
    return list(_degraded)


def failed(stage: str, error: str, log_path: str = "") -> None:
    """Report a stage that blew up, with where to find the log."""
    lines = [f"❌ <b>{escape(stage)} failed</b>", "", f"<code>{escape(error[:600])}</code>"]
    if log_path:
        lines += ["", f"Log: <code>{escape(log_path)}</code>"]
    lines += ["", "Tap Retry to pick up from where it stopped."]
    send("\n".join(lines), buttons=keyboard([("🔁 Retry", "retry")]))


if __name__ == "__main__":
    send("✅ <b>Deep Earth studio is connected.</b>",
         buttons=keyboard([("🎬 New video", "cmd:new"), ("📊 Status", "cmd:status")]))
    log(f"Test message written to {LOG_FILE}")
