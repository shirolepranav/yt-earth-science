"""STAGE 7 - Bespoke three.js charts, written by GPT-6 Astra.

For every chart shot in storyboard.json, Astra writes a one-off Remotion +
three.js component designed for that data and that line of narration (towers
rising out of fog, a gap that cracks open, a line that burns like a fuse...).

A generated component only reaches the video after passing four gates:

  1. Contract  - static checks: allowed imports only, no clocks or randomness
                 (Remotion renders frames in parallel tabs, so both flicker),
                 reads its numbers and labels from props rather than code.
  2. Compile   - `tsc` on the whole Remotion project.
  3. Render    - the ChartPreview composition renders the entire shot, so a
                 crash on any frame is caught, not just the first.
  4. Numbers   - a vision model reads the final frame; every value must be on
                 screen. A beautiful chart with a wrong number is worse than none.

Failures go back to Astra with the error (up to REPAIRS times). Anything that
still fails falls back to the built-in chart - a video never breaks on this.
Accepted components are cached by a hash of their data, so reruns are free.

Writes charts3d.json: {shot_id: component_key}; components in assets/charts/.

Run it:  python -m pipeline.charts3d --run latest
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests

from .common import ROOT, Run, has_secret, load_brand, load_config, load_prompt, log, resolve_run, secret, with_retries
from .llm import has_vision, vision_check
from .storyboard import outline_charts

REMOTION = ROOT / "remotion"
GENERATED = REMOTION / "src" / "generated"
PROMPT_VERSION = 2  # bump when prompts/charts3d.md changes meaningfully, to re-generate
ALLOWED_IMPORTS = {"react", "remotion", "@remotion/three", "@react-three/fiber", "three",
                   "../components/charts/ChartStage", "../fonts", "../types"}
BANNED = re.compile(r"Math\.random|Date\.now|new Date|useFrame|setTimeout|setInterval|requestAnimationFrame|"
                    r"\bfetch\(|XMLHttpRequest|\bwindow\.|\bdocument\.|localStorage|useLoader|TextureLoader|"
                    r"\bimport\(")
NUMBERS_CHECK = (
    "This is the final frame of an animated chart. List every number you can read on it, exactly "
    'as written. Reply as JSON only: {"numbers": ["..."], "legible": true/false}'
)


# ---------------------------------------------------------------------------
# The chart data - the same shape shotlist.py hands Remotion
# ---------------------------------------------------------------------------

def chart_spec(planned: dict, charts: dict) -> dict | None:
    if isinstance(planned.get("data"), dict):  # built from the narration's own figures
        data = planned["data"]
        return {"chartKind": data["chart_kind"], "title": data.get("title", ""),
                "labels": [str(label) for label in data["labels"]], "values": data["values"],
                "unit": data.get("unit", ""), "source": data.get("source", "")}
    if planned.get("chart_index") in charts:
        chart = charts[planned["chart_index"]]
        return {"chartKind": chart["kind"], "title": chart.get("title", ""),
                "labels": [str(label) for label in chart.get("labels", [])], "values": chart["values"],
                "unit": chart.get("unit", ""), "source": chart.get("source", "")}
    return None


def key_for(spec: dict, seconds: float, model: str) -> str:
    raw = json.dumps([spec, round(seconds, 1), model, PROMPT_VERSION], sort_keys=True)
    return "c" + hashlib.sha256(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Astra
# ---------------------------------------------------------------------------

def astra(payload: dict, cfg: dict, ledger: list) -> tuple[str, str]:
    """One Responses API call. Returns (response id, text)."""
    def call() -> dict:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {secret('OPENAI_API_KEY')}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "reasoning": {"effort": cfg["reasoning_effort"]}, **payload},
            timeout=900,
        )
        response.raise_for_status()
        return response.json()

    body = with_retries(call, attempts=2, label="gpt-6-astra chart")
    usage = body.get("usage", {})
    ledger.append(usage.get("input_tokens", 0) / 1e6 * cfg["usd_per_million_input"]
                  + usage.get("output_tokens", 0) / 1e6 * cfg["usd_per_million_output"])
    text = "".join(part.get("text", "") for item in body.get("output", []) if item.get("type") == "message"
                   for part in item.get("content", []))
    return body["id"], text


def extract_code(text: str) -> str:
    match = re.search(r"```(?:tsx|typescript|ts|jsx)?\s*\n(.*?)```", text, re.S)
    return (match.group(1) if match else text).strip()


def contract_errors(code: str, spec: dict) -> list[str]:
    errors = []
    if "export default" not in code:
        errors.append("missing `export default function Chart(props: ChartProps)`")
    for module in re.findall(r"""from\s+["']([^"']+)["']""", code):
        if module not in ALLOWED_IMPORTS:
            errors.append(f"import from '{module}' is not allowed")
    if BANNED.search(code):
        errors.append(f"uses a banned API: {BANNED.search(code).group(0)}")
    if "values" not in code or "labels" not in code:
        errors.append("must read props.values and props.labels")
    for text in [spec["title"], *spec["labels"]]:
        if len(text) > 3 and re.search(r"""["'`]""" + re.escape(text) + r"""["'`]""", code):
            errors.append(f"hardcodes '{text}' - read it from props")
    return errors


# ---------------------------------------------------------------------------
# Gates 2-4: compile, render, read the numbers back
# ---------------------------------------------------------------------------

def stage(components: dict[str, Path]) -> None:
    """Write components into src/generated/ and the registry that imports them."""
    for old in GENERATED.glob("Chart_*.tsx"):
        old.unlink()
    lines = ["// Rewritten by the pipeline - chart components GPT-6 Astra wrote for this run.",
             'import type { ComponentType } from "react";', 'import type { ChartProps } from "../types";']
    entries = []
    for key, source in components.items():
        shutil.copy2(source, GENERATED / f"Chart_{key}.tsx")
        lines.append(f'import Chart_{key} from "./Chart_{key}";')
        entries.append(f"  {key}: Chart_{key},")
    lines += ["", "export const charts: Record<string, ComponentType<ChartProps>> = {", *entries, "};", ""]
    (GENERATED / "index.ts").write_text("\n".join(lines))


def compile_errors(key: str) -> str:
    result = subprocess.run(["npx", "tsc", "--noEmit"], cwd=REMOTION, capture_output=True, text=True)
    return "\n".join(line for line in result.stdout.splitlines() if f"Chart_{key}" in line)[:3000]


def render_errors(key: str, spec: dict, seconds: float, workdir: Path) -> tuple[str, Path | None]:
    props = workdir / f"{key}_props.json"
    props.write_text(json.dumps({"brand": load_brand(), "chart": spec, "component": key, "durationSeconds": seconds}))
    video = workdir / f"{key}.mp4"
    result = subprocess.run(
        ["npx", "remotion", "render", "ChartPreview", str(video), f"--props={props}", "--scale=0.5",
         f"--gl={os.getenv('REMOTION_GL', 'angle')}", "--timeout=60000", "--log=error"],
        cwd=REMOTION, capture_output=True, text=True,
    )
    if result.returncode != 0 or not video.exists():
        return (result.stderr or result.stdout)[-3000:], None
    frame = workdir / f"{key}_last.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.2", "-i", str(video), "-frames:v", "1", str(frame)],
                   check=True)
    return "", frame


def number_errors(frame: Path, spec: dict) -> str:
    if not has_vision():
        return ""
    verdict = vision_check(str(frame), NUMBERS_CHECK)
    seen = " ".join(str(n) for n in verdict.get("numbers", [])).replace(",", "")
    missing = []
    for value in spec["values"]:
        digits = re.sub(r"[^0-9.]", "", str(value)).rstrip("0").rstrip(".") or "0"
        if digits not in seen.replace(" ", ""):
            missing.append(str(value))
    if missing:
        return f"these values are not readable on the final frame: {', '.join(missing)} (read: {seen[:200]})"
    return "" if verdict.get("legible", True) else "the numbers are not clearly legible on the final frame"


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

def build_one(run: Run, shot: dict, spec: dict, accepted: dict[str, Path], cfg: dict, ledger: list) -> str | None:
    seconds = round(shot["end"] - shot["start"], 2)
    key = key_for(spec, seconds, cfg["model"])
    final = run.path("assets", "charts", f"{key}.tsx")
    if final.exists():
        return key

    words = run.read_json("words.json")["words"]
    spoken = " ".join(w["word"] for w in words if shot["start"] - 1 <= w["start"] < shot["end"])
    prompt = load_prompt("charts3d.md").format(
        chart_kind=spec["chartKind"], title=spec["title"], labels=json.dumps(spec["labels"]),
        values=json.dumps(spec["values"]), unit=spec["unit"], source=spec["source"], seconds=seconds,
        spoken=spoken, chart_stage=(REMOTION / "src/components/charts/ChartStage.tsx").read_text(),
        bars3d=(REMOTION / "src/components/charts/Bars3D.tsx").read_text(),
    )
    workdir = run.path("assets", "charts", "_work")
    workdir.mkdir(parents=True, exist_ok=True)
    draft = workdir / f"{key}.tsx"

    started = time.monotonic()
    response_id, text = astra({"input": prompt}, cfg, ledger)
    for attempt in range(cfg["repairs"] + 1):
        code = extract_code(text)
        draft.write_text(code)
        problem = "; ".join(contract_errors(code, spec))
        frame = None
        if not problem:
            stage({**accepted, key: draft})
            problem = compile_errors(key)
        if not problem:
            problem, frame = render_errors(key, spec, seconds, workdir)
        if not problem and frame:
            problem = number_errors(frame, spec)
        if not problem:
            shutil.copy2(draft, final)
            log(f"  shot {shot['id']}: Astra chart accepted after {attempt + 1} attempt(s) "
                f"({time.monotonic() - started:.0f}s) - '{spec['title']}'")
            return key
        log(f"  shot {shot['id']}: attempt {attempt + 1} rejected - {problem[:240]}")
        if attempt == cfg["repairs"]:
            break
        response_id, text = astra({
            "previous_response_id": response_id,
            "input": f"Your component was rejected:\n{problem}\n\nFix it. Reply with the complete corrected ```tsx block only.",
        }, cfg, ledger)
    log(f"  shot {shot['id']}: falling back to the built-in chart")
    return None


def build_for_run(run: Run) -> dict:
    cfg = load_config()["charts3d"]
    board = run.read_json("storyboard.json")
    charts = {c["index"]: c for c in outline_charts(run.read_json("outline.json"))}
    shots = [(s, chart_spec(s, charts)) for s in board["shots"] if s["kind"] == "chart"]
    shots = [(s, spec) for s, spec in shots if spec and spec["chartKind"] != "bignumber"][: cfg["max_per_video"]]

    results: dict[str, str] = {}
    if not has_secret("OPENAI_API_KEY"):
        log("  no OPENAI_API_KEY - every chart uses the built-in three.js components")
    else:
        log(f"GPT-6 Astra is writing {len(shots)} chart component(s)")
        accepted: dict[str, Path] = {}
        ledger: list[float] = []
        for shot, spec in shots:  # one at a time: they share src/generated and the compiler
            try:
                key = build_one(run, shot, spec, accepted, cfg, ledger)
            except Exception as error:  # noqa: BLE001 - never lose the video over a chart
                log(f"  shot {shot['id']}: Astra failed ({error}) - built-in chart instead")
                key = None
            if key:
                results[str(shot["id"])] = key
                accepted[key] = run.path("assets", "charts", f"{key}.tsx")
        stage({})  # leave the source tree clean; render.py stages what the video uses
        spent = round(sum(ledger), 2)
        run.save_state(charts3d_spend_usd=round(run.state().get("charts3d_spend_usd", 0) + spent, 2))
        log(f"Astra charts: {len(results)}/{len(shots)} accepted, ${spent:.2f} this run")

    run.write_json("charts3d.json", results)
    run.mark_done("charts")
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Have GPT-6 Astra write the chart animations.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    build_for_run(resolve_run(args.run))
