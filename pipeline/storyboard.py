"""STAGE 6 - The storyboard.

Plans every shot of the video against the REAL narration timings, cutting to
new footage where the narration moves to a new subject.

Two model calls do the creative work:
  1. The look bible (look.json) - one visual language for this video: camera,
     light, grade, and a handful of recurring locations and props, used by any
     shot that has to be generated because no stock clip fits.
  2. Beats, a chunk of sentences at a time - what should be on screen while
     each sentence is spoken.

Everything after that is code, not model judgement: beats are snapped to the
words where their subject starts, the timeline is made contiguous, data shots
get time to be read, and every beat that can't be trusted is turned back into
ordinary stock footage. A chart index that doesn't exist, a "quote" that isn't
in the source, a fact card with a figure the dossier doesn't contain - all
become footage instead of reaching the screen.

Writes storyboard.json:
  {"duration": seconds, "shots": [{"id", "start", "end", "kind", ...}]}
with kind one of: stock, chart, number, evidence, card.

Run it:  python -m pipeline.storyboard --run latest
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from .common import Run, load_brand, load_config, load_prompt, log, resolve_run
from .llm import chat_json

SYSTEM = (
    "You are a documentary editor and director of photography. You reply with "
    "the requested JSON only - no commentary."
)
FOOTAGE = ("ai", "stock")
DATA_KINDS = ("chart", "number", "evidence", "card")
# Charts and highlighted source pages are what make the film look real, and are
# the part stock footage can never be, so they hold. A 20-word quote takes 5-6s
# to read and a chart spends its first second building; much past these and it
# turns into a slideshow of paper (15 Sep 2026).
MAX_DATA_SECONDS = {"chart": 12.0, "evidence": 8.0, "number": 5.0, "card": 5.0}
# Hold footage as long as the narration stays on its subject, but a single
# clip past this stops reading as a held shot and starts reading as a stall.
MAX_FOOTAGE_SECONDS = 15.0
MIN_DATA_SECONDS = {"chart": 8.0, "evidence": 6.0, "number": 4.0, "card": 4.0}
SENTENCE_END = re.compile(r"[.!?][\"')\]]*$")
# Cutting exactly on the word reads as late - the eye needs a moment before the
# ear. Editors cut a few frames early; 0.12s is ~4 frames at 30fps.
CUT_LEAD_SECONDS = 0.12
# Image prompts that ask for data never reach the image model: it draws fake,
# meaningless charts (and calculators with garbled digits), and the real
# numbers belong in a three.js chart.
CHARTY = re.compile(r"\b(charts?|graphs?|diagrams?|infographics?|data visuali[sz]ation|spreadsheets?|"
                    r"trend ?lines?|tickers?|bar (?:chart|graph)s?|arrows? (?:pointing|rising|going)|plotted|"
                    r"numbers?|digits?|statistics?|percent(?:ages?)?|price tags?|calculators?)\b", re.I)
# ...and the stock search for such a shot must not ask for data either (the
# first full build's "glowing phone screen financial chart" returned fake charts).
# Real-world establishing footage instead, rotated so consecutive swaps differ.
SAFE_STOCK_QUERIES = [
    "city street at night", "apartment building exterior", "rain on window at night",
    "empty apartment interior", "keys on kitchen table", "suburban houses at dusk",
    "construction site crane", "people walking in city", "moving boxes in apartment",
]


def _usable_query(query) -> bool:
    return (isinstance(query, str) and bool(query.strip()) and not CHARTY.search(query)
            and not re.search(r"collage|editorial|abstract|illustration", query, re.I))


def safe_queries(shot: dict) -> list[str]:
    """Up to three stock searches for a shot, none of which asks for data or art."""
    candidates = list(shot.get("queries") or []) + [shot.get("query"), shot.get("fallback_query")]
    queries = list(dict.fromkeys(q.strip() for q in candidates if _usable_query(q)))[:3]
    return queries or [SAFE_STOCK_QUERIES[int(shot.get("start", 0)) % len(SAFE_STOCK_QUERIES)]]


def safe_query(shot: dict) -> str:
    return safe_queries(shot)[0]


def safe_prompt(shot: dict) -> str:
    """The AI fallback prompt for a stock shot, never one that asks for data."""
    prompt = shot.get("image_prompt") or ""
    if prompt and not CHARTY.search(prompt):
        return prompt
    return f"Cinematic documentary shot: {safe_query(shot)}"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def sentences_from_words(words: list[dict]) -> list[dict]:
    """Group whisper's words into sentences, keeping word indices for snapping."""
    sentences, first = [], 0
    for i, word in enumerate(words):
        if SENTENCE_END.search(word["word"]) or i == len(words) - 1:
            sentences.append({
                "index": len(sentences),
                "first": first,
                "last": i,
                "start": words[first]["start"],
                "end": word["end"],
                "text": " ".join(w["word"] for w in words[first:i + 1]),
            })
            first = i + 1
    return sentences


def clean_page_text(text: str) -> str:
    """Scraped pages arrive with markdown images, links, bare URLs and heading
    marks - fine for the writer, amateurish on an evidence card."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)           # images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)         # links -> their text
    text = re.sub(r"(?:https?://|www\.)\S+", " ", text)             # bare URLs
    text = re.sub(r"[#*_`>|]+", " ", text)                           # markdown marks
    return re.sub(r"\s+", " ", text).strip()


def clean_title(title: str) -> str:
    title = re.sub(r"^\s*\[(?:PDF|HTML|DOC)\]\s*", "", title, flags=re.I)
    return re.split(r"\s+[|–—-]\s+", title)[0].strip()  # drop " | Site Name" suffixes


def sources_from_dossier(dossier: str) -> list[dict]:
    """The research dossier already holds each source's title, URL and text."""
    pattern = re.compile(
        r"## SOURCE \d+ \[[^\]]*\]\nTITLE: (.*?)\nURL: (.*?)\n\n(.*?)\n\n---", re.S
    )
    return [
        {"title": clean_title(title), "url": url.strip(),
         "publisher": urlparse(url.strip()).netloc.removeprefix("www."),
         "text": clean_page_text(text)}
        for title, url, text in pattern.findall(dossier)
    ]


def outline_charts(outline: dict) -> list[dict]:
    charts = []
    for index, section in enumerate(outline.get("sections", [])):
        visual = section.get("visual") or {}
        if visual.get("kind") and visual.get("values"):
            charts.append({"index": index, **visual,
                           "source": visual.get("source_note") or section.get("source", "")})
    return charts


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def figures_supported(text: str, dossier: str) -> bool:
    """Every digit run in `text` must appear in the dossier (commas ignored)."""
    haystack = dossier.replace(",", "")
    return all(run in haystack for run in re.findall(r"\d+(?:\.\d+)?", text.replace(",", "")))


def find_quote(quote: str, source_text: str) -> tuple[str, str, str] | None:
    """Locate `quote` verbatim (whitespace/case-insensitive) and return
    (before, quote, after) context taken from the source itself."""
    flat = re.sub(r"\s+", " ", source_text)
    at = flat.lower().find(normalise(quote))
    if not quote.strip() or at < 0:
        return None
    end = at + len(normalise(quote))
    before = flat[max(0, at - 380):at]
    after = flat[end:end + 380]
    sentence_start = before.rfind(". ")
    if sentence_start >= 0:  # open the excerpt at a sentence, not mid-phrase
        before = before[sentence_start + 2:]
    elif at > 380:
        before = before[before.find(" ") + 1:]
    after = after[:after.rfind(" ")] if len(flat) > end + 380 else after
    return before, flat[at:end], after


def to_footage(shot: dict) -> dict:
    """Demote a beat to stock footage using its fallback searches. The image
    prompt stays only for the case where no library has a usable clip."""
    kept = {k: shot[k] for k in ("start", "end", "sentence") if k in shot}
    return {**kept, "kind": "stock", "image_prompt": safe_prompt(shot),
            "motion_prompt": shot.get("motion_prompt") or "slow push-in",
            "style": shot.get("style", "cinematic"), "priority": 3,
            "query": safe_query(shot), "queries": safe_queries(shot), "intent": shot.get("intent", "")}


def _token(word: str) -> str:
    return re.sub(r"[^a-z0-9$%]", "", word.lower())


def find_words(phrase, words: list[dict], first: int, last: int) -> int | None:
    """Index of the word where `phrase` starts inside words[first..last]."""
    target = [t for t in map(_token, str(phrase or "").split()) if t]
    tokens = [_token(w["word"]) for w in words[first:last + 1]]
    for j in range(len(tokens) - len(target) + 1 if target else 0):
        if tokens[j:j + len(target)] == target:
            return first + j
    return None


# ---------------------------------------------------------------------------
# Assembly - pure, so tools/selftest.py can check it without any API
# ---------------------------------------------------------------------------

def split_long_footage(shot: dict, sentences: list[dict]) -> list[dict]:
    """Cut an over-long footage shot into the fewest equal parts that each fit,
    every cut snapped to a sentence start inside it. Each part finds its own clip."""
    length = shot["end"] - shot["start"]
    if shot["kind"] not in FOOTAGE or length <= MAX_FOOTAGE_SECONDS:
        return [shot]
    inside = [s["start"] for s in sentences if shot["start"] + 1 < s["start"] < shot["end"] - 1]
    if not inside:
        return [shot]  # one unbroken sentence: nowhere to cut that isn't arbitrary
    parts = int(-(-length // MAX_FOOTAGE_SECONDS))
    cuts = sorted({min(inside, key=lambda t: abs(t - (shot["start"] + length * k / parts)))
                   for k in range(1, parts)})
    edges = [shot["start"], *cuts, shot["end"]]
    return [{**shot, "start": a, "end": b, "angle": k} for k, (a, b) in enumerate(zip(edges, edges[1:]))]


def assemble(beats: list[dict], sentences: list[dict], words: list[dict], duration: float,
             charts: list[dict], sources: list[dict], dossier: str, cfg: dict) -> list[dict]:
    min_s = cfg["min_shot_seconds"]

    # 1. Place beats inside their sentence: on the words where their subject
    #    starts ("from_words"), else splitting the sentence's words evenly - an
    #    even split cut away from footage before its subject had been said.
    by_sentence: dict[int, list[dict]] = {}
    for beat in beats:
        if isinstance(beat.get("sentence"), int) and 0 <= beat["sentence"] < len(sentences):
            by_sentence.setdefault(beat["sentence"], []).append(beat)

    shots: list[dict] = []
    guessed = 0
    for sentence in sentences:
        group = by_sentence.get(sentence["index"], [])
        count = sentence["last"] - sentence["first"] + 1
        for k, beat in enumerate(group[:count]):
            at = find_words(beat.get("from_words"), words, sentence["first"], sentence["last"])
            if at is None and k == 0:
                at = sentence["first"]  # the sentence's own beat starts with it
            if at is None and beat.get("kind") in DATA_KINDS:
                # A chart or number has to be shown, so fall back to splitting
                # the sentence's words evenly between its beats.
                at = sentence["first"] + (k * count) // len(group[:count])
            if at is None:
                # Footage whose words we can't place would cut on an arbitrary
                # word; the previous shot simply holds through it instead.
                guessed += 1
                continue
            shots.append({**beat, "start": max(0.0, words[at]["start"] - CUT_LEAD_SECONDS)})
    if guessed:
        log(f"  {guessed} mid-sentence beat(s) had no usable \"from_words\" - held the previous shot")
    if not shots:
        raise RuntimeError("The storyboard model returned no usable beats.")

    # 2. Contiguous timeline: each shot runs until the next one starts.
    shots.sort(key=lambda s: s["start"])
    shots[0]["start"] = 0.0
    for current, following in zip(shots, shots[1:] + [{"start": duration}]):
        current["end"] = following["start"]

    # 3. Validate kinds - anything that can't be trusted becomes footage.
    valid_charts = {c["index"] for c in charts}
    opens_at = {c["index"]: c.get("opens_at", 0.0) for c in charts}
    used_charts: set[int] = set()
    cards_left, numbers_left = cfg["max_cards"], cfg["max_numbers"]
    extra_charts_left = cfg["max_extra_charts"]
    quotes_used: set[str] = set()

    def numbers_of(values) -> tuple:
        return tuple(sorted(float(re.sub(r"[^0-9.-]", "", str(v)) or 0) for v in values))
    # A chart built from the narration must not repeat one that already exists
    # (seen: "Rent vs. Renter Income" right after the outline's identical chart).
    chart_data_seen = {numbers_of(c["values"]) for c in charts}
    for i, shot in enumerate(shots):
        kind = shot.get("kind")
        if kind == "chart" and isinstance(shot.get("data"), dict):
            data = shot["data"]
            values, labels = data.get("values"), data.get("labels")
            if (extra_charts_left > 0 and data.get("chart_kind") in ("bar", "line", "comparison")
                    and isinstance(values, list) and 2 <= len(values) <= 8
                    and all(isinstance(v, (int, float)) for v in values)
                    and isinstance(labels, list) and len(labels) == len(values)
                    and figures_supported(" ".join(map(str, values)), dossier)
                    and numbers_of(values) not in chart_data_seen):
                chart_data_seen.add(numbers_of(values))
                extra_charts_left -= 1
                continue
        elif kind == "chart":
            index = shot.get("chart_index")
            if index in valid_charts and index not in used_charts and shot["start"] >= opens_at[index] - 1:
                used_charts.add(index)
                continue
        elif kind == "number":
            if (numbers_left > 0 and str(shot.get("value", "")).strip()
                    and figures_supported(str(shot["value"]), dossier)):
                numbers_left -= 1
                continue
        elif kind == "card":
            text = str(shot.get("text") or "").strip().upper()
            if (cards_left > 0 and text and len(text.split()) <= 8
                    and shot.get("variant") in ("question", "fact")
                    and figures_supported(text, dossier)):
                shot["text"] = text
                cards_left -= 1
                continue
        elif kind == "evidence":
            index = shot.get("source_index")
            if isinstance(index, int) and 0 <= index < len(sources):
                found = find_quote(str(shot.get("quote", "")), sources[index]["text"])
                if found and normalise(found[1]) not in quotes_used:  # the same receipt twice reads as padding
                    quotes_used.add(normalise(found[1]))
                    shot["before"], shot["quote"], shot["after"] = found
                    shot["headline"] = sources[index]["title"]
                    shot["publisher"] = sources[index]["publisher"]
                    continue
        # Everything else - stock beats, and any "ai" beat the model planned
        # anyway - is stock footage; AI only fills what the libraries can't.
        shots[i] = {**to_footage(shot), "end": shot["end"]}

    # 4. Never two data shots of the same kind back to back.
    for i in range(1, len(shots)):
        if shots[i]["kind"] in DATA_KINDS and shots[i]["kind"] == shots[i - 1]["kind"]:
            if shots[i]["kind"] == "chart":
                used_charts.discard(shots[i].get("chart_index"))
            shots[i] = {**to_footage(shots[i]), "end": shots[i]["end"]}

    # 5. Too short: fold into the previous shot (a data shot swallows the
    #    footage after it instead, so a chart is never the thing that vanishes).
    merged: list[dict] = []
    for shot in shots:
        length = shot["end"] - shot["start"]
        if merged and length < min_s:
            if merged[-1]["kind"] not in DATA_KINDS and shot["kind"] in DATA_KINDS:
                shot["start"] = merged[-1]["start"]
                merged[-1] = shot
            else:
                merged[-1]["end"] = shot["end"]
            continue
        merged.append(shot)
    shots = merged

    # 6. Too short to read: a data shot takes time from the footage after it,
    #    then before it. A sliver of footage under a second is absorbed.
    for i, shot in enumerate(shots):
        need = MIN_DATA_SECONDS.get(shot["kind"], 0.0) - (shot["end"] - shot["start"])
        for step in (1, -1):
            j = i + step
            while need > 1e-6 and 0 <= j < len(shots) and shots[j]["kind"] in FOOTAGE:
                other = shots[j]
                # The video must not open on a chart, so the first shot keeps its feet.
                room = other["end"] - other["start"] - (min_s if j == 0 else 0.0)
                if room <= 0:
                    break
                take = room if room - need < 1.0 else need
                if step > 0:
                    shot["end"] += take
                    other["start"] = shot["end"]
                else:
                    shot["start"] -= take
                    other["end"] = shot["start"]
                need -= take
                j += step
    shots = [s for s in shots if s["end"] - s["start"] > 1e-6]

    # 7. Too long: cap data shots, footage takes the rest. Footage itself is
    #    never split here - the stock stage fills a long shot with several clips.
    split: list[dict] = []
    for i, shot in enumerate(shots):
        limit = MAX_DATA_SECONDS.get(shot["kind"])
        tolerance = 1.0 if shot["kind"] == "number" else 1.25  # a number must be gone by 5s
        if limit is not None and shot["end"] - shot["start"] <= limit * tolerance:
            split.append(shot)
            continue
        if limit is None:
            split.extend(split_long_footage(shot, sentences))
            continue
        cut = shot["start"] + limit
        if i + 1 < len(shots) and shots[i + 1]["kind"] in FOOTAGE:
            shots[i + 1]["start"] = cut  # the footage after it starts earlier - no sliver shot
            parts = [shot]
        else:
            parts = [shot, {**to_footage(shot), "start": cut, "end": shot["end"]}]
        shot["end"] = cut
        split.extend(parts)
    shots = split

    for i, shot in enumerate(shots):
        shot["id"] = i
        shot["start"], shot["end"] = round(shot["start"], 3), round(shot["end"], 3)
    return shots


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------

def make_look(run: Run) -> dict:
    if run.path("look.json").exists():
        return run.read_json("look.json")
    colors = load_brand()["colors"]
    title = run.read_json("metadata.json").get("title", "")
    look = chat_json(SYSTEM, load_prompt("look.md").format(
        title=title, script=run.read_text("script.txt")[:9000],
        background=colors["background"], accent=colors["accent"], negative=colors["negative"],
    ), label="look bible")
    run.write_json("look.json", look)
    return look


def plan_beats(look: dict, sentences: list[dict], charts: list[dict],
               sources: list[dict], cfg: dict) -> list[dict]:
    source_lines = "\n\n".join(
        f"[{i}] {s['title']} ({s['publisher']})\n{s['text'][:1200]}" for i, s in enumerate(sources)
    ) or "(none)"
    beats: list[dict] = []
    step = cfg["sentences_per_call"]
    for offset in range(0, len(sentences), step):
        chunk = sentences[offset:offset + step]
        used = {b.get("chart_index") for b in beats if b.get("kind") == "chart"}
        chart_lines = "\n".join(
            f"[{c['index']}] {c['kind']}: {c.get('title', '')} - "
            f"{', '.join(map(str, c.get('labels', [])))} = {c.get('values')} {c.get('unit', '')}"
            for c in charts if c["index"] not in used and c["opens_at"] <= chunk[-1]["end"]
        ) or "(no charts belong in this stretch)"
        # An adjective ("use them freely") got 5 quotes in a whole video; a count
        # per stretch is what the model actually follows.
        minutes = (chunk[-1]["end"] - chunk[0]["start"]) / 60
        evidence_target = max(1, round(cfg["evidence_per_minute"] * minutes))
        number_target = min(numbers_left_now := max(0, cfg["max_numbers"] - sum(b.get("kind") == "number" for b in beats)),
                            max(1, round(cfg["numbers_per_minute"] * minutes)))
        cards_left_now = max(0, cfg["max_cards"] - sum(b.get("kind") == "card" for b in beats))
        card_target = min(cards_left_now, max(1, round(cfg["cards_per_minute"] * minutes)))
        extra_charts_left_now = max(0, cfg["max_extra_charts"] - sum(isinstance(b.get("data"), dict) for b in beats))
        chart_target = min(extra_charts_left_now, round(cfg["extra_charts_per_minute"] * minutes))
        cards_left = cards_left_now
        numbers_left = numbers_left_now
        extra_charts_left = extra_charts_left_now
        # Without this the model quotes the same striking sentence again and
        # again - 6 of 16 receipts were repeats before it was passed in.
        used_quotes = "\n".join(f'- "{b["quote"]}"' for b in beats
                                if b.get("kind") == "evidence" and b.get("quote")) or "(none yet)"
        sentence_lines = "\n".join(
            f"{s['index']} | {s['start']:.1f}-{s['end']:.1f} | {s['text']}" for s in chunk
        )
        log(f"  beats for sentences {offset}-{offset + len(chunk) - 1}")
        reply = chat_json(SYSTEM, load_prompt("storyboard.md").format(
            look=json.dumps(look, indent=2), charts=chart_lines, sources=source_lines,
            sentences=sentence_lines, cards_left=cards_left, numbers_left=numbers_left,
            extra_charts_left=extra_charts_left, minutes=f"{minutes:.1f}",
            evidence_target=evidence_target, number_target=number_target,
            card_target=card_target, chart_target=chart_target, used_quotes=used_quotes,
        ), label="storyboard")
        beats += [b for b in reply.get("beats", []) if isinstance(b, dict)]
    return beats


def place_missing_charts(beats: list[dict], sentences: list[dict], charts: list[dict]) -> None:
    """One extra call for charts the chunked passes left unplaced - or placed
    before their section (a hook that previews every number would otherwise
    spend all the charts in the first minute)."""
    opens_at = {c["index"]: c["opens_at"] for c in charts}
    for beat in beats:
        index = beat.get("chart_index")
        if (beat.get("kind") == "chart" and index in opens_at
                and sentences[beat["sentence"]]["start"] < opens_at[index] - 1):
            beat["kind"] = "ai"
    used = {b.get("chart_index") for b in beats if b.get("kind") == "chart"}
    missing = [c for c in charts if c["index"] not in used]
    if not missing:
        return
    log(f"  placing {len(missing)} chart(s) where their sections discuss them")
    earliest = min(c["opens_at"] for c in missing)
    reply = chat_json(SYSTEM, (
        "For each chart, give the index of the sentence where the narration discusses "
        "its numbers in depth, at or after the chart's earliest time.\n\nCHARTS:\n"
        + "\n".join(f"[{c['index']}] earliest {c['opens_at']:.0f}s - {c.get('title', '')}: {c.get('values')}"
                    for c in missing)
        + "\n\nSENTENCES (index | start seconds | text):\n"
        + "\n".join(f"{s['index']} | {s['start']:.0f} | {s['text']}" for s in sentences if s["start"] >= earliest - 1)
        + '\n\nReply with JSON only: {"placements": [{"chart_index": 0, "sentence": 12}]}'
    ), label="chart placement")
    for placement in reply.get("placements", []):
        index, sentence = placement.get("chart_index"), placement.get("sentence")
        if index not in {c["index"] for c in missing} or not isinstance(sentence, int):
            continue
        if not 0 <= sentence < len(sentences) or sentences[sentence]["start"] < opens_at[index] - 1:
            continue
        target = next((b for b in beats if b.get("sentence") == sentence), None)
        if target is not None:
            target.update(kind="chart", chart_index=index)


def top_up_evidence(beats: list[dict], sentences: list[dict], sources: list[dict], cfg: dict) -> None:
    """One extra call for the receipts the chunked passes didn't plan.

    Asked for several kinds of beat at once the model reliably trades one away
    for another; asked for quotes alone, with the sentences that have no data
    beat yet, it delivers. Invalid quotes are demoted in assemble() as always.
    """
    minutes = sentences[-1]["end"] / 60
    target = round(cfg["evidence_per_minute"] * minutes)
    have = sum(b.get("kind") == "evidence" for b in beats)
    if have >= target or not sources:
        return
    taken = {b.get("sentence") for b in beats if b.get("kind") in DATA_KINDS}
    free = [s for s in sentences if s["index"] not in taken and len(s["text"].split()) > 6]
    if not free:
        return
    log(f"  {have} receipts planned, aiming for {target} - asking for {target - have} more")
    reply = chat_json(SYSTEM, (
        f"Add {target - have} more evidence shots to a documentary: a source page with one sentence "
        "highlighted, shown while the narration makes that claim.\n\nFor each, give the index of the "
        "sentence it belongs with, the source it comes from, and ONE sentence copied EXACTLY, character "
        "for character, from that source - 15 to 25 words. Never invent, trim or reword a quote. Spread "
        "them across the narration and skip any sentence where no source says anything relevant.\n\nSOURCES:\n"
        + "\n\n".join(f"[{i}] {s['title']} ({s['publisher']})\n{s['text'][:1500]}" for i, s in enumerate(sources))
        + "\n\nQUOTES ALREADY ON SCREEN ELSEWHERE IN THIS VIDEO - do not use any of these again:\n"
        + ("\n".join(f'- "{b["quote"]}"' for b in beats if b.get("kind") == "evidence" and b.get("quote")) or "(none)")
        + "\n\nNARRATION (index | text):\n"
        + "\n".join(f"{s['index']} | {s['text']}" for s in free)
        + '\n\nReply with JSON only: {"evidence": [{"sentence": 12, "source_index": 0, "quote": "..."}]}'
    ), label="evidence top-up")
    added = 0
    for item in reply.get("evidence", []):
        index, source_index = item.get("sentence"), item.get("source_index")
        if not isinstance(index, int) or index in taken or not isinstance(source_index, int):
            continue
        if not any(s["index"] == index for s in free):
            continue
        taken.add(index)
        added += 1
        beats.append({"sentence": index, "kind": "evidence", "source_index": source_index,
                      "quote": item.get("quote", ""), "queries": [], "image_prompt": "", "motion_prompt": ""})
    log(f"  added {added} more receipt(s)")


# A spoken statistic deserves something on screen. The script spells figures out
# for the voice ("six hundred eight thousand"), so digits alone don't find them.
FIGURE = re.compile(r"\d|\b(percent|percentage|dollars?|cents?|hundred|thousand|million|billion|trillion)\b", re.I)


def cover_figures(beats: list[dict], sentences: list[dict], sources: list[dict], cfg: dict) -> None:
    """Give every spoken statistic a visual, where one isn't planned already.

    The planner covers the figures it thinks matter; the rest land on ordinary
    footage. This asks, for each uncovered statistic, for the one shot that
    shows it - a chart, a big number, or the source page it came from.
    Everything is validated in assemble() as usual, so an invented figure or a
    misquoted sentence still becomes footage.
    """
    spacing = cfg["figure_spacing_seconds"]
    taken = sorted(sentences[b["sentence"]]["start"] for b in beats
                   if b.get("kind") in DATA_KINDS and isinstance(b.get("sentence"), int))
    uncovered = []
    for sentence in sentences:
        if not FIGURE.search(sentence["text"]) or len(sentence["text"].split()) < 5:
            continue
        if any(abs(sentence["start"] - t) < spacing for t in taken):
            continue  # a data shot is already on screen around here
        uncovered.append(sentence)
        taken.append(sentence["start"])  # keeps the new ones spaced too
    if not uncovered:
        return
    numbers_left = max(0, cfg["max_numbers"] - sum(b.get("kind") == "number" for b in beats))
    charts_left = max(0, cfg["max_extra_charts"] - sum(isinstance(b.get("data"), dict) for b in beats))
    log(f"  {len(uncovered)} spoken figure(s) with nothing on screen - asking for visuals")
    reply = chat_json(SYSTEM, (
        "Each sentence below states a figure with nothing on screen to show it. For each one you can "
        "genuinely show, give ONE beat:\n"
        '  {"sentence": 12, "kind": "number", "value": "$40,000", "label": "extra interest", "source": "CFPB"}\n'
        '  {"sentence": 12, "kind": "chart", "data": {"chart_kind": "bar", "title": "...", '
        '"labels": ["...", "..."], "values": [21, 2], "unit": "%", "source": "..."}}\n'
        '  {"sentence": 12, "kind": "evidence", "source_index": 0, "quote": "one sentence copied exactly"}\n\n'
        f"At most {numbers_left} number beats and {charts_left} chart beats in total; evidence beats are not "
        "limited. Rules: a chart needs two or more figures to compare, spoken in that sentence, numbers exactly "
        "as spoken. A number beat is one figure, exactly as the narration says it. A quote must appear word for "
        "word in the source. Skip any sentence where none of the three honestly fits - a skipped sentence is "
        "better than an invented figure.\n\nSOURCES:\n"
        + "\n\n".join(f"[{i}] {s['title']} ({s['publisher']})\n{s['text'][:1200]}" for i, s in enumerate(sources))
        + "\n\nQUOTES ALREADY ON SCREEN - do not use again:\n"
        + ("\n".join(f'- "{b["quote"]}"' for b in beats if b.get("kind") == "evidence" and b.get("quote")) or "(none)")
        + "\n\nSENTENCES (index | text):\n"
        + "\n".join(f"{s['index']} | {s['text']}" for s in uncovered)
        + '\n\nReply with JSON only: {"beats": [ ... ]}'
    ), label="figure coverage")
    allowed = {s["index"] for s in uncovered}
    added: dict[str, int] = {}
    for beat in reply.get("beats", []):
        index, kind = beat.get("sentence"), beat.get("kind")
        if not isinstance(index, int) or index not in allowed or kind not in ("number", "chart", "evidence"):
            continue
        allowed.discard(index)  # one beat per sentence
        beats.append({**beat, "queries": [], "image_prompt": "", "motion_prompt": ""})
        added[kind] = added.get(kind, 0) + 1
    log(f"  added {added or 'nothing'} for spoken figures")


def generate(run: Run) -> list[dict]:
    cfg = load_config()["storyboard"]
    timing = run.read_json("words.json")
    words, duration = timing["words"], timing["duration"]
    sentences = sentences_from_words(words)
    charts = outline_charts(run.read_json("outline.json"))
    # Chart k of n belongs to body section k, so it can't appear before roughly
    # where that section starts: 8% of the runtime for the first, 58% for the last
    # (loose on purpose - it only has to keep a hook that previews every number
    # from spending all the charts in the first minute).
    for position, chart in enumerate(charts):
        chart["opens_at"] = round(duration * (0.08 + 0.5 * position / max(1, len(charts) - 1)), 1)
    dossier = run.read_text("dossier.md")
    sources = sources_from_dossier(dossier)

    log(f"Storyboarding {len(sentences)} sentences over {duration / 60:.1f} minutes")
    look = make_look(run)
    # The model's raw beats are kept, so assembly rules can be changed and
    # re-run for free. Delete look.json and beats.json to re-plan from scratch.
    if run.path("beats.json").exists():
        beats = run.read_json("beats.json")
    else:
        beats = plan_beats(look, sentences, charts, sources, cfg)
        run.write_json("beats.json", beats)
    place_missing_charts(beats, sentences, charts)
    top_up_evidence(beats, sentences, sources, cfg)
    cover_figures(beats, sentences, sources, cfg)
    run.write_json("beats.json", beats)

    shots = assemble(beats, sentences, words, duration + 1.0, charts, sources, dossier, cfg)
    run.write_json("storyboard.json", {"duration": round(duration + 1.0, 3), "shots": shots})
    run.mark_done("storyboard")

    counts: dict[str, int] = {}
    for shot in shots:
        counts[shot["kind"]] = counts.get(shot["kind"], 0) + 1
    placed = {s.get("chart_index") for s in shots if s["kind"] == "chart"}
    unplaced = [c["index"] for c in charts if c["index"] not in placed]
    log(f"Storyboard: {len(shots)} shots {counts}, "
        f"avg {duration / len(shots):.1f}s per shot")
    if unplaced:
        log(f"  warning: chart(s) {unplaced} never made it on screen")
    if counts.get("evidence", 0) < len(charts):
        log(f"  warning: only {counts.get('evidence', 0)} evidence shot(s) - "
            "the receipts carry the fear, aim for one per section")
    return shots


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Plan every shot against the narration timings.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    generate(resolve_run(args.run))
