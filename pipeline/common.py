"""Shared plumbing used by every other module.

Nothing in here is specific to YouTube. It's the boring-but-important stuff:
finding files, loading config, reading secrets, retrying failed API calls, and
keeping track of where a run got to so a crash doesn't cost you the whole run.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Where things live
# ---------------------------------------------------------------------------

# ROOT is the top of the project folder, worked out from this file's location.
# Doing it this way means the scripts work no matter which folder you run them
# from - a very common beginner trip-up.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
RUNS_DIR = ROOT / "runs"
PROMPTS_DIR = ROOT / "prompts"

# Load secrets from .env into the environment (no-op if the file is absent,
# which is the case on GitHub Actions where secrets arrive as env vars).
load_dotenv(ROOT / ".env")


# ---------------------------------------------------------------------------
# Logging - deliberately plain so it reads well in GitHub Actions logs
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    """Print a timestamped message that flushes immediately.

    Flushing matters: without it, GitHub Actions shows nothing for minutes and
    then dumps everything at the end, which makes a stuck run impossible to spot.
    """
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def die(message: str) -> None:
    """Print an error and stop with a non-zero exit code (which fails the CI job)."""
    print(f"\nERROR: {message}\n", file=sys.stderr, flush=True)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config and secrets
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Read config/channel.json - the settings for the whole pipeline."""
    return json.loads((CONFIG_DIR / "channel.json").read_text())


def load_brand() -> dict:
    """Read config/brand.json - colours and fonts."""
    return json.loads((CONFIG_DIR / "brand.json").read_text())


def load_persona() -> str:
    """Read config/persona.md - pasted into every script-writing prompt."""
    return (CONFIG_DIR / "persona.md").read_text()


def load_prompt(name: str) -> str:
    """Read a prompt template from the prompts/ folder.

    Prompts live in their own files rather than inside the Python code so you
    can tune the writing without touching (or breaking) the program.
    """
    return (PROMPTS_DIR / name).read_text()


def secret(name: str, required: bool = True) -> str:
    """Fetch an API key from the environment.

    Args:
        name: the environment variable name, e.g. "PEXELS_API_KEY".
        required: if True, stop the program with a clear message when missing.
                  If False, return an empty string so the caller can skip the
                  optional feature that needs it.
    """
    value = (os.getenv(name) or "").strip()
    if not value and required:
        die(
            f"Missing {name}.\n"
            f"  Running on your Mac?  Add it to the .env file in the project folder.\n"
            f"  Running on GitHub?    Add it under Settings > Secrets and variables > Actions."
        )
    return value


def has_secret(name: str) -> bool:
    """True if a key is set. Used to decide whether an optional step can run."""
    return bool((os.getenv(name) or "").strip())


# ---------------------------------------------------------------------------
# Retrying - because APIs fail, and a pipeline that dies at 3am is useless
# ---------------------------------------------------------------------------

def with_retries(
    fn: Callable[[], Any],
    attempts: int = 3,
    base_delay: float = 2.0,
    label: str = "call",
) -> Any:
    """Run `fn`, retrying on failure with an increasing wait between tries.

    The wait doubles each time (2s, 4s, 8s) with a little randomness added.
    The randomness ("jitter") stops several retries from all hammering the API
    at the same instant, which is what turns a small hiccup into a rate-limit ban.
    """
    last_error = ""

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as error:  # noqa: BLE001 - we genuinely want any failure
            # HTTP errors quote the full URL, and some APIs (Pixabay) only take
            # their key as a query parameter - never let a key reach a log.
            last_error = re.sub(r"([?&](?:key|api_key|apikey)=)[^&\s]+", r"\1REDACTED", str(error))
            if attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
            log(f"  {label} failed (attempt {attempt}/{attempts}): {last_error}")
            log(f"  retrying in {delay:.1f}s...")
            time.sleep(delay)

    raise RuntimeError(f"{label} failed after {attempts} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Run state - one folder per video, so a failed run resumes instead of restarting
# ---------------------------------------------------------------------------

class Run:
    """Everything about one video-in-progress lives in `runs/<run_id>/`.

    Why a folder per run: every stage writes its output to disk before the next
    stage starts. If the render crashes, the script and the narration are still
    there - you re-run one stage instead of paying for the whole thing again.
    """

    def __init__(self, run_id: str):
        self.id = run_id
        self.dir = RUNS_DIR / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        # Sub-folders for the heavier files (these are gitignored).
        for sub in ("audio", "assets", "output"):
            (self.dir / sub).mkdir(exist_ok=True)

    # --- paths every stage agrees on ---------------------------------------
    @property
    def state_file(self) -> Path:
        return self.dir / "state.json"

    def path(self, *parts: str) -> Path:
        return self.dir.joinpath(*parts)

    # --- state --------------------------------------------------------------
    def state(self) -> dict:
        """Read the run's state file (an empty dict on a brand-new run)."""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {"run_id": self.id, "stages_done": []}

    def save_state(self, **updates: Any) -> dict:
        """Merge some values into the state file and write it back."""
        data = self.state()
        data.update(updates)
        self.state_file.write_text(json.dumps(data, indent=2))
        return data

    def mark_done(self, stage: str) -> None:
        """Record that a stage finished, so `--resume` can skip it next time."""
        data = self.state()
        if stage not in data["stages_done"]:
            data["stages_done"].append(stage)
        self.state_file.write_text(json.dumps(data, indent=2))

    def is_done(self, stage: str) -> bool:
        return stage in self.state().get("stages_done", [])

    def reset_stages(self, keep: list[str]) -> None:
        """Forget every finished stage except the ones named.

        Used when something upstream changes - an edited script makes the
        narration, the shots and the render stale, so they have to be redone
        rather than skipped as "already done".
        """
        data = self.state()
        data["stages_done"] = [s for s in data.get("stages_done", []) if s in keep]
        self.state_file.write_text(json.dumps(data, indent=2))

    # --- convenience --------------------------------------------------------
    def write_json(self, name: str, data: Any) -> Path:
        p = self.path(name)
        p.write_text(json.dumps(data, indent=2))
        return p

    def read_json(self, name: str) -> Any:
        p = self.path(name)
        if not p.exists():
            die(f"Expected {p} to exist. Run the earlier stage first.")
        return json.loads(p.read_text())

    def write_text(self, name: str, text: str) -> Path:
        p = self.path(name)
        p.write_text(text)
        return p

    def read_text(self, name: str) -> str:
        p = self.path(name)
        if not p.exists():
            die(f"Expected {p} to exist. Run the earlier stage first.")
        return p.read_text()


def new_run_id() -> str:
    """A sortable, human-readable id like '2026-08-30-1432'."""
    return time.strftime("%Y-%m-%d-%H%M")


_RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}$")


def latest_run_id() -> str | None:
    """The most recent run folder, so you can type `--run latest`.

    Only considers folders shaped like new_run_id()'s output - excludes
    fixed-name folders like tools/selftest.py's 'selftest', which would
    otherwise sort after every dated run and win forever.
    """
    if not RUNS_DIR.exists():
        return None
    runs = sorted(
        p.name for p in RUNS_DIR.iterdir() if p.is_dir() and _RUN_ID_RE.match(p.name)
    )
    return runs[-1] if runs else None


def resolve_run(run_id: str | None) -> Run:
    """Turn a --run argument into a Run object.

    Accepts an explicit id, the word 'latest', or nothing (which starts a new run).
    """
    if run_id in (None, "", "new"):
        return Run(new_run_id())
    if run_id == "latest":
        found = latest_run_id()
        if not found:
            die("No previous runs found. Start one without --run.")
        return Run(found)  # type: ignore[arg-type]
    return Run(run_id)
