# Deep Earth — every command

What you can say to the bot, what it does, and what it costs you.

You never need to memorise any of this. Every message the bot sends ends with
buttons for the likely next step, and anything you type in plain English is
read by a model that either does what you meant or asks. This file is for when
you want to be precise, or you're wondering why something didn't work.

---

## The shape of it

Three gates, one conversation:

```
  new video  →  ten topics  →  tap a number  →  script  →  approve
                                                            ↓
                        publish  ←  private YouTube link  ←  build
```

Everything else on this page is either a shortcut through that, or a way to
change something on the way.

---

## Starting a video

| You send | What happens | Time |
|---|---|---|
| `new video` | Proposes ten topics, each with a button | 2–5 min |
| `new` · `start` · `make a video` | Same thing | 2–5 min |

A new video also starts on its own every **Monday at 06:00 UTC**
(`.github/workflows/weekly.yml`). You don't have to ask for it.

## Gate 1 — picking a topic

| You send | What happens | Time |
|---|---|---|
| `3` | Picks topic 3, researches it, writes the script | ~20–40 min |
| *(tap a number button)* | Same thing | ~20–40 min |

Just the digit. Any number from the list works.

## Gate 2 — the script

| You send | What happens | Time |
|---|---|---|
| `approve` | Builds the video and uploads it privately | 30–90 min |
| `yes` · `ok` · `go` · `build it` | Same thing | 30–90 min |
| *anything else in words* | Rewrites the script that way, shows it again | 2–5 min |
| *a script in a ` ``` ` code block* | Uses your text verbatim, no model involved | instant |

Free-text edits are the point of this gate. Examples that work:

```
the opening is flat, start on the 1783 eruption instead
cut the paragraph about ice cores
make it less dramatic, more matter-of-fact
add a line about what this means for Iceland today
```

You can edit as many times as you like before approving. Each one is a single
model call and costs a fraction of a cent.

> **A pasted script must be over 200 words** to be taken as a replacement.
> Shorter fenced text is read as an instruction instead, on the assumption you
> were quoting a passage you wanted changed.

## Gate 3 — the finished video

You get a private YouTube link, both thumbnails as images, the `.srt`, and
`UPLOAD.md` with everything for a manual upload.

| You send | What happens | Time |
|---|---|---|
| `publish` | Flips the video from private to public | instant |
| `ship it` · `go live` | Same thing | instant |
| `thumbnail b` | Switches the thumbnail, on YouTube too | instant |
| `thumb a` · `use thumbnail c` | Same thing | instant |
| `title The Day Iceland Burned` | Changes the title, on YouTube too | instant |
| `tags volcano, iceland, laki` | Replaces the tags | instant |
| `change the description to …` | Replaces the description | instant |
| `redo the thumbnail` | Regenerates the three thumbnails | 3–5 min |
| `redo the footage` | Re-picks stock, re-renders, re-uploads | 30–60 min |

### What `redo` can re-run

`narrate` · `captions` · `storyboard` · `charts` · `stock` · `visuals` ·
`audio` · `thumbnail` · `render`

Two behave differently, and it matters:

- **`thumbnail` and `captions` patch the existing video.** Fast, and the
  YouTube link stays the same.
- **Everything else means a re-render**, because the video file itself
  changes — and YouTube can't swap the file behind an existing video. The old
  private upload is deleted and a new one takes its place, so **the link
  changes**.

`redo` never touches the script or the research. Those are yours; re-running
them would throw away the edit you made at Gate 2.

## Any time

| You send | What happens | Time |
|---|---|---|
| `status` | Where the current run is | **instant** |
| `/status` · `where are we` · `?` | Same thing | **instant** |
| `retry` | Re-runs whatever just failed | varies |
| `try again` · `again` | Same thing | varies |
| `cancel` | Abandons the current run | instant |
| `stop` · `abandon` | Same thing | instant |

`status` is the only command answered by the Cloudflare Worker alone — it
reads one file from the repo and replies in about a second, without starting a
job. Everything else goes through GitHub Actions and takes ~60 seconds just to
boot.

`retry` works out what needs re-running by looking at how far the run got:

| Where it stopped | What `retry` does |
|---|---|
| Topic engine failed | Proposes topics again |
| Topics are waiting on you | Says so — nothing to retry |
| Research or writing failed | Re-runs them with the topic you chose |
| Build failed | Resumes the build from the stage that broke |

Finished stages are skipped, so a retry never pays for the same work twice. A
build that dies at minute 85 resumes at minute 85.

---

## Buttons

Buttons send a short code rather than words. You'll never type these, but
they're what appears in the logs.

| Button | Code |
|---|---|
| Topic number | `pick:3` |
| ✅ Build it | `cmd:approve` |
| 🅰️ 🅱️ 🅲 | `thumb:a` · `thumb:b` · `thumb:c` |
| 🔁 Redo thumbnail | `redo:thumbnail` |
| 🔁 Redo footage | `redo:stock` |
| 🚀 Publish | `cmd:publish` |
| 🎬 New video | `cmd:new` |
| 🗑 Cancel | `cmd:cancel` |

Typing `redo:visuals` directly works too, for any stage in the list above.

---

## How your message is understood

Two tiers, and knowing which is which explains most surprises.

**1. Exact phrases — free, instant, can't be misread.** Every phrase in the
tables above, plus bare numbers and button codes. No model is involved, so
these work even when the writing model is down or out of credit.

**2. Everything else — one small model call.** Your message plus the run's
current state goes to DeepSeek, which returns an intent. Costs about
$0.0003 a message.

This means free text needs `DEEPSEEK_API_KEY` set in GitHub Actions secrets.
Without it, exact phrases still work and anything else comes back
*"I couldn't work out what you meant"*.

**It will not guess into something expensive.** If the model is unsure, it
says so rather than starting a build or publishing. A misread `approve` costs
real money; a misread `publish` is public.

---

## Things that aren't commands

- **Questions get answers, not actions.** "how long will this take?" or "why
  did you pick that footage?" are answered conversationally.
- **There's no undo.** `cancel` abandons a run, but a published video has to
  be unpublished in the YouTube app.
- **Only you can talk to it.** The Worker checks every message against your
  chat ID and silently drops anything else.
- **One thing at a time.** Messages queue rather than running in parallel, so
  sending `approve` twice doesn't start two builds.

## When something breaks

Every stage reports failures into the chat with the stage name and a link to
the log. If you get silence for more than ~10 minutes after sending something,
the workflow didn't start at all — check the repo's **Actions** tab, and
suspect `GITHUB_TOKEN` in the Worker rather than the pipeline.

Run it from a terminal to see the same thing without a phone:

```bash
python -m pipeline.brain --text "use thumbnail b"     # what would that do?
python tools/telegram_setup.py --status               # is the webhook healthy?
python -m pipeline.chat                               # send yourself a test message
```
