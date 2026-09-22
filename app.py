"""Deep Earth studio - the local chat app that drives the whole pipeline.

    make app          (or: ./venv/bin/python app.py)

Opens http://127.0.0.1:8765 in your browser. Everything happens in that chat:
you type or tap, `pipeline/assistant.py` answers quick things on the spot, and
anything slow (topics, script, build, upload) runs as a background
`tools/chat_job.py` process on this Mac - so renders use the Mac's GPU.

Every message, yours and the pipeline's, is a line in runs/chat.jsonl. The page
polls it. Background job output goes to runs/job.log.

Bound to 127.0.0.1 only, and it refuses requests from other sites' pages, so
nothing but a browser tab on this Mac can drive it.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from pipeline import assistant, chat
from pipeline.common import ROOT, RUNS_DIR, log

PORT = int(os.getenv("STUDIO_PORT", "8765"))
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
LAST_JOB = RUNS_DIR / "last_job.json"

# ponytail: one background job at a time; add a queue if parallel runs are ever wanted.
job: dict | None = None
job_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------------

def start_job(intent: str, args: dict, ack: str = "") -> None:
    global job
    with job_lock:
        if job:
            chat.send(f"⏳ Still busy with <b>{job['intent']}</b>. Tap Stop to abort it, then ask again.")
            return
        chat.send(f"👍 {chat.escape(ack)}" if ack else f"👍 Starting <b>{intent}</b>…")
        LAST_JOB.write_text(json.dumps({"intent": intent, "args": args}))
        with open(RUNS_DIR / "job.log", "ab") as out:
            out.write(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} {intent} {args}\n".encode())
            proc = subprocess.Popen(
                [sys.executable, "tools/chat_job.py", "--intent", intent,
                 "--args", json.dumps(args), "--run", "latest"],
                cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, start_new_session=True,
            )
        job = {"intent": intent, "started": time.time(), "proc": proc}
    threading.Thread(target=reap, args=(proc,), daemon=True).start()


def reap(proc: subprocess.Popen) -> None:
    """Forget the job when it exits. Failures report themselves via chat.failed."""
    global job
    proc.wait()
    with job_lock:
        if job and job["proc"] is proc:
            job = None


def stop_job() -> bool:
    with job_lock:
        if not job:
            return False
        try:
            os.killpg(job["proc"].pid, signal.SIGTERM)  # the job and any render it started
        except ProcessLookupError:
            pass
        return True


def handle(text: str) -> None:
    """One message from the page. Runs in its own thread: routing may call a model."""
    chat._append({"role": "user", "text": text})
    clean = text.strip().lower()

    if clean in ("cmd:stop", "stop job"):
        if stop_job():
            chat.send("⏹ Stopped. Tap Retry to carry on from the last finished stage.",
                      buttons=chat.keyboard([("🔁 Retry", "retry")]))
        else:
            chat.send("Nothing is running.")
        return
    if clean == "retry":
        if LAST_JOB.exists():
            last = json.loads(LAST_JOB.read_text())
            start_job(last["intent"], last["args"], f"Retrying {last['intent']}.")
        else:
            chat.send("There's nothing to retry.")
        return

    decision = assistant.route(text)
    intent = decision["intent"]
    if intent == "cancel":
        stop_job()
    elif intent not in assistant.FAST:
        start_job(intent, decision.get("args", {}), decision.get("reply", ""))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # the page polls every 2 s - keep the terminal quiet
        pass

    def trusted(self) -> bool:
        """Only this page, on this Mac. Blocks DNS rebinding and cross-site POSTs."""
        origin = self.headers.get("Origin")
        return (self.headers.get("Host") in ALLOWED_HOSTS
                and (origin is None or urlparse(origin).netloc in ALLOWED_HOSTS))

    def send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self.trusted():
            return self.send_error(403)
        url = urlparse(self.path)
        if url.path == "/":
            return self.serve(ROOT / "ui.html")
        if url.path == "/messages":
            after = int(parse_qs(url.query).get("after", ["0"])[0])
            lines = chat.LOG_FILE.read_text().splitlines() if chat.LOG_FILE.exists() else []
            current = job
            return self.send_json({
                "messages": [json.loads(line) for line in lines[after:] if line.strip()],
                "next": len(lines),
                "job": {"intent": current["intent"], "started": current["started"]} if current else None,
            })
        if url.path.startswith("/runs/"):
            path = (ROOT / unquote(url.path).lstrip("/")).resolve()
            if not path.is_relative_to(RUNS_DIR) or not path.is_file():
                return self.send_error(404)
            return self.serve(path)
        self.send_error(404)

    def do_POST(self) -> None:
        if not self.trusted() or urlparse(self.path).path != "/send":
            return self.send_error(403)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        text = str(body.get("text", "")).strip()
        if text:
            threading.Thread(target=handle, args=(text,), daemon=True).start()
        self.send_json({"ok": True})

    def serve(self, path: Path) -> None:
        """Send a file, honouring Range - browsers need it to play and seek a video."""
        size = path.stat().st_size
        start, end = 0, size - 1
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if match and (match[1] or match[2]):
            if match[1]:
                start = int(match[1])
                end = min(int(match[2]), size - 1) if match[2] else size - 1
            else:  # "bytes=-500" means the last 500 bytes
                start = max(0, size - int(match[2]))
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)

        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix in (".srt", ".md", ".txt", ".log"):
            kind = "text/plain"  # shown in the tab, not downloaded or rendered
        if kind.startswith("text/"):
            kind += "; charset=utf-8"
        self.send_header("Content-Type", kind)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        remaining = end - start + 1
        try:
            with open(path, "rb") as handle:
                handle.seek(start)
                while remaining > 0:
                    chunk = handle.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the video player skipped ahead and dropped this request


def main() -> None:
    RUNS_DIR.mkdir(exist_ok=True)
    # Keep the Mac from idle-sleeping for as long as the studio is open.
    subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
    if not chat.LOG_FILE.exists():
        chat.send("👋 <b>Deep Earth studio.</b> Say <code>new video</code> to start one, "
                  "or ask me anything.",
                  buttons=chat.keyboard([("🎬 New video", "cmd:new"), ("📊 Status", "cmd:status")]))

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    log(f"Studio running at {url} - Ctrl+C to quit.")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_job()


if __name__ == "__main__":
    main()
