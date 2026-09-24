Produce the final version of this script, plus the YouTube metadata and the thumbnail concepts.

--- SCRIPT (after hook rewrite and fact-check fixes) ---
{script}
--- END SCRIPT ---

--- OUTLINE ---
{outline}
--- END OUTLINE ---

Do two jobs. (The shots are planned later, against the real narration timings - do not plan visuals here.)

JOB 1 — Final pass on the script.
Tighten anything flabby, fix any rhythm that stumbles when read aloud, and remove every remaining banned phrase. Keep the story arc and the open questions. Do not add new facts. Keep every source tag such as [S4] attached to its claim exactly as it is; tags are removed before narration, don't count as words, and never appear in the title, description, tags or pinned comment. Do not change any number. Keep it between {words_min} and {words_max} words, plain prose, blank line between paragraphs, numbers written as they are spoken.

JOB 2 — The YouTube metadata and thumbnail concepts.

Title: under 70 characters, specific and intriguing — an event, a place, a mystery or a scale. Patterns that work: "The Day ___", "What Really Killed ___", "The ___ That Almost Ended ___", "Why ___ Shouldn't Exist". It must be literally true to the script - no invented doom.

Description: a two-sentence summary that keeps the tension, and nothing else. (The source list, the AI-narration note and the footage credits are all appended automatically - don't write them.) Ten to fifteen tags.

Pinned comment: one or two sentences, under 400 characters, in the host's voice, to sit pinned under the video. Ask viewers one specific question the video raises but can't settle, or add one striking fact that didn't make the cut, so people have something to answer. No "like and subscribe", no links, no emoji.

Thumbnail concepts: three genuinely different ideas. The thumbnail and title work as a pair — the thumbnail must NOT repeat the title's words; it adds the curiosity gap the title leaves open.
  * "text": at most 4 words, ALL CAPS, or null for a pure visual story with no text at all (the strongest thumbnails in this genre often have none). At least one of the three must be null.
  * "hero": one striking, photographic image that tells the story on its own at phone size. A landscape, a phenomenon, an object or a dramatic scale contrast. One hero, huge in frame. Example: "a lone hiker silhouetted at the rim of a glowing lava lake at night". Never a specific real person.
  * "symbol": one of "arrow", "circle", "red_x", "rec_dot", "none".
  * "why_click": one sentence on the curiosity it creates.

Reply with JSON only:

{{
  "script": "The final narration text, with blank lines between paragraphs",
  "metadata": {{
    "title": "...",
    "description": "...",
    "tags": ["...", "..."],
    "pinned_comment": "...",
    "thumbnail_concepts": [
      {{"text": "4 WORDS MAX", "hero": "...", "symbol": "arrow", "why_click": "..."}},
      {{"text": null, "hero": "...", "symbol": "none", "why_click": "..."}},
      {{"text": "...", "hero": "...", "symbol": "rec_dot", "why_click": "..."}}
    ]
  }}
}}
