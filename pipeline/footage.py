"""The footage list - every shot of the video, in script order, with where its
picture came from and why it was chosen.

Written to runs/<id>/footage.json for the studio's "Review footage" panel,
where any footage shot can be swapped (tools/chat_job.py `swap`). Costs
nothing: the reasons are the ones the stock ranker and the storyboard already
wrote down.

  kind   stock    Pexels / Pixabay
         archive  NASA / Wikimedia Commons - the real thing, credited on screen
         ai       generated (the libraries had nothing scoring >= MIN_SCORE)
         data     chart, number, evidence page or text card - built from the
                  script's facts, so not swappable here

Run it:  python -m pipeline.footage --run latest
"""

from __future__ import annotations

from pathlib import Path

from .chat import _web_path
from .common import Run, resolve_run
from .stock import MIN_SCORE, spoken_during

ARCHIVES = ("nasa-", "commons-")


def data_label(shot: dict) -> str:
    kind = shot["kind"]
    if kind == "number":
        return f"🔢 {shot.get('value', '')} — {shot.get('label', '')}"
    if kind == "evidence":
        return f"📰 {shot.get('publisher', '')}: “{shot.get('quote', '')[:140]}”"
    if kind == "card":
        return f"🪧 {shot.get('text', '')}"
    return f"📊 {(shot.get('data') or {}).get('title') or 'Chart'}"


def media(path: str | None, kind: str = "") -> dict | None:
    """A file as something the page can show."""
    url = _web_path(Path(path)) if path else None
    if not url:
        return None
    video = kind == "clip" or Path(path).suffix.lower() in (".mp4", ".webm", ".mov", ".ogv")
    return {"src": url, "media": "video" if video else "image"}


def build(run: Run) -> list[dict]:
    board = run.read_json("storyboard.json")["shots"]
    stock = run.read_json("stock.json") if run.path("stock.json").exists() else {}
    visuals = run.read_json("visuals.json") if run.path("visuals.json").exists() else {}
    words = run.read_json("words.json")["words"]

    rows = []
    for shot in board:
        sid = str(shot["id"])
        row = {"id": shot["id"], "start": shot["start"], "end": shot["end"],
               "said": spoken_during(words, shot["start"], shot["end"]),
               "query": (shot.get("queries") or [shot.get("query")])[0], "clips": []}
        if shot["kind"] == "stock" and sid in stock:
            clips = stock[sid]["clips"]
            row["kind"] = "archive" if any(c["id"].startswith(ARCHIVES) for c in clips) else "stock"
            for clip in clips:
                shown = media(clip["path"], "clip" if clip.get("media") != "image" else "")
                if shown:
                    row["clips"].append({**shown, "why": clip.get("why") or "", "score": clip.get("score"),
                                         "credit": clip.get("on_screen") or clip.get("credit"),
                                         "page": clip.get("page")})
        elif shot["kind"] in ("stock", "ai"):
            row["kind"] = "ai"
            asset = visuals.get(sid, {})
            shown = media(asset.get("src"), asset.get("kind", ""))
            reason = shot.get("intent") or shot.get("image_prompt", "")
            if shot["kind"] == "stock" and not shot.get("swapped_to_ai"):
                reason = f"No library clip scored {MIN_SCORE}+/10, so generated: {reason}"
            if shown:
                row["clips"].append({**shown, "why": reason, "prompt": asset.get("for")})
        else:
            row["kind"] = "data"
            row["label"] = data_label(shot)
            shown = media(visuals.get(sid, {}).get("src"))  # a card's background plate
            if shown:
                row["clips"].append(shown)
        row["swappable"] = row["kind"] != "data"
        rows.append(row)

    run.write_json("footage.json", rows)
    return rows


def summary(rows: list[dict]) -> str:
    counts = {k: sum(r["kind"] == k for r in rows) for k in ("stock", "archive", "ai", "data")}
    return (f"{len(rows)} shots: {counts['stock']} stock · {counts['archive']} archive (NASA/Commons) · "
            f"{counts['ai']} AI · {counts['data']} charts/cards")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Write the footage list.")
    parser.add_argument("--run", default="latest")
    rows = build(resolve_run(parser.parse_args().run))
    print(summary(rows))
