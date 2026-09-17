Propose 10 video topics for this channel, ranked best first.

You have three kinds of evidence below. Weigh them like this:
- An OUTLIER VIDEO (high views relative to its channel's subscriber count) is the strongest signal — the topic carried it, not the audience.
- A RISING SEARCH TREND means the topic is growing, not dying. Reject anything clearly in decline.
- A HIGH-ENGAGEMENT QUESTION from a forum means real people are confused about this and nobody has answered it well.

--- BACKLOG (the style of topic this channel already committed to) ---
{backlog}

--- OUTLIER VIDEOS IN THIS NICHE ---
{outliers}

--- SEARCH TREND SIGNALS ---
{trends}

--- HIGH-ENGAGEMENT QUESTIONS ---
{questions}

Rules for the topics you propose:
- Each must fit the channel angle exactly. If it needs a different audience, it's the wrong topic.
- Each must be answerable from free primary data: a government statistics agency, a central bank, a regulator, a public filing, or an academic paper. Name that source.
- No topic that requires giving individual advice.
- No topic already covered in the backlog's "already made" section, if present.
- Titles must be under 70 characters and contain a specific number or a genuine contradiction — not a vague promise.

Reply with JSON only, in exactly this shape:

{{
  "topics": [
    {{
      "rank": 1,
      "title": "The 70-character-max title as it would appear on YouTube",
      "core_question": "The one question this video answers",
      "why_they_click": "The specific tension or surprise in one sentence",
      "data_source": "The named free primary source that carries the argument",
      "evidence": "Which signal above supports this, in one short sentence"
    }}
  ]
}}
