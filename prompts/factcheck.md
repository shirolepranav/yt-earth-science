Fact-check this script against the research dossier. You are looking for claims the dossier does not support — this is the last line of defence before a wrong number ends up in a published video.

--- SCRIPT ---
{script}
--- END SCRIPT ---

--- RESEARCH DOSSIER (the only thing that counts as support) ---
{dossier}
--- END DOSSIER ---

Check every one of these:
- Numbers, percentages, dates, ages and measurements: does the dossier contain this exact figure?
- Attributions: does the named source actually say this?
- Causal claims ("X happens because Y"): does the dossier support the causation, or only a correlation?
- Anything stated as current fact: is the dossier's figure recent enough to still be described that way?
- Deep-time ages, magnitudes, rates and death tolls: is the figure stated more precisely than the dossier supports, or does it pick one side where sources disagree? Sources marked PRIMARY SOURCE (USGS, NASA, NOAA, the Physical Geology textbook, peer-reviewed papers) outrank SECONDARY ones when they conflict.
- Hypotheses: is a contested idea stated as settled fact?

Be strict. A figure that is *close* to one in the dossier is a flag, not a pass — a rounded or drifted number is exactly the failure mode this pass exists to catch.

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
