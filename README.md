# Deep Earth — automated video pipeline

Makes long-form Earth science documentaries (volcanoes, earthquakes, deep time, ice ages, oceans) for the Deep Earth channel, start to finish, **driven from a chat app on your Mac**.

Forked on 17 Sep 2026 from the pipeline behind The Boring Docs. The engine is the same; the tone, the research sources and the footage libraries are not. See DECISIONS.md.

It runs on your Mac because the render needs a GPU: the three.js charts and depth-parallax stills render in about 20 minutes on an M2 Pro, and took 45–90+ on GPU-less cloud runners.

**New here? Go to [SETUP.md](SETUP.md).** This file explains how the thing works.

---

## The loop

```
  yt-studio: make app  →  http://127.0.0.1:8765  →  🌋 Deep Earth
        │
  ┌───────────────────┐
  │ Propose 10 topics │  YouTube outliers, search trends, forum questions, your backlog
  └───────────────────┘
   ╔═══════════════╗
   ║  ⏸  GATE 1    ║   ten topics, a button each. Tap one.
   ╚═══════════════╝
  ┌───────────────────┐
  │ Research + write  │  sourced dossier, then outline → draft → hook → fact-check → polish
  └───────────────────┘
   ╔═══════════════╗
   ║  ⏸  GATE 2    ║   the script. Say what to change, in words, as often as you like.
   ╚═══════════════╝   Then "Build it".
  ┌───────────────────┐
  │  Build the video  │  narrate → subtitles → storyboard → charts → footage →
  └───────────────────┘  audio → thumbnails → render (Mac GPU)
   ╔═══════════════╗
   ║  ⏸  GATE 3    ║   the video plays in the chat, with the title, description, tags,
   ╚═══════════════╝   pinned comment, 3 thumbnails, subtitles.srt and UPLOAD.md.
        │                Change anything. Then "Accept & upload".
        ▼
  Uploaded to YouTube with every field filled in, public, comment posted (you tap Pin)
```

Nothing is uploaded until you press **Accept & upload**.

### Why there are three gates

Not because the machine can't run without you. Because of what YouTube did in January 2026, when channels totalling roughly 35 million subscribers were wiped for "inauthentic content".

Using AI is explicitly allowed. Producing interchangeable, templated, low-variation output is not. A named host with a consistent point of view, a real editorial decision on every script, and a human replying to comments reads as *a person using AI tools*. The gates are where that happens — which is why Gate 2 asks you to actually change something rather than tick a box.

### What you can say

| You send | What happens |
|---|---|
| `new video` | Proposes ten topics |
| `3` | Picks topic 3, researches and writes the script |
| `make the opening punchier` | Rewrites the script with that change |
| `approve` | Builds the video |
| `thumbnail b` | Switches the thumbnail |
| `change the pinned comment to …` | Rewrites the comment |
| `redo the footage` | Re-picks stock and re-renders |
| `accept` | Uploads to YouTube and makes it public |
| `status` | Where the current run is |
| Stop / Retry buttons | Stop the running job / resume from the last finished stage |

Anything else is read by a model, which either does what you meant or answers you, with the run's script and metadata in view.

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

  chat.py           the chat log (runs/chat.jsonl) every stage writes to
  brain.py          reads what you typed — rules first, then a model
  assistant.py      does it, answers questions, and posts the three gates

remotion/         The video itself, written as React components.
  src/components/   StockClip, ParallaxStill, EvidenceCard, ImpactCard,
                    LookOverlay, charts/ (Bars3D, Line3D, BigNumber - three.js)
  src/MainVideo.tsx the composition that assembles them from the shot list

tools/            chat_job.py (the slow half of a chat request), YouTube sign-in, demo, self-test.

The chat app itself lives in ../yt-studio and drives every channel repo; this
repo honours its CHANNEL_CONTRACT.md.
docs/             A portable blueprint for reusing this design.
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

The studio is a layer on top of exactly these commands. You can also poke the chat from the command line:

```bash
python -m pipeline.brain --text "use thumbnail b"     # what would that do?
python tools/chat_job.py --intent new                 # as if you'd said "new video"
python -m pipeline.assistant --present review --run latest   # re-post Gate 3
```

Check everything is wired up correctly, with no API keys and no cost:

```bash
python tools/selftest.py    # storyboard, budget cap, shot list, thumbnail, subtitles
make demo                   # renders a real 24-second MP4, every shot type
```

---

## Cost

At six videos a month:

| Item | Monthly |
|---|---|
| The studio, rendering, word timing, subtitles (all on your Mac) | $0 |
| Remotion (individual licence) | $0 |
| NASA + Wikimedia Commons (no keys) + Pexels + Pixabay + Exa + Tavily free tiers | $0 |
| YouTube Data API | $0 |
| DeepSeek — scripts, storyboards, chat | ~$3 |
| ElevenLabs — the narration | ~$7 |
| Gemini vision checks (keyframes, clips, stock, thumbnails) | ~$1 |
| fal.ai — last-resort AI visuals and photo depth maps, capped at `visuals.budget_usd` ($5) per video | ≤ $30 |
| fal.ai — thumbnails, 3 per video | ~$2 |
| **Total** | **≤ ~$45/month** |

Real footage and photographs are the product: AI is only for scenes no camera recorded, and for shots no library could fill. The cap is enforced before anything is spent. See DECISIONS.md.

---

**And one thing the plan is right about that this repo cannot do for you:** Phase 1. Three videos made by hand, published, measured. Retention above 35%, click-through above 4%. Until you have those numbers, `config/channel.json` keeps `review_only: true`, which means nothing goes public on its own — the video is uploaded private for you to watch, and only your `publish` makes it live.

Automating a video with 20% retention just produces six failing videos a month instead of one.
