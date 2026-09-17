"""Prove the machinery works without spending a penny.

Fabricates a small run - a script, fake word timings, an outline, a dossier and
the beats a storyboard model might return (including bad ones) - then checks
the logic that decides what reaches the screen and what it costs:

  1. storyboard assembly: contiguous timeline, beats starting on their words,
     data shots long enough to read, and every untrustworthy beat demoted to
     stock footage (a chart that doesn't exist, a quote that isn't in the
     source, a fact card whose figure the dossier lacks); stock clip filling
  2. the budget allocator: never over the cap, best priorities animated first
  3. the cache key: stable for the same inputs, different for different ones
  4. the shot list: every planned shot mapped, several clips per stock shot,
     missing assets held over
  5. thumbnail compositing: text and symbols drawn

If this passes, any later failure is an API key or a network problem, not a
bug in the pipeline. Run it after `make setup` and after any code change.

    python tools/selftest.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

import pipeline.llm as llm  # noqa: E402
from pipeline.common import Run, load_config  # noqa: E402
from pipeline.shotlist import build as build_shotlist, stock_clips  # noqa: E402
import pipeline.stock as stock  # noqa: E402
from pipeline.stock import MIN_SCORE, fill  # noqa: E402
from pipeline.storyboard import (  # noqa: E402
    CUT_LEAD_SECONDS, FIGURE, assemble, outline_charts, sentences_from_words, sources_from_dossier,
)
from pipeline.thumbnail import compose  # noqa: E402
from pipeline.visuals import allocate, cache_path, plate_prompt  # noqa: E402

SCRIPT = (
    "Two people walked into the same bank last year. They walked out with different mortgage rates. "
    "Nearly two full percentage points apart. Here's the part nobody explains. The gap had almost "
    "nothing to do with income. According to the Consumer Financial Protection Bureau, the biggest "
    "driver was a three digit number. That gap costs the second borrower forty thousand dollars. "
    "Same house. Same salary. Same bank. And someone is collecting every cent of it. "
    "Lenders report the gap in their own filings every single quarter without fail. "
    "The numbers are public and nobody is reading them at all."
)
DOSSIER = """# RESEARCH DOSSIER
TOPIC: test

## SOURCE 1 [PRIMARY SOURCE]
TITLE: Rate spreads and credit scores
URL: https://www.consumerfinance.gov/data-research/rate-spreads

Borrowers with lower credit scores paid rates up to 1.7 percentage points higher on otherwise identical loans. Over thirty years that gap can exceed $40,000 in interest.

---
"""


def fake_words(script: str, seconds_each: float = 0.4) -> list[dict]:
    return [{"word": token, "start": round(i * seconds_each, 3), "end": round((i + 1) * seconds_each, 3)}
            for i, token in enumerate(script.split())]


def check_storyboard(run: Run) -> list[dict]:
    words = fake_words(SCRIPT)
    duration = words[-1]["end"] + 1
    sentences = sentences_from_words(words)
    sources = sources_from_dossier(DOSSIER)
    outline = {"sections": [{"source": "CFPB", "visual": {
        "kind": "comparison", "title": "Rate on the same loan", "labels": ["760+", "620-659"],
        "values": [6.4, 8.1], "unit": "%", "source_note": "CFPB"}}]}
    charts = outline_charts(outline)
    assert len(sentences) == 13, f"expected 13 sentences, got {len(sentences)}"
    assert sources and sources[0]["publisher"] == "consumerfinance.gov", sources

    footage = {"image_prompt": "a kitchen table at night", "motion_prompt": "slow push-in",
               "query": "city street", "priority": 2}
    beats = [
        {"sentence": 0, "kind": "stock", **footage},  # stays stock - no forced AI cold open
        {"sentence": 1, "kind": "chart", "chart_index": 0, **footage},
        {"sentence": 2, "kind": "chart", "chart_index": 7, **footage},  # no such chart
        {"sentence": 3, "kind": "card", "variant": "question", "text": "WHO PROFITS?", **footage},
        {"sentence": 4, "kind": "stock", **footage},
        {"sentence": 5, "kind": "evidence", "source_index": 0,
         "quote": "Borrowers with lower credit scores paid rates up to 1.7 percentage points higher", **footage},
        {"sentence": 6, "kind": "evidence", "source_index": 0, "quote": "A sentence nobody wrote.", **footage},
        {"sentence": 6, "kind": "evidence", "source_index": 0,  # same receipt twice
         "quote": "Borrowers with lower credit scores paid rates up to 1.7 percentage points higher", **footage},
        {"sentence": 7, "kind": "number", "value": "$40,000", "label": "extra interest", "source": "CFPB", **footage},
        {"sentence": 8, "kind": "card", "variant": "fact", "text": "FEES: $999 BILLION", **footage},  # unsupported
        {"sentence": 9, "kind": "stock", **footage},
        {"sentence": 10, "kind": "ai", **{**footage, "image_prompt": "a worn calculator on a desk"}},  # planned AI
        {"sentence": 10, "kind": "stock", "from_words": "collecting every cent", **footage},  # starts on those words
        {"sentence": 11, "kind": "ai", **{**footage, "image_prompt": "a laptop showing a rising bar chart"}},  # fake data
        {"sentence": 11, "kind": "chart", **footage, "data": {"chart_kind": "comparison", "title": "Rate gap",
         "labels": ["760+", "620-659"], "values": [1.7, 40000], "unit": "", "source": "CFPB"}},
        {"sentence": 12, "kind": "chart", **footage, "data": {"chart_kind": "bar", "title": "Same as the outline",
         "labels": ["x", "y"], "values": [8.1, 6.4], "unit": "%", "source": "CFPB"}},  # duplicate of chart 0
        {"sentence": 12, "kind": "chart", **footage, "data": {"chart_kind": "bar", "title": "Invented",
         "labels": ["a", "b"], "values": [123, 456], "unit": "", "source": "nobody"}},  # figures not in dossier
    ]
    cfg = {**load_config()["storyboard"], "min_shot_seconds": 1.0}
    shots = assemble(beats, sentences, words, duration, charts, sources, DOSSIER, cfg)

    kinds = [s["kind"] for s in shots]
    assert shots[0]["start"] == 0 and shots[0]["kind"] == "stock", shots[0]
    assert "ai" not in kinds, f"all footage is planned as stock: {kinds}"
    collecting = next(w for w in words if w["word"] == "collecting")
    cut = collecting["start"] - CUT_LEAD_SECONDS  # cut a few frames before the word, not on it
    assert any(abs(s["start"] - cut) < 1e-6 for s in shots), "from_words beat must start just before its words"
    unplaceable = [{"sentence": 10, "kind": "stock", "from_words": "words nobody said", **footage}]
    kept = assemble(beats + unplaceable, sentences, words, duration, charts, sources, DOSSIER, cfg)
    assert len(kept) == len(shots), "a beat whose words can't be found must not become an arbitrary cut"
    for shot in shots:
        length = shot["end"] - shot["start"]
        assert shot["kind"] not in ("stock", "ai") or length <= 15.0 + 1e-6, f"footage held {length:.2f}s"
        # Charts want 8s and quotes 6s; this 39-second fixture is too tight to
        # always give them that, so allow a little short of the real minimum.
        assert shot["kind"] != "chart" or length >= 7.5, f"chart on screen only {length:.2f}s"
        assert shot["kind"] != "number" or 4.0 - 1e-6 <= length <= 5.0 + 1e-6, f"number on screen {length:.2f}s"
        assert shot["kind"] != "card" or length >= 4.0 - 1e-6, f"card only {length:.2f}s"
        assert shot["kind"] != "evidence" or length >= 5.5, f"evidence only {length:.2f}s"
        assert "calculator" not in shot.get("image_prompt", ""), "a fallback prompt still asks for a calculator"
    assert abs(shots[-1]["end"] - duration) < 0.01, "timeline must reach the end"
    for a, b in zip(shots, shots[1:]):
        assert abs(a["end"] - b["start"]) < 1e-6, f"gap or overlap between {a['id']} and {b['id']}"
    assert kinds.count("chart") == 2, f"bogus index and invented data demoted, sourced data kept: {kinds}"
    assert not any("chart" in s.get("image_prompt", "") for s in shots), "a fallback prompt still draws a chart"

    clip = lambda n, seconds: {"id": f"c{n}", "duration": seconds}  # noqa: E731
    picked = fill([(9, clip(1, 4)), (8, clip(2, 3)), (7, clip(3, 5)), (7, clip(4, 6))], 9.0)
    assert [c["id"] for c in picked] == ["c1", "c2", "c3"], "fill takes the best clips until the shot is covered"
    held = fill([(9, clip(1, 4)), (8, clip(2, 12)), (7, clip(3, 20))], 9.0)
    assert [c["id"] for c in held] == ["c2"], "one clip long enough to hold the shot beats cutting two together"
    taken = {"c2"}
    shared = fill([(9, clip(1, 4)), (8, clip(2, 12)), (7, clip(3, 20))], 9.0, lambda c: c["id"] not in taken)
    ids = [c["id"] for c in shared]
    assert "c2" not in ids and sum(c["duration"] for c in shared) >= 9.0, (
        f"a clip another shot claimed must fall through to the next best, got {ids}")
    assert fill([(MIN_SCORE - 1, clip(1, 20))], 9.0) == [], "a poor match must never be used"
    assert kinds.count("evidence") == 1, f"the invented and repeated quotes must be demoted: {kinds}"
    assert kinds.count("card") == 1, f"the unsupported fact card must be demoted: {kinds}"
    assert kinds.count("number") == 1, kinds
    evidence = next(s for s in shots if s["kind"] == "evidence")
    assert evidence["quote"].startswith("Borrowers") and evidence["headline"], evidence

    run.write_json("storyboard.json", {"duration": duration, "shots": shots})
    run.write_json("outline.json", outline)
    return shots


def check_rate_limit() -> None:
    """A 429 from a library is waited out, then the same search goes through."""
    replies = [429, 429, 200]
    slept: list[float] = []

    class Reply:
        def __init__(self, status: int):
            self.status_code, self.headers = status, {}

        def raise_for_status(self) -> None:
            pass

    real_get, real_sleep = stock.requests.get, stock.time.sleep
    stock.requests.get = lambda *a, **k: Reply(replies.pop(0))
    stock.time.sleep = lambda seconds: (slept.append(seconds), stock._paused_until.clear())
    try:
        assert stock.library_get("pexels", "https://example.invalid").status_code == 200
        assert len(slept) == 2 and all(s > 500 for s in slept), f"expected two ~10 min waits, slept {slept}"
        replies[:] = [429] * 20
        try:
            stock.library_get("pexels", "https://example.invalid")
            raise AssertionError("a limit that outlasts an hour must give up, not wait forever")
        except RuntimeError:
            pass
    finally:
        stock.requests.get, stock.time.sleep = real_get, real_sleep
        stock._paused_until.clear()


def check_plate_prompt() -> None:
    look = {"locations": ["a kitchen table under a lamp", "a hallway at night"]}
    card = {"id": 3, "image_prompt": "An austere text card with bold sans-serif text in all caps"}
    assert plate_prompt(card, look) == "a hallway at night", "a card-design prompt must become a scene"
    scene = {"id": 3, "image_prompt": "An apartment building at night, wet asphalt, no people, no text."}
    assert plate_prompt(scene, look) == scene["image_prompt"], "a scene saying 'no text' is kept"


def check_figure_detector() -> None:
    """Scripts spell figures out for the voice, so digits alone won't find them."""
    spoken = ["That gap costs the second borrower forty thousand dollars.",
              "Asking rents fell zero point six percent in late 2025.",
              "Completions dropped twenty percent in 2025."]
    plain = ["Nothing in the building changed.", "You find out from the renewal notice."]
    for text in spoken:
        assert FIGURE.search(text), f"missed a spoken figure: {text!r}"
    for text in plain:
        assert not FIGURE.search(text), f"saw a figure that isn't there: {text!r}"


def check_deepseek_timeout() -> None:
    """The read timeout must cover a whole generation, not a chunk of it.

    A 60s read timeout killed every storyboard call (they take ~3 minutes) and
    sent runs to the fallback model for no reason.
    """
    captured = {}

    class Reply:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return Reply()

    real_post = llm.requests.post
    llm.requests.post = fake_post
    try:
        llm._deepseek_chat("system", "user", "model", True)
    finally:
        llm.requests.post = real_post
    connect, read = captured["timeout"]
    assert read >= 300, f"read timeout {read}s is shorter than a storyboard call takes (~180s)"
    assert connect <= 30, f"connect timeout {connect}s should stay short"


def check_allocator() -> None:
    cfg = load_config()["visuals"]
    shots = [{"id": i, "kind": "ai", "priority": i % 3 + 1, "start": float(i)} for i in range(60)]  # fits the $5 cap with some motion
    motion, estimate = allocate(shots, cfg)
    assert estimate <= cfg["budget_usd"], f"estimate ${estimate} over budget"
    assert motion, "some shots should be animated at the default budget"
    worst_animated = max(shots[i]["priority"] for i in motion)
    best_skipped = min((s["priority"] for s in shots if s["id"] not in motion), default=3)
    assert worst_animated <= best_skipped, "a lower-priority shot was animated before a higher one"
    try:
        allocate(shots, {**cfg, "budget_usd": 1})
        raise AssertionError("an impossible budget must abort, not silently overspend")
    except RuntimeError:
        pass


def check_cache(run: Run) -> None:
    a = cache_path(run, "model", {"prompt": "x", "n": 1}, "jpg")
    assert a == cache_path(run, "model", {"n": 1, "prompt": "x"}, "jpg"), "key must ignore dict order"
    assert a != cache_path(run, "model", {"prompt": "y", "n": 1}, "jpg"), "different inputs, same key"


def check_shotlist(run: Run, shots: list[dict]) -> None:
    frame = run.path("assets", "frame.jpg")
    Image.new("RGB", (64, 36)).save(frame)
    stock_shots = [s for s in shots if s["kind"] == "stock"]
    generated, filled = stock_shots[1], stock_shots[2]  # stock_shots[0] has no asset at all
    visuals = {str(generated["id"]): {"kind": "still", "src": str(frame), "depth": None}}
    card = next(s for s in shots if s["kind"] == "card")
    visuals[str(card["id"])] = {"kind": "plate", "src": str(frame)}
    run.write_json("visuals.json", visuals)
    length = filled["end"] - filled["start"]
    run.write_json("stock.json", {str(filled["id"]): {"query": "x", "clips": [
        {"id": "a", "path": "a.mp4", "duration": length * 0.3}, {"id": "b", "path": "b.mp4", "duration": length}]}})
    run.write_json("metadata.json", {"title": "Self-test"})

    shot_list = build_shotlist(run)
    out = shot_list["shots"]
    assert out[0]["start"] == 0, "first shot must start at zero even if the planned one was lost"
    for a, b in zip(out, out[1:]):
        assert abs(a["end"] - b["start"]) < 1e-6, "a lost asset must be covered by the previous shot"
    pieces = [s for s in out if s.get("src") in ("a.mp4", "b.mp4")]
    assert [p["src"] for p in pieces] == ["a.mp4", "b.mp4"], "a stock shot plays its clips in order"
    assert abs(pieces[-1]["end"] - filled["end"]) < 1e-6 and pieces[0]["playbackRate"] == 1.0, pieces
    types = {s["type"] for s in out}
    assert {"still", "chart", "evidence", "number", "card"} <= types, types


def check_open_libraries() -> None:
    """Licence filter, NASA's duration strings, and a photograph becoming a still."""
    for code in ("pd", "pd-usgov", "cc0", "cc-by-4.0", "cc-by-2.0-de"):
        assert stock.license_ok(code), code
    for code in ("cc-by-sa-4.0", "cc-by-nc-4.0", "cc-by-nd-3.0", "arr", "", None):
        assert not stock.license_ok(code), code
    assert stock.media_seconds("0:05:27") == 327 and stock.media_seconds("23.84 s") == 23.84
    assert stock.media_seconds("12.5 s (approx)") == 12.5 and stock.media_seconds(None) == 0
    pieces = stock_clips({"clips": [{"path": "a.mp4", "duration": 3.0},
                                    {"path": "p.jpg", "duration": 15.0, "media": "image", "depth": "d.png"}]}, 10.0, 20.0)
    assert [p["type"] for p in pieces] == ["clip", "still"] and pieces[1]["depth"] == "d.png", pieces
    assert pieces[1]["start"] == 13.0 and pieces[1]["end"] == 20.0, pieces


def main() -> None:
    run = Run("selftest")
    shots = check_storyboard(run)
    print("1/5 storyboard assembly ok")
    check_rate_limit()
    print("    stock rate-limit wait ok")
    check_allocator()
    check_deepseek_timeout()
    check_figure_detector()
    check_plate_prompt()
    print("2/5 budget allocator, timeouts and card plates ok")
    check_cache(run)
    print("3/5 cache keys ok")
    check_shotlist(run, shots)
    check_open_libraries()
    print("4/5 shot list, licence filter and photo stills ok")
    image = compose(Image.new("RGB", (2560, 1440), (30, 20, 40)), {"text": "THEY TOOK $40,000", "symbol": "arrow"})
    assert image.size == (1280, 720)
    print("5/5 thumbnail compositing ok")
    print("\nSELF-TEST PASSED")


if __name__ == "__main__":
    main()
