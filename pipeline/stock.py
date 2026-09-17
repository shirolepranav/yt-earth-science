"""STAGE 7 - Stock footage, found by what the narration actually says.

Real footage is most of the video, so a clip that's merely "about housing" isn't
good enough - it has to show what is being said at that second. For every stock
shot in storyboard.json:

  1. Gather   - run each of the shot's (up to three) searches on Pexels and
                Pixabay, pooling up to 16 candidates. Free, no downloads yet.
  2. Filter   - landscape, >=1280px wide, not a flash, not AI-generated or
                flagged low quality, never used before in this video or
                anywhere else on the channel.
  3. Rank     - one vision call per shot: a contact sheet of every candidate
                (frames from start, middle and end of each clip) next to the
                exact words spoken during the shot and what it must show. Each
                candidate is scored 0-10; watermarks, logos, on-screen charts or
                numbers, and glossy corporate stock are hard rejects.
  4. Fill     - the best clips scoring at least MIN_SCORE, one after another,
                until they cover the shot. Short relevant clips beat a long
                generated one. Coming up short, a model writes three fresh
                searches and steps 1-3 run again.
  5. Download - only the chosen clips.

Rate limits are waited out, never turned into AI shots: Pexels allows 200
searches an hour, so when a library says "too many requests" every search
pauses (Pexels: re-checked every 10 minutes, up to 75; Pixabay: its own reset
time) and carries on. Only a Pexels limit that outlasts a whole hour - the
monthly quota - lets that search come back empty.

Only a shot the libraries truly can't show (under MIN_COVERAGE of it covered
even after the second round) is left out of stock.json, and the visuals stage
generates it as an AI shot instead - so a thin library never leaves a gap.

Run it:  python -m pipeline.stock --run latest
"""

from __future__ import annotations

import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from .common import RUNS_DIR, Run, has_secret, log, resolve_run, secret, with_retries
from .llm import chat_json, vision_check

CANDIDATES = 16       # per shot, across all its searches
PER_QUERY = 30        # results asked for per search, per library
MIN_SCORE = 6         # below this a generated shot is the better choice
MIN_CLIP_SECONDS = 1.5  # shorter is a flash, not a shot
MIN_COVERAGE = 0.6    # clips covering this much of a shot are slowed to fill it (>= 0.6x)
SINGLE_CLIP_TOLERANCE = 1.0  # points of score worth giving up to hold one clip instead of cutting
RATE_LIMIT_STEP = 600          # Pexels sends no reset time with a 429 - look again every 10 minutes
RATE_LIMIT_MAX_WAIT = 75 * 60  # past a whole hour it's the monthly quota, and waiting won't help
WORKERS = 4
# Ranking a sheet of clips needs more judgement than Flash-Lite. 3.8 Flash is
# ~4x cheaper per sheet than 3.5 Flash ($0.007 vs $0.029, 15 Sep 2026), chosen
# to cut costs. In a 10-sheet A/B it was a little less discerning (one unrelated
# clip passed, one good clip missed) - switch back to "gemini-3.5-flash" here
# if footage relevance slips. See DECISIONS.md.
RANK_MODEL = "gemini-3.8-flash"
USED_REGISTRY = RUNS_DIR / "stock_used.json"  # every clip the channel has ever used

RANK_PROMPT = """You are choosing real stock footage for one shot of a dark, investigative finance documentary.

Narration spoken during this shot: "{spoken}"
What the shot must show: {intent}

The image is a contact sheet. Each numbered row is one candidate clip, shown as three frames (start, middle, end).
Score EVERY candidate from 0 to 10 for how well it shows what this moment of narration needs.
Score 0 (reject) for: a watermark or logo; charts, graphs, tickers or numbers on screens or paper; readable brand names;
glossy corporate stock (smiling people in bright offices, handshakes, thumbs-up); vertical or letterboxed footage; anything unrelated.
Tone matters as much as subject: this is an ominous documentary. Bright, cheerful, airy or sunny footage, and people
smiling or looking relaxed, scores AT MOST 4 even if the subject matches. Prefer real, candid, cinematic footage -
dim, moody or night-time light, tension, solitude - that would sit well in a dark documentary.

Reply as JSON only: {{"scores": [{{"n": 1, "score": 7, "why": "few words"}}]}}"""


# ---------------------------------------------------------------------------
# Libraries - both return the same candidate shape
# ---------------------------------------------------------------------------

_paused_until: dict[str, float] = {}  # library -> time searches may resume, shared by all workers
_pause_lock = threading.Lock()


def library_get(library: str, url: str, **kwargs) -> requests.Response:
    """GET a stock library API, waiting out its rate limit rather than giving up:
    an empty search turns shots into AI generations, and waiting costs nothing."""
    waited = 0.0
    while True:
        with _pause_lock:
            delay = _paused_until.get(library, 0.0) - time.time()
        if delay > 0:
            time.sleep(delay)
            waited += delay

        def get() -> requests.Response:
            response = requests.get(url, timeout=60, **kwargs)
            if response.status_code != 429:
                response.raise_for_status()  # inside with_retries, which redacts Pixabay's key from errors
            return response

        response = with_retries(get, label=library)
        if response.status_code != 429:
            return response
        if waited >= RATE_LIMIT_MAX_WAIT:
            raise RuntimeError(f"{library} is still rate-limited after {waited / 60:.0f} minutes "
                               "- probably the monthly quota")
        pause = float(response.headers.get("X-RateLimit-Reset") or RATE_LIMIT_STEP) + 1
        with _pause_lock:
            if _paused_until.get(library, 0.0) <= time.time():
                _paused_until[library] = time.time() + pause
                log(f"  {library} rate limit reached - pausing its searches for {pause / 60:.0f} min "
                    "instead of generating AI shots")


def search_pexels(query: str, count: int = PER_QUERY) -> list[dict]:
    try:
        videos = library_get(
            "pexels", "https://api.pexels.com/videos/search",
            headers={"Authorization": secret("PEXELS_API_KEY")},
            params={"query": query, "per_page": count, "orientation": "landscape", "size": "medium"},
        ).json().get("videos", [])
    except Exception as error:  # noqa: BLE001
        log(f"  pexels failed for '{query}': {error}")
        return []
    results = []
    for video in videos:
        pictures = [p["picture"] for p in sorted(video.get("video_pictures", []), key=lambda p: p.get("nr", 0))]
        results.append({
            "id": f"pexels-{video['id']}",
            "duration": video.get("duration", 0),
            "files": [{"width": f.get("width") or 0, "height": f.get("height") or 0, "url": f.get("link")}
                      for f in video.get("video_files", []) if f.get("link")],
            # start, middle, end - enough to see what the clip actually does
            "frames": [pictures[0], pictures[len(pictures) // 2], pictures[-1]] if pictures else [video.get("image")],
            "page": video.get("url", ""),
        })
    return results


def search_pixabay(query: str, count: int = PER_QUERY) -> list[dict]:
    if not has_secret("PIXABAY_API_KEY"):
        return []

    try:
        hits = library_get(
            "pixabay", "https://pixabay.com/api/videos/",
            params={"key": secret("PIXABAY_API_KEY"), "q": query, "per_page": count, "video_type": "film"},
        ).json().get("hits", [])
    except Exception as error:  # noqa: BLE001
        log(f"  pixabay failed for '{query}': {error}")
        return []
    results = []
    for hit in hits:
        if hit.get("isAiGenerated") or hit.get("isLowQuality"):
            continue  # the point of stock is real, human-shot footage
        sizes = (hit.get("videos") or {}).values()
        thumbnail = next((v.get("thumbnail") for v in sizes if v.get("thumbnail")), None)
        results.append({
            "id": f"pixabay-{hit['id']}",
            "duration": hit.get("duration", 0),
            "files": [{"width": v.get("width", 0), "height": v.get("height", 0), "url": v.get("url")}
                      for v in sizes if v.get("url")],
            "frames": [thumbnail] if thumbnail else [],
            "page": hit.get("pageURL", ""),
        })
    return results


def pick_best_file(video: dict, min_width: int = 1280, max_width: int = 1920) -> dict | None:
    """Largest landscape file that isn't bigger than 1080p needs."""
    landscape = [f for f in video["files"] if f["width"] >= min_width and f["width"] > f["height"]]
    if not landscape:
        return None
    within = [f for f in landscape if f["width"] <= max_width]
    return max(within or landscape, key=lambda f: f["width"])


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def contact_sheet(candidates: list[dict], path: Path) -> None:
    """One row per candidate: its number, then three frames."""
    tile_w, tile_h, label_w = 240, 135, 44
    sheet = Image.new("RGB", (label_w + tile_w * 3, tile_h * len(candidates)), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    for row, candidate in enumerate(candidates):
        y = row * tile_h
        draw.text((10, y + tile_h // 2 - 6), str(row + 1), fill=(255, 220, 0))
        frames = (candidate["frames"] * 3)[:3] if candidate["frames"] else []
        for col, url in enumerate(frames):
            try:
                raw = requests.get(url, timeout=30)
                raw.raise_for_status()
                tile = Image.open(io.BytesIO(raw.content)).convert("RGB")
                tile.thumbnail((tile_w, tile_h))
                sheet.paste(tile, (label_w + col * tile_w, y))
            except Exception:  # noqa: BLE001 - a missing frame just shows as dark
                pass
    sheet.save(path, "JPEG", quality=85)


def rank(candidates: list[dict], spoken: str, intent: str, sheet_path: Path) -> list[tuple[float, dict]]:
    """(score, candidate) best first. Without a vision key, keep search order."""
    if not has_secret("GEMINI_API_KEY"):
        return [(MIN_SCORE, c) for c in candidates]
    contact_sheet(candidates, sheet_path)
    try:
        verdict = vision_check(str(sheet_path), RANK_PROMPT.format(spoken=spoken, intent=intent or "fits the narration"),
                               model=RANK_MODEL)
        scores = {int(s["n"]): (float(s.get("score", 0)), s.get("why", "")) for s in verdict.get("scores", [])}
    except Exception as error:  # noqa: BLE001
        log(f"    ranking failed ({error}) - keeping search order")
        return [(MIN_SCORE, c) for c in candidates]
    finally:
        sheet_path.unlink(missing_ok=True)
    ranked = []
    for n, candidate in enumerate(candidates, 1):
        score, why = scores.get(n, (0.0, "not scored"))
        ranked.append((score, {**candidate, "why": why}))
    return sorted(ranked, key=lambda pair: pair[0], reverse=True)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def download(url: str, path: Path) -> bool:
    try:
        with requests.get(url, stream=True, timeout=300) as response:
            response.raise_for_status()
            with path.open("wb") as handle:
                for block in response.iter_content(chunk_size=1 << 16):
                    handle.write(block)
        return path.stat().st_size > 10_000
    except Exception as error:  # noqa: BLE001
        log(f"    download failed: {error}")
        path.unlink(missing_ok=True)
        return False


def spoken_during(words: list[dict], start: float, end: float) -> str:
    """The words heard during the shot, with a little lead-in for context."""
    return " ".join(w["word"] for w in words if start - 1.5 <= w["start"] < end)


def gather(queries: list[str], used: set[str], lock: threading.Lock, seen: set[str]) -> list[dict]:
    """Up to CANDIDATES fresh clips across the searches, round-robin so one
    query can't crowd out the others."""
    pool: dict[str, dict] = {}
    per_query = [search_pexels(q) + search_pixabay(q) for q in queries]
    for tier in range(PER_QUERY * 2):
        for results in per_query:
            if tier < len(results):
                candidate = results[tier]
                with lock:
                    fresh = candidate["id"] not in used
                if (fresh and candidate["id"] not in pool and candidate["id"] not in seen
                        and candidate["duration"] >= MIN_CLIP_SECONDS
                        and candidate["frames"] and pick_best_file(candidate)):
                    pool[candidate["id"]] = candidate
        if len(pool) >= CANDIDATES:
            break
    return list(pool.values())[:CANDIDATES]


def fill(ranked: list[tuple[float, dict]], length: float, claim=lambda candidate: True) -> list[dict]:
    """Best clips first, scoring at least MIN_SCORE, until they cover `length`.

    One clip held through the whole shot beats two cut together, so a clip long
    enough to cover it on its own is tried first, from within
    SINGLE_CLIP_TOLERANCE of the top score. `claim` returns False for a clip
    another shot took first (shots run in parallel and share searches) - the
    next best clip is used instead of leaving the shot to be generated."""
    usable = [(score, c) for score, c in ranked if score >= MIN_SCORE]
    if not usable:
        return []
    covering = [(score, c) for score, c in usable
                if c["duration"] >= length and score >= usable[0][0] - SINGLE_CLIP_TOLERANCE]
    order = covering[:1] + [pair for pair in usable if pair not in covering[:1]]
    chosen, covered = [], 0.0
    for score, candidate in order:
        if covered >= length:
            break
        if not claim(candidate):
            continue
        chosen.append({**candidate, "score": score})
        covered += candidate["duration"]
    return chosen


def fresh_queries(spoken: str, intent: str, tried: list[str]) -> list[str]:
    """Three new searches when the first ones didn't find enough footage."""
    try:
        reply = chat_json(
            "You find footage in stock video libraries. Reply with JSON only.",
            f'Narration: "{spoken}"\nThe shot must show: {intent or "what the narration describes"}\n'
            f"These searches on Pexels and Pixabay found too little usable footage: {tried}\n\n"
            "Write three DIFFERENT searches (two to five plain, concrete, visual words each) that a stock "
            "library is likely to have and that would still fit this moment - try simpler subjects, other "
            "settings, or a related action. No charts, numbers, screens, illustrations or brand names.\n"
            'Reply as JSON: {"queries": ["...", "...", "..."]}',
            label="stock search rewrite",
        )
    except Exception as error:  # noqa: BLE001
        log(f"    search rewrite failed ({error})")
        return []
    return [q.strip() for q in reply.get("queries", []) if isinstance(q, str) and q.strip() and q not in tried][:3]


def fetch_for_shot(run: Run, shot: dict, words: list[dict], used: set[str], lock: threading.Lock) -> dict | None:
    length = shot["end"] - shot["start"]
    queries = shot.get("queries") or [q for q in (shot.get("query"), shot.get("fallback_query")) if q]
    spoken = spoken_during(words, shot["start"], shot["end"])
    intent = shot.get("intent", "")
    sheet = run.path("assets", f"_sheet_{shot['id']}.jpg")

    def claim(candidate: dict) -> bool:
        """Take a clip for this shot, unless a parallel shot got there first."""
        with lock:
            if candidate["id"] in used:
                return False
            used.add(candidate["id"])
            return True

    candidates = gather(queries, used, lock, set())
    ranked = rank(candidates, spoken, intent, sheet) if candidates else []
    picks = fill(ranked, length, claim)
    if sum(c["duration"] for c in picks) < length:
        # Not enough good footage yet - search differently before settling.
        extra = fresh_queries(spoken, intent, queries)
        more = gather(extra, used, lock, {c["id"] for c in candidates}) if extra else []
        if more:
            ranked = sorted(ranked + rank(more, spoken, intent, sheet), key=lambda pair: pair[0], reverse=True)
            already = {c["id"] for c in picks}
            picks += fill([pair for pair in ranked if pair[1]["id"] not in already],
                          length - sum(c["duration"] for c in picks), claim)
            queries = queries + extra

    clips = []
    for candidate in picks:  # already claimed by fill()
        path = run.path("assets", f"stock_{shot['id']:03d}_{len(clips)}_{candidate['id']}.mp4")
        if download(pick_best_file(candidate)["url"], path):
            clips.append({"id": candidate["id"], "path": str(path), "duration": candidate["duration"],
                          "score": candidate["score"], "page": candidate["page"]})

    covered = sum(c["duration"] for c in clips)
    if covered < MIN_COVERAGE * length:
        for clip in clips:
            Path(clip["path"]).unlink(missing_ok=True)
        best = ranked[0][0] if ranked else 0
        log(f"  shot {shot['id']}: only {covered:.1f}s of {length:.1f}s found (best {best:.0f}/10) "
            f"for {queries} - it will be generated instead")
        return None
    log(f"  shot {shot['id']}: {len(clips)} clip(s), {covered:.1f}s for {length:.1f}s - "
        + "; ".join(f"{c['score']:.0f}/10 {c['id']}" for c in clips))
    return {"query": queries[0], "clips": clips}


def build_for_run(run: Run) -> dict:
    shots = [s for s in run.read_json("storyboard.json")["shots"] if s["kind"] == "stock"]
    words = run.read_json("words.json")["words"]
    registry = json.loads(USED_REGISTRY.read_text()) if USED_REGISTRY.exists() else {}
    # Never the same clip twice - in this video or anywhere else on the channel.
    # Repeated footage across uploads is exactly what reads as mass-produced.
    used = {clip for run_id, clips in registry.items() if run_id != run.id for clip in clips}
    lock = threading.Lock()

    log(f"Finding {len(shots)} stock clips ({len(used)} already used on the channel)")
    with ThreadPoolExecutor(WORKERS) as pool:
        results = pool.map(lambda s: fetch_for_shot(run, s, words, used, lock), shots)
        clips = {str(s["id"]): r for s, r in zip(shots, results) if r}

    run.write_json("stock.json", clips)
    registry[run.id] = sorted(c["id"] for entry in clips.values() for c in entry["clips"])
    USED_REGISTRY.write_text(json.dumps(registry, indent=1))
    run.mark_done("stock")
    scores = [c["score"] for entry in clips.values() for c in entry["clips"]]
    log(f"Filled {len(clips)}/{len(shots)} shots with {len(scores)} clips (average score {sum(scores) / max(1, len(scores)):.1f}/10) "
        "- the rest become AI shots")
    return clips


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Find, rank and fetch stock footage.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    build_for_run(resolve_run(args.run))
