"""STAGE 7 - Real footage and photographs, found by what the narration actually says.

Four libraries, searched together and ranked on one contact sheet: NASA's Image
and Video Library and Wikimedia Commons (public domain / CC0 / CC BY only - the
actual volcano, not a metaphor for it, with credits kept for the description),
then Pexels and Pixabay. A chosen photograph holds the whole shot as a parallax
still.

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

import html
import io
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from PIL import Image, ImageDraw, ImageOps

from .common import RUNS_DIR, Run, has_secret, load_config, log, resolve_run, secret, with_retries
from .llm import chat_json, has_vision, vision_check
from .storyboard import MAX_FOOTAGE_SECONDS
from .visuals import depth

CANDIDATES = 20       # per shot, across all its searches and all four libraries
PER_QUERY = 30        # results asked for per search, per library
MIN_SCORE = 6         # below this a generated shot is the better choice
MIN_CLIP_SECONDS = 1.5  # shorter is a flash, not a shot
MIN_COVERAGE = 0.6    # clips covering this much of a shot are slowed to fill it (>= 0.6x)
# A clip may come back once, far enough away that nobody reads it as a repeat.
# A single-subject documentary (one volcano) has only a handful of clips of the
# real thing, and the first shots claimed them all, leaving later ones to AI.
MAX_USES_PER_VIDEO = 2
REUSE_GAP_SECONDS = 150.0
SINGLE_CLIP_TOLERANCE = 1.0  # points of score worth giving up to hold one clip instead of cutting
RATE_LIMIT_STEP = 600          # Pexels sends no reset time with a 429 - look again every 10 minutes
# Wikimedia's anonymous search quota is tight and counted per unit time: four
# workers searching at once drew a 429 five seconds in, and even one at a time
# a second apart broke after six. Twelve searches five seconds apart ran clean
# (measured 19 Sep 2026), so Commons gets one search every COMMONS_INTERVAL
# seconds across all workers - and a shot that would have to wait longer than
# COMMONS_MAX_WAIT for its turn skips Commons rather than stalling the stage,
# since NASA, Pexels and Pixabay are still searching for it.
COMMONS_PAUSE = 60
COMMONS_INTERVAL = 5.0
COMMONS_MAX_WAIT = 20.0
_commons_slot = [0.0]
RATE_LIMIT_MAX_WAIT = 75 * 60  # past a whole hour it's the monthly quota, and waiting won't help
WORKERS = 4
# None means the configured vision model (models.vision in config/channel.json,
# gpt-5.4-mini since 19 Sep 2026). Set a model id here to rank on a different
# one than the other vision checks use. See DECISIONS.md.
RANK_MODEL = None
USED_REGISTRY = RUNS_DIR / "stock_used.json"  # every clip the channel has ever used
NASA_VIDEOS_PER_QUERY = 8  # per search; each video costs one extra request for its length and size
USER_AGENT = "DeepEarth-pipeline/1.0 (automated documentary footage search)"  # Wikimedia requires one

RANK_PROMPT = """You are choosing real footage for one shot of a cinematic Earth science documentary.

Narration spoken during this shot: "{spoken}"
What the shot must show: {intent}

The image is a contact sheet. Each numbered row is one candidate clip, shown as three frames (start, middle, end).
A row showing one frame three times is a still photograph, or a clip with a single preview - judge it the same way.
Some rows are still photographs (the same image three times) - judge those exactly like clips.
Score EVERY candidate from 0 to 10 for how well it shows what this moment of narration needs.
Score 0 (reject) for: a watermark or logo; charts, graphs, tickers or numbers on screens or paper; readable brand names;
glossy lifestyle stock (smiling people posing, tourists taking selfies); vertical or letterboxed footage; illustrations,
renders or CGI presented as real; anything unrelated.
Accuracy matters more than mood: footage of the ACTUAL phenomenon, rock, landform or place named in the narration
beats a pretty but generic landscape. A named place shown by a different volcano, glacier or fault scores AT MOST 5,
unless the narration is speaking generally.
Some subjects cannot be filmed at all - a pressure wave, an aerosol layer, a measurement, a process inside the Earth,
anything in deep time. When "what the shot must show" describes something like that, judge how well the footage stands
in for it instead: honest, real footage of the right setting, material or scale (the sky it happened in, the ocean it
crossed, the instrument that recorded it) is a GOOD shot and can score 7 or 8. Reserve low scores for footage that
would mislead the viewer or has nothing to do with the moment. Scientific photos, field and aerial survey footage and satellite imagery
are welcome; prefer sharp, well-exposed, cinematic material.

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
        pause = float(response.headers.get("Retry-After")
                      or response.headers.get("X-RateLimit-Reset")
                      or (COMMONS_PAUSE if library == "commons" else RATE_LIMIT_STEP)) + 1
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


# ---------------------------------------------------------------------------
# Public-domain and openly licensed libraries - the real thing, not a metaphor
# ---------------------------------------------------------------------------

def media_seconds(value) -> float:
    """'0:05:27', '23.84 s' or '12.5 s (approx)' -> seconds."""
    match = re.search(r"[\d:.]+", str(value or ""))
    try:
        parts = [float(p) for p in match.group().split(":")] if match else []
    except ValueError:
        return 0.0
    return sum(part * 60 ** i for i, part in enumerate(reversed(parts)))


def license_ok(code: str) -> bool:
    """Public domain, CC0 and CC BY only. Share-alike could bind the whole video
    to its licence, and NC/ND forbid a monetised edit."""
    code = (code or "").lower()
    if code.startswith("pd") or code == "cc0":
        return True
    return code.startswith("cc-by-") and not any(tag in code for tag in ("-sa", "-nc", "-nd"))


def search_nasa(query: str, count: int = PER_QUERY) -> list[dict]:
    """NASA Image and Video Library: no key, and satellite, aerial and field
    imagery of the actual event. Images and videos are searched separately -
    mixed, the images crowd the videos out of the first page."""
    results = []
    for media, size in (("image", count // 2), ("video", NASA_VIDEOS_PER_QUERY)):
        try:
            items = library_get(
                "nasa", "https://images-api.nasa.gov/search",
                params={"q": query, "media_type": media, "page_size": size},
            ).json()["collection"]["items"]
        except Exception as error:  # noqa: BLE001
            log(f"  nasa failed for '{query}': {error}")
            continue
        for item in items:
            data, links = item["data"][0], item.get("links", [])
            nasa_id = data["nasa_id"]
            base = {
                "id": f"nasa-{nasa_id}",
                "media": media,
                "page": f"https://images.nasa.gov/details/{quote(nasa_id)}",
                "credit": data.get("photographer") or data.get("secondary_creator") or f"NASA {data.get('center', '')}".strip(),
                "license": "NASA media (public domain)",
            }
            if media == "image":
                results.append({**base, "duration": MAX_FOOTAGE_SECONDS,
                                "frames": [l["href"] for l in links if l.get("rel") == "preview"],
                                "files": [{"width": l.get("width") or 0, "height": l.get("height") or 0, "url": l["href"]}
                                          for l in links if l.get("rel") != "preview"]})
                continue
            root = f"https://images-assets.nasa.gov/video/{quote(nasa_id)}"
            try:
                meta = library_get("nasa", f"{root}/metadata.json").json()
            except Exception:  # noqa: BLE001 - one unreadable video just isn't a candidate
                continue
            width, height = int(meta.get("QuickTime:ImageWidth") or 0), int(meta.get("QuickTime:ImageHeight") or 0)
            # ~large.mp4 is NASA's 1080p encode, a third the size of ~orig (204 vs 653 MB for a 5-minute
            # 1080p original, 17 Sep 2026). The whole file downloads though only a shot's length plays.
            results.append({**base,
                            "duration": media_seconds(meta.get("QuickTime:Duration") or meta.get("Composite:Duration")),
                            "files": [{"width": min(width, 1920), "height": round(height * min(1, 1920 / max(width, 1))),
                                       "url": f"{root}/{quote(nasa_id)}~large.mp4"}],
                            "frames": [f"{root}/{quote(nasa_id)}~large_{n}.jpg" for n in (1, 3, 5)]})
    return results


def _credit(artist) -> str:
    """The uploader's name, stripped of Commons' markup. Some files carry no
    artist at all, and the API can send that as the string "null"."""
    text = re.sub(r"\[\d+\]", "", html.unescape(re.sub(r"<[^>]+>", "", str(artist or ""))))
    # Derivative works list every source file ("Sarychev.jpg: NASA\nderivative: User"),
    # and the credit has one line in the corner of the shot.
    text = re.sub(r"^[^\n:]+\.(jpg|jpeg|png|tif|tiff|webm|ogv|gif):\s*", "", text.strip(), flags=re.I)
    text = re.sub(r"\s+", " ", text.split("\n")[0]).strip(" ,;:-")
    if len(text) > 60:
        text = text[:57].rsplit(" ", 1)[0] + "..."
    return "Wikimedia Commons" if text.lower() in ("", "null", "none", "unknown") else text


def _commons_turn() -> bool:
    """Take the next Commons search slot, or give up if the queue is too long."""
    with _pause_lock:
        wait = _commons_slot[0] - time.time()
        if wait > COMMONS_MAX_WAIT:
            return False
        _commons_slot[0] = max(time.time(), _commons_slot[0]) + COMMONS_INTERVAL
    if wait > 0:
        time.sleep(wait)
    return True


def search_commons(query: str, count: int = PER_QUERY) -> list[dict]:
    """Wikimedia Commons, keeping only files whose licence allows this use
    (see license_ok). Holds much of USGS's public-domain photography.

    Video and images come back in one request: the quota is per request, not
    per result."""
    if not _commons_turn():
        return []
    try:
        pages = library_get(
            "commons", "https://commons.wikimedia.org/w/api.php",
            headers={"User-Agent": USER_AGENT},
            params={"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                    "gsrsearch": f"{query} filetype:video|bitmap", "gsrlimit": count,
                    "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1920,
                    "iiextmetadatafilter": "License|LicenseShortName|Artist"},
        ).json().get("query", {}).get("pages", {})
    except Exception as error:  # noqa: BLE001
        log(f"  commons failed for '{query}': {error}")
        return []
    results = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        if not info.get("url") or not license_ok(meta.get("License", {}).get("value", "")):
            continue
        video = not str(info.get("mime", "")).startswith("image/")
        # ponytail: videos download the original file (up to 4K webm); use Commons' 1080p transcode if renders get slow
        file = ({"width": info.get("width", 0), "height": info.get("height", 0), "url": info["url"]} if video else
                {"width": info.get("thumbwidth", 0), "height": info.get("thumbheight", 0),
                 "url": info.get("thumburl") or info["url"]})
        results.append({
            "id": f"commons-{page['pageid']}",
            "media": "video" if video else "image",
            "duration": info.get("duration", 0) if video else MAX_FOOTAGE_SECONDS,
            "files": [file],
            "frames": [info["thumburl"]] if info.get("thumburl") else [],
            "page": info.get("descriptionurl", ""),
            "credit": _credit(meta.get("Artist", {}).get("value")),
            "license": meta.get("LicenseShortName", {}).get("value", ""),
        })
    return results


def pick_best_file(video: dict, min_width: int = 1280, max_width: int = 1920) -> dict | None:
    """Largest landscape file that isn't bigger than 1080p needs, else the smallest one that is."""
    landscape = [f for f in video["files"] if f["width"] >= min_width and f["width"] > f["height"]]
    if not landscape:
        return None
    within = [f for f in landscape if f["width"] <= max_width]
    return max(within, key=lambda f: f["width"]) if within else min(landscape, key=lambda f: f["width"])


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
                raw = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
                raw.raise_for_status()
                tile = Image.open(io.BytesIO(raw.content)).convert("RGB")
                tile.thumbnail((tile_w, tile_h))
                sheet.paste(tile, (label_w + col * tile_w, y))
            except Exception:  # noqa: BLE001 - a missing frame just shows as dark
                pass
    sheet.save(path, "JPEG", quality=85)


def rank(candidates: list[dict], spoken: str, intent: str, sheet_path: Path) -> list[tuple[float, dict]]:
    """(score, candidate) best first. Without a vision key, keep search order."""
    if not has_vision():
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
        with requests.get(url, stream=True, timeout=300, headers={"User-Agent": USER_AGENT}) as response:
            response.raise_for_status()
            with path.open("wb") as handle:
                for block in response.iter_content(chunk_size=1 << 16):
                    handle.write(block)
        return path.stat().st_size > 10_000
    except Exception as error:  # noqa: BLE001
        log(f"    download failed: {error}")
        path.unlink(missing_ok=True)
        return False


def on_screen_credit(candidate: dict) -> str | None:
    """The line shown in the corner of the shot, for archives whose whole point
    is that the footage is real and checkable. Pexels and Pixabay ask for no
    credit and naming them adds nothing, so they get none."""
    credit, library = candidate.get("credit") or "", candidate["id"].split("-")[0]
    if library == "nasa":
        return credit if credit.upper().startswith("NASA") else f"NASA / {credit}" if credit else "NASA"
    if library == "commons":
        licence = candidate.get("license") or ""
        who = credit if credit and credit != "Wikimedia Commons" else "Wikimedia Commons"
        return f"{who} / Wikimedia Commons ({licence})".replace(" ()", "") if who != "Wikimedia Commons" \
            else f"Wikimedia Commons ({licence})".replace(" ()", "")
    return None


def prepare_photo(run: Run, path: Path) -> dict:
    """A photograph as a 1920x1080 frame (centre-cropped, so the parallax plane
    isn't stretched) plus a depth map for a slow parallax move (~$0.005 on
    fal.ai; without one it gets a plain push-in)."""
    frame = path.with_suffix(".jpg")
    ImageOps.fit(Image.open(path).convert("RGB"), (1920, 1080)).save(frame, "JPEG", quality=92)
    if frame != path:
        path.unlink(missing_ok=True)
    depth_map = depth(run, frame, load_config()["visuals"], []) if has_secret("FAL_KEY") else None
    return {"path": str(frame), "depth": str(depth_map) if depth_map else None}


def spoken_during(words: list[dict], start: float, end: float) -> str:
    """The words heard during the shot, with a little lead-in for context."""
    return " ".join(w["word"] for w in words if start - 1.5 <= w["start"] < end)


def gather(queries: list[str], used: set[str], lock: threading.Lock, seen: set[str]) -> list[dict]:
    """Up to CANDIDATES fresh clips across the searches, round-robin so one
    query can't crowd out the others."""
    pool: dict[str, dict] = {}
    # The public-domain archives first - footage of the actual thing - with stock filling what's left.
    # Commons is searched once per shot, not once per query: its quota is the
    # scarce one, and its results rarely differ much between a shot's queries.
    per_query = [search_nasa(q) + (search_commons(q) if i == 0 else []) + search_pexels(q) + search_pixabay(q)
                 for i, q in enumerate(queries)]
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
            f"These searches on NASA, Wikimedia Commons, Pexels and Pixabay found too little usable footage: {tried}\n\n"
            "Write three DIFFERENT searches (two to five plain, concrete, visual words each) that a stock "
            "library is likely to have and that would still fit this moment - try the proper scientific name, the "
            "place name, simpler subjects, or a related landform. No charts, numbers, screens, illustrations or brand names.\n"
            'Reply as JSON: {"queries": ["...", "...", "..."]}',
            label="stock search rewrite",
        )
    except Exception as error:  # noqa: BLE001
        log(f"    search rewrite failed ({error})")
        return []
    return [q.strip() for q in reply.get("queries", []) if isinstance(q, str) and q.strip() and q not in tried][:3]


def fetch_for_shot(run: Run, shot: dict, words: list[dict], used: set[str], lock: threading.Lock,
                   claims: dict[str, list[float]] | None = None) -> dict | None:
    length = shot["end"] - shot["start"]
    queries = shot.get("queries") or [q for q in (shot.get("query"), shot.get("fallback_query")) if q]
    spoken = spoken_during(words, shot["start"], shot["end"])
    intent = shot.get("intent", "")
    sheet = run.path("assets", f"_sheet_{shot['id']}.jpg")
    claims = {} if claims is None else claims

    def claim(candidate: dict) -> bool:
        """Take a clip for this shot. A clip already used in this video comes
        back only once, and only REUSE_GAP_SECONDS away from where it played."""
        with lock:
            at = shot["start"]
            when = claims.get(candidate["id"], [])
            if len(when) >= MAX_USES_PER_VIDEO or any(abs(at - t) < REUSE_GAP_SECONDS for t in when):
                return False
            claims.setdefault(candidate["id"], []).append(at)
            return True

    with lock:  # clips from other videos, and ones this video has finished with
        spent = used | {cid for cid, when in claims.items() if len(when) >= MAX_USES_PER_VIDEO}
    candidates = gather(queries, spent, lock, set())
    ranked = rank(candidates, spoken, intent, sheet) if candidates else []
    picks = fill(ranked, length, claim)
    if sum(c["duration"] for c in picks) < length:
        # Not enough good footage yet - search differently before settling.
        extra = fresh_queries(spoken, intent, queries)
        more = gather(extra, spent, lock, {c["id"] for c in candidates}) if extra else []
        if more:
            ranked = sorted(ranked + rank(more, spoken, intent, sheet), key=lambda pair: pair[0], reverse=True)
            already = {c["id"] for c in picks}
            picks += fill([pair for pair in ranked if pair[1]["id"] not in already],
                          length - sum(c["duration"] for c in picks), claim)
            queries = queries + extra

    clips = []
    for candidate in picks:  # already claimed by fill()
        url = pick_best_file(candidate)["url"]
        ext = Path(urlparse(url).path).suffix.lower() or ".mp4"
        safe_id = re.sub(r"[^\w.-]", "_", candidate["id"])[:80]
        path = run.path("assets", f"stock_{shot['id']:03d}_{len(clips)}_{safe_id}{ext}")
        if download(url, path):
            clip = {"id": candidate["id"], "path": str(path), "duration": candidate["duration"],
                    "score": candidate["score"], "why": candidate.get("why"), "page": candidate["page"],
                    "media": candidate.get("media", "video"),
                    "credit": candidate.get("credit"), "license": candidate.get("license"),
                    "on_screen": on_screen_credit(candidate)}
            if clip["media"] == "image":
                try:
                    clip.update(prepare_photo(run, path))
                except Exception as error:  # noqa: BLE001 - an unreadable photo is just a lost candidate
                    log(f"    photo unusable ({error})")
                    continue
            clips.append(clip)

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

    claims: dict[str, list[float]] = {}  # clip id -> the shot times it plays at, this video
    log(f"Finding {len(shots)} stock clips ({len(used)} already used on the channel)")
    with ThreadPoolExecutor(WORKERS) as pool:
        results = pool.map(lambda s: fetch_for_shot(run, s, words, used, lock, claims), shots)
        clips = {str(s["id"]): r for s, r in zip(shots, results) if r}

    run.write_json("stock.json", clips)
    registry[run.id] = sorted({c["id"] for entry in clips.values() for c in entry["clips"]})
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
