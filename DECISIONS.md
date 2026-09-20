# Decisions

Why things are the way they are. Written so that a model launching next month
doesn't restart an argument that's already been had.

---

## 19 September 2026 — what the first real build taught us

Video 1 (Hunga Tonga, 13:11) came out at 81% real footage, 19% AI, with 39 data
shots. These changes came out of watching it build.

### Vision: Gemini 3.8 Flash ranks, OpenAI catches the fall
Measured head to head on 7 real contact sheets from that build. Gemini passes
honest stand-in footage for subjects no camera can film (satellite wave clouds
9/10 for a pressure pulse, a sunset haze layer 7/10); gpt-5.4-mini scored both
under the 6/10 bar and those shots became AI. gpt-5.4-mini is stricter, 3s vs
7-14s per sheet, $0.0033 vs $0.007, and better on literal subjects - it found
real underwater vent plumes Gemini missed. Strictness is the dearer option
here: a rejected shot costs $0.04-$0.44 of AI generation. OpenAI is now the
automatic fallback when Gemini's prepaid balance runs dry, which it did
mid-build. Motion QA on AI clips stays Gemini-only: OpenAI takes images only.

### The ranking prompt allows stand-ins
"Footage of the ACTUAL phenomenon" is right for a named volcano and wrong for a
pressure wave, an aerosol layer or anything in deep time. For a subject that
cannot be filmed, footage of the right setting, material or scale now scores
7-8 instead of 2.

### A clip may come back once, 150s away
Never reusing a clip is right for a channel covering different subjects each
week. On one volcano, the handful of real clips were claimed by the first shots
and later ones fell to AI. MAX_USES_PER_VIDEO = 2, REUSE_GAP_SECONDS = 150.
Across videos the rule is unchanged: never twice on the channel.

### A dead provider costs seconds, not minutes
402/401/403 - and Google's 400 INVALID_ARGUMENT for a bad key - raise
PermanentError instead of being retried five times with backoff.

### Wikimedia is paced, not hammered
Its anonymous search quota is per unit time: four workers at once drew a 429
five seconds in, and even one a second apart broke after six. Twelve searches
5s apart ran clean. Commons gets one combined video+image search every 5s
across all workers, once per shot, and a shot that would wait more than 20s
skips it rather than stalling the stage.

---

## 17 September 2026 — founding: forked from The Boring Docs

This repo started as a copy of the `yt-boring-docs` pipeline (finance channel).
Everything below is what was changed for an Earth science channel, and why.
Anything not mentioned works exactly as it does there, including the lessons
it paid for, which carry over as code:

- **The planner needs counts, not adjectives** (`*_per_minute` in config,
  `top_up_evidence`, used quotes passed back in).
- **Cuts land 0.12s before the word**, and word times come from ElevenLabs'
  `/with-timestamps`, never a transcript.
- **DeepSeek's read timeout covers the whole generation** (storyboards take
  about 3 minutes).
- **Hold a shot while the narration stays on its subject** (6-12s, cap 15s).

### Tone: story with stakes, not fear
Deep time told as events with consequences (PBS Eons, Kurzgesagt), not the
finance channel's fear-driven investigation. The facts of Earth's history are
extreme enough on their own. So the persona (Ellis Hart, placeholder), the
system rules, hook mechanisms, titles and thumbnails aim at curiosity and scale.
Hard lines: never state a figure more precisely than the sources agree
(deep-time ages and magnitudes are often ranges), never present a hypothesis
as settled, never predict a specific disaster.

### The fact-check applies every flag, including overstated causation
On the finance channel `overstated_causation` was only a warning, because the
checker kept sanding down deliberately dark framing. On a science channel a
dramatic causal leap is a factual error, so it is rewritten like any other
flag. There are two new flag types, `imprecise_deep_time` and `hypothesis_as_fact`.

### Research: canonical sources searched on their own
One extra Exa query per video is limited to `CANONICAL_DOMAINS` (USGS, NASA,
NOAA, Smithsonian GVP, Earle's *Physical Geology* at opentextbc.ca, NPS, BGS,
ESA), so every dossier carries authoritative sources even when the open web
ranks blogs higher. These sources are marked PRIMARY and outrank the rest in
the fact-check. The Earle textbook is not downloaded whole; add that if the
domain search proves too thin.

### Footage: public-domain archives first
`stock.py` searches the NASA Image and Video Library and Wikimedia Commons
before Pexels and Pixabay, and ranks them all on one contact sheet. The
ranking rewards footage of the actual phenomenon over pretty generic scenery.
- Commons keeps only public domain, CC0 and CC BY. **CC BY-SA is rejected**,
  because share-alike could bind the whole video, and NC/ND forbid a monetised edit.
- Much USGS photography (e.g. Hawaiian Volcano Observatory) reaches the
  pipeline through Commons. USGS has no usable media API of its own.
- A chosen photograph is centre-cropped to 1920x1080 and gets a fal depth map
  (~$0.005), then plays as the existing parallax still.
- NASA videos download `~large.mp4` (1080p; a third the size of `~orig`).
- Wikimedia refuses requests without a User-Agent, so every fetch sends one.
- Credits (author, licence, page) are stored per clip and appended to the
  description (`output/description.txt`, also used on upload).

### AI visuals: last resort, $5 cap
AI imagery can show geology that is simply wrong, so it only fills scenes no
camera recorded and shots no library could fill. `visuals.budget_usd` is 5
(was 25). The look bible and QA checks reject fantasy styling and any
recognisable real landmark.

### Voice: a different narrator
ElevenLabs as before, but deliberately not Bren, so the two channels don't
read as one mass-produced operation. `elevenlabs_voice_id` is
`CHOOSE_A_VOICE` until one is picked by ear; narration refuses to run until then.

### Grade: near-natural colour
The finance grade (desaturated, crushed blacks, heavy vignette and grain)
fought nature footage. It is now `saturate(0.95) contrast(1.05) brightness(0.97)`,
with a softer vignette and lighter grain. Tune by eye after the first real video.
