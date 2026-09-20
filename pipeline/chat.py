"""Talking to you on Telegram.

Everything the pipeline says to you goes through here, and every button you tap
comes back through the Cloudflare Worker in `bot/`. This module is deliberately
one-way plumbing: it sends, it does not listen. Listening is the Worker's job.

Two secrets make it work:

  TELEGRAM_BOT_TOKEN   from @BotFather when you create the bot
  TELEGRAM_CHAT_ID     your own chat id, so the bot only ever messages you

If either is missing, every function here quietly does nothing. That's on
purpose: the pipeline still runs end to end without Telegram configured, it
just doesn't narrate itself.

See docs/TELEGRAM_SETUP.md for the ten-minute setup.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import requests

from .common import has_secret, log, secret

# Telegram caps a message at 4096 characters. We split below that with headroom
# for the "(1/3)" counter we add.
MAX_MESSAGE_CHARS = 3900
TIMEOUT = 60


# ---------------------------------------------------------------------------
# Is Telegram switched on?
# ---------------------------------------------------------------------------

def enabled() -> bool:
    """True when both secrets are present. Everything else checks this first."""
    return has_secret("TELEGRAM_BOT_TOKEN") and has_secret("TELEGRAM_CHAT_ID")


def _call(method: str, payload: dict, files: dict | None = None) -> dict:
    """POST to the Telegram Bot API.

    Never raises. A chat notification failing is annoying; a chat notification
    failing and taking a 90-minute video build down with it is unacceptable.
    """
    if not enabled():
        return {}

    url = f"https://api.telegram.org/bot{secret('TELEGRAM_BOT_TOKEN')}/{method}"
    payload.setdefault("chat_id", secret("TELEGRAM_CHAT_ID"))

    try:
        if files:
            # Multipart upload: the payload fields ride alongside the file.
            response = requests.post(url, data=payload, files=files, timeout=TIMEOUT)
        else:
            response = requests.post(url, json=payload, timeout=TIMEOUT)
        body = response.json()
        if not body.get("ok"):
            log(f"  telegram {method} refused: {body.get('description', response.text[:200])}")
            return {}
        return body.get("result", {})
    except Exception as error:  # noqa: BLE001
        log(f"  telegram {method} failed: {error}")
        return {}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def escape(text: str) -> str:
    """Make text safe for Telegram's HTML mode.

    HTML mode rather than Markdown: a stray underscore or asterisk in a script
    silently breaks a Markdown message, and scripts are full of both.
    """
    return html.escape(str(text), quote=False)


def keyboard(*rows: list[tuple[str, str]]) -> dict:
    """Build the row of tappable buttons under a message.

    Each button is a `(label, code)` pair. The code comes back to the Worker as
    `callback_data` when you tap it, so keep it short - Telegram caps it at 64
    bytes. We use forms like "pick:3", "ok:script", "thumb:b".
    """
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": code} for label, code in row]
            for row in rows
        ]
    }


def split(text: str) -> list[str]:
    """Break a long message into Telegram-sized pieces, on line boundaries."""
    if len(text) <= MAX_MESSAGE_CHARS:
        return [text]

    pieces, current = [], ""
    for line in text.split("\n"):
        # A single line longer than a whole message - a script pasted with no
        # paragraph breaks - has to be chopped, or Telegram rejects the send.
        while len(line) > MAX_MESSAGE_CHARS:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(line[:MAX_MESSAGE_CHARS])
            line = line[MAX_MESSAGE_CHARS:]

        # +1 for the newline we're about to add back.
        if len(current) + len(line) + 1 > MAX_MESSAGE_CHARS:
            pieces.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        pieces.append(current)

    total = len(pieces)
    return [f"{piece}\n<i>({index}/{total})</i>" for index, piece in enumerate(pieces, 1)]


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send(text: str, *, buttons: dict | None = None, preview: bool = False) -> int | None:
    """Send a message. Returns its id so it can be edited later."""
    message_id = None
    pieces = split(text)

    for index, piece in enumerate(pieces):
        payload = {
            "text": piece,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": not preview},
        }
        # Buttons go on the last piece only, where your thumb ends up.
        if buttons and index == len(pieces) - 1:
            payload["reply_markup"] = buttons
        result = _call("sendMessage", payload)
        message_id = result.get("message_id", message_id)

    return message_id


def edit(message_id: int, text: str, *, buttons: dict | None = None) -> None:
    """Rewrite a message already on screen - used for live progress updates."""
    payload = {"message_id": message_id, "text": text, "parse_mode": "HTML"}
    if buttons is not None:
        payload["reply_markup"] = buttons
    _call("editMessageText", payload)


def send_photo(path: Path, caption: str = "", buttons: dict | None = None) -> None:
    """Send an image - thumbnails, mostly. Telegram caps photos at 10 MB."""
    if not Path(path).exists():
        return
    payload = {"caption": caption[:1024], "parse_mode": "HTML"}
    if buttons:
        payload["reply_markup"] = json.dumps(buttons)
    with open(path, "rb") as handle:
        _call("sendPhoto", payload, files={"photo": handle})


def send_file(path: Path, caption: str = "") -> None:
    """Send a file - the .srt, the description. Bots cap documents at 50 MB,
    which is why the finished video goes to YouTube rather than down this pipe.
    """
    if not Path(path).exists():
        return
    payload = {"caption": caption[:1024], "parse_mode": "HTML"}
    with open(path, "rb") as handle:
        _call("sendDocument", payload, files={"document": handle})


def progress(stage: str, detail: str = "") -> None:
    """A one-line 'still working' note. Called between build stages."""
    send(f"⚙️ <b>{escape(stage)}</b>{(' — ' + escape(detail)) if detail else ''}")


def failed(stage: str, error: str, log_url: str = "") -> None:
    """Report a stage that blew up, with a link to the log."""
    lines = [f"❌ <b>{escape(stage)} failed</b>", "", f"<code>{escape(error[:600])}</code>"]
    if log_url:
        lines += ["", f'<a href="{log_url}">Open the log</a>']
    lines += ["", "Reply <code>retry</code> to pick up from where it stopped."]
    send("\n".join(lines), preview=False)


if __name__ == "__main__":
    # `python -m pipeline.chat` sends a test message, so you can check the two
    # secrets are right without running anything expensive.
    if not enabled():
        raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not both set.")
    send(
        "✅ <b>Deep Earth is connected.</b>\n\nReply <code>new video</code> to start one.",
        buttons=keyboard([("🎬 New video", "cmd:new"), ("📊 Status", "cmd:status")]),
    )
    log("Test message sent.")
