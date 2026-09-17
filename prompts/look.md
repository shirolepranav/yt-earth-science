You are the director of photography for a dark, investigative finance documentary on YouTube, in the vein of ColdFusion and Moon. Write the look bible for this one video. Every AI-generated shot will be prompted with it, so it is what makes ninety separate images feel like one film.

TITLE: {title}

--- SCRIPT ---
{script}
--- END SCRIPT ---

Brand palette: near-black blue {background}, warm amber accent {accent}. (The brand's danger red {negative} belongs to charts and cards, not to images.)

Rules for the whole film:
- Cinematic documentary: 35mm film look, anamorphic lens, practical light sources (desk lamps, window light, streetlights), shallow depth of field, fine grain, crushed blacks, desaturated with the warm amber accent. Ominous, quiet, expensive.
- The script carries the fear; the images stay ordinary. Tension comes from light, shadow, emptiness and scale - never from what is in frame. Locations are clean, well-kept, recognisable homes, offices, streets and buildings the viewer could live or work in.
- Never: blood, red liquid, red stains or red splashes, injury, gore, mould, rust, decay, peeling walls, broken or filthy rooms, squalor, horror imagery. No red at all except a small practical light.
- No props with displays or digits: calculators, phones or screens showing numbers, clocks, tickers (image models garble them).
- No recurring people. People may appear only as hands, silhouettes, backs, or out-of-focus figures - never a face as the subject.
- No readable text, signage, logos or brand marks anywhere (image models garble them).

Invent 4 to 6 recurring LOCATIONS and 4 to 6 recurring PROPS specific to this story (e.g. "a tidy kitchen table under a single pendant lamp", "a thick sealed envelope on a hallway console", "a glass bank tower at dusk"). They will come back across the video the way a set does in a real documentary.

Reply with JSON only:

{{
  "style": "One dense sentence of camera, lens, light, grade and mood language, prefixed to every cinematic shot prompt",
  "collage_style": "One dense sentence describing a dark editorial collage look (halftone photo cut-outs, torn paper edges, flat color blocks in navy and amber), prefixed to metaphor shots",
  "locations": ["...", "..."],
  "props": ["...", "..."]
}}
