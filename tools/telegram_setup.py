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
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.common import log, secret  # noqa: E402


def api(method: str, token: str, **params) -> dict:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=30
    )
    body = response.json()
    if not body.get("ok"):
        raise SystemExit(f"Telegram refused {method}: {body.get('description')}")
    return body["result"]


def find_chat_id(token: str) -> None:
    """Print the chat id of whoever has messaged the bot most recently.

    Telegram won't tell you your own id directly - you have to send the bot a
    message first, then read it back off the update. Say anything to the bot,
    then run this.
    """
    updates = api("getUpdates", token)
    if not updates:
        raise SystemExit(
            "No messages yet. Open Telegram, find your bot, send it 'hello', "
            "then run this again.\n\n"
            "(If you've already set a webhook, Telegram delivers updates there "
            "instead - run with --delete-webhook first.)"
        )

    seen = {}
    for update in updates:
        message = update.get("message") or update.get("edited_message") or {}
        sender = message.get("from", {})
        if message.get("chat", {}).get("id"):
            seen[message["chat"]["id"]] = sender.get("username") or sender.get("first_name", "?")

    print("\nChat ids that have messaged this bot:\n")
    for chat_id, name in seen.items():
        print(f"  {chat_id}   ({name})")
    print("\nPut yours in the TELEGRAM_CHAT_ID secret, in GitHub and in the Worker.\n")


def show_status(token: str) -> None:
    info = api("getWebhookInfo", token)
    print("\nWebhook status\n")
    print(f"  URL:            {info.get('url') or '(none set)'}")
    print(f"  Pending updates: {info.get('pending_update_count', 0)}")
    print(f"  Secret token:   {'set' if info.get('has_custom_certificate') is not None else '?'}")

    if info.get("last_error_message"):
        print(f"\n  ⚠️  Last error: {info['last_error_message']}")
        print("      That's Telegram failing to reach your Worker. Check the URL,")
        print("      and that TELEGRAM_WEBHOOK_SECRET matches on both sides.")
    else:
        print("\n  No delivery errors. ✅")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wire the Telegram bot to the Worker.")
    parser.add_argument("--url", help="Your Worker's URL, from `wrangler deploy`.")
    parser.add_argument("--secret", help="TELEGRAM_WEBHOOK_SECRET. Read from the environment if omitted.")
    parser.add_argument("--status", action="store_true", help="Just show the current webhook.")
    parser.add_argument("--find-chat-id", action="store_true", help="Print your chat id.")
    parser.add_argument("--delete-webhook", action="store_true", help="Unhook the bot.")
    args = parser.parse_args()

    token = secret("TELEGRAM_BOT_TOKEN")

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
