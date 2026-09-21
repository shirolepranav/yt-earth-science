"""One place that talks to language models, so the rest of the code doesn't care
which provider is in use.

Two providers are supported:
  * DeepSeek  - cheap, strong English prose. Used for writing.
  * Gemini    - free tier, vision-capable. Used as a backup writer and for the
                stock-footage image checks.

Both are wrapped by `chat()`, which automatically falls back to the backup
provider if the primary one errors out. That fallback is the difference between
"a run failed at 3am" and "a run finished at 3am".
"""

from __future__ import annotations

import base64
import json
import re
import threading
import time
from typing import Any

import requests

from .common import (PermanentError, has_secret, load_config, log, permanent_if_hopeless, secret,
                      with_retries)

TIMEOUT = 420  # seconds. A storyboard chunk measured 174s (27k chars in, 14k out).

# Set once DeepSeek has failed every retry in this process. After that, calls go
# straight to Gemini: an overloaded DeepSeek otherwise costs every later call
# its full retry cycle before falling back (observed: 45 minutes per call).
_deepseek_down = False


def _post_with_deadline(url: str, headers: dict, payload: dict) -> dict:
    """POST and return the JSON reply, failing after TIMEOUT seconds of wall clock.

    requests' timeout is per read, so a server that trickles keep-alive bytes
    never trips it (one storyboard call hung 107 minutes). The request runs in a
    daemon thread and is abandoned at the deadline, whatever the socket is doing.
    The reply arrives in one piece only when generation finishes, so the
    deadline covers the whole generation (a storyboard chunk measured 174s).
    """
    result: dict[str, Any] = {}

    def work() -> None:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=(15, TIMEOUT))
            response.raise_for_status()
            result["data"] = response.json()
        except Exception as error:  # noqa: BLE001 - re-raised in the caller's thread
            result["error"] = error

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(TIMEOUT)
    if thread.is_alive():
        raise TimeoutError(f"no complete reply within {TIMEOUT}s")
    if "error" in result:
        raise result["error"]
    return result["data"]

# ---------------------------------------------------------------------------
# Provider 1: DeepSeek (and anything else that speaks the OpenAI format)
# ---------------------------------------------------------------------------

def _deepseek_chat(system: str, user: str, model: str, json_mode: bool) -> str:
    cfg = load_config()["models"]["writer"]
    base_url = cfg["base_url"].rstrip("/")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
    }
    # "JSON mode" tells the model to return valid JSON and nothing else.
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    body = _post_with_deadline(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {secret('DEEPSEEK_API_KEY')}",
            "Content-Type": "application/json",
        },
        payload=payload,
    )
    if "choices" not in body:
        raise RuntimeError(f"DeepSeek returned no choices: {str(body)[:200]}")
    return body["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Provider 2: Gemini
# ---------------------------------------------------------------------------

def _gemini_chat(system: str, user: str, model: str, json_mode: bool) -> str:
    generation_config: dict[str, Any] = {"temperature": 0.7}
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    data = _post_with_deadline(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": secret("GEMINI_API_KEY")},  # header, not URL: URLs end up in error logs
        payload={
            # Gemini keeps the "system" instruction in its own field rather than
            # as a message, which is why this looks different from DeepSeek.
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation_config,
        },
    )
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# The function everything else calls
# ---------------------------------------------------------------------------

def chat(
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    heavy: bool = False,
    label: str = "llm",
) -> str:
    """Send a prompt to the writing model and return its text reply.

    Args:
        system: the persistent instruction (persona, rules, banned phrases).
        user:   the actual request for this call.
        json_mode: ask the model to reply with strict JSON.
        heavy:  use the more expensive, better model. Reserve this for the final
                polish pass - it's where script quality actually shows up.
        label:  what to call this in the logs when it retries.
    """
    cfg = load_config()["models"]
    writer = cfg["writer"]
    fallback = cfg["writer_fallback"]

    model = writer["polish_model"] if heavy else writer["model"]

    def validated(raw: str) -> str:
        # In json_mode, a 200 with unparseable JSON is still a failure - it
        # needs to trigger the same retry-then-fallback path as an HTTP error,
        # not surface as a crash two calls further up the stack.
        if json_mode:
            parse_json_loosely(raw)
        return raw

    global _deepseek_down
    try:
        if _deepseek_down:
            raise RuntimeError("it already failed earlier in this run")
        return with_retries(
            lambda: validated(_deepseek_chat(system, user, model, json_mode)),
            label=f"{label} (deepseek/{model})",
        )
    except Exception as error:  # noqa: BLE001
        if not _deepseek_down:
            log(f"  DeepSeek unavailable ({error}). Falling back to Gemini for the rest of this run.")
        _deepseek_down = True
        return with_retries(
            lambda: validated(_gemini_chat(system, user, fallback["model"], json_mode)),
            label=f"{label} (gemini fallback)",
        )


def chat_json(system: str, user: str, *, heavy: bool = False, label: str = "llm") -> Any:
    """Same as chat(), but parses the reply as JSON and hands back Python data.

    Models occasionally wrap JSON in ```json fences even when told not to, so we
    strip those before parsing rather than letting the whole run fail on it.
    """
    raw = chat(system, user, json_mode=True, heavy=heavy, label=label)
    return parse_json_loosely(raw)


def parse_json_loosely(raw: str) -> Any:
    """Best-effort JSON parsing of a model reply."""
    text = raw.strip()

    # Strip ```json ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost {...} or [...] block and try that.
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


# ---------------------------------------------------------------------------
# Vision - used to check a stock clip's frame, or an AI-generated clip's
# actual motion, before either is allowed into the render.
# ---------------------------------------------------------------------------

def _openai_vision(mime_type: str, data_b64: str, prompt: str, model: str, timeout: int) -> Any:
    """OpenAI's chat API, which takes an image as a data URI. Images only -
    these models don't accept video, which is why motion QA stays on Gemini."""
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret('OPENAI_API_KEY')}"},
        json={
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{data_b64}"}},
            ]}],
        },
        timeout=timeout,
    )
    try:
        response.raise_for_status()
    except Exception as error:  # noqa: BLE001
        permanent_if_hopeless(error, "openai vision")
        raise
    return parse_json_loosely(response.json()["choices"][0]["message"]["content"])


def _vision_generate(mime_type: str, data_b64: str, prompt: str, *, timeout: int, label: str,
                     model: str | None = None, provider: str | None = None) -> Any:
    cfg = {**load_config()["models"]["vision"], **({"model": model} if model else {})}
    chosen = provider or cfg.get("provider")
    if chosen == "openai":
        return with_retries(lambda: _openai_vision(mime_type, data_b64, prompt, cfg["model"], timeout),
                            attempts=5, base_delay=4.0, label=label)

    def call() -> Any:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent",
            headers={"x-goog-api-key": secret("GEMINI_API_KEY")},  # header, not URL: URLs end up in error logs
            json={
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": data_b64}},
                    ]
                }],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except Exception as error:  # noqa: BLE001
            permanent_if_hopeless(error, "gemini vision")
            raise
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json_loosely(text)

    # Generous backoff: parallel visuals QA hits per-minute rate limits (429s).
    try:
        return with_retries(call, attempts=5, base_delay=4.0, label=label)
    except PermanentError:
        # An empty balance or a bad key: the other provider can still answer,
        # which is how a dry Gemini account stops costing a whole build.
        fallback = cfg.get("fallback_model")
        if provider == "gemini" or not fallback or not has_secret("OPENAI_API_KEY"):
            raise
        log(f"  {label}: gemini unavailable - falling back to {fallback}")
        return with_retries(lambda: _openai_vision(mime_type, data_b64, prompt, fallback, timeout),
                            attempts=3, base_delay=2.0, label=f"{label} (openai)")


def has_vision() -> bool:
    """Whether the configured vision provider has a key to call."""
    cfg = load_config()["models"]["vision"]
    keys = ["OPENAI_API_KEY"] if cfg.get("provider") == "openai" else ["GEMINI_API_KEY", "OPENAI_API_KEY"]
    return any(has_secret(k) for k in keys)


def vision_check(image_path: str, prompt: str, model: str | None = None) -> Any:
    """Show one still frame to a cheap vision model and get a small JSON verdict back.

    Kept deliberately tiny: a short prompt and a yes/no answer means a few
    hundred tokens per call, which is a fraction of a cent even at 60 clips
    per video.
    """
    with open(image_path, "rb") as handle:
        image_b64 = base64.b64encode(handle.read()).decode()
    return _vision_generate("image/jpeg", image_b64, prompt, timeout=120, label="vision check", model=model)


def vision_check_video(video_path: str, prompt: str) -> Any:
    """Same idea as vision_check(), but hands the model the actual clip so it
    can judge motion over time - a still frame can't show a physics mistake
    or a morphing artifact that only appears between frames.
    """
    with open(video_path, "rb") as handle:
        video_b64 = base64.b64encode(handle.read()).decode()
    # Video understanding takes longer than a single image - generous timeout.
    # Gemini regardless of the configured vision provider: OpenAI's chat models
    # take images only. Without a Gemini key the caller keeps the clip (visuals.check).
    return _vision_generate("video/mp4", video_b64, prompt, timeout=180, label="physics check",
                            model=load_config()["models"]["writer_fallback"]["model"], provider="gemini")
