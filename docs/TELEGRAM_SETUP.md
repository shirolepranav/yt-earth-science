# Setting up the chat control

About twenty minutes, all of it free, no credit card. When you're done you'll
run the whole channel from Telegram on your phone.

You need: a phone with Telegram, and a computer for steps 2 and 3.

---

## Step 1 — Make the bot (3 minutes, phone)

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot`.
3. Give it a name (`Deep Earth`) and a username ending in `bot`
   (`deepearth_studio_bot`).
4. BotFather replies with a **token** like `8134567890:AAH...`. Keep it — this
   is `TELEGRAM_BOT_TOKEN`.
5. Find your new bot and send it `hello`. It won't reply yet. That's expected —
   you're just creating a message for the next step to read.

Then find your own chat id. On your computer, in the project folder:

```bash
export TELEGRAM_BOT_TOKEN="8134567890:AAH..."
python tools/telegram_setup.py --find-chat-id
```

It prints a number like `6123456789`. That's `TELEGRAM_CHAT_ID` — the bot will
refuse to talk to anyone else.

---

## Step 2 — Deploy the Worker (8 minutes, computer)

The Worker is the always-awake piece that receives your messages. Cloudflare's
free tier covers it permanently.

```bash
# 1. Sign up at https://dash.cloudflare.com/sign-up (no card needed)

# 2. Install the CLI and log in
npm install -g wrangler
wrangler login

# 3. Deploy
cd bot
wrangler deploy
```

It prints your Worker's URL:

```
https://deepearth-chat.<your-subdomain>.workers.dev
```

Keep that. Now give the Worker its five secrets. `wrangler secret put` prompts
for each value and stores it encrypted — nothing is written to disk.

```bash
wrangler secret put TELEGRAM_BOT_TOKEN        # from step 1
wrangler secret put TELEGRAM_CHAT_ID          # from step 1
wrangler secret put TELEGRAM_WEBHOOK_SECRET   # invent a long random string
wrangler secret put GITHUB_TOKEN              # see below
wrangler secret put GITHUB_REPO               # e.g. yourname/yt-earth-science
```

For `TELEGRAM_WEBHOOK_SECRET`, any long random string works:

```bash
openssl rand -hex 32
```

For `GITHUB_TOKEN`, create a **fine-grained personal access token** at
GitHub → Settings → Developer settings → Personal access tokens → Fine-grained:

- **Repository access:** only this repository
- **Permissions:** `Contents` → **Read and write**

That's the only permission it needs. Nothing else.

---

## Step 3 — Connect Telegram to the Worker (1 minute, computer)

```bash
export TELEGRAM_BOT_TOKEN="8134567890:AAH..."
export TELEGRAM_WEBHOOK_SECRET="the same string you gave the Worker"

python tools/telegram_setup.py --url https://deepearth-chat.<your-subdomain>.workers.dev
```

It confirms the webhook and reports any delivery error. "No delivery errors ✅"
means Telegram can reach your Worker.

---

## Step 4 — Add the GitHub secrets (2 minutes)

In your repository: **Settings → Secrets and variables → Actions → New
repository secret**. Add these two alongside the API keys you already have:

| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from step 1 |
| `TELEGRAM_CHAT_ID` | from step 1 |

---

## Step 5 — Try it

Send your bot:

```
new video
```

Within a minute or two you should get ten topics with a numbered button under
each. Tap one and the conversation takes over from there.

If nothing happens, work down this list:

| Symptom | Cause | Fix |
|---|---|---|
| No reply at all | Webhook not reaching the Worker | `python tools/telegram_setup.py --status` and read the last error |
| "Couldn't reach GitHub" | Token wrong or lacks Contents write | Recreate the PAT with `Contents: Read and write` |
| Reply says "On it…" then silence | Workflow failed early | Check the Actions tab; usually a missing API key |
| Bot ignores you completely | Chat id mismatch | Re-run `--find-chat-id` and update both GitHub and the Worker |

---

## What you can say

Buttons cover the common path, but anything below works as typed text.

| You send | What happens |
|---|---|
| `new video` | Proposes ten topics |
| `3` | Picks topic 3, researches and writes the script (~20 min) |
| `make the opening punchier` | Rewrites the script with that change, shows it again |
| a script in a ``` code block ``` | Uses your text verbatim as the script |
| `approve` | Builds the video (30–90 min), uploads it private, sends the link |
| `thumbnail b` | Switches the thumbnail, on YouTube too |
| `title The Day Iceland Burned` | Changes the title, on YouTube too |
| `redo the thumbnail` | Regenerates just the thumbnail |
| `redo the footage` | Re-picks stock, re-renders, re-uploads |
| `publish` | Flips the video from private to public |
| `status` | Where the current run is (answered instantly by the Worker) |
| `cancel` | Abandons the run |

Anything else is read by a model, which either does what you meant or asks.

---

## A note on publishing

Until Google audits your API project, **any video uploaded through the API
stays private no matter what** — so `publish` will report success while the
video remains private. That's a Google restriction, not a bug here.

Until the audit clears, flip it public with two taps in the YouTube app. Apply
early (YouTube Studio → Settings → API compliance) so the clock runs while you
make your first videos.

---

## Turning it off

```bash
python tools/telegram_setup.py --delete-webhook
```

The pipeline still works without Telegram — every stage runs from the command
line as before, and `pipeline/chat.py` becomes a silent no-op when the secrets
are absent.
