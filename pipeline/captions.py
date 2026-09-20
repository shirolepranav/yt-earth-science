"""STAGE - Subtitles.

Turns the word-level timings from the align stage into a `subtitles.srt` file
you can upload to YouTube alongside the video.

Why bother when YouTube auto-captions everything? Two reasons:

  1. Auto-captions guess at proper nouns. "Toba", "Chicxulub" and "Laki" come
     back as nonsense, and this channel is made of proper nouns.
  2. An uploaded caption track is indexed by YouTube search immediately;
     auto-captions can take hours and are not indexed as reliably.

The timings are exact - they come from the voice engine itself (ElevenLabs) or
from faster-whisper - so no guessing happens here. This stage only decides
where one subtitle ends and the next begins.

Run it:  python -m pipeline.captions --run latest
"""

from __future__ import annotations

from .common import Run, log, resolve_run

# Subtitle shape. These are the conventions broadcast captions use, and they're
# what YouTube's own player is laid out for.
MAX_LINE_CHARS = 42      # characters per line before we wrap
MAX_LINES = 2            # never more than two lines on screen
MAX_SECONDS = 6.0        # a cue that hangs longer than this feels stuck
MIN_SECONDS = 1.2        # ...and one shorter than this is unreadable
PAUSE_SECONDS = 0.65     # a gap this long in the narration is a natural break
MIN_CHARS_TO_BREAK = 20  # don't end a cue on a two-word sentence
SOFT_BREAK_CHARS = 48    # past this, take the next clause boundary offered

SENTENCE_ENDINGS = (".", "!", "?", "…")
CLAUSE_ENDINGS = (",", ";", ":", "—", "–")


def _timestamp(seconds: float) -> str:
    """Seconds -> the `HH:MM:SS,mmm` format SRT requires."""
    if seconds < 0:
        seconds = 0.0
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _wrap(text: str) -> str:
    """Split a cue across at most two lines, keeping them a similar length.

    Greedy wrapping (fill line one, spill into line two) leaves ugly cues like
    a full line above a single orphan word. Balancing on the midpoint reads
    better and costs nothing.

    Break points that would leave either line over the limit are rejected
    outright - a balanced split is no good if one half still overflows.
    """
    if len(text) <= MAX_LINE_CHARS:
        return text

    words = text.split()
    midpoint = len(text) / 2
    best_split, best_distance = None, float("inf")
    fallback_split, fallback_distance = 1, float("inf")

    for index in range(1, len(words)):
        left = len(" ".join(words[:index]))
        right = len(" ".join(words[index:]))
        distance = abs(left - midpoint)

        if distance < fallback_distance:
            fallback_split, fallback_distance = index, distance
        # Prefer the most balanced split where BOTH lines actually fit.
        if left <= MAX_LINE_CHARS and right <= MAX_LINE_CHARS and distance < best_distance:
            best_split, best_distance = index, distance

    # No split fits - a single very long word. Let it run over rather than
    # dropping it; a cue is capped at 6 seconds so this stays rare.
    split_at = best_split if best_split is not None else fallback_split
    return "\n".join([" ".join(words[:split_at]), " ".join(words[split_at:])])


def _fits(text: str) -> bool:
    """Would this cue text wrap into the two-line box without overflowing?

    Counting characters isn't enough. "In 1783 a fissure opened in southern
    Iceland and did not close for eight months." is 79 characters - inside a
    2 x 42 budget - but there is no word boundary that splits it into two
    lines of 42 or fewer. The only reliable test is to wrap it and look.
    """
    lines = _wrap(text).split("\n")
    return len(lines) <= MAX_LINES and all(
        len(line) <= MAX_LINE_CHARS or " " not in line for line in lines
    )


def _text_of(group: list[dict]) -> str:
    """The words of a cue, joined back into a line."""
    return " ".join(word["word"] for word in group)


def _fix_orphans(groups: list[list[dict]]) -> list[list[dict]]:
    """Deal with a stranded tail like "sea." alone on screen.

    Working on word lists rather than rendered text is what makes this
    possible: every word still carries its own timing, so a word can be moved
    between cues and the cue boundaries follow it exactly.

    Two ways out, in order of preference:
      1. Merge the orphan into the cue before it, if the result still fits.
      2. Otherwise donate the previous cue's last word to the orphan, so it
         has company - as long as that doesn't strand the previous cue instead.
    """
    fixed: list[list[dict]] = []

    for group in groups:
        previous = fixed[-1] if fixed else None

        if previous and len(_text_of(group)) < MIN_CHARS_TO_BREAK:
            if (_fits(_text_of(previous + group))
                    and group[-1]["end"] - previous[0]["start"] <= MAX_SECONDS + 1.0):
                previous.extend(group)
                continue

            # Merging didn't fit. Move one word across instead - but not if
            # that just moves the problem back onto the previous cue.
            if len(previous) > 2 and len(_text_of(previous[:-1])) >= MIN_CHARS_TO_BREAK:
                moved = previous.pop()
                group.insert(0, moved)

        fixed.append(group)

    return fixed


def build_cues(words: list[dict]) -> list[dict]:
    """Group timed words into subtitle cues.

    Each word is `{"word": ..., "start": ..., "end": ...}`. Words keep joining
    the current cue until something says stop, in this order of preference:

      * the narrator finished a sentence, or took a breath  - the best breaks
      * the cue is long enough and a clause ended (a comma) - the next best
      * the cue won't wrap into two lines, or has been up 6 seconds - forced

    The forced break is the one that reads worst, so the first two exist to
    make it rare.
    """
    groups: list[list[dict]] = []
    current: list[dict] = []

    for index, word in enumerate(words):
        token = (word.get("word") or "").strip()
        if not token:
            continue

        if current:
            duration = word["end"] - current[0]["start"]
            # Won't wrap into two lines, or it's been up too long -> forced cut.
            if not _fits(_text_of(current) + " " + token) or duration > MAX_SECONDS:
                groups.append(current)
                current = []

        current.append(word)

        characters = len(_text_of(current))
        if characters < MIN_CHARS_TO_BREAK:
            continue

        next_word = words[index + 1] if index + 1 < len(words) else None
        ends_sentence = token.endswith(SENTENCE_ENDINGS)
        pauses_after = next_word is not None and (next_word["start"] - word["end"]) >= PAUSE_SECONDS
        # A comma is only worth breaking on once the cue is already substantial.
        ends_clause = token.endswith(CLAUSE_ENDINGS) and characters >= SOFT_BREAK_CHARS

        if ends_sentence or pauses_after or ends_clause:
            groups.append(current)
            current = []

    if current:
        groups.append(current)

    cues = [
        {"start": group[0]["start"], "end": group[-1]["end"], "text": _wrap(_text_of(group))}
        for group in _fix_orphans(groups)
    ]

    # Stretch cues that flashed by too fast, but never far enough to overlap
    # the one after them - overlapping cues make players flicker.
    for index, cue in enumerate(cues):
        if cue["end"] - cue["start"] >= MIN_SECONDS:
            continue
        ceiling = cues[index + 1]["start"] if index + 1 < len(cues) else cue["end"] + MIN_SECONDS
        cue["end"] = min(cue["start"] + MIN_SECONDS, ceiling)

    return cues


def to_srt(cues: list[dict]) -> str:
    """Render cues as SubRip (.srt) text."""
    blocks = []
    for number, cue in enumerate(cues, start=1):
        blocks.append(
            f"{number}\n"
            f"{_timestamp(cue['start'])} --> {_timestamp(cue['end'])}\n"
            f"{cue['text']}\n"
        )
    return "\n".join(blocks)


def generate(run: Run) -> str:
    """Write output/subtitles.srt from words.json."""
    if not run.path("words.json").exists():
        raise FileNotFoundError(
            f"{run.path('words.json')} not found. Run the align stage first."
        )

    words = run.read_json("words.json").get("words") or []
    if not words:
        raise RuntimeError("words.json contains no words - nothing to caption.")

    cues = build_cues(words)
    srt = to_srt(cues)
    path = run.write_text("output/subtitles.srt", srt)

    run.save_state(subtitle_path=str(path), subtitle_cues=len(cues))
    run.mark_done("captions")

    log(f"Wrote {len(cues):,} subtitles to {path}")
    return srt


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the subtitle file.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    generate(resolve_run(args.run))
