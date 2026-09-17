"""STAGE 11 - Publish (optional).

Uploads the finished video to YouTube with its title, description, tags and
thumbnail.

Two things to know before you turn this on:

1. Google restricts unaudited API projects. Until your compliance audit clears,
   every video uploaded through the API is forced to PRIVATE no matter what
   privacy setting you request. That's fine - you flip it public with two taps
   in the YouTube app. Submit the audit request early so the clock runs.

2. This stage refuses to run while config/channel.json has review_only: true.
   That flag exists so the machine can't publish anything until you've decided
   the format works.

Getting the refresh token: run `python tools/youtube_auth.py` once, on a machine
with a browser, and paste the token it prints into your secrets.

Run it:  python -m pipeline.publish --run latest
"""

from __future__ import annotations

from pathlib import Path

from .common import Run, has_secret, load_config, log, resolve_run, secret

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def build_client():
    """Create an authenticated YouTube API client from the stored refresh token."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=secret("YOUTUBE_REFRESH_TOKEN"),
        client_id=secret("YOUTUBE_CLIENT_ID"),
        client_secret=secret("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def build_description(run: Run, metadata: dict) -> str:
    """Description text: summary, then sources, then the AI disclosure.

    The source list is not decoration. It's useful to viewers and it's concrete
    evidence of original research if the channel is ever reviewed.
    """
    parts = [metadata.get("description", "").strip(), "", "SOURCES", ""]

    try:
        sources = run.read_json("sources.json")
    except Exception:  # noqa: BLE001
        sources = []

    for source in sources[:12]:
        parts.append(f"- {source.get('title', 'Source')}: {source['url']}")

    parts += [
        "",
        "This video's narration is generated with AI text-to-speech. "
        "The research, editorial judgement and final edit are human.",
    ]
    return "\n".join(parts)


def upload(run: Run) -> str:
    cfg = load_config()
    safety = cfg["safety"]

    if safety.get("review_only", True):
        log("review_only is true in config/channel.json - not uploading.")
        log("The finished video is in the run's output/ folder. Upload it yourself,")
        log("or set review_only to false once your Phase 1 numbers say the format works.")
        return ""

    for name in ("YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"):
        if not has_secret(name):
            log(f"{name} is not set - skipping upload.")
            return ""

    from googleapiclient.http import MediaFileUpload

    metadata = run.read_json("metadata.json")
    video_path = Path(run.state()["video_path"])
    youtube = build_client()

    body = {
        "snippet": {
            "title": metadata["title"][:100],
            "description": build_description(run, metadata)[:5000],
            "tags": metadata.get("tags", [])[:15],
            "categoryId": "22",  # People & Blogs. 25 is News & Politics.
        },
        "status": {
            "privacyStatus": safety.get("upload_privacy", "private"),
            "selfDeclaredMadeForKids": False,
            # Declaring synthetic content costs nothing in reach and is far
            # better than being found not to have declared it.
            "containsSyntheticMedia": safety.get("declare_ai_generated", True),
        },
    }

    log(f"Uploading {video_path.name} ({video_path.stat().st_size / 1e6:.0f} MB)...")
    media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log(f"  {int(status.progress() * 100)}%")

    video_id = response["id"]
    log(f"Uploaded: https://youtu.be/{video_id}")

    thumbnail = run.path("output", "thumbnail.jpg")
    if thumbnail.exists():
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=str(thumbnail)).execute()
            log("  thumbnail set")
        except Exception as error:  # noqa: BLE001
            log(f"  thumbnail upload failed ({error}) - set it by hand in YouTube Studio")

    run.save_state(video_id=video_id, video_url=f"https://youtu.be/{video_id}")
    run.mark_done("publish")
    return video_id


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload the finished video.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    upload(resolve_run(args.run))
