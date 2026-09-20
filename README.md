# Deep Earth — automated video pipeline

Makes long-form Earth science documentaries (volcanoes, earthquakes, deep time, ice ages, oceans) for the Deep Earth channel, start to finish, **run entirely from Telegram on your phone**.

Forked on 17 Sep 2026 from the pipeline behind The Boring Docs. The engine is the same; the tone, the research sources and the footage libraries are not. See DECISIONS.md.

It runs on GitHub's servers on a weekly schedule, so nothing needs to be switched on at your end. It also runs on your own Mac with the same commands — see [MAC.md](MAC.md).

**New here? Go straight to [SETUP.md](SETUP.md)**, then [docs/TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md) to wire up the chat. This file explains how the thing works.

---

## The weekly loop

Everything below happens in one Telegram conversation. You never open a laptop.

```
  Monday 06:00 UTC
        │
        ▼
  ┌───────────────────┐
  │ Propose 10 topics │  looks at YouTube outliers, search trends,
  └───────────────────┘  forum questions and your own backlog
        │
        ▼
   ╔═══════════════╗
   ║  ⏸  GATE 1    ║   ten topics arrive with a button each. Tap one.   ~30 sec
   ╚═══════════════╝
        │
        ▼
  ┌───────────────────┐
  │ Research + write  │  builds a sourced dossier, then a five-pass
  └───────────────────┘  script chain: outline, draft, hook, fact-check, polish
        │
        ▼
   ╔═══════════════╗
   ║  ⏸  GATE 2    ║   the script arrives. Say what to change, in words,  ~5 min
   ╚═══════════════╝   as many times as you like. Then "approve".
        │
        ▼
  ┌───────────────────┐
  │  Build the video  │  narrate → subtitles → storyboard → charts →
  └───────────────────┘  footage → render → thumbnail → upload PRIVATE
        │
        ▼
   ╔═══════════════╗
   ║  ⏸  GATE 3    ║   a YouTube link you can watch in the app, both      ~5 min
   ╚═══════════════╝   thumbnails, the .srt and the upload details.
        │                Change anything. Then "publish".
        ▼
  Public on YouTube, title/description/tags/thumbnail/subtitles all set
```

Total time from you: about ten minutes per video, none of it at a desk.

### Why the video is uploaded before you approve it

An eleven-minute 1080p video is 150–400 MB — far too big for a chat app to send. So the finished video goes up to YouTube as **private** first, and the chat sends you the link.

That turns YouTube itself into the review player: native playback on your phone, full quality, no download. Approving costs one API call that flips private to public, rather than a second upload. Changing the title, the tags or the thumbnail patches the video that's already there.

Nothing is ever public until you reply `publish`.

### Why there are three gates

Not because the machine can't run without you. Because of what YouTube did in January 2026, when channels totalling roughly 35 million subscribers were wiped for "inauthentic content".

Using AI is explicitly allowed. Producing interchangeable, templated, low-variation output is not. A named host with a consistent point of view, a real editorial decision on every script, and a human replying to comments reads as *a person using AI tools*. The gates are where that happens — which is why Gate 2 asks you to actually change something rather than tick a box.

### What you can say

| You send | What happens |
|---|---|
| `new video` | Proposes ten topics |
| `3` | Picks topic 3, researches and writes the script |
| `make the opening punchier` | Rewrites the script with that change |
| `approve` | Builds the video and uploads it privately |
| `thumbnail b` | Switches the thumbnail, on YouTube too |
| `redo the footage` | Re-picks stock, re-renders, re-uploads |
| `publish` | Flips the video from private to public |
| `status` | Where the current run is |

Anything else is read by a model, which either does what you meant or asks. Full list in [docs/TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md).

---

## What's in here

```
config/           Your channel, as data. Edit these, not the code.
  channel.json      cadence, model choices, safety switches, shot rules
  brand.json        colours — used by charts, cards, thumbnails and video
  persona.md        who Ellis Hart is; pasted into every writing prompt
  topic_backlog.csv your 32 seed topics

prompts/          The instructions sent to the writing model, one file per pass.
                  Tune these to change how the videos read. No code involved.

pipeline/         One module per stage. Each runs on its own.
  common.py         config, secrets, retries, run folders
  llm.py            talks to DeepSeek, falls back to Gemini
  topics.py         stage 1 — topic engine
  research.py       stage 2 — dossier from Exa + Tavily, plus a USGS/NASA/NOAA/textbook-only search
  script.py         stage 3 — the five-pass writing chain
  narrate.py        stage 4 — text to speech
  align.py          stage 5 — word-level timings (required)
  captions.py       stage 6 — subtitles.srt, cut from those timings
  storyboard.py     stage 7 — plans every shot against those timings
  charts3d.py       stage 7 — GPT-6 Astra writes a three.js component per chart
  stock.py          stage 7 — NASA, Wikimedia Commons, Pexels, Pixabay footage and photos, ranked by vision against the narration
  visuals.py        stage 8 — AI keyframes, motion clips, depth maps, budget cap
  fal.py            the fal.ai client every generation model goes through
  shotlist.py       stage 9 — maps the storyboard to what was built
  audio.py          stage 10 — music ducking and loudness
  thumbnail.py      stage 11 — three thumbnails, ranked by a shrink test
  render.py         stage 12 — hands it all to Remotion
  publish.py        stage 13 — uploads private, then flips it public on your word
  run.py            the orchestrator that chains them together

  chat.py           sends messages, buttons, photos and files to Telegram
  brain.py          reads what you typed — rules first, then a model
  assistant.py      does it, and posts the three gates

bot/              The Cloudflare Worker that receives your Telegram messages
                  and pokes GitHub Actions. Stateless, free tier, ~150 lines.

remotion/         The video itself, written as React components.
  src/components/   StockClip, ParallaxStill, EvidenceCard, ImpactCard,
                    LookOverlay, charts/ (Bars3D, Line3D, BigNumber - three.js)
  src/MainVideo.tsx the composition that assembles them from the shot list

.github/workflows/  chat.yml drives the whole loop; weekly.yml is the Monday nudge.
tools/            One-off helpers: YouTube sign-in, Telegram setup, demo, self-test.
docs/             Chat setup, and a portable blueprint for reusing this design.
DECISIONS.md      Why the model choices are what they are. Read before
                  swapping in a newly-launched model.
runs/             One folder per video. Everything a run produced.
```

---

## The idea that makes it work: planning shots after the narration exists

The writing model has never heard the narration, so it can't know that the credit-score chart belongs at 4 minutes 12 seconds.

So shots aren't planned with the script. They're planned by `storyboard.py` *after* the voice is recorded and every word is timestamped: the model sees each sentence with its real start and end time and decides what's on screen while it's spoken, cutting where the narration changes subject. Code then snaps every shot to the words where its subject starts and refuses anything it can't verify: a chart that doesn't exist, a "quote" that isn't in the source, a figure the research doesn't contain. Those become ordinary footage instead of reaching the screen.

That one ordering is why the videos cut like a real documentary rather than like a slideshow, and it's the piece worth understanding if you only read one part of the code.

---

## Running a stage by hand

Every stage is independently runnable, and each writes its output to `runs/<id>/` before the next starts. A failure costs you one stage, not the whole run.

```bash
python -m pipeline.run topics                  # Gate 1
python -m pipeline.run choose --run latest --pick 3
python -m pipeline.run write  --run latest     # Gate 2
python -m pipeline.run build  --run latest     # everything else

python -m pipeline.run stage render --run latest   # redo just one stage
python -m pipeline.publish --run latest --go-live  # flip private to public
```

The chat is a layer on top of exactly these commands — `pipeline/chat.py` becomes a silent no-op when the Telegram secrets are absent, so everything above still works unchanged.

You can also drive the chat from the command line, which is the easiest way to test it:

```bash
python -m pipeline.chat                        # send yourself a test message
python -m pipeline.brain --text "use thumbnail b"     # what would that do?
python tools/chat_job.py --intent new                 # as if you'd said "new video"
python tools/telegram_setup.py --status               # is the webhook healthy?
```

Check everything is wired up correctly, with no API keys and no cost:

```bash
python tools/selftest.py    # storyboard, budget cap, shot list, thumbnail, subtitles
make demo                   # renders a real 24-second MP4, every shot type
```

---

## Cost

At six videos a month, on the free GitHub Actions allowance:

| Item | Monthly |
|---|---|
| GitHub Actions | $0 — free for public repos; 2,000 min/month on private |
| Telegram Bot API | $0 — unlimited |
| Cloudflare Worker (the chat bridge) | $0 — 100,000 requests/day free, no card |
| Remotion (individual licence) | $0 |
| Word timing and subtitles (run on the runner) | $0 |
| NASA + Wikimedia Commons (no keys) + Pexels + Pixabay + Exa + Tavily free tiers | $0 |
| DeepSeek — the scripts and storyboards | ~$3 |
| ElevenLabs — the narration | ~$7 |
| Gemini vision checks (keyframes, clips, stock, thumbnails) | ~$1 |
| fal.ai — last-resort AI visuals and photo depth maps, capped at `visuals.budget_usd` ($5) per video | ≤ $30 |
| fal.ai — thumbnails, 3 per video | ~$2 |
| **Total** | **≤ ~$45/month** |

Real footage and photographs are the product: AI is only for scenes no camera recorded, and for shots no library could fill. The cap is enforced before anything is spent. See DECISIONS.md.

If you make the repo **private**, watch the 2,000 free minutes: a build is roughly 60–150 minutes (most of it waiting on video generation and the three.js render), so six videos can approach the limit. A **public** repo has unlimited minutes. Nothing here is secret — the keys live in GitHub Secrets, not in the code — so public is a reasonable choice.

---

## Where this deliberately differs from the plan

Four changes, each with a reason:

| Plan said | This does | Why |
|---|---|---|
| Oracle Cloud free VM running n8n | GitHub Actions + a Cloudflare Worker | Nothing to set up, maintain or renew, and everything works from a phone. The Oracle box was one more thing that could quietly die. The Worker is stateless and free, and holds no run state of its own. |
| WhisperX for word timing | faster-whisper | Same word-level output, no PyTorch, ~200 MB instead of ~2.5 GB, far less likely to break. |
| Rendering on your Mac | Rendering on the runner | Removes the "is the Mac awake?" dependency. The Mac still works — see [MAC.md](MAC.md). |
| Review the MP4, then upload it | Upload it private, review on YouTube | A 400 MB file can't go down a chat pipe. YouTube's private state is a free review player that streams natively to your phone, and approving becomes one API call. |

The Telegram approval gates the plan called for are what this now uses — an earlier version routed them through GitHub issue comments instead. See [docs/CHAT_AUTOMATION_BLUEPRINT.md](docs/CHAT_AUTOMATION_BLUEPRINT.md) for the reasoning, and for reusing the design on another project.

Everything else follows the plan: the phases, the gates and the anti-templating rules. The tone, sources and footage differ from The Boring Docs — see DECISIONS.md.

**And one thing the plan is right about that this repo cannot do for you:** Phase 1. Three videos made by hand, published, measured. Retention above 35%, click-through above 4%. Until you have those numbers, `config/channel.json` keeps `review_only: true`, which means nothing goes public on its own — the video is uploaded private for you to watch, and only your `publish` makes it live.

Automating a video with 20% retention just produces six failing videos a month instead of one.
