Fact-check this script against the research dossier. You are looking for claims the dossier does not support — this is the last line of defence before a wrong number ends up in a published video.

--- SCRIPT ---
{script}
--- END SCRIPT ---

--- RESEARCH DOSSIER (the only thing that counts as support) ---
{dossier}
--- END DOSSIER ---

Check every one of these:
- Numbers, percentages, dates, ages and measurements: does the dossier contain this exact figure?
- Attributions: is the organisation named out loud the publisher of the tagged source (judged from its TITLE and URL)? Crediting a figure to an agency that a news article merely quotes, or to the wrong agency, is wrong_attribution.
- Causal claims ("X happens because Y"): does the dossier support the causation, or only a correlation?
- Anything stated as current fact: is the dossier's figure recent enough to still be described that way?
- Deep-time ages, magnitudes, rates and death tolls: is the figure stated more precisely than the dossier supports, or does it pick one side where sources disagree? Sources marked PRIMARY SOURCE (USGS, NASA, NOAA, the Physical Geology textbook, peer-reviewed papers) outrank SECONDARY ones when they conflict.
- Hypotheses: is a contested idea stated as settled fact?

Be strict. A figure that is *close* to one in the dossier is a flag, not a pass — a rounded or drifted number is exactly the failure mode this pass exists to catch.

SOURCE TAGS. Factual sentences end with tags such as [S4] naming the dossier SOURCE they come from.
- Check each tagged claim against the tagged source(s) specifically. If the tagged source doesn't say it, flag it - as wrong_attribution if a different source does say it (and give the right tag in the fix), otherwise as unsupported - even when the claim is true elsewhere.
- A sentence with no tag that still states a figure, date, name or claim of fact is unsupported.
- If the script carries no tags at all (a script a person pasted), check every claim against the whole dossier instead.
- "quote" must be copied exactly from the script, tags included. "suggested_fix" keeps the correct tag(s).

Reply with JSON only:

{{
  "flags": [
    {{
      "quote": "The exact sentence from the script",
      "problem": "unsupported | wrong_number | wrong_attribution | overstated_causation | outdated | imprecise_deep_time | hypothesis_as_fact",
      "detail": "What the dossier actually says, or that it says nothing",
      "suggested_fix": "The corrected sentence, or 'CUT' if it cannot be salvaged"
    }}
  ],
  "verdict": "clean | minor_fixes | do_not_publish"
}}
