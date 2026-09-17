# Setup — all of it from your phone

Every step here works in a mobile browser. No laptop, no terminal, nothing installed.

Budget about **45 minutes**, most of it waiting for sign-up emails. You can stop after any step and pick up later.

There are four parts:

1. [Get your API keys](#part-1--get-your-api-keys) (~30 min)
2. [Put them into GitHub](#part-2--put-the-keys-into-github) (~10 min)
3. [Let the workflows do their job](#part-3--give-the-workflows-permission) (~1 min)
4. [Make your first video](#part-4--make-your-first-video) (~90 min, but only 7 of them yours)

---

## Part 1 — Get your API keys

An **API key** is a long password that lets this pipeline use a service on your behalf. You'll collect seven of them.

Open each link, sign up, generate a key, and **paste it somewhere you can get to again** — your phone's Notes app is fine for the next half hour. You'll move them into GitHub in Part 2, and you should delete the note afterwards.

> Do not paste API keys into a chat window, a text message, or an email — including to me. The only place they belong is GitHub Secrets.

### The seven you need

| # | Service | What it does | Cost | Where |
|---|---|---|---|---|
| 1 | **DeepSeek** | Writes the scripts | ~$3/mo | [platform.deepseek.com](https://platform.deepseek.com) → API keys → Create |
| 2 | **Google AI Studio** | The vision checks on every clip and image (Gemini 3.8 Flash ranks the stock footage, Flash-Lite checks AI images), the backup writer, and a fallback video model — one key does all of it | ~$1–2/video. Prepaid: when credits run out every check fails, so keep a few dollars of balance | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Create API key |
| 3 | **Exa** | Finds research sources | Free (20k/mo) | [dashboard.exa.ai](https://dashboard.exa.ai) → API Keys |
| 4 | **Tavily** | Backup research | Free (1k/mo) | [app.tavily.com](https://app.tavily.com) → API Keys |
| 5 | **Pexels** | Stock video (after the NASA and Wikimedia Commons archives, which need no key) | Free | [pexels.com/api](https://www.pexels.com/api/) → Get Started |
| 6 | **Pixabay** | More stock video | Free | [pixabay.com/api/docs](https://pixabay.com/api/docs/) — the key is shown on that page once you're signed in |
| 7 | **ElevenLabs** | The narrator's voice (`eleven_multilingual_v2`, one fixed voice stitched across chunks) | ~$1.10/video ($0.10 per 1k characters) | [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys) → Create key. A paid plan (Creator) covers many videos a month. |
| 8 | **fal.ai** | Every AI-generated visual and thumbnail: keyframe images, image-to-video clips, depth maps | ≤ $5/video, hard-capped by `visuals.budget_usd` | [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys) → Add key. Add credit under Billing first. |

### Two notes before you start

**DeepSeek needs a small top-up.** It's pay-as-you-go with no monthly fee, but you need a few dollars of credit before the first call works. $10 will last you months at six videos.

**Google AI Studio: use the paid tier.** The free tier's terms allow Google to use your content to improve their products. Add billing in Google Cloud and link it — it's still about $1.50/month at this volume, and it removes the question entirely.

### One optional extra

| # | Service | What it does | Where |
|---|---|---|---|
| 8 | **YouTube Data API key** | Lets the topic engine find videos that outperformed their own channel — the strongest topic signal there is | Google Cloud Console → APIs & Services → Library → enable **YouTube Data API v3** → Credentials → Create credentials → **API key** |

Skip it if you want to get going. The pipeline notices it's missing and carries on with the other signals.

---

## Part 2 — Put the keys into GitHub

GitHub has a built-in vault called **Secrets**. Anything in there is available to the workflows but invisible to everyone, including in the logs — GitHub blanks them out automatically.

**On your phone, in a browser** (the GitHub mobile app can't do this bit — it has no Settings screen):

1. Open your repository
2. Tap **Settings** (you may need to scroll the tab bar sideways)
3. In the left menu tap **Secrets and variables** → **Actions**
4. Tap **New repository secret**
5. Enter the **Name** exactly as written below — capitals, underscores and all
6. Paste the key into **Secret**
7. Tap **Add secret**
8. Repeat for each one

The names must match exactly:

```
DEEPSEEK_API_KEY
GEMINI_API_KEY
EXA_API_KEY
TAVILY_API_KEY
PEXELS_API_KEY
PIXABAY_API_KEY
FAL_KEY
YOUTUBE_API_KEY      (optional)
```

When you're done you should see seven or eight entries listed. You can't read them back — that's the point. If you get one wrong, add it again with the same name and it overwrites.

**Now delete the note on your phone.**

---

## Part 3 — Give the workflows permission

The workflows need to open issues and save files back to the repository. GitHub blocks that by default.

1. **Settings** → **Actions** → **General**
2. Scroll to **Workflow permissions**
3. Choose **Read and write permissions**
4. Tap **Save**

One tap, and everything else stops working without it.

---

## Part 4 — Make your first video

### Step 1 — Start it

1. Go to the **Actions** tab
2. If GitHub asks you to enable workflows, say yes
3. Tap **1 - Propose topics (Gate 1)** in the left list
4. Tap **Run workflow** → **Run workflow**

It takes two or three minutes. It's gathering signals and asking the model for ten topics.

*(After this first manual run it goes by itself every Monday at 06:00 UTC. One thing to know: GitHub switches off scheduled workflows in a repository that's had no activity for 60 days, and emails you when it does. Approving a video counts as activity, so in normal use this never comes up.)*

### Step 2 — Gate 1: pick a topic

Go to the **Issues** tab. There's a new issue: *Gate 1 — pick a topic (run 2026-…)*.

It lists ten topics with the reasoning behind each. Read them, then **reply with just the number**:

```
3
```

Nothing else in the comment. A rocket emoji appears on your comment when the job picks it up.

**How to choose well:** the evidence line matters more than the title. A topic backed by an outlier video — one that out-drew its own channel's subscriber count — is a topic where the *subject* pulled the views, and subjects travel between channels. That's a stronger signal than a title that merely sounds good.

Now it researches and writes. Ten to twenty minutes. You can close the browser.

### Step 3 — Gate 2: approve the script

The script gets posted back into the same issue, along with:

- the proposed title
- how long it runs
- **the fact-check flags** — every claim the checker couldn't find in the research

Read the flags first. If the verdict is `do_not_publish`, something's wrong with the sources — reply with a different topic number on a fresh run rather than pushing on.

Then read the script. **Change something.** Add an observation only you would make, cut the paragraph that drags, sharpen the hook. This is the step that makes the channel a person using AI tools rather than a content farm, and it's the difference between a channel that survives and one that doesn't.

To approve with no changes:

```
approve
```

To approve with your edit — paste the whole corrected script inside a fenced block, three backticks above and below:

````
approve

```
The morning of May eighteenth, the north face of the mountain began to move...
...your full edited script...
```
````

### Step 4 — Wait

The build takes 45 to 90 minutes: narration, caption timing, charts, stock footage and its vision checks, then the render. It can take longer: Pexels allows 200 searches an hour, and when a build hits that the stock stage pauses and waits for the limit to reset (re-checking every 10 minutes) instead of filling those shots with AI images. You'll see `pexels rate limit reached - pausing its searches` in the log; that's expected, not a hang. If a whole hour of waiting doesn't clear it, the monthly quota (20,000) is used up. Only then do those searches come back empty, and the shots they couldn't fill are generated. Pexels raises the limits for free if you ask: [pexels.com/api](https://www.pexels.com/api/) → request higher limits.

You'll get a comment when it's done, with a download link. The download contains:

- `video.mp4` — the finished video
- `thumbnail.jpg`
- `metadata.json` — the title, description and tags
- `script.txt`

### Step 5 — Check it, then publish

Watch it before you upload. Specifically:

- **The first 30 seconds.** Does the hook actually land? This is 80% of your retention.
- **Do the pictures land on the words?** With ElevenLabs the cuts use the voice engine's own word timings, so they should sit right on the beat. If a shot feels early or late, check `words.json`: `"method": "elevenlabs"` is the exact path, `"faster-whisper"` means it fell back to transcribing.
- **The chunk joins.** The narration is generated in two or three chunks and stitched together; the narrate log prints where each join is. Listen for the voice shifting pitch or pace there.
- **The stock footage.** The vision check catches clips that don't match. It doesn't catch clips that match but feel wrong.

Then, in the YouTube app: upload, set the thumbnail, paste the title and description, and **tick the "altered or synthetic content" box**. The narration is AI-generated. Declaring it costs you nothing in reach; not declaring it and being found out costs you the channel.

---

## When something breaks

The pipeline posts the failure straight into the issue with a link to the log. The most common causes, in order:

| What you'll see | What it means |
|---|---|
| `Missing DEEPSEEK_API_KEY` | The secret name has a typo, or it's saved as an *environment* secret instead of a *repository* secret |
| `Insufficient balance` | DeepSeek needs a top-up |
| `No usable sources found` | The topic was too obscure. Start a fresh run and pick a different one |
| `403` from Pexels | Wrong key, or you've hit the hourly rate limit — wait an hour |
| The build times out | Retry by replying `approve` again. Finished stages are skipped, so it resumes rather than restarting |

**Retrying is always safe.** Every stage records that it finished, and a re-run skips what's already done. You never pay twice for the same narration.

---

## Later, when you're back at the Mac

Two things worth doing:

- **[MAC.md](MAC.md)** — run the whole thing locally, which makes iterating on prompts and components much faster
- **The voice bake-off** — the narrator is currently ElevenLabs' premade `Brian`, which is a sensible default and nothing more. Try a few voices from the ElevenLabs voice library (set `elevenlabs_voice_id`; avoid voices showing a credit multiplier), or generate the same 90 seconds through ElevenLabs, Gemini, Qwen, and Speechify, rename them `a.wav`, `b.wav`, `c.wav`, and listen on your phone while walking. That's how your viewers will hear it. Set the winner in `config/channel.json`.

And the one from your own plan: **three videos by hand, published, measured.** Retention above 35%, click-through above 4%. Until then, leave `review_only: true` and treat this as a machine that hands you drafts.
