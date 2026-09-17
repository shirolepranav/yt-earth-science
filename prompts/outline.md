Build the outline for this video. Decide the argument before any prose gets written.

TOPIC: {title}
CORE QUESTION: {core_question}

--- RESEARCH DOSSIER (everything you are allowed to claim comes from here) ---
{dossier}
--- END DOSSIER ---

Structure, with rough timings for a {target_minutes}-minute video:
- HOOK (0:00–0:30) — the threat: a number from the dossier that should scare the viewer, or a disaster already underway.
- STAKES (0:30–1:30) — what this is taking from the viewer personally, who profits, and how bad it gets.
- BODY — 3 or 4 sections, each raising the stakes on the last. Each section is built around exactly ONE number or ONE chart.
- PAYOFF — the answer to the core question, plus what it means in practice.
- CLOSE — one concrete takeaway line.

For every body section, name the single visual that carries it. A visual is either:
  * a chart you can build from a number in the dossier, or
  * a "big number" card, or
  * a comparison of two figures.
If a section has no number behind it, it is not a section — cut it or merge it.

{variation_instruction}

Reply with JSON only:

{{
  "hook_angle": "The threat or number the video opens on",
  "stakes": "Why this matters to the viewer's own money, one sentence",
  "sections": [
    {{
      "heading": "Short internal label",
      "claim": "The one thing this section establishes",
      "key_number": "The figure it hangs on",
      "source": "Named source for that figure, taken from the dossier",
      "visual": {{
        "kind": "bar | line | comparison | bignumber",
        "title": "Chart title as it appears on screen",
        "labels": ["x-axis labels, in order"],
        "values": [1.0, 2.0],
        "unit": "%",
        "source_note": "Short source credit shown under the chart"
      }}
    }}
  ],
  "payoff": "The answer, one or two sentences",
  "takeaway": "The single practical closing line"
}}
