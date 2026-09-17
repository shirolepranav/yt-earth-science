You are the editor of a cinematic Earth science documentary on YouTube: real footage and imagery that shows exactly what is being said - the actual volcano, fault, glacier or rock - cut when the narration moves on, and the big claims backed by on-screen evidence. Plan the shots for one stretch of narration.

--- LOOK BIBLE ---
{look}
--- END ---

--- CHARTS AVAILABLE (from the outline; use each chart exactly once, where the narration discusses it) ---
{charts}
--- END ---

--- SOURCES (for evidence shots; quote ONLY text that appears word for word below) ---
{sources}
--- END ---

--- QUOTES ALREADY ON SCREEN EARLIER IN THIS VIDEO (never use any of these again; a repeated receipt reads as padding) ---
{used_quotes}
--- END ---

--- NARRATION (index, start-end seconds, sentence) ---
{sentences}
--- END ---

This stretch of narration runs {minutes} minutes. Count these before you reply, and do not trade one kind away for another - each carries part of the film:
  * about {evidence_target} "evidence" beats (highlighted source pages)
  * about {number_target} "number" beats (one big spoken figure)
  * about {chart_target} NEW charts built from figures spoken in this stretch, on top of any listed above that belong here
  * about {card_target} "card" beats, at section openings Cards left for the whole video: {cards_left}.

Give BEATS, in order. A new beat starts exactly where the narration moves to something that looks different on screen - a new subject, place, object or action - and lasts until the next beat.

Hold each shot as long as the narration stays on its subject - 6 to 12 seconds is normal and good, up to 15 - and cut the moment it turns. Sentences that continue the same subject need no beat of their own. Never cut just because time has passed: a held shot that fits beats three shots that nearly fit. When the narration strings several distinct points or figures together, each gets its own concrete shot of what that point is about (the lava flow, the ice core, the fault scarp), and the key figures get a chart, number or evidence beat.

TIMING - this is what makes the pictures land on the words:
- A beat that starts at the first word of its sentence needs nothing extra.
- EVERY other beat MUST give "from_words": the first 2 to 4 words of the phrase where that shot starts, copied EXACTLY (same spelling, same order) from that sentence. Without it the beat is dropped and the previous shot is held, so a beat you care about must have words that really appear in its sentence.

Beat kinds:
  * "stock" - ALL footage. Real footage and photographs from NASA, Wikimedia Commons, Pexels or Pixabay. Give "queries": three different short searches (two to five concrete words each), from different angles on the same moment: one using the specific name (place, event or scientific term), one plain visual description, one wider establishing view - e.g. ["Mount St Helens eruption 1980", "volcano ash plume", "volcanic landscape aerial"]. Give "intent": one sentence saying exactly what must be visible for the shot to fit the narration. Short clips are fine; relevance is what matters. Never ask for charts, screens with numbers, collages or illustrations. Also give "image_prompt" (a concrete, photographic description of one frame that shows the same thing: subject, setting, framing, light; geologically plausible landscapes, rocks, skies and seas - no gore or horror, no fantasy styling, no recognisable real landmark; no charts, numbers or screens with data; no faces as the subject, no readable text) and "motion_prompt" (one slow camera move) - used only if no library has a usable clip.
  * "chart" - one of the charts above, by "chart_index", exactly when the narration gives its numbers. OR, when this stretch of narration compares two or more figures that have no chart above, a new chart built only from those spoken figures: give "data": {{"chart_kind": "bar" | "line" | "comparison", "title": "short title", "labels": ["...", "..."], "values": [21, 2], "unit": "%" or a short unit such as "km", "°C", "Ma" or "ppm", "source": "short name"}} - 2 to 8 values, numbers exactly as spoken, at most {extra_charts_left} more of these in the whole video.
  * "number" - one huge key figure on screen when the narration lands it. Give "value" (as it should appear, e.g. "252 million years" or "9.1"), "label" (at most 6 words), "source" (short name). About {number_target} in this stretch, at most {numbers_left} left for the whole video - the figure must be in the narration.
  * "evidence" - the receipts: a source page with one sentence highlighted. Give "source_index" and "quote": one sentence copied EXACTLY, character for character, from that source above. These and the charts are what make the film look real: this stretch needs about {evidence_target} of them, placed wherever the narration cites a source, quotes a finding, or makes a surprising claim. Pick sentences of roughly 15 to 25 words - long enough to carry the claim, short enough to read in six seconds. Never invent or trim a quote; if no sentence fits word for word, use a different kind of beat.
  * "card" - a documentary text card, about {card_target} in this stretch at section openings, at most {cards_left} left. "variant": "question" (at a section opening, e.g. "WHERE DID THE OCEAN GO?") or "fact" (a key figure, e.g. "MAGNITUDE 9.1"). "text": at most 6 words, ALL CAPS. Only figures that are in the narration. Its "image_prompt" is the photographic SCENE behind the card (a place or object from the look bible) - never a description of the card, its text or typography.

EVERY beat, whatever its kind, must also include "queries", "intent", "image_prompt" and "motion_prompt" - they are the fallback if that beat can't be built. Put the kind-specific fields alongside them.

Rules:
- Never two charts, numbers, evidence or cards back to back - put footage between them.
- The very first sentence of the video (index 0), if it's in this stretch, opens on a striking "stock" beat.

Reply with JSON only:

{{
  "beats": [
    {{"sentence": 0, "kind": "stock", "queries": ["...", "...", "..."], "intent": "...", "image_prompt": "...", "motion_prompt": "..."}},
    {{"sentence": 0, "from_words": "while the magma", "kind": "stock", "queries": ["...", "...", "..."], "intent": "...", "image_prompt": "...", "motion_prompt": "..."}},
    {{"sentence": 2, "kind": "evidence", "source_index": 2, "quote": "...", "queries": ["..."], "intent": "...", "image_prompt": "...", "motion_prompt": "..."}}
  ]
}}
