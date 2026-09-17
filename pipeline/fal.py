"""fal.ai - one pay-per-use key (FAL_KEY) for every image, video and depth model.

Talks to fal's queue REST API directly with `requests` rather than adding the
fal SDK: submit, poll the status URL, fetch the result. Model IDs and prices
live in config/channel.json, so swapping to whatever tops the leaderboard next
month is a config change.

https://fal.ai/docs/model-apis/model-endpoints/queue
"""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path

import requests
from PIL import Image

from .common import secret, with_retries

QUEUE_URL = "https://queue.fal.run"
POLL_SECONDS = 4
TIMEOUT_SECONDS = 900  # video models can sit in a queue for several minutes


def _headers() -> dict:
    return {"Authorization": f"Key {secret('FAL_KEY')}", "Content-Type": "application/json"}


def fal_run(model: str, args: dict) -> dict:
    """Run one model call to completion and return its output JSON."""
    def submit() -> dict:
        response = requests.post(f"{QUEUE_URL}/{model}", headers=_headers(), json=args, timeout=120)
        response.raise_for_status()
        return response.json()

    job = with_retries(submit, label=f"fal submit {model}")
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        status = requests.get(job["status_url"], headers=_headers(), timeout=60).json()
        if status.get("status") == "COMPLETED":
            if status.get("error"):
                raise RuntimeError(f"{model} failed: {status['error']}")
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"{model} still not done after {TIMEOUT_SECONDS}s")
        time.sleep(POLL_SECONDS)

    result = requests.get(job["response_url"], headers=_headers(), timeout=120)
    if result.status_code >= 400:
        raise RuntimeError(f"{model} failed ({result.status_code}): {result.text[:300]}")
    return result.json()


def download(url: str, path: Path) -> Path:
    with requests.get(url, stream=True, timeout=300) as response:
        response.raise_for_status()
        tmp = path.with_suffix(path.suffix + ".part")
        with tmp.open("wb") as handle:
            for block in response.iter_content(chunk_size=1 << 16):
                handle.write(block)
    tmp.replace(path)  # never leave a half-written file where the cache would trust it
    return path


def data_uri(path: Path) -> str:
    """Local file as a data URI - fal accepts these anywhere it takes a URL."""
    mime = "image/png" if path.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def image_args(model: str, prompt: str) -> dict:
    """Each image family names its size parameters differently."""
    if "nano-banana" in model:
        return {"prompt": prompt, "aspect_ratio": "16:9", "resolution": "2K", "num_images": 1}
    return {"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1}


def generate_image(model: str, prompt: str, path: Path, width: int, height: int) -> Path:
    """Generate one image, cover-crop it to exactly width x height, save as JPEG."""
    output = fal_run(model, image_args(model, prompt))
    raw = requests.get(output["images"][0]["url"], timeout=300)
    raw.raise_for_status()
    image = Image.open(io.BytesIO(raw.content)).convert("RGB")
    scale = max(width / image.width, height / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left, top = (image.width - width) // 2, (image.height - height) // 2
    tmp = path.with_suffix(".part.jpg")
    image.crop((left, top, left + width, top + height)).save(tmp, "JPEG", quality=92)
    tmp.replace(path)
    return path
