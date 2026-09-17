# Running it on your Mac

The same pipeline, same code, run by hand instead of by GitHub.

**Which one should you use?** Both, for different things.

| | GitHub Actions | Your Mac |
|---|---|---|
| Weekly production runs | ✅ nothing to switch on | needs the Mac awake |
| Changing prompts and seeing the result | slow — 20 min per attempt | ✅ seconds |
| Building a new video component | painful | ✅ Remotion Studio, live preview |
| Rendering speed | ~45–90 min | ✅ ~15–25 min on an M2 Pro |
| Costs you anything | no | no |

The sensible split: **Actions runs your weekly videos, the Mac is where you improve the thing.** They share the repository, so changes you make locally take effect on the next scheduled run as soon as you push them.

**Video quality is identical either way.** The narration comes from a hosted API, the caption timing uses the same model, and Remotion renders deterministically — the same shot list produces the same frames on both machines. Only the speed differs.

---

## One-time setup

### 1. Install the toolchain

Open **Terminal** (⌘+Space, type "Terminal") and run these one at a time. Wait for each to finish.

```bash
# Homebrew — the package manager everything else installs through.
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# The four tools the pipeline needs.
brew install node python git ffmpeg

# Check them. Every line should print a version number.
node --version && python3 --version && git --version && ffmpeg -version | head -1
```

If `brew` isn't found after the first command, Homebrew prints two lines at the end telling you to run something — run those, then continue.

### 2. Get the code

```bash
cd ~
git clone https://github.com/<your-username>/<your-repo>.git yt-pipeline
cd yt-pipeline
```

### 3. Install the project

```bash
make setup
```

This creates an isolated Python environment (so this project can't break anything else on your Mac), installs the Python libraries, and installs Remotion. It takes five to ten minutes, mostly Remotion.

### 4. Add your keys

```bash
cp .env.example .env
open -e .env          # opens it in TextEdit
```

Paste each key after its `=`, with no spaces and no quotes:

```
DEEPSEEK_API_KEY=sk-abc123...
```

Save and close. `.env` is in `.gitignore`, so it can never be pushed to GitHub by accident. That one line of config is the most important security feature in the repo.

### 5. Check it works

```bash
source venv/bin/activate     # do this in every new Terminal window
make check                   # everything imports, config is valid
python tools/selftest.py     # storyboard checks, budget cap, shot list, thumbnail
make demo                    # renders a real 24-second MP4, every shot type
```

`make demo` costs nothing and calls no APIs. If it produces `remotion/out/demo.mp4`, your Mac can build videos.

---

## Making a video locally

```bash
source venv/bin/activate

python -m pipeline.run topics                     # Gate 1: prints 10 topics
python -m pipeline.run choose --run latest --pick 3
python -m pipeline.run write  --run latest        # Gate 2: prints the script
```

Now edit `runs/<run-id>/script.txt` in any text editor. Then:

```bash
python -m pipeline.run build --run latest
```

Your video ends up in `runs/<run-id>/output/video.mp4`.

There are shortcuts for all of these — `make topics`, `make write`, `make build`. Type `make` on its own to see them.

---

## Working on the look

This is the part that's genuinely painful on GitHub and pleasant locally.

```bash
cd remotion
npx remotion studio
```

A browser opens with a live preview. Edit any file in `src/components/` and the video updates as you type. The components:

| Component | What it does |
|---|---|
| `StockClip` | AI or stock footage with a slow push-in (stretched slightly if a clip is short) |
| `ParallaxStill` | An AI keyframe moved in 2.5D using its depth map — footage for free |
| `charts/Bars3D`, `charts/Line3D` | three.js charts that build while the camera dollies in |
| `charts/BigNumber` | A key figure counting up over the dark three.js stage |
| `EvidenceCard` | A recreated source page with the quoted sentence highlighted — the receipts |
| `ImpactCard` | A ColdFusion-style question or fact card over a darkened plate |
| `LookOverlay` | Vignette, film grain and optional letterbox over everything |

To preview against a real video rather than the demo:

```bash
npx remotion studio --props=../runs/<run-id>/shotlist.json
```

---

## Faster renders

The Mac has more cores than a GitHub runner, so tell Remotion to use them:

```bash
cd remotion
npx remotion render MainVideo out/video.mp4 \
  --props=../runs/<run-id>/shotlist.json \
  --concurrency=8
```

Render on the Mac with the GPU: `pipeline/render.py` reads `REMOTION_GL` (default `angle`, the GPU path) and `REMOTION_CONCURRENCY`:

```bash
REMOTION_CONCURRENCY=8 python -m pipeline.run stage render --run latest
```

The three.js charts and parallax stills are much faster on the Mac's GPU than on the GPU-less Actions runner (`swangle`, software WebGL). If an Actions build approaches its 180-minute limit, render here instead.

On an M2 Pro, `--concurrency=8` is a good starting point. Higher isn't always faster — each worker is a browser tab, and past a point they compete for memory. Try 8, then 10, and keep whichever is quicker.

---

## Pushing your changes back

Once you've improved a prompt or a component, send it to GitHub so the weekly runs pick it up:

```bash
git add -A
git commit -m "Tighter hook prompt"
git push
```

The next scheduled run uses the new version. Nothing else to do.

---

## If you'd rather not use GitHub Actions at all

You don't have to. Run `make topics`, `make write` and `make build` on a schedule of your own, or just when you feel like making a video. The workflows in `.github/workflows/` are one way to drive the pipeline, not part of it — deleting that folder breaks nothing.
