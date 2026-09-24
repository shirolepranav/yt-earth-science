"""STAGE 3 - The script chain.

Six separate model calls, each doing one job:

  1. Outline      decide the argument before writing any prose
  2. Draft        get the words down, every fact tagged with its source ([S4])
  3. Hook rewrite five alternative openings, pick the best
  4. Fact-check   flag every claim its tagged source doesn't support, and fix it
  5. Polish       final pass + YouTube metadata + thumbnail concepts
  6. Final check  the same fact-check on the polished script - the words that
                  are actually narrated. Whatever it can't fix is listed at the
                  script gate for a person.

Edits made at the gate (script.revise, or a pasted script) are fact-checked the
same way. The source tags are kept in script_cited.txt; script.txt, which is
what gets narrated, has them removed.

Why six calls instead of one: asking a model for a finished script in one shot
gives you mush. Each pass here has a single job and a single output, which is
the difference between "an AI wrote this" and something worth publishing.

Run it:  python -m pipeline.script --run latest
"""

from __future__ import annotations

import re

from .common import Run, load_config, load_persona, load_prompt, log, resolve_run
from .llm import chat, chat_json

# ---------------------------------------------------------------------------
# Anti-templating: rotate the script shape between videos.
#
# YouTube's enforcement is at the channel level, and the pattern that gets a
# channel wiped is a run of interchangeable uploads. Rotating the structure is
# cheap insurance, and it makes the channel better viewing anyway.
# ---------------------------------------------------------------------------
SCRIPT_SHAPES = [
    "STRUCTURE FOR THIS VIDEO - 'the mechanism': open on the surprising number, "
    "then walk forward through how the system produces it, step by step, in order.",

    "STRUCTURE FOR THIS VIDEO - 'the investigation': open on a claim everyone "
    "repeats, then test it against the data one piece at a time until what's "
    "actually true emerges. State early that you're going to check it.",

    "STRUCTURE FOR THIS VIDEO - 'two cases': open on two people or two scenarios "
    "with near-identical inputs and very different outcomes, then explain what "
    "produced the gap. Return to both at the end.",

    "STRUCTURE FOR THIS VIDEO - 'the timeline': open on where things stand now, "
    "then go back to the decision or rule change that caused it, then walk "
    "forward to today. Anchor each era to one figure.",
]


def pick_shape(run_id: str) -> str:
    """Choose a structure from the rotation, based on the run id.

    Using the id rather than a random number means re-running the same video
    gives the same shape, which keeps runs reproducible.
    """
    digits = re.sub(r"\D", "", run_id) or "0"
    return SCRIPT_SHAPES[int(digits) % len(SCRIPT_SHAPES)]


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", strip_citations(text)))


def first_seconds_of(script: str, seconds: int = 30) -> str:
    """Roughly the opening N seconds of narration.

    Spoken English runs about 150 words a minute, so 30 seconds is ~75 words.
    """
    words = script.split()
    return " ".join(words[: int(150 * seconds / 60)])


# ---------------------------------------------------------------------------
# Source tags and fact-check fixes
# ---------------------------------------------------------------------------

# The draft tags each factual sentence with the dossier sources it comes from,
# "[S4]" or "[S4, S9]", so the fact-check can hold each claim to its own source
# instead of "anything in the dossier". Removed from what gets narrated.
CITATION = re.compile(r"\s*\[S\d+(?:\s*,\s*S?\d+)*\]")

# Flag kinds this channel never rewrites automatically. They're still listed at
# the script gate for a person.
NOT_AUTOFIXED: tuple[str, ...] = ()


def strip_citations(text: str) -> str:
    return CITATION.sub("", text)


def _loose(quote: str) -> re.Pattern:
    """A flagged quote as a pattern that survives the checker's copying drift:
    any run of whitespace, curly or straight quotes, any dash."""
    parts: list[str] = []
    for char in quote.strip():
        if char.isspace():
            if parts[-1:] != [r"\s+"]:
                parts.append(r"\s+")
        elif char in "'\u2018\u2019":
            parts.append("['\u2018\u2019]")
        elif char in '"\u201c\u201d':
            parts.append('["\u201c\u201d]')
        elif char in "-\u2013\u2014":
            parts.append("[-\u2013\u2014]")
        else:
            parts.append(re.escape(char))
    return re.compile("".join(parts))


def apply_fixes(text: str, flags: list[dict]) -> tuple[str, list[dict]]:
    """Swap each flagged sentence for the checker's fix. Returns the new text and
    the flags a person still has to look at: a CUT (deleting a sentence can break
    the flow), a kind in NOT_AUTOFIXED, or a quote that isn't in the script -
    which used to be skipped without a word."""
    unresolved = []
    for flag in flags:
        quote = (flag.get("quote") or "").strip()
        fix = (flag.get("suggested_fix") or "").strip()
        match = _loose(quote).search(text) if quote else None
        if not match:
            unresolved.append({**flag, "unresolved": "quote not found in the script"})
            log(f"  could not apply (quote not found): {quote[:60]}...")
        elif flag.get("problem") in NOT_AUTOFIXED or not fix or fix.upper() == "CUT":
            unresolved.append({**flag, "unresolved": "needs a person"})
            log(f"  left for a person: {quote[:60]}...")
        else:
            text = text[:match.start()] + fix + text[match.end():]
            log(f"  fixed: {quote[:60]}...")
    return text, unresolved


def fact_check(text: str, system: str, dossier: str, label: str) -> tuple[str, dict]:
    """One fact-check pass: flag, apply what can be applied, keep what can't."""
    check = chat_json(system, load_prompt("factcheck.md").format(script=text, dossier=dossier), label=label)
    log(f"  verdict: {check.get('verdict', 'unknown')} - {len(check.get('flags', []))} flag(s)")
    text, check["unresolved"] = apply_fixes(text, check.get("flags", []))
    return text, check


def save_script(run: Run, text: str) -> None:
    """script_cited.txt keeps the source tags; script.txt is what gets narrated."""
    run.write_text("script_cited.txt", text.strip())
    run.write_text("script.txt", re.sub(r"[ \t]+\n", "\n", strip_citations(text)).strip())


def recheck(run: Run, text: str) -> dict:
    """Fact-check an edited script against the dossier, apply the fixes it can,
    and save it. The result becomes factcheck.json, shown at the script gate."""
    cfg = load_config()
    system = load_prompt("system.md").format(persona=load_persona(), angle=cfg["channel"]["angle"])
    text, check = fact_check(text, system, run.read_text("dossier.md"), label="edit factcheck")
    save_script(run, text)
    run.write_json("factcheck.json", check)
    return check


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------

def generate(run: Run) -> dict:
    cfg = load_config()
    video_cfg = cfg["video"]

    dossier = run.read_text("dossier.md")
    topic = run.read_json("chosen_topic.json")

    system = load_prompt("system.md").format(
        persona=load_persona(), angle=cfg["channel"]["angle"]
    )

    target_minutes = f"{video_cfg['target_minutes_min']}-{video_cfg['target_minutes_max']}"

    # --- Pass 1: outline ---------------------------------------------------
    log("Pass 1/6: outline")
    outline = chat_json(
        system,
        load_prompt("outline.md").format(
            title=topic["title"],
            core_question=topic.get("core_question", ""),
            dossier=dossier,
            target_minutes=target_minutes,
            variation_instruction=pick_shape(run.id),
        ),
        label="outline",
    )
    run.write_json("outline.json", outline)
    log(f"  {len(outline.get('sections', []))} sections")

    # --- Pass 2: draft -----------------------------------------------------
    log("Pass 2/6: draft")
    import json as _json
    draft = chat(
        system,
        load_prompt("draft.md").format(
            outline=_json.dumps(outline, indent=2),
            dossier=dossier,
            words_min=video_cfg["target_words_min"],
            words_max=video_cfg["target_words_max"],
        ),
        label="draft",
    ).strip()
    run.write_text("draft.txt", draft)
    log(f"  {word_count(draft):,} words")

    # --- Pass 3: hook rewrite ---------------------------------------------
    log("Pass 3/6: hook rewrite")
    hooks = chat_json(
        system,
        load_prompt("hook.md").format(
            opening=first_seconds_of(draft),
            facts=dossier[:12000],
        ),
        label="hook",
    )
    run.write_json("hooks.json", hooks)

    options = hooks.get("options", [])
    best = options[hooks.get("best_index", 0)] if options else None
    if best:
        # Replace the old opening with the winning one. We swap the same number
        # of words we sent, so the rest of the script is left untouched.
        old_opening = first_seconds_of(draft)
        draft_with_hook = draft.replace(old_opening, best["text"].strip(), 1)
        if draft_with_hook == draft:
            # The opening didn't match exactly (punctuation drift). Prepend
            # instead of silently keeping the weaker hook.
            remaining = " ".join(draft.split()[len(old_opening.split()):])
            draft_with_hook = f"{best['text'].strip()}\n\n{remaining}"
        draft = draft_with_hook
        log(f"  new hook: {best['mechanism']} - {hooks.get('why', '')}")
    run.write_text("draft_hooked.txt", draft)

    # --- Pass 4: fact-check ------------------------------------------------
    log("Pass 4/6: fact-check")
    draft, draft_check = fact_check(draft, system, dossier, label="factcheck")
    run.write_json("factcheck_draft.json", draft_check)

    # --- Pass 5: polish + metadata + thumbnail concepts ---------------------
    # Shots are no longer planned here: pipeline/storyboard.py plans them after
    # narration, against the real word timings.
    log("Pass 5/6: polish, metadata and thumbnail concepts")
    prompt = load_prompt("polish.md").format(
        script=draft,
        outline=_json.dumps(outline, indent=2),
        words_min=video_cfg["target_words_min"],
        words_max=video_cfg["target_words_max"],
    )
    final = chat_json(system, prompt, heavy=True, label="polish")

    run.write_json("metadata.json", final.get("metadata", {}))

    # --- Pass 6: final check -----------------------------------------------
    # Polish rewrites the whole script, so the checked draft is not what gets
    # narrated. Check the words that are.
    log("Pass 6/6: fact-check the final script")
    script_text, check = fact_check(final["script"].strip(), system, dossier, label="final factcheck")
    run.write_json("factcheck.json", check)
    save_script(run, script_text)
    run.mark_done("script")

    log(f"Final script: {word_count(script_text):,} words, {len(check['unresolved'])} claim(s) left for a person")

    return {
        "script": script_text,
        "metadata": final.get("metadata", {}),
        "factcheck": check,
        "outline": outline,
    }


def revise(run: Run, instruction: str) -> str:
    """Apply a change you asked for in words, and rewrite script.txt.

    This is what happens when you reply "the opening is flat, start on the
    1783 eruption" instead of "approve". One focused model call, the whole
    script back, the metadata refreshed if the change affects the title.

    The edited script is fact-checked again (recheck): an edit is exactly where
    an unsupported claim can slip in after the checks have run.
    """
    cfg = load_config()
    system = load_prompt("system.md").format(
        persona=load_persona(), angle=cfg["channel"]["angle"]
    )
    current = run.read_text("script_cited.txt" if run.path("script_cited.txt").exists() else "script.txt")
    metadata = run.read_json("metadata.json") if run.path("metadata.json").exists() else {}
    video_cfg = cfg["video"]

    prompt = f"""Revise this narration script. The channel owner asked for one change:

\"\"\"{instruction}\"\"\"

Make that change and nothing else. Do not rewrite passages the request doesn't
touch - the rest of this script has already been approved. Keep every source
tag such as [S4] where it is, and tag any new fact with its source the same way.
Keep the length
between {video_cfg['target_words_min']} and {video_cfg['target_words_max']} words.

If the change makes the current title wrong, give a new one. Otherwise repeat
the existing title unchanged.

Current title: {metadata.get('title', '(none)')}

--- SCRIPT ---
{current}

Reply with JSON only:
{{"script": "the full revised script", "title": "...", "what_changed": "one sentence"}}"""

    result = chat_json(system, prompt, heavy=True, label="revise")

    revised = result["script"].strip()
    recheck(run, revised)

    if result.get("title"):
        metadata["title"] = result["title"]
        run.write_json("metadata.json", metadata)

    # The approved script changed, so the narration and everything cut against
    # it are stale. Keep only the stages that came before the script.
    run.reset_stages(keep=["choose", "research", "script"])

    log(f"Revised: {result.get('what_changed', instruction)}")
    log(f"  {word_count(revised):,} words")
    return result.get("what_changed", "Done.")


def format_for_humans(run: Run) -> str:
    """Render the script for review in a GitHub issue comment (Gate 2)."""
    script = run.read_text("script.txt")
    metadata = run.read_json("metadata.json")
    check = run.read_json("factcheck.json")
    concepts = metadata.get("thumbnail_concepts", [])
    concept_lines = "\n".join(
        f"- **{c.get('text') or '(no text)'}** — {c.get('hero', '')} "
        f"(symbol: {c.get('symbol', 'none')}) — _{c.get('why_click', '')}_"
        for c in concepts
    ) or "_None proposed - the thumbnail stage will generate its own._"

    flags = check.get("unresolved", check.get("flags", []))
    flag_lines = (
        "\n".join(
            f"- **{f.get('problem')}** — \"{f.get('quote', '')[:120]}\"  \n"
            f"  {f.get('detail', '')}"
            for f in flags
        )
        or "_No claims flagged._"
    )

    return "\n".join([
        f"## Gate 2 — script review",
        "",
        f"**Proposed title:** {metadata.get('title', '(none)')}",
        f"**Length:** {word_count(script):,} words "
        f"(~{word_count(script) / 150:.1f} min of narration)",
        f"**Fact-check verdict:** `{check.get('verdict', 'unknown')}`",
        "",
        "### Fact-check: claims left for a person",
        flag_lines,
        "",
        "### Thumbnail concepts",
        concept_lines,
        "",
        "### Script",
        "",
        script,
        "",
        "---",
        "",
        "**This gate is not a rubber stamp.** Edit something. Add an observation, "
        "cut a weak paragraph, sharpen an argument. That edit is the difference "
        "between a person using AI tools and a content farm.",
        "",
        "Reply with `approve` to build the video, or paste an edited script in a "
        "fenced code block and it will be used instead.",
    ])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the five-pass script chain.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    active_run = resolve_run(args.run)
    generate(active_run)
    print()
    print(format_for_humans(active_run))
