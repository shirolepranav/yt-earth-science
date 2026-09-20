# Graph Report - yt-deep-earth  (2026-09-19)

## Corpus Check
- 81 files · ~53,134 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 552 nodes · 1285 edges · 35 communities (32 shown, 3 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7a03ca60`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MainVideo.tsx
- storyboard.py
- chat_json
- Run
- narrate.py
- visuals.py
- Running it on your Mac
- log
- llm.py
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
- common.py
- research.py
- thumbnail.py
- search_commons

## God Nodes (most connected - your core abstractions)
1. `log()` - 68 edges
2. `Run` - 63 edges
3. `load_config()` - 32 edges
4. `secret()` - 29 edges
5. `resolve_run()` - 26 edges
6. `with_retries()` - 23 edges
7. `has_secret()` - 22 edges
8. `chat_json()` - 19 edges
9. `formatValue()` - 16 edges
10. `project()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `check_allocator()` --calls--> `load_config()`  [EXTRACTED]
  tools/selftest.py → pipeline/common.py
- `check_storyboard()` --calls--> `load_config()`  [EXTRACTED]
  tools/selftest.py → pipeline/common.py
- `check_reuse_and_permanent_errors()` --calls--> `permanent_if_hopeless()`  [EXTRACTED]
  tools/selftest.py → pipeline/common.py
- `check_reuse_and_permanent_errors()` --calls--> `with_retries()`  [EXTRACTED]
  tools/selftest.py → pipeline/common.py
- `check_cache()` --references--> `Run`  [EXTRACTED]
  tools/selftest.py → pipeline/common.py

## Import Cycles
- None detected.

## Communities (35 total, 3 thin omitted)

### Community 0 - "MainVideo.tsx"
Cohesion: 0.07
Nodes (54): Bars3D(), BigNumber(), Camera, ChartStage(), decimalsOf(), formatValue(), Label(), project() (+46 more)

### Community 1 - "storyboard.py"
Cohesion: 0.05
Nodes (69): chart_spec(), load_brand(), Read config/brand.json - colours and fonts., build(), STAGE 9 - The shot list. The join between planning and rendering. The…, One planned stock shot as consecutive clips. Clips that together fall short of…, stock_clips(), to_shot() (+61 more)

### Community 2 - "chat_json"
Cohesion: 0.12
Nodes (23): load_persona(), Read config/persona.md - pasted into every script-writing prompt., chat(), chat_json(), Send a prompt to the writing model and return its text reply. Args: system: the…, Same as chat(), but parses the reply as JSON and hands back Python data. Models…, _elevenlabs_pcm(), ElevenLabs returns raw PCM when asked, plus the exact time of every character… (+15 more)

### Community 3 - "Run"
Cohesion: 0.07
Nodes (41): audio_duration_seconds(), generate(), Path, STAGE 5 - Word-level timing. Produces a JSON file listing every spoken word…, transcribe_with_whisper(), master(), pick_music(), Path (+33 more)

### Community 4 - "narrate.py"
Cohesion: 0.15
Nodes (20): chunk_text(), _gemini_pcm(), generate(), median_pitch(), Path, _qwen_pcm(), STAGE 4 - Narration. Turns script.txt into one narration WAV. Long scripts have…, Speechify streams raw 16-bit PCM directly when asked via output_format. (+12 more)

### Community 5 - "visuals.py"
Cohesion: 0.18
Nodes (25): data_uri(), download(), fal_run(), generate_image(), _headers(), image_args(), Path, fal.ai - one pay-per-use key (FAL_KEY) for every image, video and depth model.… (+17 more)

### Community 6 - "Running it on your Mac"
Cohesion: 0.05
Nodes (35): 1. Install the toolchain, 2. Get the code, 3. Install the project, 4. Add your keys, 5. Check it works, Faster renders, If you'd rather not use GitHub Actions at all, Making a video locally (+27 more)

### Community 7 - "log"
Cohesion: 0.12
Nodes (34): Lock, log(), Run `fn`, retrying on failure with an increasing wait between tries. The wait…, Print a timestamped message that flushes immediately. Flushing matters: without…, Fetch an API key from the environment. Args: name: the environment variable…, secret(), with_retries(), search_tavily() (+26 more)

### Community 8 - "llm.py"
Cohesion: 0.16
Nodes (20): Exception, permanent_if_hopeless(), PermanentError, A failure no amount of retrying will fix - an empty balance, a bad key. Raised…, Re-raise as PermanentError when the response says retrying is pointless., _deepseek_chat(), _gemini_chat(), _openai_vision() (+12 more)

### Community 9 - "dependencies"
Cohesion: 0.06
Nodes (30): react, react-dom, @react-three/fiber, remotion, @remotion/cli, dependencies, react, react-dom (+22 more)

### Community 10 - "charts3d.py"
Cohesion: 0.15
Nodes (22): astra(), build_for_run(), build_one(), compile_errors(), contract_errors(), extract_code(), key_for(), number_errors() (+14 more)

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

### Community 31 - "common.py"
Cohesion: 0.15
Nodes (18): has_secret(), load_config(), Shared plumbing used by every other module. Nothing in here is specific to…, True if a key is set. Used to decide whether an optional step can run., Read config/channel.json - the settings for the whole pipeline., has_vision(), Whether the configured vision provider has a key to call., build_client() (+10 more)

### Community 32 - "research.py"
Cohesion: 0.31
Nodes (9): build_queries(), fetch_clean_text(), generate(), is_blocked(), is_primary(), STAGE 2 - Research chain. Turns an approved topic into a dossier of real,…, Download a page and strip the navigation, ads and cookie banners. trafilatura…, Turn one topic into several searches that hit different angles. One search… (+1 more)

### Community 33 - "thumbnail.py"
Cohesion: 0.38
Nodes (9): compose(), draw_symbol(), draw_text(), generate(), Image, STAGE 11 - Thumbnails. Thumbnail and title decide whether anyone ever sees the…, Big block capitals in the left ~45%, top-aligned. Returns the text box., score() (+1 more)

### Community 34 - "search_commons"
Cohesion: 0.25
Nodes (8): _commons_turn(), _credit(), license_ok(), Public domain, CC0 and CC BY only. Share-alike could bind the whole video to…, The uploader's name, stripped of Commons' markup. Some files carry no artist at…, Take the next Commons search slot, or give up if the queue is too long., Wikimedia Commons, keeping only files whose licence allows this use (see…, search_commons()

## Knowledge Gaps
- **79 isolated node(s):** `name`, `version`, `private`, `description`, `dev` (+74 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `log()` connect `log` to `research.py`, `storyboard.py`, `chat_json`, `Run`, `narrate.py`, `search_commons`, `thumbnail.py`, `visuals.py`, `llm.py`, `charts3d.py`, `common.py`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `Run` connect `Run` to `research.py`, `storyboard.py`, `chat_json`, `thumbnail.py`, `narrate.py`, `visuals.py`, `log`, `charts3d.py`, `common.py`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `secret()` connect `log` to `research.py`, `chat_json`, `Run`, `narrate.py`, `visuals.py`, `llm.py`, `charts3d.py`, `common.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _79 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MainVideo.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.06964443138407288 - nodes in this community are weakly interconnected._
- **Should `storyboard.py` be split into smaller, more focused modules?**
  _Cohesion score 0.051251956181533644 - nodes in this community are weakly interconnected._
- **Should `chat_json` be split into smaller, more focused modules?**
  _Cohesion score 0.11594202898550725 - nodes in this community are weakly interconnected._