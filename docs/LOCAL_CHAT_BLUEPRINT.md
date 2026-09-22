# Blueprint: a local chat UI that drives a long-running, GPU-heavy content pipeline

Use this when a pipeline (video/audio/image generation) needs the local machine's GPU,
takes minutes-to-hours per job, and needs human approval gates — and you want to drive
all of it by chatting with an AI in a browser tab. Zero hosting, zero new dependencies.

## Why local, not cloud
- Cloud CI runners have no GPU: WebGL/three.js/Remotion renders fall back to software and take 3–5× longer, often hitting job time limits.
- Chat-app bridges (Telegram + serverless worker + CI) add three moving parts and cap files at ~50 MB, forcing workarounds for video review.
- Local: the GPU is used, files are on disk so a 400 MB MP4 plays directly in a `<video>` tag, and state lives in ordinary files.

## Components (keep it to these five)
1. **Pipeline stages** — one function per stage, each writes its output to `runs/<id>/` and marks itself done in `state.json`, so any stage can be redone alone.
2. **Chat log** — `runs/chat.jsonl`, append-only. One record per message: `{id, ts, role, html, buttons:[[label, code]], image, video, file, edit?}`. It is the *only* channel from pipeline to human; every stage calls `chat.send(...)`.
3. **Brain** — message text -> `{intent, args, reply}`. Rules first (button codes like `cmd:approve`, `pick:3`, `thumb:b`, bare digits, exact words), then an LLM returning JSON over a *fixed* intent list with the run's current stage as context. On failure return `unclear` — never guess an intent that spends money or publishes.
4. **Assistant** — executes fast intents in-process (status, edit title/tags/description/pinned comment, pick thumbnail, answer a question with run context + last 20 messages); names slow ones. Posts each gate as a message with buttons.
5. **Server + one HTML page** — stdlib HTTP server on 127.0.0.1:
   - `GET /` page · `GET /messages?after=N` (UI polls every 2 s) · `POST /send {text}` · `GET /runs/<path>` with **HTTP Range support** (browsers need it to play/seek large MP4s) and a path-traversal check.
   - Slow intents run as a subprocess (`caffeinate -i python job.py --intent X --args JSON`) so the server never blocks; one job at a time; `stop` terminates it; job stdout -> `runs/<id>/job.log`; job crash -> `chat.failed(...)` with a Retry button.

## The gates
1. **Topics** — N options with numbered buttons, or free-text "make one about X".
2. **Script** — full text; free-text edits ("punchier opening") loop through an LLM revise; pasted ``` block replaces verbatim; "Build it" button.
3. **Review** — inline `<video>`, all thumbnails (pick a/b/c), title, description, tags, pinned comment, .srt and upload packet as files; free-text edits change metadata only; "Redo <stage>" re-runs from that stage; **Accept & upload**.

## Upload (YouTube Data API v3, OAuth refresh token)
- On Accept: `videos.insert` (snippet + status, resumable) -> `thumbnails.set` -> `captions.insert` (.srt) -> `videos.update` privacy -> `commentThreads.insert` for the comment.
- The API **cannot pin** a comment: tell the user to tap Pin.
- Unaudited Google API projects force uploads to private; the user flips public in the YouTube app until the audit clears.
- Always also write `UPLOAD.md` (title, description, tags, chosen thumbnail, .srt path, pinned comment, checklist: category, not-for-kids, altered/synthetic content) so manual upload is always possible.

## Every run must output
title · description (with sources/credits) · tags (<=15) · 3 thumbnails + chosen one · subtitles.srt · pinned comment · video.mp4 · UPLOAD.md

## Rules that save pain
- Chat notifications never raise; a failed message must not kill a 90-minute job.
- Keep the transport behind one module (`chat.py`) with `send/send_photo/send_file/send_video/progress/failed/keyboard` — swapping Telegram <-> local UI is then a one-file change.
- Button codes are just message text, so buttons and typing share one code path.
- Bind to 127.0.0.1. For phone access later, use Tailscale — no code change.
- Keep the Mac awake during jobs with `caffeinate -i`; set `REMOTION_GL=angle` and a sensible concurrency (8 on an M2 Pro).

## Reference implementation
`../yt-studio`: `app.py` (server, multi-channel queue), `ui.html` (page), `CHANNEL_CONTRACT.md`.
This repo: `pipeline/chat.py` (transport),
`pipeline/brain.py` (routing), `pipeline/assistant.py` (fast intents + gates),
`tools/chat_job.py` (slow intents), `pipeline/publish.py` (YouTube upload).

