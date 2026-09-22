# Graph Report - yt-deep-earth  (2026-09-21)

## Corpus Check
- 106 files · ~125,686 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 784 nodes · 1761 edges · 53 communities (50 shown, 3 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6192b934`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MainVideo.tsx
- storyboard.py
- load_config
- resolve_run
- narrate.py
- visuals.py
- Deep Earth — automated video pipeline
- stock.py
- llm.py
- dependencies
- charts3d.py
- compilerOptions
- 17 September 2026 — founding: forked from The Boring Docs
- Channel Host Persona
- make_demo.py
- selftest.py
- embed_fonts.py
- youtube_auth.py
- CLAUDE.md
- assets.d.ts
- publish.py
- secret
- thumbnail.py
- Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption
- assistant.py
- Run
- app.py
- chat.py
- Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption
- chat_job.py
- log
- generate
- shotlist.py
- dossier.md
- Stereo Plume Height and Motion Retrievals for the Record-Setting Hunga Tonga-Hunga Ha'apai Eruption of 15 January 2022
- Blueprint: a local chat UI that drives a long-running, GPU-heavy content pipeline
- with_retries
- Upload packet — run `2026-09-18-2239`
- Tonga Eruption Blasted Unprecedented Amount of Water Into Stratosphere
- The unexpected radiative impact of the Hunga Tonga eruption of 15th January 2022
- Suggested Searches
- Abstract

## God Nodes (most connected - your core abstractions)
1. `Run` - 90 edges
2. `log()` - 88 edges
3. `resolve_run()` - 36 edges
4. `load_config()` - 35 edges
5. `secret()` - 29 edges
6. `Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption` - 24 edges
7. `with_retries()` - 23 edges
8. `send()` - 22 edges
9. `has_secret()` - 22 edges
10. `chat_json()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `read_backlog()` --indirect_call--> `handle()`  [INFERRED]
  pipeline/topics.py → app.py
- `start_job()` --calls--> `escape()`  [EXTRACTED]
  app.py → pipeline/chat.py
- `start_job()` --calls--> `send()`  [EXTRACTED]
  app.py → pipeline/chat.py
- `handle()` --calls--> `route()`  [EXTRACTED]
  app.py → pipeline/assistant.py
- `handle()` --calls--> `_append()`  [EXTRACTED]
  app.py → pipeline/chat.py

## Import Cycles
- None detected.

## Communities (53 total, 3 thin omitted)

### Community 0 - "MainVideo.tsx"
Cohesion: 0.07
Nodes (53): Bars3D(), BigNumber(), Camera, ChartStage(), decimalsOf(), formatValue(), Label(), project() (+45 more)

### Community 1 - "storyboard.py"
Cohesion: 0.16
Nodes (20): assemble(), figures_supported(), find_quote(), find_words(), normalise(), STAGE 6 - The storyboard. Plans every shot of the video against the REAL…, Every digit run in `text` must appear in the dossier (commas ignored)., Locate `quote` verbatim (whitespace/case-insensitive) and return (before,… (+12 more)

### Community 2 - "load_config"
Cohesion: 0.16
Nodes (20): load_config(), load_persona(), load_prompt(), Read config/channel.json - the settings for the whole pipeline., Read config/persona.md - pasted into every script-writing prompt., Read a prompt template from the prompts/ folder. Prompts live in their own…, chat_json(), Same as chat(), but parses the reply as JSON and hands back Python data. Models… (+12 more)

### Community 3 - "resolve_run"
Cohesion: 0.07
Nodes (41): audio_duration_seconds(), generate(), Path, STAGE 5 - Word-level timing. Produces a JSON file listing every spoken word…, transcribe_with_whisper(), master(), pick_music(), Path (+33 more)

### Community 4 - "narrate.py"
Cohesion: 0.15
Nodes (20): chunk_text(), _gemini_pcm(), generate(), median_pitch(), Path, _qwen_pcm(), STAGE 4 - Narration. Turns script.txt into one narration WAV. Long scripts have…, Speechify streams raw 16-bit PCM directly when asked via output_format. (+12 more)

### Community 5 - "visuals.py"
Cohesion: 0.22
Nodes (21): has_secret(), True if a key is set. Used to decide whether an optional step can run., data_uri(), download(), Path, Local file as a data URI - fal accepts these anywhere it takes a URL., allocate(), build_for_run() (+13 more)

### Community 6 - "Deep Earth — automated video pipeline"
Cohesion: 0.12
Nodes (15): Cost, Deep Earth — automated video pipeline, Running a stage by hand, The idea that makes it work: planning shots after the narration exists, The loop, What's in here, What you can say, Why there are three gates (+7 more)

### Community 7 - "stock.py"
Cohesion: 0.09
Nodes (39): Lock, build_for_run(), _commons_turn(), contact_sheet(), _credit(), download(), fetch_for_shot(), fresh_queries() (+31 more)

### Community 8 - "llm.py"
Cohesion: 0.14
Nodes (23): Exception, permanent_if_hopeless(), PermanentError, A failure no amount of retrying will fix - an empty balance, a bad key. Raised…, Re-raise as PermanentError when the response says retrying is pointless., chat(), _deepseek_chat(), _gemini_chat() (+15 more)

### Community 9 - "dependencies"
Cohesion: 0.06
Nodes (30): react, react-dom, @react-three/fiber, remotion, @remotion/cli, dependencies, react, react-dom (+22 more)

### Community 10 - "charts3d.py"
Cohesion: 0.22
Nodes (16): astra(), build_for_run(), build_one(), compile_errors(), contract_errors(), extract_code(), key_for(), number_errors() (+8 more)

### Community 11 - "compilerOptions"
Cohesion: 0.12
Nodes (16): DOM, DOM.Iterable, ES2020, src, compilerOptions, esModuleInterop, jsx, lib (+8 more)

### Community 12 - "17 September 2026 — founding: forked from The Boring Docs"
Cohesion: 0.12
Nodes (15): 17 September 2026 — founding: forked from The Boring Docs, 19 September 2026 — what the first real build taught us, A clip may come back once, 150s away, A dead provider costs seconds, not minutes, AI visuals: last resort, $5 cap, Decisions, Footage: public-domain archives first, Grade: near-natural colour (+7 more)

### Community 13 - "Channel Host Persona"
Cohesion: 0.25
Nodes (7): Channel Host Persona, Making it land, Perspective, Verbal tics (what makes Ellis sound like Ellis, script after script), Voice, What Ellis refuses to do, Who Ellis is

### Community 14 - "make_demo.py"
Cohesion: 0.32
Nodes (7): main(), make_scene(), make_silence(), Image, Path, Build the assets the Remotion demo needs, without calling any paid API. Run…, A dark scene with a lit ground plane and an orange glow, plus a matching depth…

### Community 15 - "selftest.py"
Cohesion: 0.06
Nodes (50): ask_model(), extract_fenced_script(), match_literally(), Turning what you typed into something the pipeline can do. You shouldn't have…, Pull a pasted script out of a ``` code block, if there is one. Takes the…, Send the message to DeepSeek and get a structured intent back., Message in, `{"intent", "args", "reply"}` out. Never raises., Catch the handful of messages that have exactly one possible meaning. (+42 more)

### Community 16 - "embed_fonts.py"
Cohesion: 0.50
Nodes (4): main(), Path, Embed the Remotion fonts in the JS bundle as base64, subset to Latin. Why:…, subset_font()

### Community 31 - "publish.py"
Cohesion: 0.15
Nodes (26): apply_metadata(), apply_thumbnail(), build_client(), build_description(), build_packet(), build_snippet(), chosen_thumbnail(), delete_video() (+18 more)

### Community 32 - "secret"
Cohesion: 0.21
Nodes (14): Fetch an API key from the environment. Args: name: the environment variable…, secret(), _elevenlabs_pcm(), ElevenLabs returns raw PCM when asked, plus the exact time of every character…, build_queries(), fetch_clean_text(), generate(), is_blocked() (+6 more)

### Community 33 - "thumbnail.py"
Cohesion: 0.30
Nodes (11): generate_image(), Generate one image, cover-crop it to exactly width x height, save as JPEG., compose(), draw_symbol(), draw_text(), generate(), Image, STAGE 11 - Thumbnails. Thumbnail and title decide whether anyone ever sees the… (+3 more)

### Community 34 - "Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption"
Cohesion: 0.06
Nodes (32): Abstract, Abstract, Bulletin Report for March 2022 (BGVN 47:03) Cite this Report, Cathryn N Mitchell, Cathy Clerbaux, Cora E Randall, Corwin J Wright, Digital Commons @ University of South Florida (+24 more)

### Community 35 - "assistant.py"
Cohesion: 0.13
Nodes (28): active_run(), do_cancel(), do_edit_metadata(), do_pick_thumbnail(), do_question(), do_status(), present_script(), present_topics() (+20 more)

### Community 36 - "Run"
Cohesion: 0.15
Nodes (12): die(), Any, Path, Everything about one video-in-progress lives in `runs/<run_id>/`. Why a folder…, Read the run's state file (an empty dict on a brand-new run)., Merge some values into the state file and write it back., Record that a stage finished, so `--resume` can skip it next time., Forget every finished stage except the ones named. Used when something upstream… (+4 more)

### Community 37 - "app.py"
Cohesion: 0.15
Nodes (14): handle(), Handler, main(), Path, Deep Earth studio - the local chat app that drives the whole pipeline. make app…, Only this page, on this Mac. Blocks DNS rebinding and cross-site POSTs., Send a file, honouring Range - browsers need it to play and seek a video., Forget the job when it exits. Failures report themselves via chat.failed. (+6 more)

### Community 38 - "chat.py"
Cohesion: 0.19
Nodes (17): present_review(), Post the video to watch here, the thumbnails and every upload detail., _append(), edit(), enabled(), history(), Path, Talking to you in the local studio app. Everything the pipeline says to you… (+9 more)

### Community 39 - "Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption"
Cohesion: 0.11
Nodes (18): Abstract, Cathryn N Mitchell, Cathy Clerbaux, Cora E Randall, Corwin J Wright, Fred Prata, Jia Yue, Justin Carstens (+10 more)

### Community 40 - "chat_job.py"
Cohesion: 0.17
Nodes (15): log_path(), Where app.py sends background jobs' output, for error messages., dispatch(), do_build(), do_pick(), do_publish(), do_revise(), do_topics() (+7 more)

### Community 41 - "log"
Cohesion: 0.24
Nodes (11): generate(), Write output/subtitles.srt from words.json., log(), Shared plumbing used by every other module. Nothing in here is specific to…, Print a timestamped message that flushes immediately. Flushing matters: without…, ensure_dependencies(), Path, STAGE 10 - Render. Hands the shot list to Remotion, which draws every frame in… (+3 more)

### Community 42 - "generate"
Cohesion: 0.17
Nodes (12): clean_page_text(), clean_title(), cover_figures(), generate(), place_missing_charts(), Scraped pages arrive with markdown images, links, bare URLs and heading marks -…, The research dossier already holds each source's title, URL and text., One extra call for charts the chunked passes left unplaced - or placed before… (+4 more)

### Community 43 - "shotlist.py"
Cohesion: 0.27
Nodes (10): chart_spec(), load_brand(), Read config/brand.json - colours and fonts., build(), STAGE 9 - The shot list. The join between planning and rendering. The…, One planned stock shot as consecutive clips. Clips that together fall short of…, stock_clips(), to_shot() (+2 more)

### Community 44 - "dossier.md"
Cohesion: 0.18
Nodes (10): A volcanic eruption sent enough water vapor into the stratosphere to cause a rapid change in chemistry, As big as it gets: Hunga volcano comparable to Krakatoa, PERMALINK, References, RESEARCH DOSSIER, SOURCE 1 [PRIMARY SOURCE], SOURCE 4 [PRIMARY SOURCE], SOURCE 5 [PRIMARY SOURCE] (+2 more)

### Community 45 - "Stereo Plume Height and Motion Retrievals for the Record-Setting Hunga Tonga-Hunga Ha'apai Eruption of 15 January 2022"
Cohesion: 0.20
Nodes (10): Abstract, Eruptive column and water phase transition, Introduction, Key Points, Plain Language Summary, Results, SOURCE 10 [PRIMARY SOURCE], SOURCE 9 [PRIMARY SOURCE] (+2 more)

### Community 46 - "Blueprint: a local chat UI that drives a long-running, GPU-heavy content pipeline"
Cohesion: 0.22
Nodes (8): Blueprint: a local chat UI that drives a long-running, GPU-heavy content pipeline, Components (keep it to these five), Every run must output, Reference implementation, Rules that save pain, The gates, Upload (YouTube Data API v3, OAuth refresh token), Why local, not cloud

### Community 47 - "with_retries"
Cohesion: 0.28
Nodes (8): Run `fn`, retrying on failure with an increasing wait between tries. The wait…, with_retries(), fal_run(), _headers(), image_args(), fal.ai - one pay-per-use key (FAL_KEY) for every image, video and depth model.…, Run one model call to completion and return its output JSON., Each image family names its size parameters differently.

### Community 48 - "Upload packet — run `2026-09-18-2239`"
Cohesion: 0.22
Nodes (8): Before you publish, Description, Pinned comment, Subtitles, Tags, Thumbnails, Title, Upload packet — run `2026-09-18-2239`

### Community 49 - "Tonga Eruption Blasted Unprecedented Amount of Water Into Stratosphere"
Cohesion: 0.29
Nodes (7): Richard W. Henley a,*, Cornel E.J. de Ronde b, Richard J. Arculus c, Graham Hughes d, Thanh Son Pham c, Ana S. Casas c, Vasily Titov e, Sharon L. Walker e, SOURCE 6 [PRIMARY SOURCE], SOURCE 7 [PRIMARY SOURCE], SOURCE 8 [PRIMARY SOURCE], Suggested Searches, The 15 January 2022 Hunga (Tonga) eruption: A gas-driven climactic explosion, Tonga Eruption Blasted Unprecedented Amount of Water Into Stratosphere

### Community 50 - "The unexpected radiative impact of the Hunga Tonga eruption of 15th January 2022"
Cohesion: 0.40
Nodes (5): Abstract, Initial dispersion, evolution and optical properties of the HT aerosol plume, Introduction, SOURCE 11 [PRIMARY SOURCE], The unexpected radiative impact of the Hunga Tonga eruption of 15th January 2022

### Community 51 - "Suggested Searches"
Cohesion: 0.40
Nodes (5): Highlights, How 2 US, European Satellites Are Studying Hurricanes During El Niño, NASA Boosts Open Science, Data Sharing with Artemis Accords, NASA’s Chandra Unveils Mysterious X-Ray Objects, Suggested Searches

### Community 52 - "Abstract"
Cohesion: 0.50
Nodes (4): Abstract, Perturbations in stratospheric aerosol evolution due to the water-rich plume of the 2022 Hunga-Tonga eruption, Strong persistent cooling of the stratosphere after the Hunga eruption, Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption

## Knowledge Gaps
- **151 isolated node(s):** `name`, `version`, `private`, `description`, `dev` (+146 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log()` connect `log` to `storyboard.py`, `load_config`, `resolve_run`, `narrate.py`, `visuals.py`, `stock.py`, `llm.py`, `charts3d.py`, `selftest.py`, `publish.py`, `secret`, `thumbnail.py`, `assistant.py`, `Run`, `app.py`, `chat.py`, `chat_job.py`, `generate`, `shotlist.py`, `with_retries`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Why does `Run` connect `Run` to `secret`, `storyboard.py`, `load_config`, `assistant.py`, `resolve_run`, `narrate.py`, `chat.py`, `stock.py`, `thumbnail.py`, `log`, `charts3d.py`, `shotlist.py`, `generate`, `visuals.py`, `selftest.py`, `publish.py`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `resolve_run()` connect `resolve_run` to `secret`, `storyboard.py`, `load_config`, `assistant.py`, `Run`, `narrate.py`, `thumbnail.py`, `stock.py`, `visuals.py`, `log`, `charts3d.py`, `shotlist.py`, `chat_job.py`, `selftest.py`, `publish.py`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _151 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MainVideo.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.07136404697380307 - nodes in this community are weakly interconnected._
- **Should `resolve_run` be split into smaller, more focused modules?**
  _Cohesion score 0.06938020351526364 - nodes in this community are weakly interconnected._
- **Should `Deep Earth — automated video pipeline` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._