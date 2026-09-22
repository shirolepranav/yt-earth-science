"""STAGE - Publish.

Uploads the finished video to YouTube with its title, description, tags,
thumbnail and subtitles, then waits for you to say the word before it goes
public.

The two-step matters, and it's what makes reviewing from a phone work at all.
An eleven-minute 1080p video is 150-400 MB - far too big to send over a chat
app. So the video is uploaded to YouTube as **private** first, and the chat
sends you the link. YouTube becomes the review player: it streams to your
phone, it's free, and approving costs one more API call rather than a second
upload.

  build stage      -> uploads PRIVATE, sends you the link       (upload)
  you reply        -> title/tags/thumbnail edits land in place  (apply_metadata)
  you say publish  -> the same video flips to public            (go_live)

Two things to know:

1. Google restricts unaudited API projects. Until your compliance audit clears,
   a video uploaded through the API is locked private no matter what privacy
   you ask for - so `go_live` will appear to work and the video will stay
   private. Flip it public with two taps in the YouTube app until the audit
   clears, and submit the audit request early so the clock runs.

2. `safety.review_only` in config/channel.json controls only the automatic
   flip to public. Private review uploads still happen, because that's how you
   see the video at all. Replying `publish` in the chat is a human decision and
   is always honoured.

Getting the refresh token: run `python tools/youtube_auth.py` once, on a machine
with a browser, and paste the token it prints into your secrets.

Run it:  python -m pipeline.publish --run latest
"""

from __future__ import annotations

from pathlib import Path

from .common import Run, has_secret, load_config, log, resolve_run, secret

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    # Needed to attach the subtitle track. Harmless if captions aren't used.
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# The thumbnail stage writes three images and ranks them. You can override its
# pick by letter - "a" is the winner it chose, "b" and "c" are the runners-up.
THUMBNAIL_FILES = {"a": "thumbnail.jpg", "b": "thumbnail_b.jpg", "c": "thumbnail_c.jpg"}


def select_thumbnail(run: Run, choice: str) -> str:
    """Record which of the three thumbnails you want used.

    Called from the review chat ("thumbnail b") or by hand. Stored in the run's
    state so the upload and the packet both agree on it.
    """
    # Accept "b", "thumbnail_b" or "thumbnail_b.jpg" - they all mean the same.
    key = choice.strip().lower().removesuffix(".jpg").removeprefix("thumbnail").strip("_ ") or "a"
    if key not in THUMBNAIL_FILES:
        raise ValueError(f"Thumbnail must be one of {', '.join(THUMBNAIL_FILES)} - got '{choice}'.")

    filename = THUMBNAIL_FILES[key]
    if not run.path("output", filename).exists():
        raise FileNotFoundError(f"{filename} was not produced by this run.")

    run.save_state(chosen_thumbnail=filename)
    log(f"Thumbnail set to {filename}")
    return filename


def chosen_thumbnail(run: Run) -> Path:
    """The thumbnail file to upload: your pick, or the ranked winner."""
    return run.path("output", run.state().get("chosen_thumbnail", "thumbnail.jpg"))


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

    # Commons' CC BY files require this, and NASA asks for it.
    stock = run.read_json("stock.json") if run.path("stock.json").exists() else {}
    credits = sorted({f"- {c['credit']} ({c['license']}): {c['page']}"
                      for entry in stock.values() for c in entry.get("clips", []) if c.get("credit")})
    if credits:
        parts += ["", "FOOTAGE & IMAGES", "", *credits]

    parts += [
        "",
        "This video's narration is generated with AI text-to-speech. "
        "The research, editorial judgement and final edit are human.",
    ]
    return "\n".join(parts)


def build_packet(run: Run) -> str:
    """One file with everything needed to upload the video by hand.

    The point is that you never have to go hunting through the run folder: the
    title, the finished description, the tags, which thumbnail is selected and
    where the subtitle file is are all here, in the order YouTube asks for them.
    """
    metadata = run.read_json("metadata.json")
    state = run.state()
    tags = metadata.get("tags", [])[:15]
    selected = chosen_thumbnail(run).name

    thumbnails = run.read_json("thumbnails.json") if run.path("thumbnails.json").exists() else []
    thumbnail_lines = []
    for letter, filename in THUMBNAIL_FILES.items():
        if not run.path("output", filename).exists():
            continue
        # thumbnails.json records the concept behind each file it wrote.
        concept = next((t for t in thumbnails if t.get("file") == filename), {})
        marker = "**SELECTED**" if filename == selected else "reply `thumbnail " + letter + "` to use"
        thumbnail_lines.append(
            f"- **{letter}** — `output/{filename}` — "
            f"{concept.get('text') or '(no text)'}: {concept.get('hero', '')} — {marker}"
        )

    subtitles = run.path("output", "subtitles.srt")
    minutes = state.get("narration_seconds", 0) / 60

    return "\n".join([
        f"# Upload packet — run `{run.id}`",
        "",
        f"Video: `output/video.mp4` (~{minutes:.1f} min)",
        "",
        "## Title",
        "",
        f"{metadata.get('title', '(none)')}",
        "",
        f"_{len(metadata.get('title', ''))} / 100 characters_",
        "",
        "## Description",
        "",
        "```",
        build_description(run, metadata),
        "```",
        "",
        "## Tags",
        "",
        "```",
        ", ".join(tags),
        "```",
        "",
        "## Thumbnails",
        "",
        *(thumbnail_lines or ["_None produced._"]),
        "",
        "## Subtitles",
        "",
        (f"`output/subtitles.srt` — {state.get('subtitle_cues', 0):,} cues"
         if subtitles.exists() else "_Not produced - run the captions stage._"),
        "",
        "## Pinned comment",
        "",
        "```",
        metadata.get("pinned_comment") or "(none written)",
        "```",
        "",
        "## Before you publish",
        "",
        "- Category: **Science & Technology**",
        "- Audience: **not made for kids**",
        "- Tick **altered or synthetic content** (the narration is AI text-to-speech)",
        f"- Start it **{load_config()['safety'].get('upload_privacy', 'private')}**, "
        "watch the first 30 seconds, then go public",
    ])


def have_youtube_keys() -> bool:
    """True when all three OAuth secrets are set."""
    return all(has_secret(name) for name in
               ("YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"))


def build_snippet(run: Run, metadata: dict) -> dict:
    """The snippet block YouTube wants, built from metadata.json.

    Shared by the first upload and by every later edit, so a title change and
    a fresh upload can never disagree about the description or the category.
    """
    return {
        "title": metadata["title"][:100],
        "description": build_description(run, metadata)[:5000],
        "tags": metadata.get("tags", [])[:15],
        "categoryId": "28",  # Science & Technology. 27 is Education.
    }


def upload(run: Run) -> str:
    """Upload the finished video as PRIVATE, ready for you to review."""
    cfg = load_config()
    safety = cfg["safety"]

    # Written every time, so a hand upload gets the sources and footage credits too.
    run.write_text("output/description.txt", build_description(run, run.read_json("metadata.json")))
    run.write_text("output/UPLOAD.md", build_packet(run))

    if not have_youtube_keys():
        log("YouTube secrets are not set - skipping the upload.")
        log("Everything needed to upload by hand is in the run's output/UPLOAD.md.")
        return ""

    from googleapiclient.http import MediaFileUpload

    metadata = run.read_json("metadata.json")
    video_path = Path(run.state()["video_path"])
    youtube = build_client()

    review_privacy = safety.get("upload_privacy", "private")

    body = {
        "snippet": build_snippet(run, metadata),
        "status": {
            # Never public on the way in. The video sits at this privacy while
            # you review it on your phone; replying `publish` flips it to
            # public - see go_live() below.
            "privacyStatus": review_privacy if review_privacy != "public" else "private",
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

    thumbnail = chosen_thumbnail(run)
    if thumbnail.exists():
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=str(thumbnail)).execute()
            log(f"  thumbnail set ({thumbnail.name})")
        except Exception as error:  # noqa: BLE001
            log(f"  thumbnail upload failed ({error}) - set it by hand in YouTube Studio")

    # Captions are a separate API call - the video exists first, then the track
    # is attached to it. Losing them is not worth failing the upload over.
    subtitles = run.path("output", "subtitles.srt")
    if subtitles.exists():
        try:
            youtube.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "language": "en", "name": "English"}},
                media_body=MediaFileUpload(str(subtitles), mimetype="application/octet-stream"),
            ).execute()
            log("  subtitles attached")
        except Exception as error:  # noqa: BLE001
            log(f"  subtitle upload failed ({error}) - add subtitles.srt by hand in YouTube Studio")

    run.save_state(
        video_id=video_id,
        video_url=f"https://youtu.be/{video_id}",
        video_privacy=body["status"]["privacyStatus"],
        chat_stage="review",
    )
    run.mark_done("publish")
    return video_id


# ---------------------------------------------------------------------------
# Editing a video that's already uploaded
#
# These are what the chat calls when you reply "make the title shorter" or
# "use thumbnail b" after watching the private upload. None of them re-upload
# the video - they change one thing on the video that's already there.
# ---------------------------------------------------------------------------

def apply_metadata(run: Run) -> bool:
    """Push the current metadata.json up to the already-uploaded video."""
    video_id = run.state().get("video_id")
    if not video_id or not have_youtube_keys():
        return False

    metadata = run.read_json("metadata.json")
    # Rewrite the packet too, so the file on disk never disagrees with YouTube.
    run.write_text("output/description.txt", build_description(run, metadata))
    run.write_text("output/UPLOAD.md", build_packet(run))

    build_client().videos().update(
        part="snippet",
        body={"id": video_id, "snippet": build_snippet(run, metadata)},
    ).execute()

    log(f"Updated {video_id}: {metadata['title']}")
    return True


def apply_thumbnail(run: Run) -> bool:
    """Push the chosen thumbnail up to the already-uploaded video."""
    video_id = run.state().get("video_id")
    thumbnail = chosen_thumbnail(run)
    if not video_id or not have_youtube_keys() or not thumbnail.exists():
        return False

    build_client().thumbnails().set(videoId=video_id, media_body=str(thumbnail)).execute()
    run.write_text("output/UPLOAD.md", build_packet(run))
    log(f"Thumbnail on {video_id} is now {thumbnail.name}")
    return True


def go_live(run: Run, privacy: str = "public") -> str:
    """Flip the reviewed video from private to public. This is the publish step.

    Note the caveat in this module's docstring: while the Google API project is
    unaudited, this call succeeds but YouTube keeps the video private. Check
    the link before you announce it anywhere.
    """
    video_id = run.state().get("video_id")
    if not video_id:
        raise RuntimeError("This run has no uploaded video to publish.")
    if not have_youtube_keys():
        raise RuntimeError("YouTube secrets are not set - publish it from the app instead.")

    safety = load_config()["safety"]
    build_client().videos().update(
        part="status",
        body={
            "id": video_id,
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
                "containsSyntheticMedia": safety.get("declare_ai_generated", True),
            },
        },
    ).execute()

    run.save_state(video_privacy=privacy, chat_stage="published")
    log(f"https://youtu.be/{video_id} is now {privacy}")
    return video_id


def post_comment(run: Run) -> bool:
    """Post metadata's pinned_comment under the video. Never raises.

    YouTube's API can post a comment but cannot pin it - that's one tap on
    the comment in the YouTube app or Studio.
    """
    video_id = run.state().get("video_id")
    text = run.read_json("metadata.json").get("pinned_comment", "")
    if not video_id or not text or not have_youtube_keys() or run.state().get("comment_id"):
        return False
    try:
        response = build_client().commentThreads().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id,
                              "topLevelComment": {"snippet": {"textOriginal": text}}}},
        ).execute()
    except Exception as error:  # noqa: BLE001
        log(f"Could not post the comment ({error}) - paste it from UPLOAD.md")
        return False
    run.save_state(comment_id=response["id"])
    log(f"Comment posted on {video_id}")
    return True


def delete_video(run: Run) -> bool:
    """Remove the private upload.

    Needed when the video itself is re-rendered: YouTube cannot swap the file
    behind an existing video, so a re-render means a new upload and this one
    has to go.
    """
    video_id = run.state().get("video_id")
    if not video_id or not have_youtube_keys():
        return False

    try:
        build_client().videos().delete(id=video_id).execute()
        log(f"Deleted the previous upload ({video_id})")
    except Exception as error:  # noqa: BLE001
        log(f"Could not delete {video_id} ({error}) - remove it in YouTube Studio")

    # Cleared either way: the run must not keep pointing at a video it replaced.
    run.save_state(video_id="", video_url="", video_privacy="", comment_id="")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload the finished video.")
    parser.add_argument("--run", default="latest")
    parser.add_argument("--go-live", action="store_true",
                        help="Flip an already-uploaded video to public.")
    args = parser.parse_args()

    active = resolve_run(args.run)
    if args.go_live:
        go_live(active)
    else:
        upload(active)
