# Setup

Everything runs on your Mac: the pipeline, the render (on the Mac's GPU) and the
studio chat app you drive it from. Budget about an hour, most of it sign-up emails.

1. [Install the toolchain](#1--install-the-toolchain) (~15 min)
2. [Get your API keys](#2--get-your-api-keys) (~30 min)
3. [Connect YouTube](#3--connect-youtube-optional) (~10 min, optional)
4. [Open the studio](#4--open-the-studio)

---

## 1 — Install the toolchain

In **Terminal**:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install node python git ffmpeg
```

Then, in the project folder:

```bash
make setup                 # venv, Python libraries, Remotion (5–10 min)
cp .env.example .env
```

Check it works, for free:

```bash
source venv/bin/activate
make check
python tools/selftest.py
make demo                  # renders remotion/out/demo.mp4 - if it exists, your Mac can build videos
```

---

## 2 — Get your API keys

Open `.env` (`open -e .env`) and paste each key after its `=`, no spaces, no quotes.
`.env` is gitignored, so it never leaves your Mac.

| Key | What it does | Cost | Where |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | Writes the scripts, reads your chat messages | ~$3/mo, top up $10 first | [platform.deepseek.com](https://platform.deepseek.com) |
| `GEMINI_API_KEY` | Vision checks on clips and images, backup writer | ~$1–2/video, prepaid — keep a balance; use the paid tier | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `EXA_API_KEY` | Research sources | Free (20k/mo) | [dashboard.exa.ai](https://dashboard.exa.ai) |
| `TAVILY_API_KEY` | Backup research | Free (1k/mo) | [app.tavily.com](https://app.tavily.com) |
| `PEXELS_API_KEY` | Stock video | Free | [pexels.com/api](https://www.pexels.com/api/) |
| `PIXABAY_API_KEY` | More stock video | Free | [pixabay.com/api/docs](https://pixabay.com/api/docs/) |
| `ELEVENLABS_API_KEY` | The narrator's voice | ~$1.10/video | [elevenlabs.io](https://elevenlabs.io/app/settings/api-keys) |
| `FAL_KEY` | AI visuals and thumbnails | ≤ $5/video, capped by `visuals.budget_usd` | [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys) |
| `YOUTUBE_API_KEY` *(optional)* | Finds outlier videos for topic ideas | Free | Google Cloud Console → enable YouTube Data API v3 → Credentials → API key |

---

## 3 — Connect YouTube (optional)

Needed for **Accept & upload** to upload the video with its title, description,
tags, thumbnail, subtitles and comment filled in. Without it you still get
everything in `output/UPLOAD.md` and upload by hand.

1. Google Cloud Console → new project → **APIs & Services → Library** → enable **YouTube Data API v3**
2. **OAuth consent screen** → External → add yourself as a test user
3. **Credentials → Create credentials → OAuth client ID → Desktop app** → download the JSON as `config/youtube_oauth.json`
4. `python tools/youtube_auth.py` → sign in → paste the three values it prints into `.env` as `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`

Two things to know:
- **Until Google audits your API project, every API upload is locked private.** Accept will upload it and ask for public, and it will stay private; flip it public in YouTube Studio. Request the audit early.
- **The API can post the comment but can't pin it.** Open the comment and tap Pin.

---

## 4 — Open the studio

The chat app lives in its own folder, `../yt-studio`, and drives all your
channels. Deep Earth is listed in its `channels.json`.

```bash
make app            # here, or in ../yt-studio
```

Your browser opens **http://127.0.0.1:8765**; pick **🌋 Deep Earth** in the header.
Keep the Terminal window open; the Mac won't idle-sleep while the studio runs (it
may still sleep if you close the lid on battery). One job runs at a time across
all channels, so another channel's build may queue behind this one.

From there it's all chat:

| You | It |
|---|---|
| **🎬 New video** | proposes ten topics with buttons |
| tap a number | researches and writes the script (~20 min), posts it |
| "make the opening punchier" / paste a script in ``` | rewrites or replaces it |
| **✅ Build it** | narrates, plans shots, fetches footage, renders on the GPU (~20–40 min) |
| watch the video right in the chat | title, description, tags, pinned comment, 3 thumbnails, .srt, UPLOAD.md |
| "change the title to …", "thumbnail b", "redo the footage", "shorter pinned comment" | does it |
| any question — "why this footage?" | answers with the run in view |
| **✅ Accept & upload** | uploads with everything filled in, sets it public, posts the comment |
| **⏹ Stop** / **🔁 Retry** | stops the running job / resumes from the last finished stage |

Background job output goes to `runs/job.log`; the conversation lives in `runs/chat.jsonl`.

### Working on the look

```bash
cd remotion && npx remotion studio --props=../runs/<run-id>/shotlist.json
```

Live preview; edit anything in `remotion/src/components/` and it updates as you type.

---

## When something breaks

Failures are posted in the chat with a **Retry** button. Retrying is always safe: every stage records that it finished, and a re-run skips what's done.

| What you'll see | What it means |
|---|---|
| `Missing DEEPSEEK_API_KEY` | Typo in `.env` |
| `Insufficient balance` | DeepSeek needs a top-up |
| `No usable sources found` | Topic too obscure — start a new video |
| `403` from Pexels | Wrong key, or the hourly limit — the stock stage waits it out |

And the rule from the plan: **three videos made by hand, published and measured** (retention above 35%, click-through above 4%) before you automate more.
