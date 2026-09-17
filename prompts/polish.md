Produce the final version of this script, plus the YouTube metadata and the thumbnail concepts.

--- SCRIPT (after hook rewrite and fact-check fixes) ---
{script}
--- END SCRIPT ---

--- OUTLINE ---
{outline}
--- END OUTLINE ---

Do two jobs. (The shots are planned later, against the real narration timings - do not plan visuals here.)

JOB 1 — Final pass on the script.
Tighten anything flabby, fix any rhythm that stumbles when read aloud, and remove every remaining banned phrase. Keep the dread arc and the open loops. Do not add new facts. Do not change any number. Keep it between {words_min} and {words_max} words, plain prose, blank line between paragraphs, numbers written as they are spoken.

JOB 2 — The YouTube metadata and thumbnail concepts.

Title: under 70 characters, alarming and specific — a threat, a disaster, a trap, or who is profiting. Patterns that work: "... A Disaster Waiting to Happen", "The ___ Trap", "Why ___ Is Quietly Ruining You", "The ___ Nobody Warned You About". It must still be true to the script.

Description: open with a two-sentence summary that keeps the tension, then the sources as a plain list of URLs from the outline, then a one-line note that the narration is AI-generated. Ten to fifteen tags.

Thumbnail concepts: three genuinely different ideas. The thumbnail and title work as a pair — the thumbnail must NOT repeat the title's words; it adds the curiosity gap the title leaves open.
  * "text": at most 4 words, ALL CAPS, or null for a pure visual story with no text at all (the strongest thumbnails in this genre often have none). At least one of the three must be null.
  * "hero": one striking, photographic image that tells the threat story on its own at phone size. Objects, hands, places, or one extreme close-up face showing fear or shock. One hero, huge in frame. Example: "extreme close-up of a frightened eye with a foreclosure notice reflected in it".
  * "symbol": one of "arrow", "circle", "red_x", "rec_dot", "none".
  * "why_click": one sentence on the curiosity or fear it creates.

Reply with JSON only:

{{
  "script": "The final narration text, with blank lines between paragraphs",
  "metadata": {{
    "title": "...",
    "description": "...",
    "tags": ["...", "..."],
    "thumbnail_concepts": [
      {{"text": "4 WORDS MAX", "hero": "...", "symbol": "arrow", "why_click": "..."}},
      {{"text": null, "hero": "...", "symbol": "none", "why_click": "..."}},
      {{"text": "...", "hero": "...", "symbol": "rec_dot", "why_click": "..."}}
    ]
  }}
}}
