# Decisions

Why things are the way they are. Written so that a model launching next month
doesn't restart an argument that's already been had.

---

## 14 September 2026 (evening) — stock-first footage, Astra charts, one voice

Revises the entry below after the first full video. Read both.

### Voice: Charon's natural read, with a drift guard
A British RP style instruction was tried and rejected by ear; `models.tts.gemini_style`
is empty. The long-standing "two narrators" problem was measured, not imagined:
each ~2,500-character chunk is a separate TTS call and the voice drifts between
calls (median pitch per chunk 116, 146, 121, 145, 125, 124 Hz - chunks 2 and 4
about 25% higher). `narrate.py` now measures each chunk's median pitch against
the first and regenerates any more than 8% off.

**Superseded 15 Sep 2026:** the drift guard missed a voice change at the 2:19
join (pitch matched, timbre didn't - Gemini re-rolls the voice per call). The
default provider is now ElevenLabs `eleven_multilingual_v2` with one fixed
voice, a fixed seed, `previous_text`/`next_text` stitching and 5,000-char
chunks (2-3 joins instead of 6), ~$1.10 per video. The pitch guard still runs.

### Footage: stock everywhere, AI only where no library can show it
Viewer feedback on the 14 Sep build (15 Sep 2026): stock was the most relevant
footage, AI generations were weakest (garbled calculators, blood-red accents,
squalid rooms), footage cut away before its narration finished, and charts and
numbers vanished before they could be read. So:
- The storyboard plans every footage beat as stock, starting on the words where
  its subject starts (`from_words`), not at an even split of the sentence.
- `stock.py` fills a shot with as many short relevant clips as it needs (each
  ranked on a contact sheet against the words spoken, >= 6/10). Coming up
  short, a model writes three fresh searches for a second round. Only a shot
  under 60% covered after that is generated; 60-100% is slowed to fit.
- Rate limits are waited out, not turned into AI (Pexels: 200 searches/hour,
  and its 429s carry no reset time, so `library_get` pauses all searches and
  re-checks every 10 minutes; Pixabay: waits its `X-RateLimit-Reset`). Only a
  limit that outlasts 75 minutes - the monthly quota - gives up.
- Charts stay >= 6s, numbers/cards/evidence >= 4s (numbers <= 5s).
- The look bible and keyframe check ban blood, decay, squalor and digit
  displays, and reject a keyframe that doesn't show the shot's intent.
Clips are never reused across the channel (`runs/stock_used.json`).

### Timing: the voice engine's own word times, not a transcript (15 Sep 2026)
Viewer feedback: "the audio is always ahead of or behind the visuals". The audio
path was measured exact (mastered WAV and muxed video match narration.wav sample
for sample, no drift over 11 minutes), and whisper's word starts were only
~0.1-0.2s early. The real fault was the transcript: faster-whisper heard
12.5% of words differently from the script - every one of them a number
("six hundred eight thousand" -> "608 000") - so sentence boundaries, and the
phrases the storyboard model quotes back as "from_words", did not match the
script it was shown. ElevenLabs' /with-timestamps returns character times for
the text it spoke, so narrate.py now writes words.json itself and align.py only
falls back to whisper for other providers (or if the timings don't cover the
script). Cuts also land CUT_LEAD_SECONDS (0.12s, ~4 frames) before the word -
cutting on it reads as late - and a mid-sentence footage beat with no findable
"from_words" is dropped rather than cut at an arbitrary word.

### DeepSeek was never down - our read timeout was too short (16 Sep 2026)
Every storyboard fell back to Gemini with "Read timed out". Measured: a
storyboard chunk takes ~174s (27k chars in, 14k of JSON out) and the reply only
arrives once generation finishes, but llm.py passed `timeout=(15, 60)`, so the
socket closed first - every time, on the one call big enough to matter, which
is why it looked like an outage while 5s calls kept working. The comment
claiming keep-alive bytes hold the connection open was wrong: that only happens
on streaming requests, and this one isn't streamed. The read timeout now covers
the whole generation and TIMEOUT (420s) stays as the dribble guard.
Every video up to and including v4 was therefore planned by Gemini, not
DeepSeek.

### Counts, not adjectives, drive the planner (16 Sep 2026)
"Use them freely: about two a minute" produced 5 evidence beats in a whole
video. Explicit per-stretch counts (evidence_per_minute, numbers_per_minute,
cards_per_minute, extra_charts_per_minute in config) produced the asked-for
mix - but only once EVERY kind had a count: given a target for one, the model
robs the others to pay it. Two more things were needed:
- top_up_evidence(): one extra call asking for quotes alone when the chunk
  passes came up short. Asked for quotes on their own, the model delivers.
- The quotes already used are passed into both prompts. Without that, 6 of 16
  receipts were the same sentence repeated, and duplicates get demoted.
v4: 30 data shots, 32% of runtime, one every 21s (v3: 25, 24%, every 27s).

### More receipts, held longer (15 Sep 2026)
Viewer feedback: the charts and highlighted source pages are what make the video
look real, and they cut the reliance on stock. So: charts hold 8-12s (was 6-9),
source quotes 6-8s (was 4-6), extra charts built from spoken figures capped at 6
(was 4), and the storyboard prompt asks for about two quotes a minute (was one
or two) of 15-25 words each. Re-assembling v3's beats at these lengths alone
moved data shots from 24% to 29% of runtime; the count rises when a new video is
planned. The rule that every figure must appear in the dossier is untouched -
that check is why they read as trustworthy. Watch the next video for
slideshow-of-paper: past roughly a third of runtime this stops helping.
A data shot now leaves the opening shot at least min_shot_seconds when it takes
time from its neighbours, so the video can never open on a chart.

### Voice: Bren (Irish), documentary read (15 Sep 2026)
Chosen by ear from snippets of the real script, over Charlie (Australian),
Brian, Adam and Bill. A conversational rewrite was tried and rejected - the
scripted documentary register stays. Pace matters as much as timbre: Charlie
ran ~14% slower than Bren on the same passage, which would have pushed an
11-minute video past 12:30.

### Shot length: hold until the narration turns (15 Sep 2026)
Footage is capped at MAX_FOOTAGE_SECONDS (15) and an over-long shot is cut at
the sentence boundaries inside it, each part finding its own clip - v3 planned
one 33s shot over a run of index figures.
Shots run in parallel and share searches, so fill() takes a `claim` callback:
a clip another shot grabbed first falls through to the next best instead of
leaving the shot to be generated (v3's first pass lost 3 shots that way,
including two with 8-9/10 candidates).
6-12s (up to 15) rather than a 2-6s cadence: fewer cuts mean fewer chances to
land wrong, one clip that fits beats three that nearly fit, and fewer searches
means fewer rate-limit waits. stock.py's fill() now prefers a single clip that
covers the whole shot over stitching two, within 1 point of the best score.

### Gemini models (15 Sep 2026): 3.8 Flash everywhere 3.5 Flash was
Gemini 3.5 Flash became Google's priciest Flash ($1.50/$9.00 per 1M tokens vs
3.8 Flash's $0.75/$3.75, introductory until 31 Dec 2026, then $1.50/$7.50),
so the backup writer, stock ranking and the chart number check all use
`gemini-3.8-flash` to cut costs. Flash-Lite QA checks are unchanged.
Known trade-off, from an A/B on 10 real contact sheets: 3.8 Flash cost $0.007
a sheet vs $0.029 (~$0.90 vs ~$3.50 of ranking per video) but was a little
less discerning - it passed an unrelated clip (a bright card-writing scene for
"a closed apartment door at night") and missed a good envelope clip, where 3.5
Flash didn't; high thinking ($0.012) didn't fix either, and 3.5 Flash in turn
passed a sunny clip the prompt caps at 4/10. If footage relevance slips, set
`RANK_MODEL` in `pipeline/stock.py` back to `gemini-3.5-flash`.

### Rejected: Storyblocks (subscription, API, or an agent driving the browser)
The CA$30-42/month plans forbid "robots or similar data gathering or extraction
technology... including artificial intelligence... to crawl, scrape" and using
content or metadata "for any machine learning and/or artificial intelligence
purposes" - which rules out automated search, AI ranking of previews, and an AI
agent operating the site on the owner's laptop. The API is the sanctioned route
but is quoted at roughly $6k-12k+/year. Hand-picking clips into the pipeline
remains possible if ever wanted; it was not built.

### Adopted: GPT-6 Astra writes a chart component per video
This reverses "per-video animation code generation should not start" (below),
at the channel owner's request. The objections were cost, latency and
non-determinism; they are handled rather than avoided:
- **Cost:** ~$0.25 per chart measured ($10/$50 per M tokens), max 8 per video.
- **Correctness:** numbers arrive as props, never code; every component must pass
  static rules (allowed imports, no clocks/randomness), `tsc`, a full render of
  its shot, and a vision read-back of every value on the final frame. Failures
  go back to Astra twice, then fall back to the built-in chart.
- **Determinism:** the same frame rules as every other component; accepted
  components are cached by a hash of their data.
The first test ("Median Rent vs. Median Renter Income") passed on attempt 1 in
99 s for $0.23: an apartment tower rising beside a flat income slab.

---

## 14 September 2026 — AI-first visuals and fear-driven framing

This entry **supersedes** three earlier calls below: "Rejected: AI imagery for
stock footage", "Charts stay on matplotlib", and the ~$5–12/month budget. It
**keeps** "no per-video animation codegen". Read it before reverting any of them.

### Why the change

The first full render (7:57, run 2026-09-14-0135) was mostly word-by-word
kinetic text on a dark background, with flat matplotlib bars and generic Pexels
office clips. Nine of sixteen sampled frames were text. The script and voice
were right; the picture was not something anyone would keep watching.

The reference points are ColdFusion ("SpaceX Went Public – A Disaster Waiting
to Happen", 1.07M views) and Moon ("The Pervert Economy", 234K in three days),
studied frame by frame via their storyboards. What they share:

- **Fear on top of receipts.** Alarmist framing, but every scary claim is
  *shown*: highlighted filings, headlines, tweets. That's why the alarm is
  credible rather than dismissible.
- **Fast cutting.** Moon ~2–3 s a shot, ColdFusion ~4–6 s.
- **A dark, ominous grade** and brooding music under a calm, grave narrator.
- **Text only where it lands a beat**: bold condensed question and figure
  cards, never captions.
- **Thumbnails that tell a visual story**, often with no text at all.

### What was adopted

**Tone: fear-driven.** `config/persona.md`, `prompts/system.md` (rule 4),
`prompts/hook.md`, `prompts/draft.md`, `prompts/outline.md` and the polish
title rules now lead with the threat, name who profits, escalate, and end
sections on open loops. The fact-check's `overstated_causation` flag is logged
as a warning rather than auto-rewritten, because it was sanding dramatic
framing back into neutral prose.

**Kept as hard lines:** never invent or inflate a number, source or quote, and
never give individual financial advice. The fact-check still auto-fixes wrong
numbers and attributions. Both reference channels build their alarm on real
documents; a fabricated finance claim is both a credibility collapse and a
misinformation strike.

**Visuals: ~80% AI footage, ~20% stock, via fal.ai.** Shots are planned *after*
narration against real word timings (`pipeline/storyboard.py`), every 2–6 s.
Each AI shot gets a keyframe (Seedream 5 Lite, ~$0.035); the highest-priority
ones are animated (MiniMax H3 Max image-to-video, #1 on Artificial Analysis'
image-to-video board, $0.08/s at 768P); the rest get a free depth-parallax
camera move rendered in three.js. A pre-flight allocator caps spend at
`visuals.budget_usd` ($25 ≈ 40 animated shots in an 11-minute video).
Everything is cached by content hash, so a rebuild costs nothing.

**Receipts: evidence cards.** Recreated source pages with the exact sentence
highlighted, built from the research dossier's own text. The storyboard only
lets through quotes that appear verbatim in the source. Broadcast clips
(ColdFusion's CNBC inserts) are deliberately not used: Content ID and
copyright risk on an automated channel.

**Charts: three.js, committed components.** `Bars3D`, `Line3D` and `BigNumber`
are parameterised by the outline's data, with near-frontal cameras and crisp
HTML labels projected from 3D, so the numbers stay legible. The objection that
"3D reads as decoration" is answered by the camera limits, not by avoiding 3D.
Per-video LLM-written animation code stays rejected (cost, non-determinism);
the September `animation.py` experiment was deleted.

**Cards:** at most 6 per video (`storyboard.max_cards`), question or fact, and
fact cards only with figures found in the dossier.

**Thumbnails:** three concepts planned at Gate 2 with the title (≤4 words, never
repeating the title, at least one with no text) → Nano Banana 2 hero image →
Pillow text and symbol → vision-model shrink test at phone size → ranked
`thumbnail.jpg`, `_b`, `_c` for YouTube Test & Compare.

**Alignment is required.** Estimated timings drift a second or more a minute,
which is fatal at this cutting pace, so `align.py` now fails instead of guessing.

### What was rejected

- **An AI presenter / lip-synced host** (the Otis Granger approach). YouTube's
  16 July 2026 clarification says it won't incentivise "AI personas" discussing
  finance. Continuity comes from a per-video look bible of recurring locations
  and props instead. No recurring people on screen.
- **Higgsfield, vidIQ's video generator, Kutly.** Higgsfield resells the same
  models on hard-to-budget credits (its "unlimited" only applies in the web UI)
  and doesn't assemble long-form video; useful by hand for testing a look.
  vidIQ's generator makes 4–15 s clips. Kutly generates the whole video from a
  prompt, largely from stock, discarding our script and producing exactly the
  templated output the inauthentic-content policy targets.
- **n8n.** Orchestration doesn't change output quality; prompts, models, QA and
  edit logic do. The Python stages already resume, and GitHub issues already
  gate. n8n would add a server while Remotion, ffmpeg and alignment stayed code.

### Budget and disclosure

AI media is now ~$25 per video, ~$150/month at six videos, on top of the ~$5
running cost. That is a deliberate move from a near-free pipeline to one where
the visuals are the product. Photorealistic AI footage will trigger YouTube's
C2PA/SynthID auto-label; `containsSyntheticMedia` is already declared on upload
(`publish.py`), and YouTube states the label alone affects neither reach nor
monetisation. The inauthentic-content risk is templated sameness, which the
rotating script shapes, per-video look bibles and storyboarded shots work against.

### Render determinism (checked)

The same range rendered twice on the Mac (`--gl=angle`): parallax-still frames
are bit-identical; three.js chart frames differ at PSNR 48–58 dB (mean error
under one grey level) — GPU antialiasing noise, invisible, not flicker.

---

## September 2026 — GPT-6 Astra and ChatGPT Images 2.5

Two OpenAI launches were assessed against this pipeline on 13 September 2026.

### Rejected: GPT-6 Astra for the writing chain

`gpt-6-astra` (launched 3–4 Sep 2026) costs **$10/M input and $50/M output**.
DeepSeek V4.1 Flash costs **$0.15/M input and $0.60/M output** off-peak. That is
67× on input and 83× on output.

Working from this pipeline's actual shape — a roughly 4,000-word dossier, five
sequential passes, a ~1,400-word script out, six videos a month — the answer
tokens alone come to about 240,000 in and 54,000 out per month:

| | Input | Output | Monthly |
|---|---|---|---|
| DeepSeek V4.1 Flash | 0.24M × $0.15 = $0.04 | 0.054M × $0.60 = $0.03 | **~$0.07** |
| GPT-6 Astra | 0.24M × $10 = $2.40 | 0.054M × $50 = $2.70 | **~$5.10+** |

The $5.10 figure is optimistic: Astra is a reasoning model and bills hidden
reasoning tokens at the same $50/M, commonly one to three times the answer
tokens. Scaling the real observed DeepSeek spend (~$3/month, higher than this
clean model because of research summarising and retries) puts all-Astra at
roughly **$60–$240/month** against a total budget of $8–12.

The cost would be arguable if quality followed. It doesn't. Astra gained on
analytical substance and **regressed on prose**: Artificial Analysis records a
drop in Presentation Quality Elo with GPT-5.6 Sol still leading, and Astra
places third on the Lech Mazur creative-writing benchmark with reviewers
describing its output as identifiably AI. The polish pass is the one place where
voice *is* the product.

**If an OpenAI writer is ever wanted, test GPT-5.6 Sol ($4/$20)** — better prose
and cheaper. Batch tier is 50% off and would suit this pipeline's async shape,
but 50% off the wrong model is still the wrong model.

### Adopted: Astra as a build-time tool only

Astra is genuinely state of the art at three.js code generation, and
`@remotion/three` renders three.js inside the existing composition. The value is
one-off — generate a component once, commit it, render it forever at no
recurring cost. `remotion/src/components/AnimatedBackdrop.tsx` was the result
(deleted 14 Sep 2026 with the kinetic-text cards it sat behind).

Calling any model per-video to generate animation code would add cost, latency
and non-determinism, so the pipeline does not do that and should not start.

**Charts stay on matplotlib.** *(Superseded 14 Sep 2026: three.js components, see above.)* 3D chart geometry reads as decoration, and this
channel's credibility rests on the numbers being plainly legible.

### Adopted, off by default: ChatGPT Images 2.5 for thumbnail backgrounds *(superseded 14 Sep 2026: fal.ai thumbnails, see above)*

`gpt-image-2.5-flare` (launched 8 Sep 2026) is token-metered rather than flat
rate; a 1536×1024 high-quality image measures at roughly **$0.05**, so about
**$0.31/month** at six videos, near $1 with A/B variants.

**Correcting a mismatch between the plan and the build:** the implementation plan
budgets ~$1/month for "thumbnail image generation" via Seedream or FLUX. That was
never built. `pipeline/thumbnail.py` draws a Pillow gradient with an accent
shape — free, deterministic, already on-brand, and layout-rotated. So this is not
swapping one paid generator for another; it is going from **$0 to ~$0.31–$1**.

That's why `thumbnail.background` ships as `"gradient"`. Run
`tools/thumbnail_bakeoff.py`, judge blind on a phone, and only switch if the
photographic version genuinely wins. If it doesn't, thirty cents has confirmed
the thumbnail line stays at zero.

### Rejected: AI imagery for stock footage *(superseded 14 Sep 2026, see above)*

Image models produce stills, not motion, so they cannot fill the 30–60
four-second clips a video needs. Even ignoring that, 30–60 images × 6 videos is
**$10–$22/month** on its own. The Sora 2 API is scheduled to sunset on 24 Sep
2026 with no announced successor, and at $0.10/sec would run about $108/month.
Pexels and Pixabay stay.

### The enforcement angle

None of the adopted changes move the risk category.

YouTube's inauthentic-content policy targets mass-produced, low-variation output
whether or not AI made it; the January 2026 sweep hit channels on that basis, not
for AI use as such. Synthetic-content **disclosure** applies to *realistic*
content that could mislead about real people, events or places — charts,
animations, AI thumbnails and synthetic narration all sit outside it, and YouTube
states the label alone affects neither reach nor monetisation.

Swapping a procedural thumbnail background for a photographic one changes
nothing there. Putting photorealistic AI imagery *inside* the videos would:
since May 2026 YouTube auto-labels significant photorealistic AI use by reading
C2PA and SynthID, both of which OpenAI images carry. That is a second,
independent reason the stock-footage substitution stays rejected.

### Housekeeping done at the same time

DeepSeek renamed its models. `deepseek-v4-flash` became `deepseek-flash` (V4.1
Flash) on 10 Sep 2026, and `deepseek-v4-pro` reroutes to V4.1 Flash from 04:00
UTC on 14 Sep until V4.1 Pro ships. `config/channel.json` has been updated.
**When V4.1 Pro ships, point `polish_model` back at it** — until then the polish
pass runs the same model as the other four, which is what DeepSeek is doing
server-side anyway.

---
