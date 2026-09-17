"""STAGE 1 - Topic engine.

Gathers evidence about what people in this niche are actually watching and
asking, then asks the writing model for ten ranked candidates.

Why evidence rather than just asking an LLM for ideas: an LLM asked cold will
produce ten plausible-sounding topics with no demand behind them. Topic choice
drives more of a channel's outcome than script quality does, so it gets real
signals.

Every signal source below is optional and fails soft. If Reddit blocks the
request or Google Trends is having a bad day, the run continues with fewer
signals rather than dying.

Run it:  python -m pipeline.topics
"""

from __future__ import annotations

import csv
import json

import requests

from .common import (
    CONFIG_DIR,
    Run,
    has_secret,
    load_config,
    load_persona,
    load_prompt,
    log,
    resolve_run,
    secret,
)
from .llm import chat_json

USER_AGENT = "TheBoringDocs-pipeline/1.0"


# ---------------------------------------------------------------------------
# Signal 1: your own backlog (the style anchor)
# ---------------------------------------------------------------------------

def read_backlog(limit: int = 30) -> str:
    """Load config/topic_backlog.csv as plain text for the prompt."""
    path = CONFIG_DIR / "topic_backlog.csv"
    if not path.exists():
        return "(no backlog file found)"

    lines = []
    with path.open() as handle:
        for i, row in enumerate(csv.reader(handle)):
            if i == 0 or not any(row):
                continue  # skip the header row and blank rows
            lines.append(" | ".join(row))
            if len(lines) >= limit:
                break
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Signal 2: outlier videos (views high relative to the channel's subscribers)
# ---------------------------------------------------------------------------

def find_outliers(keywords: list[str], per_keyword: int = 8) -> str:
    """Find videos that outperformed their own channel.

    The ratio views / subscribers is the useful number here. A video with
    500k views on a 2M-subscriber channel is normal. The same 500k on a
    20k-subscriber channel means the *topic* did the work - and topics travel.

    Needs YOUTUBE_API_KEY. Skipped cleanly if you haven't set one up.
    """
    if not has_secret("YOUTUBE_API_KEY"):
        log("  no YOUTUBE_API_KEY - skipping the outlier signal")
        return "(not available)"

    key = secret("YOUTUBE_API_KEY")
    # (views, description) pairs, so we can sort by views without parsing text.
    findings: list[tuple[int, str]] = []

    for keyword in keywords:
        try:
            # Step 1: find recent videos for this keyword.
            search = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": keyword,
                    "type": "video",
                    "order": "viewCount",
                    "publishedAfter": "2025-08-01T00:00:00Z",
                    "maxResults": per_keyword,
                    "key": key,
                },
                timeout=60,
            )
            search.raise_for_status()
            items = search.json().get("items", [])
            if not items:
                continue

            video_ids = ",".join(i["id"]["videoId"] for i in items)
            channel_ids = ",".join({i["snippet"]["channelId"] for i in items})

            # Step 2: get the view counts and the subscriber counts. Batching
            # both lookups keeps us well inside the 10,000 units/day quota.
            videos = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics,snippet", "id": video_ids, "key": key},
                timeout=60,
            ).json().get("items", [])

            channels = requests.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "statistics", "id": channel_ids, "key": key},
                timeout=60,
            ).json().get("items", [])

            subs = {
                c["id"]: max(int(c["statistics"].get("subscriberCount", 0)), 1)
                for c in channels
            }

            for video in videos:
                views = int(video["statistics"].get("viewCount", 0))
                channel_id = video["snippet"]["channelId"]
                ratio = views / subs.get(channel_id, 1)
                # A ratio above 1 means it out-drew the whole subscriber base.
                if ratio > 1.0 and views > 20_000:
                    findings.append((
                        views,
                        f'"{video["snippet"]["title"]}" - {views:,} views, '
                        f"{ratio:.1f}x its channel's subscriber count",
                    ))
        except Exception as error:  # noqa: BLE001
            log(f"  outlier lookup failed for '{keyword}': {error}")

    if not findings:
        return "(no clear outliers found)"

    # Strongest first, and cap it so the prompt stays a sensible size.
    findings.sort(key=lambda item: item[0], reverse=True)
    return "\n".join(line for _views, line in findings[:20])


# ---------------------------------------------------------------------------
# Signal 3: search trends (is interest rising or dying?)
# ---------------------------------------------------------------------------

def find_trends(keywords: list[str]) -> str:
    """Five-year interest direction for each keyword, via Google Trends.

    pytrends scrapes an unofficial endpoint, so it breaks from time to time.
    That's exactly why this returns a friendly string instead of raising.
    """
    try:
        from pytrends.request import TrendReq  # imported here so the whole
        # pipeline doesn't fail to start if pytrends isn't installed
    except ImportError:
        return "(pytrends not installed)"

    try:
        pytrends = TrendReq(hl="en-US", tz=0)
        lines = []
        # Google Trends accepts at most 5 terms per request.
        for batch_start in range(0, len(keywords), 5):
            batch = keywords[batch_start:batch_start + 5]
            pytrends.build_payload(batch, timeframe="today 5-y")
            frame = pytrends.interest_over_time()
            if frame.empty:
                continue
            for term in batch:
                if term not in frame:
                    continue
                series = frame[term]
                first_year = series[:52].mean()   # roughly the first year
                last_year = series[-52:].mean()   # roughly the most recent year
                if first_year == 0:
                    continue
                change = (last_year - first_year) / first_year * 100
                direction = "rising" if change > 10 else "declining" if change < -10 else "flat"
                lines.append(f"{term}: {direction} ({change:+.0f}% over 5 years)")
        return "\n".join(lines) or "(no trend data)"
    except Exception as error:  # noqa: BLE001
        log(f"  trends unavailable: {error}")
        return "(not available)"


# ---------------------------------------------------------------------------
# Signal 4: questions people are actually asking
# ---------------------------------------------------------------------------

def find_questions(subreddits: list[str], per_sub: int = 10) -> str:
    """Top posts of the month from the niche's subreddits.

    High comment counts are the signal worth chasing: lots of comments on a
    money question usually means nobody gave a clear answer.
    """
    lines: list[str] = []
    for sub in subreddits:
        try:
            response = requests.get(
                f"https://www.reddit.com/r/{sub}/top.json",
                params={"t": "month", "limit": per_sub},
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            response.raise_for_status()
            for child in response.json()["data"]["children"]:
                post = child["data"]
                if post.get("num_comments", 0) < 40:
                    continue
                lines.append(
                    f'r/{sub}: "{post["title"]}" - {post["num_comments"]} comments'
                )
        except Exception as error:  # noqa: BLE001
            log(f"  reddit unavailable for r/{sub}: {error}")

    return "\n".join(lines[:25]) or "(not available)"


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------

def generate(run: Run) -> dict:
    cfg = load_config()
    channel = cfg["channel"]

    log("Gathering topic signals...")
    backlog = read_backlog()
    outliers = find_outliers(channel["niche_keywords"])
    trends = find_trends(channel["niche_keywords"])
    questions = find_questions(channel["subreddits"])

    log("Asking the model for ten ranked candidates...")
    system = load_prompt("system.md").format(
        persona=load_persona(), angle=channel["angle"]
    )
    user = load_prompt("topics.md").format(
        backlog=backlog, outliers=outliers, trends=trends, questions=questions
    )

    result = chat_json(system, user, label="topic engine")
    topics = result.get("topics", [])
    if not topics:
        raise RuntimeError("The model returned no topics. Check the API key and try again.")

    run.write_json("topics.json", result)
    run.mark_done("topics")
    log(f"Wrote {len(topics)} topics to {run.path('topics.json')}")
    return result


def format_for_humans(topics: dict) -> str:
    """Render the topic list as Markdown, for pasting into a GitHub issue."""
    lines = ["Pick one by replying with **just its number** (for example: `3`).", ""]
    for topic in topics.get("topics", []):
        lines += [
            f"### {topic['rank']}. {topic['title']}",
            f"- **Answers:** {topic['core_question']}",
            f"- **Why they click:** {topic['why_they_click']}",
            f"- **Data source:** {topic['data_source']}",
            f"- **Evidence:** {topic.get('evidence', 'n/a')}",
            "",
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Propose ten video topics.")
    parser.add_argument("--run", help="Run id, or 'latest'. Omit to start a new run.")
    args = parser.parse_args()

    active_run = resolve_run(args.run)
    log(f"Run id: {active_run.id}")
    output = generate(active_run)
    print()
    print(format_for_humans(output))
    print(json.dumps({"run_id": active_run.id}))
