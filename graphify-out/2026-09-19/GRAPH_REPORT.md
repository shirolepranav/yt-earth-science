# Graph Report - yt-deep-earth  (2026-09-17)

## Corpus Check
- 76 files · ~46,022 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 512 nodes · 1130 edges · 31 communities (28 shown, 3 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 11 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `85059d87`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MainVideo.tsx
- Run
- llm.py
- common.py
- secret
- visuals.py
- Running it on your Mac
- log
- storyboard.py
- dependencies
- charts3d.py
- compilerOptions
- 17 September 2026 — founding: forked from The Boring Docs
- Channel Host Persona
- make_demo.py
- apply_edit.py
- embed_fonts.py
- youtube_auth.py
- CLAUDE.md
- assets.d.ts

## God Nodes (most connected - your core abstractions)
1. `log()` - 67 edges
2. `Run` - 63 edges
3. `load_config()` - 30 edges
4. `secret()` - 28 edges
5. `resolve_run()` - 26 edges
6. `has_secret()` - 21 edges
7. `with_retries()` - 20 edges
8. `chat_json()` - 19 edges
9. `build_one()` - 14 edges
10. `generate()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `check_deepseek_timeout()` --calls--> `_deepseek_chat()`  [EXTRACTED]
  tools/selftest.py → pipeline/llm.py
- `check_rate_limit()` --calls--> `library_get()`  [EXTRACTED]
  tools/selftest.py → pipeline/stock.py
- `check_open_libraries()` --calls--> `media_seconds()`  [EXTRACTED]
  tools/selftest.py → pipeline/stock.py
- `check_open_libraries()` --calls--> `license_ok()`  [EXTRACTED]
  tools/selftest.py → pipeline/stock.py
- `check_storyboard()` --calls--> `sources_from_dossier()`  [EXTRACTED]
  tools/selftest.py → pipeline/storyboard.py

## Import Cycles
- None detected.

## Communities (31 total, 3 thin omitted)

### Community 0 - "MainVideo.tsx"
Cohesion: 0.08
Nodes (38): Bars3D(), BigNumber(), Camera, ChartStage(), decimalsOf(), formatValue(), Label(), project() (+30 more)

### Community 1 - "Run"
Cohesion: 0.07
Nodes (45): build_for_run(), chart_spec(), die(), load_brand(), load_config(), Any, Path, Everything about one video-in-progress lives in `runs/<run_id>/`. Why a folder… (+37 more)

### Community 2 - "llm.py"
Cohesion: 0.08
Nodes (41): load_persona(), load_prompt(), Read config/persona.md - pasted into every script-writing prompt., Read a prompt template from the prompts/ folder. Prompts live in their own…, chat(), chat_json(), _deepseek_chat(), _gemini_chat() (+33 more)

### Community 3 - "common.py"
Cohesion: 0.08
Nodes (37): audio_duration_seconds(), generate(), Path, STAGE 5 - Word-level timing. Produces a JSON file listing every spoken word…, transcribe_with_whisper(), master(), pick_music(), Path (+29 more)

### Community 4 - "secret"
Cohesion: 0.09
Nodes (37): Run `fn`, retrying on failure with an increasing wait between tries. The wait…, Fetch an API key from the environment. Args: name: the environment variable…, secret(), with_retries(), chunk_text(), _elevenlabs_pcm(), _gemini_pcm(), generate() (+29 more)

### Community 5 - "visuals.py"
Cohesion: 0.12
Nodes (36): data_uri(), download(), fal_run(), generate_image(), _headers(), image_args(), Path, fal.ai - one pay-per-use key (FAL_KEY) for every image, video and depth model.… (+28 more)

### Community 6 - "Running it on your Mac"
Cohesion: 0.05
Nodes (35): 1. Install the toolchain, 2. Get the code, 3. Install the project, 4. Add your keys, 5. Check it works, Faster renders, If you'd rather not use GitHub Actions at all, Making a video locally (+27 more)

### Community 7 - "log"
Cohesion: 0.11
Nodes (35): Lock, log(), Print a timestamped message that flushes immediately. Flushing matters: without…, build_for_run(), contact_sheet(), download(), fetch_for_shot(), fresh_queries() (+27 more)

### Community 8 - "storyboard.py"
Cohesion: 0.09
Nodes (31): assemble(), clean_page_text(), clean_title(), cover_figures(), figures_supported(), find_quote(), find_words(), normalise() (+23 more)

### Community 9 - "dependencies"
Cohesion: 0.06
Nodes (30): react, react-dom, @react-three/fiber, remotion, @remotion/cli, dependencies, react, react-dom (+22 more)

### Community 10 - "charts3d.py"
Cohesion: 0.17
Nodes (19): astra(), build_one(), compile_errors(), contract_errors(), extract_code(), key_for(), number_errors(), Path (+11 more)

### Community 11 - "compilerOptions"
Cohesion: 0.12
Nodes (16): DOM, DOM.Iterable, ES2020, src, compilerOptions, esModuleInterop, jsx, lib (+8 more)

### Community 12 - "17 September 2026 — founding: forked from The Boring Docs"
Cohesion: 0.20
Nodes (9): 17 September 2026 — founding: forked from The Boring Docs, AI visuals: last resort, $5 cap, Decisions, Footage: public-domain archives first, Grade: near-natural colour, Research: canonical sources searched on their own, The fact-check applies every flag, including overstated causation, Tone: story with stakes, not fear (+1 more)

### Community 13 - "Channel Host Persona"
Cohesion: 0.25
Nodes (7): Channel Host Persona, Making it land, Perspective, Verbal tics (what makes Ellis sound like Ellis, script after script), Voice, What Ellis refuses to do, Who Ellis is

### Community 14 - "make_demo.py"
Cohesion: 0.32
Nodes (7): main(), make_scene(), make_silence(), Image, Path, Build the assets the Remotion demo needs, without calling any paid API. Run…, A dark scene with a lit ground plane and an orange glow, plus a matching depth…

### Community 15 - "apply_edit.py"
Cohesion: 0.50
Nodes (4): extract_script(), main(), Replace a run's script with an edited version pasted into a GitHub comment.…, Find the longest fenced code block in the comment.

### Community 16 - "embed_fonts.py"
Cohesion: 0.50
Nodes (4): main(), Path, Embed the Remotion fonts in the JS bundle as base64, subset to Latin. Why:…, subset_font()

## Knowledge Gaps
- **78 isolated node(s):** `name`, `version`, `private`, `description`, `dev` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Run` connect `Run` to `llm.py`, `common.py`, `secret`, `visuals.py`, `log`, `storyboard.py`, `charts3d.py`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `log()` connect `log` to `Run`, `llm.py`, `common.py`, `secret`, `visuals.py`, `storyboard.py`, `charts3d.py`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `secret()` connect `secret` to `Run`, `llm.py`, `common.py`, `visuals.py`, `log`, `charts3d.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _78 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MainVideo.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.08192090395480225 - nodes in this community are weakly interconnected._
- **Should `Run` be split into smaller, more focused modules?**
  _Cohesion score 0.07199032062915911 - nodes in this community are weakly interconnected._
- **Should `llm.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07822410147991543 - nodes in this community are weakly interconnected._