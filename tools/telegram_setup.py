"""Point your Telegram bot at the Cloudflare Worker, and check it works.

Run this once, after you've deployed the Worker. It does the two fiddly bits of
Telegram setup for you and tells you plainly whether they worked.

    python tools/telegram_setup.py --url https://deepearth-chat.<you>.workers.dev

What it does:

  1. Calls setWebhook, so Telegram delivers your messages to the Worker rather
     than queueing them for a bot that never collects them.
  2. Registers the secret token Telegram sends with every delivery, which is
     how the Worker knows a request really came from Telegram.
  3. Reads getWebhookInfo back and shows you the result, including the last
     error Telegram hit - which is where a broken setup shows itself.

Use --status on its own to check an existing setup without changing it, and
--find-chat-id if you don't know your chat id yet.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.common import log, secret  # noqa: E402


def api(method: str, token: str, http_timeout: int = 30, **params) -> dict:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=http_timeout
    )
    body = response.json()
    if not body.get("ok"):
        detail = body.get("description", "")
        # By far the most common cause, and the description alone ("Unauthorized")
        # doesn't say which of the two things is wrong.
        if response.status_code == 401:
            raise SystemExit(
                f"Telegram rejected the token.\n\n"
                "Either TELEGRAM_BOT_TOKEN is wrong, or it was revoked in @BotFather.\n"
                "It looks like 8134567890:AAHdq... - digits, a colon, then ~35 characters.\n"
                "Send @BotFather /mybots -> your bot -> API Token to see the current one."
            )
        raise SystemExit(f"Telegram refused {method}: {detail}")
    return body["result"]


def chat_id_from(update: dict) -> tuple[int, str] | None:
    """Pull (chat_id, who) out of an update, or None if it carries neither."""
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    if not chat.get("id"):
        return None
    sender = message.get("from") or {}
    return chat["id"], sender.get("username") or sender.get("first_name") or "?"


def watch_for_chat_id(token: str, seconds: int = 120) -> None:
    """Hold the line open and print the chat id the moment a message arrives.

    This exists because "nothing is queued" and "you sent nothing" are
    indistinguishable after the fact. Watching live removes the ordering
    question entirely: start this, then send the message, and either it turns
    up - in which case the bot and the token match - or it does not, which
    means the message is reaching a different bot.

    Long polling, so Telegram answers the instant something lands rather than
    on the next poll.
    """
    bot = api("getMe", token)
    handle = bot.get("username", "?")

    print(f"\nWatching @{handle} for {seconds} seconds.\n")
    print(f"  Open  https://t.me/{handle}  and send it any message now.")
    print("  (Ctrl-C to stop.)\n")

    deadline = time.monotonic() + seconds
    offset = None

    while time.monotonic() < deadline:
        params = {"timeout": 20}
        if offset is not None:
            params["offset"] = offset
        # The HTTP read must outlast the long poll, or requests gives up first.
        updates = api("getUpdates", token, http_timeout=40, **params)

        for update in updates:
            offset = update["update_id"] + 1
            found = chat_id_from(update)
            if found:
                chat_id, who = found
                print(f"  ✅ Message from {who}\n")
                print(f"     TELEGRAM_CHAT_ID = {chat_id}\n")
                print("  Put that in GitHub Secrets and in the Worker.\n")
                return
            print("  ...an update arrived, but it carried no chat id. Send plain text.")

    raise SystemExit(
        f"\nNothing arrived in {seconds} seconds.\n\n"
        f"That means your message is not reaching @{handle}. The chat you are\n"
        f"typing into belongs to some other bot - open https://t.me/{handle}\n"
        "directly (don't use Telegram search) and send from the chat it opens.\n"
    )


def find_chat_id(token: str) -> None:
    """Print the chat id of whoever has messaged the bot most recently.

    Telegram won't tell you your own id directly - you have to send the bot a
    message first, then read it back off the update. Say anything to the bot,
    then run this.

    When there's nothing to read, "no messages yet" is a useless answer on its
    own: it looks identical whether you messaged the wrong bot, a webhook is
    collecting the updates instead, or you simply haven't sent anything. So
    each of those is checked and named before we give up.
    """
    # Which bot does this token actually belong to? If the answer isn't the
    # bot you've been messaging, that's the whole problem - and it is
    # invisible otherwise, because both look like silence.
    bot = api("getMe", token)
    handle = bot.get("username", "?")
    print(f"\nThis token belongs to:  @{handle}  ({bot.get('first_name', '')})")

    # A webhook takes delivery of every update, and then getUpdates is refused
    # outright (409). Say so plainly rather than letting the API error surface.
    info = api("getWebhookInfo", token)
    if info.get("url"):
        raise SystemExit(
            f"\nA webhook is already set: {info['url']}\n"
            "Telegram delivers your messages there, so there is nothing left for\n"
            "this command to read. Clear it, find your id, then set it again:\n\n"
            "    python tools/telegram_setup.py --delete-webhook\n"
            "    python tools/telegram_setup.py --find-chat-id\n"
            f"    python tools/telegram_setup.py --url {info['url']}\n"
        )

    updates = api("getUpdates", token)
    if not updates:
        raise SystemExit(
            f"\nNo messages waiting for @{handle}.\n\n"
            "Most likely one of these:\n\n"
            f"  1. You haven't messaged @{handle} yet. Open this link on your\n"
            f"     phone, tap Start, and send it 'hello':\n\n"
            f"         https://t.me/{handle}\n\n"
            "  2. You messaged a DIFFERENT bot. Check the @name at the top of\n"
            f"     the Telegram chat you typed into - it has to read @{handle}\n"
            "     exactly. Making two bots while picking a free username is an\n"
            "     easy way to end up talking to the first one.\n\n"
            "  3. The message is more than 24 hours old. Telegram drops\n"
            "     undelivered updates after that - just send another.\n\n"
            "To settle which it is, watch for one live:\n\n"
            "    python tools/telegram_setup.py --watch\n\n"
            "then send the message while it's running.\n"
        )

    seen = {}
    for update in updates:
        message = update.get("message") or update.get("edited_message") or {}
        sender = message.get("from", {})
        if message.get("chat", {}).get("id"):
            seen[message["chat"]["id"]] = sender.get("username") or sender.get("first_name", "?")

    if not seen:
        raise SystemExit(
            f"\n{len(updates)} update(s) arrived, but none was a message with a chat id.\n"
            "Send the bot a plain text message rather than tapping a button.\n"
        )

    print("\nChat ids that have messaged this bot:\n")
    for chat_id, name in seen.items():
        print(f"  {chat_id}   ({name})")
    print("\nPut yours in the TELEGRAM_CHAT_ID secret, in GitHub and in the Worker.\n")


def show_status(token: str) -> None:
    bot = api("getMe", token)
    info = api("getWebhookInfo", token)

    print(f"\nBot:  @{bot.get('username', '?')}")
    print("\nWebhook status\n")
    print(f"  URL:             {info.get('url') or '(none set)'}")
    print(f"  Pending updates: {info.get('pending_update_count', 0)}")
    # Telegram does not report the secret token back - it can only be checked
    # by whether deliveries are actually succeeding, below. (An earlier version
    # of this line reported has_custom_certificate, which is a different thing
    # entirely and was always printed as "set".)
    print(f"  Max connections: {info.get('max_connections', '?')}")

    if info.get("last_error_message"):
        print(f"\n  ⚠️  Last error: {info['last_error_message']}")
        print("      That's Telegram failing to reach your Worker. Check the URL,")
        print("      and that TELEGRAM_WEBHOOK_SECRET matches on both sides -")
        print("      a mismatch shows up here as 401 Unauthorized.")
    elif not info.get("url"):
        print("\n  No webhook set yet - run with --url once the Worker is deployed.")
    else:
        print("\n  No delivery errors. ✅")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wire the Telegram bot to the Worker.")
    parser.add_argument("--url", help="Your Worker's URL, from `wrangler deploy`.")
    parser.add_argument("--secret", help="TELEGRAM_WEBHOOK_SECRET. Read from the environment if omitted.")
    parser.add_argument("--status", action="store_true", help="Just show the current webhook.")
    parser.add_argument("--find-chat-id", action="store_true", help="Print your chat id.")
    parser.add_argument("--watch", action="store_true",
                        help="Wait for a message and print its chat id as it arrives.")
    parser.add_argument("--delete-webhook", action="store_true", help="Unhook the bot.")
    args = parser.parse_args()

    token = secret("TELEGRAM_BOT_TOKEN")

    if args.watch:
        return watch_for_chat_id(token)

    if args.find_chat_id:
        return find_chat_id(token)

    if args.delete_webhook:
        api("deleteWebhook", token)
        log("Webhook removed. getUpdates works again.")
        return

    if args.status:
        return show_status(token)

    if not args.url:
        parser.error("Pass --url, or use --status / --find-chat-id.")

    webhook_secret = args.secret or secret("TELEGRAM_WEBHOOK_SECRET")

    api(
        "setWebhook",
        token,
        url=args.url,
        secret_token=webhook_secret,
        # Button taps are a different update type from messages, and the bot is
        # useless without them. Asking for only what we use keeps the noise down.
        allowed_updates=["message", "edited_message", "callback_query"],
        drop_pending_updates=True,
    )
    log(f"Webhook set to {args.url}")
    show_status(token)

    print("Now open Telegram and send your bot: new video\n")


if __name__ == "__main__":
    main()
