"""STAGE 8 - AI visuals.

Turns every stock shot the libraries couldn't fill (and any "ai" shot in an
older storyboard.json, and every card's background plate) into an asset:

  1. Keyframe  - a 1920x1080 image, prompted with the look bible. A cheap vision
                 check rejects garbled text, logos, faces and obvious artefacts
                 BEFORE any money is spent animating it.
  2. Motion    - for the highest-priority shots, image-to-video from that
                 keyframe. A vision model watches the clip for morphing and
                 impossible motion; a failure falls back to a still.
  3. Still     - everything else gets a depth map, and Remotion renders a slow
                 2.5D parallax camera move over it for free.

The budget: before spending anything, the allocator estimates the whole video
from the price table in config/channel.json and gives motion to shots in
priority order until visuals.budget_usd (with a retry allowance) is reached.
It aborts if even all-stills would exceed the cap.

The cache: every generated file is named by a hash of the model and its inputs
(runs/<id>/assets/gen/). Rerunning a build pays only for what's missing.

Run it:  python -m pipeline.visuals --run latest [--until-seconds 90]
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .common import Run, has_secret, load_config, log, resolve_run, secret, with_retries
from .fal import data_uri, download, fal_run, generate_image
from .llm import has_vision, vision_check, vision_check_video

WORKERS = 6  # parallel shots; fal queues the rest, so more mostly adds rate-limit retries
NEGATIVE = (
    "No faces as the subject - silhouettes, backs or out-of-focus figures only. "
    "Avoid hands; if one is essential keep it small, still and out of focus. "
    "No readable text, letters, numbers, signage, logos, brand marks or watermarks. "
    "No charts, graphs, bars, trend lines, arrows or data visualisations on screens, "
    "paper or anywhere else - real figures are shown separately. "
    "No calculators, clocks, phones or screens showing digits. "
    "No gore, injury, dead bodies or horror imagery. No fantasy or sci-fi styling - geologically "
    "plausible landscapes, rocks, skies and seas only; no recognisable real landmark."
)
# Calibrated on the first pilot: a strict "anything AI-looking" check rejected 23
# of 30 good cinematic frames for tiny background hands. These shots are on
# screen for 3-5 seconds, darkened and under film grain - judge like a viewer
# on a phone, not a pixel-peeper.
KEYFRAME_CHECK = (
    "You are checking an AI-generated frame for a cinematic Earth science documentary. It will be "
    "on screen for about 4 seconds, darkened, under film grain, mostly watched on phones. "
    "Reject it ONLY if a casual viewer would clearly notice a problem at a glance: large "
    "readable or garbled text that draws the eye, a visible logo, a human face as the main "
    "subject, a prominent hand in the foreground with obviously wrong fingers, or a main "
    "object that is clearly melted or impossible, or any chart, graph, bar, trend "
    "line or data visualisation (the video shows real charts separately), a calculator or screen showing "
    "digits, anything that reads as gore, injury or horror, or geology that is obviously impossible or "
    "fantasy-styled (floating rocks, glowing crystals, alien skies). Small, dark, blurred or background "
    "imperfections are fine - do not reject for them. "
    'Reply as JSON only: {"usable": true/false, "reason": "one short sentence"}'
)
MOTION_CHECK = (
    "You are checking a 5-second AI-generated clip for a cinematic Earth science documentary, watched "
    "mostly on phones under film grain. Reject it ONLY if a casual viewer would clearly "
    "notice something wrong on first watch: the main subject visibly morphing into a "
    "different shape, objects melting or passing through each other, a prominent hand with "
    "obviously wrong fingers, or a large object popping in or out of existence. Slow "
    "subtle drift, small background changes, soft focus shifts and minor flicker are fine. "
    'Reply as JSON only: {"physically_plausible": true/false, "reason": "one short sentence"}'
)


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

def allocate(shots: list[dict], cfg: dict) -> tuple[set[int], float]:
    """Pick which AI shots get motion. Returns (shot ids, estimated USD).

    Every AI shot and card plate needs a keyframe and (conservatively) a depth
    map; motion is then granted best-priority-first while it still fits.
    """
    per_image = cfg["usd_per_image"]
    image_cost = per_image[cfg["image_model"]] + per_image[cfg["depth_model"]]
    motion_cost = cfg["usd_per_second"][cfg["video_model"]] * cfg["video_seconds"]
    allowance = cfg["retry_allowance"]

    ai = [s for s in shots if s["kind"] == "ai"]
    base = image_cost * (len(ai) + sum(s["kind"] == "card" for s in shots))
    if base * allowance > cfg["budget_usd"]:
        raise RuntimeError(
            f"Even all-stills needs ~${base * allowance:.2f}, over the "
            f"${cfg['budget_usd']} budget. Raise visuals.budget_usd or cut shots."
        )

    motion, cost = set(), base
    for shot in sorted(ai, key=lambda s: (s.get("priority", 2), s["start"])):
        if (cost + motion_cost) * allowance <= cfg["budget_usd"]:
            motion.add(shot["id"])
            cost += motion_cost
    return motion, round(cost * allowance, 2)


# ---------------------------------------------------------------------------
# Generation, cached by content hash
# ---------------------------------------------------------------------------

def cache_path(run: Run, model: str, args: dict, ext: str) -> Path:
    digest = hashlib.sha256(json.dumps([model, args], sort_keys=True).encode()).hexdigest()[:24]
    folder = run.path("assets", "gen")
    folder.mkdir(exist_ok=True)
    return folder / f"{digest}.{ext}"


# A card beat's prompt sometimes describes the card itself ("a text card with bold
# sans-serif text") - the 15 Sep build got plates with fake text boxes baked in.
CARD_DESIGN = re.compile(r"\b(text|card|caps|sans-serif|serif|font|typograph\w*|letters?|headline|title|underline)\b", re.I)


def plate_prompt(shot: dict, look: dict) -> str:
    """The scene behind a text card: the beat's own prompt if it describes a
    scene, else one of the look bible's locations."""
    scene = re.sub(r"\bno [^,.]*", "", shot["image_prompt"], flags=re.I)  # "no text" is fine
    if CARD_DESIGN.search(scene) and look.get("locations"):
        return look["locations"][shot["id"] % len(look["locations"])]
    return shot["image_prompt"]


def keyframe(run: Run, shot: dict, look: dict, cfg: dict, ledger: list) -> Path:
    style = look.get("collage_style") if shot.get("style") == "collage" else look.get("style")
    subject = plate_prompt(shot, look) if shot["kind"] == "card" else shot["image_prompt"]
    prompt = f"{style or ''} {subject}. {NEGATIVE}"
    if shot.get("angle"):
        prompt += f" Alternate angle {shot['angle']}: a different framing of the same moment."
    if shot["kind"] == "card":
        prompt += (" Dark, simple composition with plenty of empty space. This is only the background "
                   "scene behind a title card: no text, boxes, panels, cards, captions or graphic overlays.")

    # Viewer feedback on the 14 Sep build: generations that were merely moody
    # (a calculator, a grim hallway) instead of showing what was being said.
    relevance = (f"The frame is meant to show: {shot['intent']}. Also reject it if it clearly "
                 "shows something unrelated to that. " if shot.get("intent") else "")
    path = None
    for take in (1, 2):
        # Hands cause most rejections (65 of 80 in the first full build), so the
        # retry removes them entirely rather than rolling the same dice again.
        attempt = prompt if take == 1 else (
            prompt + " Absolutely no hands, fingers or people in frame. Clean, simple, uncluttered composition.")
        path = cache_path(run, cfg["image_model"], {"prompt": attempt}, "jpg")
        if not path.exists():
            generate_image(cfg["image_model"], attempt, path, 1920, 1080)
            ledger.append(cfg["usd_per_image"][cfg["image_model"]])
        if check(path, relevance + KEYFRAME_CHECK, "usable", video=False):
            return path
    shot["_rejected"] = True  # keep the second take, but never pay to animate it
    return path


def motion(run: Run, shot: dict, frame: Path, cfg: dict, ledger: list) -> Path | None:
    args = {
        "prompt": f"{shot.get('motion_prompt') or 'slow push-in'}. Slow, subtle, cinematic "
                  "camera movement; photorealistic; no morphing.",
        "duration": cfg["video_seconds"],
        "resolution": cfg["video_resolution"],
        "prompt_expansion_mode": "balanced",
    }
    path = cache_path(run, cfg["video_model"], {**args, "image": frame.stem}, "mp4")
    if not path.exists():
        try:
            output = fal_run(cfg["video_model"], {**args, "image_url": data_uri(frame)})
            download(output["video"]["url"], path)
            ledger.append(cfg["usd_per_second"][cfg["video_model"]] * cfg["video_seconds"])
        except Exception as error:  # noqa: BLE001 - fall back rather than lose the shot
            log(f"  shot {shot['id']}: {cfg['video_model']} failed ({error})")
            return omni_fallback(run, shot, cfg, ledger)
    return path if check(path, MOTION_CHECK, "physically_plausible", video=True) else None


def omni_fallback(run: Run, shot: dict, cfg: dict, ledger: list) -> Path | None:
    """Gemini Omni Flash text-to-video, only when the fal video call itself fails."""
    model = cfg.get("fallback_video_model")
    if not model or not has_secret("GEMINI_API_KEY"):
        return None
    prompt = f"{shot['image_prompt']}. {shot.get('motion_prompt', '')}. {NEGATIVE}"
    path = cache_path(run, model, {"prompt": prompt}, "mp4")
    if path.exists():
        return path

    def call() -> dict:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": secret("GEMINI_API_KEY")},  # header, not URL: URLs end up in error logs
            json={"model": model, "input": prompt,
                  "response_format": {"type": "video", "aspect_ratio": "16:9", "resolution": "1080p"},
                  "background": False, "store": False, "stream": False},
            timeout=300,
        )
        response.raise_for_status()
        return response.json()

    try:
        body = with_retries(call, attempts=2, label="gemini omni fallback")
        for step in body.get("steps", []):
            for item in step.get("content", []) if step.get("type") == "model_output" else []:
                if item.get("type") == "video" and item.get("data"):
                    path.write_bytes(base64.b64decode(item["data"]))
                    ledger.append(cfg["usd_per_second"][model] * 8)  # Omni picks ~8s itself
                    return path if check(path, MOTION_CHECK, "physically_plausible", video=True) else None
    except Exception as error:  # noqa: BLE001
        log(f"  shot {shot['id']}: Omni fallback failed too ({error})")
    return None


def depth(run: Run, frame: Path, cfg: dict, ledger: list) -> Path | None:
    path = cache_path(run, cfg["depth_model"], {"image": frame.stem}, "png")
    if path.exists():
        return path
    try:
        output = fal_run(cfg["depth_model"], {"image_url": data_uri(frame)})
        download(output["image"]["url"], path)
        ledger.append(cfg["usd_per_image"][cfg["depth_model"]])
        return path
    except Exception as error:  # noqa: BLE001 - no depth just means a Ken Burns move
        log(f"  depth map failed for {frame.name} ({error}) - plain zoom instead")
        return None


def check(path: Path, prompt: str, key: str, *, video: bool) -> bool:
    """Vision QA. If the check itself can't run, keep the asset."""
    # Motion QA is Gemini-only (OpenAI's vision takes images), so it checks that key.
    if not (has_secret("GEMINI_API_KEY") if video else has_vision()):
        return True
    try:
        verdict = (vision_check_video if video else vision_check)(str(path), prompt)
        if not verdict.get(key):
            log(f"  QA rejected {path.name}: {verdict.get('reason', verdict)}")
        return bool(verdict.get(key))
    except Exception as error:  # noqa: BLE001
        log(f"  QA errored on {path.name} ({error}) - keeping it")
        return True


def clip_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

def build_shot(run: Run, shot: dict, animate: bool, look: dict, cfg: dict, ledger: list,
               spent_before: float = 0.0) -> dict | None:
    try:
        frame = keyframe(run, shot, look, cfg, ledger)
        if shot["kind"] == "card":
            return {"kind": "plate", "src": str(frame)}
        # The cap is per video, across every run of it - a rebuild must not get a fresh $25.
        # A clip can be slowed to at most half speed, so a longer shot gets a parallax still.
        fits = shot["end"] - shot["start"] <= 2 * cfg["video_seconds"]
        if animate and fits and not shot.get("_rejected") and spent_before + sum(ledger) < cfg["budget_usd"]:
            clip = motion(run, shot, frame, cfg, ledger)
            if clip:
                return {"kind": "clip", "src": str(clip), "duration": clip_seconds(clip)}
            log(f"  shot {shot['id']}: no usable motion - parallax still instead")
        depth_map = depth(run, frame, cfg, ledger)
        return {"kind": "still", "src": str(frame), "depth": str(depth_map) if depth_map else None}
    except Exception as error:  # noqa: BLE001 - one lost shot must not cost the video
        log(f"  shot {shot['id']}: failed ({error}) - the previous shot will hold")
        if "locked" in str(error).lower() or "403" in str(error):
            ledger.append(0.0)
            shot["_account_blocked"] = True
        return None


def build_for_run(run: Run, until_seconds: float | None = None) -> dict:
    cfg = load_config()["visuals"]
    if not has_secret("FAL_KEY"):
        raise RuntimeError("FAL_KEY is not set - AI visuals are most of the video. See SETUP.md.")

    look = run.read_json("look.json")
    stock = run.read_json("stock.json")
    shots = run.read_json("storyboard.json")["shots"]
    if until_seconds is not None:
        shots = [s for s in shots if s["start"] < until_seconds]

    # Stock shots the libraries couldn't fill are generated like any AI shot.
    shots = [{**s, "kind": "ai", "priority": 3} if s["kind"] == "stock" and str(s["id"]) not in stock
             else s for s in shots]
    # Keep what an earlier run already built (and checked) - a rerun after a
    # failure or a prompt tweak only generates the shots that are still missing.
    previous = run.read_json("visuals.json") if run.path("visuals.json").exists() else {}
    # Only if it was made for the same shot: a re-planned storyboard reuses ids.
    by_id = {str(s["id"]): s for s in shots}
    kept = {sid: a for sid, a in previous.items()
            if Path(a["src"]).exists() and sid in by_id and a.get("for") == by_id[sid].get("image_prompt")}
    todo = [s for s in shots if s["kind"] in ("ai", "card") and str(s["id"]) not in kept]

    animate, estimate = allocate(shots, cfg)
    spent_before = run.state().get("visuals_spend_usd", 0.0)
    log(f"Visuals: {len(kept)} already built, {len(todo)} to generate, {len(animate)} animated, "
        f"estimated ${estimate:.2f} of ${cfg['budget_usd']} budget "
        f"(${spent_before:.2f} already spent on this video; cached files are free)")
    if spent_before >= cfg["budget_usd"]:
        log("  budget already used - anything not cached is generated as a still, no new motion")

    ledger: list[float] = []
    with ThreadPoolExecutor(WORKERS) as pool:
        results = pool.map(
            lambda s: build_shot(run, s, s["id"] in animate, look, cfg, ledger, spent_before), todo)
        assets = {**kept, **{str(s["id"]): {**r, "for": s.get("image_prompt")} for s, r in zip(todo, results) if r}}

    run.write_json("visuals.json", assets)
    spent = round(sum(ledger), 2)
    run.save_state(visuals_spend_usd=round(run.state().get("visuals_spend_usd", 0) + spent, 2))
    blocked = sum(1 for s in todo if s.get("_account_blocked"))
    if blocked:
        # Everything that did succeed is cached, so a rerun after topping up only pays for these.
        raise RuntimeError(
            f"fal.ai refused {blocked} shot(s) (403 / account locked - usually an empty balance). "
            "Top up at fal.ai/dashboard/billing, then rerun this stage."
        )
    if until_seconds is None:
        run.mark_done("visuals")

    kinds = [a["kind"] for a in assets.values()]
    log(f"Visuals done: {kinds.count('clip')} clips, {kinds.count('still')} stills, "
        f"{kinds.count('plate')} card plates; {len(todo) + len(kept) - len(assets)} lost; "
        f"spent ${spent:.2f} this run (cache hits are free)")
    return assets


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate the AI visuals.")
    parser.add_argument("--run", default="latest")
    parser.add_argument("--until-seconds", type=float, default=None,
                        help="Only generate shots that start before this time (cheap pilots).")
    args = parser.parse_args()

    build_for_run(resolve_run(args.run), args.until_seconds)
