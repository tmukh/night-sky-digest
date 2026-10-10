You are helping build an evaluation set for a search engine over arXiv astrophysics (astro-ph)
paper abstracts. The index holds about 51,000 abstracts submitted or revised between October 2024
and October 2026. Only titles and abstracts are indexed, never full text.

Write 60 search queries, in English, that real people would type into this search engine: researchers,
PhD students, and curious readers. Each query comes with an "intent" that defines which papers count
as relevant. Another model will later use your intent to judge search results, so the intent must be
precise enough to decide "relevant or not" from a title and abstract alone.

Rules:
1. Do not look anything up and do not base a query on a specific paper or paper title you remember.
   Write information needs, not paraphrased titles.
2. Each topic must have been actively published on during October 2024 to October 2026, so that at
   least a few relevant abstracts plausibly exist.
3. Exactly 10 queries per astro-ph subfield:
   CO (cosmology and nongalactic), EP (earth and planetary), GA (galaxies), HE (high-energy),
   IM (instrumentation and methods), SR (solar and stellar).
4. Use every query kind at least 6 times:
   - topical: plain subject words ("tidal disruption events in dwarf galaxies")
   - identifier: a named object, event, catalogue ID, mission or survey ("GW230529", "TRAPPIST-1e")
   - question: natural phrasing ("why do some magnetars emit fast radio bursts")
   - synonym: everyday or unusual wording that differs from the jargon papers use
     ("planets around dead stars" for planets orbiting white dwarfs)
   - method: a technique rather than an object ("simulation-based inference for weak lensing")
   - contrarian: the relevant papers argue against the mainstream view ("galaxy rotation curves
     without dark matter")
5. Vary the length from 2 to 15 words. Write some queries casually, in lower case without punctuation,
   the way people type into search boxes.
6. No two queries about the same topic. No time-relative words ("latest", "recent", "new").
7. The intent has 2 to 3 sentences: what makes a paper relevant, then a sentence starting with
   "Not relevant:" naming close-but-wrong papers.

Output only YAML, no commentary before or after, in exactly this shape:

- id: q001
  query: how are fast radio bursts localised to their host galaxies
  intent: >
    Papers that localise fast radio bursts (interferometry, VLBI, ASKAP, MeerKAT, CHIME outriggers)
    or identify and characterise FRB host galaxies. Not relevant: FRB population statistics or
    emission mechanisms without any localisation.
  subfield: HE
  kind: question

Number the ids q001 to q060.
