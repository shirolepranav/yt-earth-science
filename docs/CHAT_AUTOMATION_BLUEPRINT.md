# Blueprint: running a long content pipeline from a chat app

**What this describes:** a way to drive an expensive, slow, multi-stage
automated pipeline — one that takes 30 to 180 minutes per run and costs real
money — entirely from chat messages on a phone, including reviewing the
output, requesting changes, and publishing.

**Who it's for:** hand this file to an AI coding assistant working on a similar
project. It's written to be portable: the examples are a YouTube video
pipeline, but nothing here is specific to video.

**Total infrastructure cost: $0/month.** Every component below is on a free
tier that does not expire and does not require a credit card.

---

## 1. The problem this solves

An automated content pipeline has an awkward shape. Most of it should run
unattended, but two or three points genuinely need a human — choosing a
direction, approving the text, accepting the finished artefact. Those decisions
take about two minutes each. Everything around them takes hours.

So the human interface has to satisfy conditions that pull against each other:

| Requirement | Why it rules things out |
|---|---|
| Reachable from a phone, anywhere | Kills anything requiring a terminal or a desktop |
| Push notification when it needs you | Kills web apps and dashboards — you'd have to remember to check |
| Survives 3-hour gaps between messages | Kills anything holding an in-memory session |
| Costs nothing at low volume | Kills managed queues, always-on VMs, most PaaS |
| No server to maintain, patch or renew | Kills the "small VPS running a bot" answer |

The combination that satisfies all five is **a chat app for the interface, a
CI runner for the compute, and a serverless function to join them**.

---

## 2. The architecture

```
   your phone                  always-on                 on demand
  ┌───────────┐   webhook   ┌─────────────┐  dispatch  ┌──────────────┐
  │ Telegram  │ ──────────► │ Cloudflare  │ ─────────► │   GitHub     │
  │           │ ◄────────── │  Worker     │            │   Actions    │
  └───────────┘   sendMsg   └─────────────┘            └──────┬───────┘
        ▲                    (stateless,                      │
        │                     ~150 lines)                     │
        │                                                     │
        └─────────────────────────────────────────────────────┘
                     the pipeline messages you directly
                       (outbound needs no middleman)

                                                    ┌──────────────┐
                                                    │  git repo    │
                                                    │  = the only  │
                                                    │    state     │
                                                    └──────────────┘
```

### The four components

**1. Chat app — the interface.** Telegram, specifically. It's free, it has a
first-class bot API with no business-account approval, it pushes notifications
reliably, and it supports inline keyboards (tappable buttons), which turn a
two-minute typed decision into one thumb tap.

**2. Serverless function — the doorbell.** Something must be awake to receive
webhooks. Cloudflare Workers: free forever, 100k requests/day, never sleeps, no
card required. It is **stateless** and does three things only: authenticate,
answer trivial reads, forward everything else.

**3. CI runner — the compute.** GitHub Actions. Free and unlimited on public
repositories, 2,000 minutes/month on private. Secrets management is built in.
Jobs can run for 6 hours. It's already where the code lives.

**4. Git repository — the state.** Not a database. Each run is a folder of
files; every job commits it back when it finishes.

### Why the repo is the database

This is the design decision that makes everything else simple, so it's worth
stating plainly.

Each job starts in a **fresh container with no memory of the last one**. A
conventional design would reach for Redis or Postgres to carry state between
them — another service, another credential, another thing on a free tier that
expires.

Instead: one folder per run, one JSON file recording where it got to.

```
runs/2026-09-20-0600/
  state.json          ← the entire state machine: {"stage": "review", ...}
  topics.json         ← stage 1 output
  script.txt          ← stage 3 output
  output/             ← the deliverables
```

The benefits compound:

- **Free and permanent.** No database, no expiry, no backup strategy.
- **Auditable.** `git log` is a complete history of every decision.
- **Debuggable from a phone.** The GitHub app shows you any file.
- **Resumable.** A crashed run has all completed stages on disk; a retry skips
  them. A 90-minute build that dies at minute 85 costs you one stage.
- **Readable by the doorbell.** The Worker answers "what's the status?"
  instantly by fetching one file through the GitHub API — no job boot needed.

**Concurrency caveat:** two jobs committing at once will conflict. Use a
workflow-level `concurrency: { group: chat, cancel-in-progress: false }` so
messages queue rather than collide, and have the commit script `pull --rebase`
before pushing.

**Check your `.gitignore` before you trust any of this.** A pipeline that
generates large media almost always has rules excluding its own output
directory — and those rules will silently swallow your state files too. Two
traps:

1. A broad pattern like `runs/*` ignores the state you depend on. `git add`
   succeeds, commits nothing, and the next message starts from zero.
2. An unanchored directory pattern like `output/` matches at *every* depth, and
   **git never descends into an excluded directory** — so `!runs/*/output/x.srt`
   can never take effect. Anchor root-level rules with a leading slash
   (`/output/`), then exclude the contents rather than the directory
   (`runs/*/output/*`) so the negations work.

Verify it rather than assuming, one line per file that matters:

```bash
git check-ignore -v runs/<id>/state.json     # should print nothing
```

This cost us a debugging session on a design that otherwise looks correct: the
commit step reports success, and the conversation quietly loses its memory
between every message.

---

## 3. The message flow

```
You type "approve"
  → Telegram POSTs to the Worker
  → Worker checks the secret header and your chat id      ← security boundary
  → Worker POSTs repository_dispatch to GitHub
  → route job wakes, works out what "approve" means
  → route job starts the build job
  → build job runs for 90 minutes, messaging you at each stage
  → build job uploads the result, posts the link, and commits the run folder
```

### Splitting fast replies from slow work

Put the router and the workers in **separate jobs in one workflow**, gated on
the intent:

```yaml
jobs:
  route:                                  # ~40 seconds
    outputs: { intent: ..., args: ..., run_id: ... }
    steps:
      - run: pip install requests python-dotenv    # NOT the full requirements
      - run: python -m assistant --text "$MESSAGE"

  build:                                  # up to 180 minutes
    needs: route
    if: needs.route.outputs.intent == 'approve'
    steps: ...
```

Two things make this work:

- **The router installs only what it needs.** Our full `requirements.txt` is a
  ~200 MB install (it includes a speech model). Answering "status" must not
  wait for it. Light deps cut the reply from ~3 minutes to ~40 seconds.
- **Fast intents never start a second job.** Status, metadata edits, and
  publishing are all finished inside the router. Only genuinely slow work
  (generation, rendering) gets its own job.

### Passing data between jobs safely

Job outputs land in a shell command, so anything the user typed is an
injection risk. **Always route user text through the environment:**

```yaml
# WRONG - an instruction like "the opening's flat" breaks the quoting
run: python job.py --args '${{ needs.route.outputs.args }}'

# RIGHT
env:
  ARGS: ${{ needs.route.outputs.args }}
run: python job.py --args "$ARGS"
```

---

## 4. Understanding free-form messages

Users don't remember command syntax. "make the title punchier", "use the second
thumbnail" and "ship it" should all work. Use a two-tier router:

**Tier 1 — deterministic rules.** Free, instant, cannot be misread. Cover:
button callbacks (`thumb:b`), bare numbers, and the dozen exact phrases people
actually type (`approve`, `yes`, `ship it`, `status`).

**Tier 2 — a small LLM call.** Everything else goes to a cheap model with the
run's current state as context, returning JSON:

```json
{"intent": "edit_script", "args": {"instruction": "punch up the opening"},
 "reply": "Rewriting the opening now."}
```

Cost: roughly $0.00002 per message on a budget model. Genuinely negligible.

**Three rules that matter:**

1. **Enumerate intents in the prompt and validate the reply against that list.**
   An unrecognised intent is a failure, not something to improvise on.
2. **Never guess into an expensive or irreversible action.** If the model is
   unsure, it must return `unclear` and ask. A misread "approve" costs real
   money; a misread "publish" is public.
3. **Ask once.** Route on one decision and pass it forward. Calling the model
   twice can yield two different answers and start the wrong job.

---

## 5. Reviewing large artefacts on a phone

**The problem:** chat apps cap file uploads. Telegram bots max out at 50 MB.
An 11-minute 1080p video is 150–400 MB. Discord is worse (10 MB). This blocks
the obvious "just send me the file" approach.

**The solution: upload to the destination platform in its private state, and
send the link.**

```
build finishes
  → upload to YouTube as PRIVATE, with title/description/tags/captions set
  → chat sends the link
  → you watch it in the YouTube app, natively, at full quality
  → you reply "publish"
  → one API call flips private → public
```

This inverts the usual flow, and it's better in every dimension: no file
transfer, no transcoding, no hosting, native playback, and approval costs one
API call instead of a second upload. The destination platform becomes your
review environment for free.

**Generalising:** the same trick works for any platform with a draft or
unlisted state — a draft blog post, an unpublished newsletter, a private
repository, a Figma file. Look for the "not visible yet but fully rendered"
state and use it as the review surface.

**Two caveats to design around:**

- **Platform edit limits.** YouTube can't swap the video file behind an
  existing video. Metadata edits are free, but a re-render means deleting and
  re-uploading. Split your redo logic accordingly: changes that affect the
  artefact ("redo the footage") need a fresh upload; changes that don't ("redo
  the thumbnail", "change the title") patch in place. This distinction saves a
  lot of time on the edits people make most.
- **API verification gates.** YouTube forces uploads from unaudited API
  projects to stay private regardless of the requested privacy. Your "publish"
  call will appear to succeed while the video stays private. Detect it, say so
  in the chat, and tell the user to flip it in the app. Apply for the audit
  early.

---

## 6. Security

The bot can spend money and publish to your channel. Four controls, all cheap:

1. **Webhook secret.** Telegram echoes a token you set in a header on every
   delivery. Reject any request without it — this stops anyone who discovers
   the URL.
2. **Chat-id allowlist.** Hard-check that the sender is you, in the Worker,
   before anything else. One line; it is the single most important line in the
   system.
3. **Least-privilege token.** The Worker's GitHub PAT needs `Contents:
   read/write` on one repository. Nothing else.
4. **Keep secrets in the platforms.** GitHub Secrets and `wrangler secret put`.
   Never in the repo — the repo is public, which is what makes CI free.

Always return HTTP 200 to Telegram, even on rejection. A non-200 makes it
retry, and a retry storm from a malformed message is its own problem.

---

## 7. Conversation design

A pipeline that talks to you badly is worse than one that doesn't talk at all.

**Acknowledge instantly, then report progress.** A 90-minute silence is
indistinguishable from a crash. Acknowledge within seconds, name the stage as
each one starts, and give a realistic estimate up front — "30 to 90 minutes"
sets expectations far better than "working…".

**Buttons for decisions, text for everything else.** Every message ending in a
decision carries buttons for the likely answers. Free text stays available for
everything you didn't anticipate.

**Never dead-end.** Every message ends by making the next step obvious. A
failure says what broke, links the log, and states how to retry.

**Deliver everything at the last gate, not just the artefact.** Ours sends the
video link, both thumbnail images inline (so you pick by eye, not by filename),
the subtitle file, and a single `UPLOAD.md` containing the title, finished
description, tags and checklist. The rule: after the final message, the human
should never need to open the repo.

**Fail loudly in the chat.** If a stage throws, catch it and message the user
with the stage name and a log link. An error that only exists in a CI log is an
error nobody sees.

---

## 8. Component checklist

Port this to another project by building these seven pieces:

| # | Piece | Responsibility |
|---|---|---|
| 1 | `chat.py` | Send messages, buttons, photos, files. Silent no-op when unconfigured. |
| 2 | `brain.py` | Message + state → `{intent, args, reply}`. Rules first, model second. |
| 3 | `assistant.py` | Execute fast intents; present each gate; return the intent. |
| 4 | `worker.js` | Authenticate, answer cheap reads, forward the rest. Stateless. |
| 5 | `chat.yml` | One router job + one job per slow intent class. |
| 6 | `commit-runs.sh` | Commit state back, with rebase-and-retry. |
| 7 | `setup.py` | Register the webhook; verify it; print the last delivery error. |

**Design invariants worth preserving:**

- State lives in files in the repo; nothing lives in memory between messages.
- Every stage writes its output before the next begins, so a crash costs one
  stage.
- The chat layer degrades to a silent no-op when unconfigured, so the pipeline
  still runs headless.
- The user's text never reaches a shell without going through an env var.
- No intent that spends money or publishes is ever reached by a guess.

---

## 9. Costs

| Component | Free tier | Realistic usage | Cost |
|---|---|---|---|
| Telegram Bot API | Unlimited | ~200 messages/week | $0 |
| Cloudflare Workers | 100,000 req/day | ~200/week | $0 |
| GitHub Actions (public repo) | Unlimited | ~10 hours/month | $0 |
| GitHub storage | 1 GB | Text only; artefacts excluded via `.gitignore` | $0 |
| Intent parsing (budget LLM) | — | ~200 calls/month | <$0.01 |
| **Infrastructure total** | | | **$0** |

On a **private** repo you get 2,000 Actions minutes/month, and a 90-minute
build six times a month will approach that. Public is the cheaper choice, and
it's safe: secrets live in GitHub Secrets, not the code.

Content generation costs (models, TTS, stock media) are unchanged by any of
this — the chat layer adds nothing measurable.

---

## 10. Alternatives, and why they lost

| Option | Verdict |
|---|---|
| **WhatsApp** (Meta Cloud API) | Needs a Business account, pre-approved message templates, and only permits free-form messages within 24h of the user's last reply — fatal for a pipeline that goes quiet for hours. |
| **Discord** | Workable, close second. 10 MB file cap, slash-command registration is fiddlier. Choose it only if you already live in Discord. |
| **Web app on free hosting** | No push notifications, so you must remember to check. Needs auth built and maintained. Free tiers sleep, adding cold-start delays. Most work, worst result. |
| **GitHub Issues as the chat** | Zero new services and a perfect audit trail — a genuinely reasonable fallback. But the mobile app is clunky for typing, and notifications are weak. Good "phase zero" if you want to defer the Worker. |
| **Polling from a cron job** | Avoids the Worker but wastes CI minutes continuously, lags up to 5 minutes, and scheduled CI is unreliable under load. |
| **Self-hosted bot on a VPS** | An always-on box to patch, monitor and pay for. The thing most likely to quietly die. |
| **Managed queue (SQS/PubSub)** | Real infrastructure, real credentials, real bills, for a system handling ~200 messages a week. |
