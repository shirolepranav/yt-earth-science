Fact-check this script against the research dossier. You are looking for claims the dossier does not support — this is the last line of defence before a wrong number ends up in a published video.

--- SCRIPT ---
{script}
--- END SCRIPT ---

--- RESEARCH DOSSIER (the only thing that counts as support) ---
{dossier}
--- END DOSSIER ---

Check every one of these:
- Numbers, percentages, dates and dollar amounts: does the dossier contain this exact figure?
- Attributions: does the named source actually say this?
- Causal claims ("X happens because Y"): does the dossier support the causation, or only a correlation?
- Anything stated as current fact: is the dossier's figure recent enough to still be described that way?

Be strict. A figure that is *close* to one in the dossier is a flag, not a pass — a rounded or drifted number is exactly the failure mode this pass exists to catch.

Reply with JSON only:

{{
  "flags": [
    {{
      "quote": "The exact sentence from the script",
      "problem": "unsupported | wrong_number | wrong_attribution | overstated_causation | outdated",
      "detail": "What the dossier actually says, or that it says nothing",
      "suggested_fix": "The corrected sentence, or 'CUT' if it cannot be salvaged"
    }}
  ],
  "verdict": "clean | minor_fixes | do_not_publish"
}}
