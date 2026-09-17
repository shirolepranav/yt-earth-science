"""STAGE 11 - Thumbnails.

Thumbnail and title decide whether anyone ever sees the video. Three genuinely
different concepts are made, tested, and ranked:

  1. Concepts   - planned with the title at Gate 2 (polish pass): at most four
                  words that DON'T repeat the title, or no text at all (the
                  strongest thumbnails in this genre often
                  have none); one hero image that tells the story; one
                  symbol. Older runs without concepts get them generated here.
  2. Image      - one photographic hero per concept, prompted for the checklist:
                  one huge subject, high contrast and saturation, darkened
                  background, clear space where the text goes, nothing important
                  in the bottom-right (the duration badge), no text or logos.
  3. Text       - drawn with Pillow, not the image model: Anton block capitals,
                  white with figures in yellow, a heavy black stroke, top-left.
                  Pixel-perfect every time. Plus the symbol (arrow, circle, red X,
                  REC dot) and no border, no channel logo.
  4. Shrink test - each candidate is shown to a vision model at phone size and
                  scored for readability, attention and curiosity.

Writes output/thumbnail.jpg (the winner) plus thumbnail_b.jpg and
thumbnail_c.jpg for YouTube Studio's Test & Compare, and thumbnails.json with
the scores.

Run it:  python -m pipeline.thumbnail --run latest
"""

from __future__ import annotations

import re

from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, Run, has_secret, load_config, log, resolve_run
from .fal import generate_image
from .llm import chat_json, vision_check
from .visuals import cache_path

WIDTH, HEIGHT = 1280, 720  # YouTube's thumbnail size
FONT = ROOT / "assets" / "fonts" / "Anton-Regular.ttf"
YELLOW, RED = (255, 212, 0), (235, 38, 38)

IMAGE_PROMPT = (
    "Photographic YouTube thumbnail for a cinematic Earth science documentary: {hero}. "
    "One single huge hero subject, dramatic high-contrast lighting, rich saturated colour "
    "against a darkened, softly blurred background, razor-sharp detail. {layout} "
    "Nothing important in the bottom-right corner. Absolutely no text, letters, numbers, "
    "logos, emojis, borders or watermarks."
)
SHRINK_TEST = (
    "This image is a YouTube thumbnail, shown at the size it appears on a phone. "
    'Reply as JSON only: {"text_readable": true/false (true if there is no text), '
    '"about": "what you think the video is about, in under 10 words", '
    '"attention": 0-10 (how hard it grabs the eye in a feed), '
    '"emotion": 0-10 (how much curiosity or sense of scale it creates)}'
)
CONCEPTS_PROMPT = """Title of a cinematic Earth science video: {title}

Opening of the narration:
{opening}

Give three genuinely different thumbnail concepts. The thumbnail must NOT repeat the title's words.
"text": at most 4 words, ALL CAPS, or null for a pure visual story (at least one must be null).
"hero": one striking photographic image telling the story at phone size - a landscape, a phenomenon, an object or a dramatic scale contrast. Never a specific real person.
"symbol": one of "arrow", "circle", "red_x", "rec_dot", "none".
"why_click": one sentence.

Reply with JSON only: {{"thumbnail_concepts": [{{"text": "...", "hero": "...", "symbol": "...", "why_click": "..."}}]}}"""


# ---------------------------------------------------------------------------
# Compositing
# ---------------------------------------------------------------------------

def wrap_to_width(draw, text: str, font, max_width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_text(image: Image.Image, text: str) -> tuple[int, int, int, int]:
    """Big block capitals in the left ~45%, top-aligned. Returns the text box."""
    draw = ImageDraw.Draw(image)
    words = text.upper().split()[:4]
    max_width = int(WIDTH * 0.47)

    size = 190
    while True:  # largest size that fits in three lines and the width
        font = ImageFont.truetype(str(FONT), size)
        lines = wrap_to_width(draw, " ".join(words), font, max_width)
        if size <= 70 or (len(lines) <= 3 and all(draw.textlength(l, font=font) <= max_width for l in lines)):
            break
        size -= 8

    x, y = 48, 44
    line_height = int(size * 1.02)
    widest = 0
    for index, line in enumerate(lines):
        cursor = x
        for word in line.split():
            # Figures in yellow: the number is the hook.
            fill = YELLOW if re.search(r"[\d$%?!]", word) else (255, 255, 255)
            draw.text((cursor, y + index * line_height), word, font=font, fill=fill,
                      stroke_width=max(6, size // 16), stroke_fill=(0, 0, 0))
            cursor += draw.textlength(word + " ", font=font)
        widest = max(widest, int(cursor - x))
    return x, y, x + widest, y + line_height * len(lines)


def draw_symbol(image: Image.Image, symbol: str, text_box: tuple[int, int, int, int] | None) -> None:
    draw = ImageDraw.Draw(image)
    if symbol == "arrow":
        # From beside the text toward the hero, stopping short of the bottom-right.
        sx = text_box[2] + 30 if text_box else 300
        sy = (text_box[1] + text_box[3]) // 2 + 40 if text_box else 420
        ex, ey = int(WIDTH * 0.6), int(HEIGHT * 0.5)
        mx, my = (sx + ex) // 2, max(sy, ey) + 60  # control point: the arrow bows downward
        points = [((1 - t) ** 2 * sx + 2 * (1 - t) * t * mx + t ** 2 * ex,
                   (1 - t) ** 2 * sy + 2 * (1 - t) * t * my + t ** 2 * ey)
                  for t in (i / 12 for i in range(13))]
        draw.line(points, fill=(0, 0, 0), width=26, joint="curve")
        draw.line(points, fill=YELLOW, width=16, joint="curve")
        draw.polygon([(ex + 8, ey - 6), (ex - 44, ey - 16), (ex - 22, ey + 34)], fill=YELLOW, outline=(0, 0, 0))
    elif symbol == "circle":
        box = [int(WIDTH * 0.55), int(HEIGHT * 0.2), int(WIDTH * 0.88), int(HEIGHT * 0.72)]
        draw.ellipse(box, outline=(0, 0, 0), width=22)
        draw.ellipse(box, outline=RED, width=14)
    elif symbol == "red_x":
        cx, cy, r = int(WIDTH * 0.8), int(HEIGHT * 0.3), 90
        for width, colour in ((42, (0, 0, 0)), (28, RED)):
            draw.line([(cx - r, cy - r), (cx + r, cy + r)], fill=colour, width=width)
            draw.line([(cx - r, cy + r), (cx + r, cy - r)], fill=colour, width=width)
    elif symbol == "rec_dot":
        cx, cy, r = WIDTH - 90, 80, 30
        draw.ellipse([cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6], fill=(0, 0, 0))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)


def compose(background: Image.Image, concept: dict) -> Image.Image:
    image = background.convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
    text = (concept.get("text") or "").strip()
    box = draw_text(image, text) if text else None
    draw_symbol(image, concept.get("symbol", "none"), box)
    return image


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

def score(run: Run, image: Image.Image) -> tuple[float, dict]:
    small = run.path("assets", "_thumb_check.jpg")
    image.resize((320, 180), Image.LANCZOS).save(small, "JPEG", quality=90)
    try:
        verdict = vision_check(str(small), SHRINK_TEST)
        total = float(verdict.get("attention", 0)) + float(verdict.get("emotion", 0))
        return (total if verdict.get("text_readable", True) else total - 6), verdict
    except Exception as error:  # noqa: BLE001 - an unscored thumbnail still ships
        return 0.0, {"error": str(error)}
    finally:
        small.unlink(missing_ok=True)


def generate(run: Run) -> list:
    cfg = load_config()["thumbnail"]
    if not has_secret("FAL_KEY"):
        raise RuntimeError("FAL_KEY is not set - thumbnails are generated with fal.ai. See SETUP.md.")

    metadata = run.read_json("metadata.json")
    title = metadata.get("title", "")
    concepts = metadata.get("thumbnail_concepts") or chat_json(
        "You are a YouTube packaging strategist. Reply with JSON only.",
        CONCEPTS_PROMPT.format(title=title, opening=run.read_text("script.txt")[:800]),
        label="thumbnail concepts",
    ).get("thumbnail_concepts", [])

    candidates = []
    for concept in concepts[: cfg["variants"]]:
        layout = ("Hero subject on the right two-thirds of the frame; the left third is dark and empty."
                  if concept.get("text") else "Hero subject centred, filling the frame edge to edge.")
        prompt = IMAGE_PROMPT.format(hero=concept.get("hero", title), layout=layout)
        background_path = cache_path(run, cfg["image_model"], {"prompt": prompt}, "jpg")
        try:
            if not background_path.exists():
                generate_image(cfg["image_model"], prompt, background_path, WIDTH * 2, HEIGHT * 2)
            image = compose(Image.open(background_path), concept)
        except Exception as error:  # noqa: BLE001 - lose one variant, not the stage
            log(f"  thumbnail concept failed ({error}): {concept.get('hero', '')[:60]}")
            continue
        points, verdict = score(run, image)
        log(f"  {concept.get('text') or '(no text)'}: score {points:.0f} - {verdict.get('about', '')}")
        candidates.append((points, image, {**concept, "score": points, "shrink_test": verdict}))

    if not candidates:
        raise RuntimeError("No thumbnail could be generated.")

    candidates.sort(key=lambda c: c[0], reverse=True)
    names = ["thumbnail.jpg", "thumbnail_b.jpg", "thumbnail_c.jpg"]
    written = []
    for name, (_, image, info) in zip(names, candidates):
        path = run.path("output", name)
        image.save(path, "JPEG", quality=92)
        written.append({"file": name, **info})
    run.write_json("thumbnails.json", written)
    run.mark_done("thumbnail")
    log(f"Thumbnails written: {', '.join(w['file'] for w in written)} (best first)")
    return written


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate and rank the thumbnails.")
    parser.add_argument("--run", default="latest")
    args = parser.parse_args()

    generate(resolve_run(args.run))
