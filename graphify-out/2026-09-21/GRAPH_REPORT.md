# Graph Report - yt-deep-earth  (2026-09-21)

## Corpus Check
- 105 files · ~123,930 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 763 nodes · 1714 edges · 51 communities (48 shown, 3 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 31 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e880b634`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MainVideo.tsx
- storyboard.py
- check_storyboard
- resolve_run
- narrate.py
- captions.py
- Deep Earth — automated video pipeline
- log
- common.py
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
- brain.py
- audio.py
- Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption
- assistant.py
- Run
- chat.py
- Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption
- chat_job.py
- build_cues
- generate
- load_config
- dossier.md
- Stereo Plume Height and Motion Retrievals for the Record-Setting Hunga Tonga-Hunga Ha'apai Eruption of 15 January 2022
- Blueprint: a local chat UI that drives a long-running, GPU-heavy content pipeline
- Upload packet — run `2026-09-18-2239`
- Tonga Eruption Blasted Unprecedented Amount of Water Into Stratosphere
- The unexpected radiative impact of the Hunga Tonga eruption of 15th January 2022
- Suggested Searches
- Abstract

## God Nodes (most connected - your core abstractions)
1. `Run` - 89 edges
2. `log()` - 86 edges
3. `resolve_run()` - 36 edges
4. `load_config()` - 35 edges
5. `secret()` - 29 edges
6. `Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption` - 24 edges
7. `with_retries()` - 23 edges
8. `has_secret()` - 22 edges
9. `chat_json()` - 22 edges
10. `send()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `do_topics()` --calls--> `present_topics()`  [EXTRACTED]
  tools/chat_job.py → pipeline/assistant.py
- `do_pick()` --calls--> `present_script()`  [EXTRACTED]
  tools/chat_job.py → pipeline/assistant.py
- `do_revise()` --calls--> `present_script()`  [EXTRACTED]
  tools/chat_job.py → pipeline/assistant.py
- `do_build()` --calls--> `present_review()`  [EXTRACTED]
  tools/chat_job.py → pipeline/assistant.py
- `do_build()` --calls--> `escape()`  [EXTRACTED]
  tools/chat_job.py → pipeline/chat.py

## Import Cycles
- None detected.

## Communities (51 total, 3 thin omitted)

### Community 0 - "MainVideo.tsx"
Cohesion: 0.07
Nodes (53): Bars3D(), BigNumber(), Camera, ChartStage(), decimalsOf(), formatValue(), Label(), project() (+45 more)

### Community 1 - "storyboard.py"
Cohesion: 0.16
Nodes (20): assemble(), figures_supported(), find_quote(), find_words(), normalise(), STAGE 6 - The storyboard. Plans every shot of the video against the REAL…, Every digit run in `text` must appear in the dossier (commas ignored)., Locate `quote` verbatim (whitespace/case-insensitive) and return (before,… (+12 more)

### Community 2 - "check_storyboard"
Cohesion: 0.18
Nodes (11): fill(), Best clips first, scoring at least MIN_SCORE, until they cover `length`. One…, clean_page_text(), clean_title(), Group whisper's words into sentences, keeping word indices for snapping., Scraped pages arrive with markdown images, links, bare URLs and heading marks -…, The research dossier already holds each source's title, URL and text., sentences_from_words() (+3 more)

### Community 3 - "resolve_run"
Cohesion: 0.18
Nodes (17): new_run_id(), A sortable, human-readable id like '2026-08-30-1432'., Turn a --run argument into a Run object. Accepts an explicit id, the word…, resolve_run(), Deep Earth - automated YouTube pipeline. Each module in this package does…, cmd_build(), cmd_choose(), cmd_stage() (+9 more)

### Community 4 - "narrate.py"
Cohesion: 0.15
Nodes (20): chunk_text(), _gemini_pcm(), generate(), median_pitch(), Path, _qwen_pcm(), STAGE 4 - Narration. Turns script.txt into one narration WAV. Long scripts have…, Speechify streams raw 16-bit PCM directly when asked via output_format. (+12 more)

### Community 5 - "captions.py"
Cohesion: 0.27
Nodes (9): _fits(), _fix_orphans(), STAGE - Subtitles. Turns the word-level timings from the align stage into a…, Deal with a stranded tail like "sea." alone on screen. Working on word lists…, Split a cue across at most two lines, keeping them a similar length. Greedy…, Would this cue text wrap into the two-line box without overflowing? Counting…, The words of a cue, joined back into a line., _text_of() (+1 more)

### Community 6 - "Deep Earth — automated video pipeline"
Cohesion: 0.12
Nodes (15): Cost, Deep Earth — automated video pipeline, Running a stage by hand, The idea that makes it work: planning shots after the narration exists, The loop, What's in here, What you can say, Why there are three gates (+7 more)

### Community 7 - "log"
Cohesion: 0.08
Nodes (49): Lock, log(), Print a timestamped message that flushes immediately. Flushing matters: without…, has_vision(), Whether the configured vision provider has a key to call., ensure_dependencies(), Path, STAGE 10 - Render. Hands the shot list to Remotion, which draws every frame in… (+41 more)

### Community 8 - "common.py"
Cohesion: 0.05
Nodes (75): Exception, audio_duration_seconds(), generate(), Path, STAGE 5 - Word-level timing. Produces a JSON file listing every spoken word…, transcribe_with_whisper(), has_secret(), load_persona() (+67 more)

### Community 9 - "dependencies"
Cohesion: 0.06
Nodes (30): react, react-dom, @react-three/fiber, remotion, @remotion/cli, dependencies, react, react-dom (+22 more)

### Community 10 - "charts3d.py"
Cohesion: 0.24
Nodes (15): astra(), build_for_run(), build_one(), chart_spec(), compile_errors(), contract_errors(), extract_code(), key_for() (+7 more)

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
Cohesion: 0.13
Nodes (22): match_literally(), Catch the handful of messages that have exactly one possible meaning., allocate(), plate_prompt(), The scene behind a text card: the beat's own prompt if it describes a scene,…, Pick which AI shots get motion. Returns (shot ids, estimated USD). Every AI…, check_allocator(), check_button_routing() (+14 more)

### Community 16 - "embed_fonts.py"
Cohesion: 0.50
Nodes (4): main(), Path, Embed the Remotion fonts in the JS bundle as base64, subset to Latin. Why:…, subset_font()

### Community 31 - "publish.py"
Cohesion: 0.12
Nodes (30): apply_metadata(), apply_thumbnail(), build_client(), build_description(), build_packet(), build_snippet(), chosen_thumbnail(), delete_video() (+22 more)

### Community 32 - "brain.py"
Cohesion: 0.29
Nodes (7): ask_model(), extract_fenced_script(), Turning what you typed into something the pipeline can do. You shouldn't have…, Pull a pasted script out of a ``` code block, if there is one. Takes the…, Send the message to DeepSeek and get a structured intent back., Message in, `{"intent", "args", "reply"}` out. Never raises., understand()

### Community 33 - "audio.py"
Cohesion: 0.43
Nodes (6): master(), pick_music(), Path, STAGE 8 - Audio mastering. Two jobs: 1. Duck background music under the…, Choose a music bed, rotating between tracks across videos. Rotation is…, run_ffmpeg()

### Community 34 - "Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption"
Cohesion: 0.06
Nodes (32): Abstract, Abstract, Bulletin Report for March 2022 (BGVN 47:03) Cite this Report, Cathryn N Mitchell, Cathy Clerbaux, Cora E Randall, Corwin J Wright, Digital Commons @ University of South Florida (+24 more)

### Community 35 - "assistant.py"
Cohesion: 0.15
Nodes (26): active_run(), do_cancel(), do_edit_metadata(), do_pick_thumbnail(), do_question(), do_status(), present_script(), present_topics() (+18 more)

### Community 36 - "Run"
Cohesion: 0.08
Nodes (46): die(), Any, Path, Everything about one video-in-progress lives in `runs/<run_id>/`. Why a folder…, Read the run's state file (an empty dict on a brand-new run)., Merge some values into the state file and write it back., Record that a stage finished, so `--resume` can skip it next time., Forget every finished stage except the ones named. Used when something upstream… (+38 more)

### Community 38 - "chat.py"
Cohesion: 0.19
Nodes (17): present_review(), Post the video to watch here, the thumbnails and every upload detail., _append(), edit(), enabled(), history(), Path, Talking to you in the local studio app. Everything the pipeline says to you… (+9 more)

### Community 39 - "Surface-to-space atmospheric waves from Hunga Tonga–Hunga Ha’apai eruption"
Cohesion: 0.11
Nodes (18): Abstract, Cathryn N Mitchell, Cathy Clerbaux, Cora E Randall, Corwin J Wright, Fred Prata, Jia Yue, Justin Carstens (+10 more)

### Community 40 - "chat_job.py"
Cohesion: 0.17
Nodes (15): log_path(), Where the studio sends background jobs' output, for error messages., progress(), A one-line 'still working' note. Called between build stages., dispatch(), do_build(), do_pick(), do_revise() (+7 more)

### Community 41 - "build_cues"
Cohesion: 0.22
Nodes (10): build_cues(), generate(), Group timed words into subtitle cues. Each word is `{"word": ..., "start": ...,…, Render cues as SubRip (.srt) text., Write output/subtitles.srt from words.json., Seconds -> the `HH:MM:SS,mmm` format SRT requires., _timestamp(), to_srt() (+2 more)

### Community 42 - "generate"
Cohesion: 0.29
Nodes (7): cover_figures(), generate(), place_missing_charts(), One extra call for charts the chunked passes left unplaced - or placed before…, One extra call for the receipts the chunked passes didn't plan. Asked for…, Give every spoken statistic a visual, where one isn't planned already. The…, top_up_evidence()

### Community 43 - "load_config"
Cohesion: 0.22
Nodes (12): load_brand(), load_config(), Read config/channel.json - the settings for the whole pipeline., Read config/brand.json - colours and fonts., build(), STAGE 9 - The shot list. The join between planning and rendering. The…, One planned stock shot as consecutive clips. Clips that together fall short of…, stock_clips() (+4 more)

### Community 44 - "dossier.md"
Cohesion: 0.18
Nodes (10): A volcanic eruption sent enough water vapor into the stratosphere to cause a rapid change in chemistry, As big as it gets: Hunga volcano comparable to Krakatoa, PERMALINK, References, RESEARCH DOSSIER, SOURCE 1 [PRIMARY SOURCE], SOURCE 4 [PRIMARY SOURCE], SOURCE 5 [PRIMARY SOURCE] (+2 more)

### Community 45 - "Stereo Plume Height and Motion Retrievals for the Record-Setting Hunga Tonga-Hunga Ha'apai Eruption of 15 January 2022"
Cohesion: 0.20
Nodes (10): Abstract, Eruptive column and water phase transition, Introduction, Key Points, Plain Language Summary, Results, SOURCE 10 [PRIMARY SOURCE], SOURCE 9 [PRIMARY SOURCE] (+2 more)

### Community 46 - "Blueprint: a local chat UI that drives a long-running, GPU-heavy content pipeline"
Cohesion: 0.22
Nodes (8): Blueprint: a local chat UI that drives a long-running, GPU-heavy content pipeline, Components (keep it to these five), Every run must output, Reference implementation, Rules that save pain, The gates, Upload (YouTube Data API v3, OAuth refresh token), Why local, not cloud

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

- **Why does `Run` connect `Run` to `brain.py`, `audio.py`, `storyboard.py`, `assistant.py`, `resolve_run`, `captions.py`, `chat.py`, `narrate.py`, `common.py`, `build_cues`, `charts3d.py`, `log`, `load_config`, `generate`, `check_storyboard`, `selftest.py`, `publish.py`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Why does `log()` connect `log` to `brain.py`, `audio.py`, `storyboard.py`, `assistant.py`, `narrate.py`, `captions.py`, `chat.py`, `resolve_run`, `common.py`, `build_cues`, `charts3d.py`, `load_config`, `generate`, `Run`, `chat_job.py`, `publish.py`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `resolve_run()` connect `resolve_run` to `brain.py`, `audio.py`, `storyboard.py`, `assistant.py`, `Run`, `captions.py`, `narrate.py`, `log`, `common.py`, `chat_job.py`, `charts3d.py`, `load_config`, `publish.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _151 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MainVideo.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.07136404697380307 - nodes in this community are weakly interconnected._
- **Should `Deep Earth — automated video pipeline` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._
- **Should `log` be split into smaller, more focused modules?**
  _Cohesion score 0.07529411764705882 - nodes in this community are weakly interconnected._