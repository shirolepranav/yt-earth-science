"""Build the assets the Remotion demo needs, without calling any paid API.

Run this once after installing, then render the demo to check that video
assembly - including the three.js charts and the depth-parallax stills - works
on your machine before you spend anything:

    python tools/make_demo.py
    cd remotion && npx remotion render MainVideo out/demo.mp4 --props=demo-props.json

It writes, into remotion/public/demo/:
  still.jpg / depth.png   a synthetic "keyframe" and depth map for the parallax shot
  plate.jpg               a background plate for the card
  narration.wav           silence, as a stand-in for the voice
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = ROOT / "remotion" / "public" / "demo"


def make_silence(path: Path, seconds: float, sample_rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(b"\x00" * int(seconds * sample_rate * 2))


def make_scene(size=(1920, 1080)) -> tuple[Image.Image, Image.Image]:
    """A dark scene with a lit ground plane and an orange glow, plus a matching depth map."""
    w, h = size
    image = Image.new("RGB", size, (14, 17, 23))
    depth = Image.new("L", size, 30)
    draw, ddraw = ImageDraw.Draw(image), ImageDraw.Draw(depth)
    for i in range(12):  # far wall panels
        draw.rectangle([i * 170, 80, i * 170 + 120, 620], fill=(24 + i, 30 + i, 40 + i))
    draw.polygon([(0, h), (w, h), (w * 0.8, 640), (w * 0.2, 640)], fill=(52, 40, 30))  # table
    ddraw.polygon([(0, h), (w, h), (w * 0.8, 640), (w * 0.2, 640)], fill=170)
    draw.ellipse([1200, 300, 1500, 600], fill=(245, 166, 35))  # lamp glow
    ddraw.ellipse([1200, 300, 1500, 600], fill=120)
    draw.rectangle([700, 700, 1100, 980], fill=(225, 220, 205))  # envelope, nearest
    ddraw.rectangle([700, 700, 1100, 980], fill=250)
    return image.filter(ImageFilter.GaussianBlur(3)), depth.filter(ImageFilter.GaussianBlur(12))


def main() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    still, depth = make_scene()
    still.save(DEMO_DIR / "still.jpg", quality=92)
    depth.save(DEMO_DIR / "depth.png")
    still.transpose(Image.FLIP_LEFT_RIGHT).save(DEMO_DIR / "plate.jpg", quality=92)

    duration = json.loads((ROOT / "remotion" / "demo-props.json").read_text())["durationSeconds"]
    make_silence(DEMO_DIR / "narration.wav", duration + 0.5)

    print(f"Demo assets written to {DEMO_DIR}")
    print("Now run:  cd remotion && npx remotion render MainVideo out/demo.mp4 --props=demo-props.json")


if __name__ == "__main__":
    main()
