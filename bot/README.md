# The chat bridge

One Cloudflare Worker, about 150 lines, sitting between Telegram and GitHub
Actions.

## Why it exists

Telegram needs somewhere always-awake to deliver your messages. GitHub Actions
only wakes up when something pokes it. This is the thing in between.

It does three jobs and nothing else:

1. **Authenticate.** Checks the webhook secret header, then checks the message
   came from your chat id. Anything else is dropped silently.
2. **Answer `/status` directly.** Reads `runs/<latest>/state.json` through the
   GitHub API and replies. The most common question, answered in a second
   rather than waiting a minute for a job to boot.
3. **Forward everything else** to GitHub as a `repository_dispatch` event,
   which starts `.github/workflows/chat.yml`.

## Why it holds no state

All state is the `runs/` folder in the repository. The Worker can be
redeployed, rewritten or deleted mid-run without losing anything — the next
message picks up from the files on disk.

## Deploying

Full walkthrough in [`docs/TELEGRAM_SETUP.md`](../docs/TELEGRAM_SETUP.md).
The short version:

```bash
npm install -g wrangler
wrangler login
wrangler deploy

wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_CHAT_ID
wrangler secret put TELEGRAM_WEBHOOK_SECRET
wrangler secret put GITHUB_TOKEN        # fine-grained PAT, Contents: read/write
wrangler secret put GITHUB_REPO         # owner/repo
```

## Watching it work

```bash
wrangler tail          # live logs from the deployed Worker
```

## Cost

Free tier is 100,000 requests a day. A busy week here is around 200.
