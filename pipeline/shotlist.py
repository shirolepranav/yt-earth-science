"""STAGE 9 - The shot list.

The join between planning and rendering. The storyboard already decided what
is on screen and when; this maps each planned shot to the asset that was
actually built and produces the props Remotion renders without any further
decisions:

  * storyboard.json  every shot, timed against the narration
  * stock.json       the stock clips filling each shot, by shot id
  * visuals.json     AI clips, parallax stills and card plates, by shot id
  * outline.json     chart data
  * charts3d.json    which charts got a GPT-6 Astra component

A shot whose asset didn't get built is dropped and the previous shot holds
over its time, so a failed generation never shows up as a black gap.

Run it:  python -m pipeline.shotlist --run latest
"""

from __future__ import annotations

from .common import Run, load_brand, load_config, log, resolve_run
from .charts3d import chart_spec
from .storyboard import outline_charts


def stock_clips(entry: dict, start: float, end: float) -> list[dict]:
    """One planned stock shot as consecutive clips. Clips that together fall
    short of the shot are all slowed by the same rate; the last one is cut
    where the shot ends. (Reads the old one-clip-per-shot stock.json too.)"""
    clips = entry.get("clips") or [entry]
    length = end - start
    rate = min(1.0, sum(c["duration"] for c in clips) / length)
    shots, at = [], start
    for clip in clips:
        if at >= end - 1e-6:
            break
        shots.append({"type": "clip", "src": clip["path"], "playbackRate": round(rate, 3),
                      "start": at, "end": min(end, at + clip["duration"] / rate)})
        at = shots[-1]["end"]
    shots[-1]["end"] = end
    return shots


def to_shot(planned: dict, stock: dict, visuals: dict, charts: dict, charts3d: dict | None = None) -> dict | None:
    sid, kind = str(planned["id"]), planned["kind"]
    length = planned["end"] - planned["start"]

    if kind in ("ai", "stock") and sid in visuals:
        asset = visuals[sid]
        if asset["kind"] == "clip":
            # Stretch a clip that's shorter than its shot rather than let it run out.
            rate = min(1.0, max(0.5, asset.get("duration", length) / length))
            return {"type": "clip", "src": asset["src"], "playbackRate": round(rate, 3)}
        return {"type": "still", "src": asset["src"], "depth": asset.get("depth"), "seed": planned["id"]}
    if kind == "chart":
        spec = chart_spec(planned, charts)
        if spec:  # the GPT-6 Astra component if one was accepted, else the built-in chart
            return {"type": "chart", **spec, "component": (charts3d or {}).get(sid)}
    if kind == "number":
        return {"type": "number", "value": str(planned["value"]),
                "label": planned.get("label", ""), "source": planned.get("source", "")}
    if kind == "evidence":
        return {"type": "evidence",
                "variant": "filing" if planned.get("variant") == "filing" else "article",
                **{k: planned.get(k, "") for k in ("publisher", "headline", "before", "quote", "after")}}
    if kind == "card" and sid in visuals:
        return {"type": "card", "variant": planned.get("variant", "fact"),
                "text": planned["text"], "src": visuals[sid]["src"]}
    return None


def build(run: Run) -> dict:
    video_cfg = load_config()["video"]
    board = run.read_json("storyboard.json")
    stock = run.read_json("stock.json")
    visuals = run.read_json("visuals.json") if run.path("visuals.json").exists() else {}
    charts = {c["index"]: c for c in outline_charts(run.read_json("outline.json"))}
    charts3d = run.read_json("charts3d.json") if run.path("charts3d.json").exists() else {}

    shots: list[dict] = []
    dropped = 0
    for planned in board["shots"]:
        if planned["kind"] == "stock" and str(planned["id"]) in stock:
            pieces = stock_clips(stock[str(planned["id"])], planned["start"], planned["end"])
        else:
            shot = to_shot(planned, stock, visuals, charts, charts3d)
            pieces = [{**shot, "start": planned["start"], "end": planned["end"]}] if shot else []
        if not pieces:
            dropped += 1
            if shots:
                shots[-1]["end"] = planned["end"]  # the previous shot holds
            continue
        if not shots:
            pieces[0]["start"] = 0.0
        shots.extend(pieces)
    if not shots:
        raise RuntimeError("No shot has a built asset. Run the stock and visuals stages first.")

    shot_list = {
        "title": run.read_json("metadata.json").get("title", ""),
        "durationSeconds": board["duration"],
        "fps": video_cfg["fps"],
        "width": video_cfg["width"],
        "height": video_cfg["height"],
        "brand": load_brand(),
        "audioFile": str(run.path("audio", "narration_mixed.wav")),
        "shots": shots,
        "letterbox": bool(video_cfg.get("letterbox", False)),
    }
    run.write_json("shotlist.json", shot_list)
    run.mark_done("shotlist")

    counts: dict[str, int] = {}
    for shot in shots:
        counts[shot["type"]] = counts.get(shot["type"], 0) + 1
    stock_ids = {c["path"] for entry in stock.values() for c in (entry.get("clips") or [entry])}
    footage = [s for s in shots if s["type"] in ("clip", "still")]
    seconds = sum(s["end"] - s["start"] for s in footage) or 1.0
    stock_seconds = sum(s["end"] - s["start"] for s in footage if s.get("src") in stock_ids)
    log(f"Shot list: {len(shots)} shots {counts}, {dropped} dropped; footage is "
        f"{100 - 100 * stock_seconds / seconds:.0f}% AI / {100 * stock_seconds / seconds:.0f}% stock")
    return shot_list


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the timed shot list.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    build(resolve_run(args.run))
