You are the director of photography for a cinematic Earth science documentary on YouTube. Write the look bible for this one video. Most shots are real footage; the few AI-generated shots are for things no camera ever recorded (deep-time landscapes, events before people), and they are prompted with this bible so they sit alongside the real footage as one film.

TITLE: {title}

--- SCRIPT ---
{script}
--- END SCRIPT ---

Brand palette: basalt near-black {background}, magma accent {accent}. (The brand's warning colour {negative} belongs to charts and cards, not to images.)

Rules for the whole film:
- Nature documentary cinematography: natural light (low sun, overcast, dusk, firelight of lava), wide lenses for scale, aerial and ground-level views, fine grain, rich but natural colour. Grand, quiet, real.
- Geologically plausible above all. Rocks, landforms, skies, seas and ice must look like the real processes the script describes. No fantasy or sci-fi styling: no glowing crystals, floating rocks, alien skies or impossible colours.
- Never a specific real, recognisable landmark or place presented as if photographed - real places are shown with real footage.
- Never: gore, dead bodies, injury, horror imagery.
- No readable text, signage, logos, charts or numbers anywhere (image models garble them).
- No recurring people. People may appear only as small silhouettes for scale - never a face as the subject.

Invent 4 to 6 recurring LOCATIONS and 4 to 6 recurring ELEMENTS specific to this story (e.g. "a black basalt shoreline under a low overcast sky", "a layered red sandstone cliff at dusk", "a steaming fissure across bare rock"). They will come back across the video the way a set does in a real documentary.

Reply with JSON only:

{{
  "style": "One dense sentence of camera, lens, light, grade and mood language, prefixed to every cinematic shot prompt",
  "collage_style": "One dense sentence describing a clean scientific-illustration collage look (cut-out rock and landscape photos, paper textures, flat colour blocks in basalt black and magma orange), prefixed to metaphor shots",
  "locations": ["...", "..."],
  "props": ["...", "..."]
}}
