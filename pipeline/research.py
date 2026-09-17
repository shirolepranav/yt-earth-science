"""STAGE 2 - Research chain.

Turns an approved topic into a dossier of real, sourced material.

This stage is what stops the channel producing generic AI slop. A language
model writing from memory produces vague, occasionally wrong, and completely
uncitable content. The same model writing from a fresh dossier of primary
sources produces specific, checkable content - which is both better viewing and
your evidence of original research if YouTube ever questions the channel.

Run it:  python -m pipeline.research --run latest
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from .common import Run, has_secret, log, resolve_run, secret, with_retries

# Domains whose numbers we trust without hedging. Anything from here is placed
# at the top of the dossier so the writing model leans on it first.
PRIMARY_SOURCE_HINTS = (
    ".gov", ".gov.uk", "europa.eu", ".edu", "si.edu", "opentextbc.ca",
    "openstax.org", "esa.int", "bgs.ac.uk", "ipcc.ch", "nature.com",
    "science.org", "agu.org", "agupubs.onlinelibrary.wiley.com",
    "geosociety.org", "pnas.org", "jstor.org",
)

# The canonical sources, searched on their own so every dossier carries them
# even when the open web ranks blogs higher. opentextbc.ca/geology is Steven
# Earle's Physical Geology (CC BY 4.0).
CANONICAL_DOMAINS = [
    "usgs.gov", "nasa.gov", "noaa.gov", "volcano.si.edu", "opentextbc.ca",
    "nps.gov", "bgs.ac.uk", "esa.int",
]

# Content farms and SEO aggregators. Their numbers are often copied wrong, and
# repeating them means laundering someone else's error into your video.
BLOCKED_HINTS = (
    "pinterest.", "quora.", "answers.", "ehow.", "wikihow.",
    "medium.com/@", "linkedin.com/pulse",
)

MAX_CHARS_PER_SOURCE = 6000  # keeps the dossier inside the model's context


def is_primary(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return any(hint in host for hint in PRIMARY_SOURCE_HINTS)


def is_blocked(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in BLOCKED_HINTS)


# ---------------------------------------------------------------------------
# Search provider 1: Exa (semantic - finds meaning, not just keywords)
# ---------------------------------------------------------------------------

def search_exa(query: str, count: int = 12, include_domains: list[str] | None = None) -> list[dict]:
    body = {
        "query": query,
        "numResults": count,
        "type": "auto",
        # Ask Exa for the page text directly - saves a second fetch for
        # most results and works on pages that block plain scrapers.
        "contents": {"text": {"maxCharacters": MAX_CHARS_PER_SOURCE}},
    }
    if include_domains:
        body["includeDomains"] = include_domains

    def call() -> list[dict]:
        response = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": secret("EXA_API_KEY"), "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("results", [])

    try:
        results = with_retries(call, label="exa search")
    except Exception as error:  # noqa: BLE001
        log(f"  Exa failed: {error}")
        return []

    return [
        {
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "text": (r.get("text") or "").strip(),
        }
        for r in results
        if r.get("url")
    ]


# ---------------------------------------------------------------------------
# Search provider 2: Tavily (keyword - the backup, and a different result set)
# ---------------------------------------------------------------------------

def search_tavily(query: str, count: int = 10) -> list[dict]:
    if not has_secret("TAVILY_API_KEY"):
        return []

    def call() -> list[dict]:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": secret("TAVILY_API_KEY"),
                "query": query,
                "max_results": count,
                "search_depth": "advanced",
                "include_raw_content": True,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("results", [])

    try:
        results = with_retries(call, label="tavily search")
    except Exception as error:  # noqa: BLE001
        log(f"  Tavily failed: {error}")
        return []

    return [
        {
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "text": (r.get("raw_content") or r.get("content") or "").strip(),
        }
        for r in results
        if r.get("url")
    ]


# ---------------------------------------------------------------------------
# Fetching a page ourselves, when the search API didn't return the text
# ---------------------------------------------------------------------------

def fetch_clean_text(url: str) -> str:
    """Download a page and strip the navigation, ads and cookie banners.

    trafilatura does the stripping. Without it you feed the model 4,000 words
    of menu links and it writes worse for it.
    """
    try:
        import trafilatura
    except ImportError:
        return ""

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
        return (text or "")[:MAX_CHARS_PER_SOURCE]
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# Building the dossier
# ---------------------------------------------------------------------------

def build_queries(topic: dict) -> list[str]:
    """Turn one topic into several searches that hit different angles.

    One search gives you one slice of the internet. Four give you the official
    figures, the analysis, and the recent movement - which is what a good
    explainer actually needs.
    """
    title = topic["title"]
    question = topic.get("core_question", title)
    source = topic.get("data_source", "")

    queries = [
        question,
        f"{title} evidence research",
        f"{question} USGS NASA scientific explanation",
    ]
    if source:
        queries.append(f"{source} {question}")
    return queries


def generate(run: Run, topic: dict) -> str:
    log(f"Researching: {topic['title']}")

    collected: dict[str, dict] = {}  # keyed by URL so duplicates collapse

    searches = [(q, search_exa(q) + search_tavily(q)) for q in build_queries(topic)]
    question = topic.get("core_question", topic["title"])
    searches.append((f"{question} [canonical sources]", search_exa(question, include_domains=CANONICAL_DOMAINS)))
    for query, results in searches:
        log(f"  searched: {query}")
        for result in results:
            url = result["url"]
            if not url or url in collected or is_blocked(url):
                continue
            collected[url] = result

    log(f"  {len(collected)} unique sources found")

    # Fill in any missing page text ourselves.
    for url, result in collected.items():
        if len(result["text"]) < 400:
            log(f"  fetching text for {url}")
            result["text"] = fetch_clean_text(url)

    # Drop sources we still have nothing usable from.
    usable = [r for r in collected.values() if len(r["text"]) >= 400]

    # Primary sources first. The writing model reads top-down and weights early
    # material more heavily, so this ordering is doing real work.
    usable.sort(key=lambda r: (not is_primary(r["url"]), -len(r["text"])))

    if not usable:
        raise RuntimeError(
            "No usable sources found. Check EXA_API_KEY, or try a less obscure topic."
        )

    # Assemble. Each source keeps its URL attached to its text so citations
    # survive all the way into the script and the video description.
    parts = [
        f"# RESEARCH DOSSIER",
        f"TOPIC: {topic['title']}",
        f"CORE QUESTION: {topic.get('core_question', '')}",
        "",
    ]
    for i, result in enumerate(usable[:15], 1):
        tag = "PRIMARY SOURCE" if is_primary(result["url"]) else "SECONDARY SOURCE"
        parts += [
            f"## SOURCE {i} [{tag}]",
            f"TITLE: {result['title']}",
            f"URL: {result['url']}",
            "",
            result["text"][:MAX_CHARS_PER_SOURCE],
            "",
            "---",
            "",
        ]

    dossier = "\n".join(parts)
    run.write_text("dossier.md", dossier)
    run.write_json("sources.json", [{"url": r["url"], "title": r["title"]} for r in usable[:15]])
    run.mark_done("research")

    word_count = len(re.findall(r"\w+", dossier))
    primary_count = sum(1 for r in usable[:15] if is_primary(r["url"]))
    log(f"Dossier written: {word_count:,} words, {primary_count} primary sources")
    return dossier


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Research an approved topic.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    active_run = resolve_run(args.run)
    chosen = active_run.read_json("chosen_topic.json")
    generate(active_run, chosen)
