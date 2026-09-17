# The Boring Docs — automated video pipeline

Makes long-form personal-finance explainer videos for [@TheBoringDocs](https://youtube.com/@TheBoringDocs), start to finish, with two short human approvals.

It runs on GitHub's servers on a weekly schedule, so nothing needs to be switched on at your end. It also runs on your own Mac with the same commands — see [MAC.md](MAC.md).

**New here? Go straight to [SETUP.md](SETUP.md).** It's the step-by-step, phone-friendly version. This file explains how the thing works.

---

## The weekly loop

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
   ║  ⏸  GATE 1    ║   an issue appears. You reply with a number.  ~2 min
   ╚═══════════════╝
        │
        ▼
  ┌───────────────────┐
  │ Research + write  │  builds a sourced dossier, then a five-pass
  └───────────────────┘  script chain: outline, draft, hook, fact-check, polish
        │
        ▼
   ╔═══════════════╗
   ║  ⏸  GATE 2    ║   the script appears. You edit it, reply "approve".  ~5 min
   ╚═══════════════╝
        │
        ▼
  ┌───────────────────┐
  │  Build the video  │  narrate → time the captions → build charts →
  └───────────────────┘  fetch and check stock → render → thumbnail
        │
        ▼
  Finished MP4 + thumbnail + title/description, posted back to the issue
```

Total time from you: about seven minutes per video.

### Why there are exactly two gates

Not because the machine can't run without you. Because of what YouTube did in January 2026, when channels totalling roughly 35 million subscribers were wiped for "inauthentic content".

Using AI is explicitly allowed. Producing interchangeable, templated, low-variation output is not. A named host with a consistent point of view, a real editorial decision on every script, and a human replying to comments reads as *a person using AI tools*. Those two gates are where that happens — which is why Gate 2 asks you to actually change something rather than tick a box.

---

## What's in here

```
config/           Your channel, as data. Edit these, not the code.
  channel.json      cadence, model choices, safety switches, shot rules
  brand.json        colours — used by charts, cards, thumbnails and video
  persona.md        who Armin Kessler is; pasted into every writing prompt
  topic_backlog.csv your 32 seed topics

prompts/          The instructions sent to the writing model, one file per pass.
                  Tune these to change how the videos read. No code involved.

pipeline/         One module per stage. Each runs on its own.
  common.py         config, secrets, retries, run folders
  llm.py            talks to DeepSeek, falls back to Gemini
  topics.py         stage 1 — topic engine
  research.py       stage 2 — dossier from Exa + Tavily + trafilatura
  script.py         stage 3 — the five-pass writing chain
  narrate.py        stage 4 — text to speech
  align.py          stage 5 — word-level timings (required)
  storyboard.py     stage 6 — plans every shot against those timings
  charts3d.py       stage 7 — GPT-6 Astra writes a three.js component per chart
  stock.py          stage 7 — stock clips, ranked by vision against the narration
  visuals.py        stage 8 — AI keyframes, motion clips, depth maps, budget cap
  fal.py            the fal.ai client every generation model goes through
  shotlist.py       stage 9 — maps the storyboard to what was built
  audio.py          stage 10 — music ducking and loudness
  thumbnail.py      stage 11 — three thumbnails, ranked by a shrink test
  render.py         stage 12 — hands it all to Remotion
  publish.py        stage 13 — YouTube upload (off by default)
  run.py            the orchestrator that chains them together

remotion/         The video itself, written as React components.
  src/components/   StockClip, ParallaxStill, EvidenceCard, ImpactCard,
                    LookOverlay, charts/ (Bars3D, Line3D, BigNumber - three.js)
  src/MainVideo.tsx the composition that assembles them from the shot list

.github/workflows/  The three scheduled jobs that drive the loop.
tools/            One-off helpers: YouTube sign-in, demo assets, self-test.
DECISIONS.md      Why the model choices are what they are. Read before
                  swapping in a newly-launched model.
runs/             One folder per video. Everything a run produced.
```

---

## The idea that makes it work: planning shots after the narration exists

The writing model has never heard the narration, so it can't know that the credit-score chart belongs at 4 minutes 12 seconds.

So shots aren't planned with the script. They're planned by `storyboard.py` *after* the voice is recorded and every word is timestamped: the model sees each sentence with its real start and end time and decides what's on screen while it's spoken, cutting where the narration changes subject. Code then snaps every shot to the words where its subject starts and refuses anything it can't verify: a chart that doesn't exist, a "quote" that isn't in the source, a figure the research doesn't contain. Those become ordinary footage instead of reaching the screen.

That one ordering is why the videos cut like ColdFusion and Moon rather than like a slideshow, and it's the piece worth understanding if you only read one part of the code.

---

## Running a stage by hand

Every stage is independently runnable, and each writes its output to `runs/<id>/` before the next starts. A failure costs you one stage, not the whole run.

```bash
python -m pipeline.run topics                  # Gate 1
python -m pipeline.run choose --run latest --pick 3
python -m pipeline.run write  --run latest     # Gate 2
python -m pipeline.run build  --run latest     # everything else

python -m pipeline.run stage render --run latest   # redo just one stage
```

Check everything is wired up correctly, with no API keys and no cost:

```bash
python tools/selftest.py    # storyboard checks, budget cap, shot list, thumbnail
make demo                   # renders a real 24-second MP4, every shot type
```

---

## Cost

At six videos a month, on the free GitHub Actions allowance:

| Item | Monthly |
|---|---|
| GitHub Actions | $0 — free for public repos; 2,000 min/month on private |
| Remotion (individual licence) | $0 |
| Word timing (runs on the runner) | $0 |
| Pexels + Pixabay + Exa + Tavily free tiers | $0 |
| DeepSeek — the scripts and storyboards | ~$3 |
| Gemini TTS — the narration | ~$1.50 |
| Gemini vision checks (keyframes, clips, stock, thumbnails) | ~$1 |
| **fal.ai — AI visuals, capped at `visuals.budget_usd` ($25) per video** | **~$150** |
| fal.ai — thumbnails, 3 per video | ~$2 |
| **Total** | **~$155/month** |

The AI visuals are the product now — about 80% of what's on screen. The cap is enforced before anything is spent: lower `visuals.budget_usd` and fewer shots get paid motion (the rest get free depth-parallax moves). See DECISIONS.md.

If you make the repo **private**, watch the 2,000 free minutes: a build is roughly 60–150 minutes (most of it waiting on video generation and the three.js render), so six videos can approach the limit. A **public** repo has unlimited minutes. Nothing here is secret — the keys live in GitHub Secrets, not in the code — so public is a reasonable choice.

---

## Where this deliberately differs from the plan

Four changes, each with a reason:

| Plan said | This does | Why |
|---|---|---|
| Oracle Cloud free VM running n8n | GitHub Actions | Nothing to set up, maintain or renew, and everything works from a phone. The Oracle box was one more thing that could quietly die. |
| Telegram approval gates | GitHub issue comments | No extra service, and the whole history of every video lives next to its code. |
| WhisperX for word timing | faster-whisper | Same word-level output, no PyTorch, ~200 MB instead of ~2.5 GB, far less likely to break. |
| Rendering on your Mac | Rendering on the runner | Removes the "is the Mac awake?" dependency. The Mac still works — see [MAC.md](MAC.md). |

Everything else follows the plan: the phases, the two gates and the anti-templating rules. The visual style, tone and budget changed in September 2026 — see DECISIONS.md.

**And one thing the plan is right about that this repo cannot do for you:** Phase 1. Three videos made by hand, published, measured. Retention above 35%, click-through above 4%. Until you have those numbers, `config/channel.json` keeps `review_only: true` and the pipeline will not publish anything — it hands you the file and you decide.

Automating a video with 20% retention just produces six failing videos a month instead of one.
