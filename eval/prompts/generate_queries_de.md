You are helping build an evaluation set for a search engine over arXiv astrophysics (astro-ph)
paper abstracts. The index holds about 51,000 abstracts submitted or revised between October 2024
and October 2026. The abstracts are in English, but users search in German, Russian and Arabic too.
Only titles and abstracts are indexed, never full text.

Write 20 search queries in German, the way German-speaking researchers, students and curious readers
would really type them into this search engine. Each query comes with an "intent" in English that
defines which papers count as relevant. Another model will later use your intent to judge the
English abstracts, so the intent must be precise enough to decide "relevant or not" from a title
and abstract alone.

Below are the 60 English queries already in the set. Use them as follows:
- Queries q061 to q065: German versions of five English queries from the list, one each from five
  different subfields. Write them as a German speaker would phrase that need, not as a word-for-word
  translation. Copy the original's intent, subfield and kind unchanged, and add
  "translation_of: <original id>".
- Queries q066 to q080: new topics that none of the 60 English queries cover.

Rules:
1. Do not look anything up and do not base a query on a specific paper or paper title you remember.
   Write information needs, not paraphrased titles.
2. Each topic must have been actively published on during October 2024 to October 2026, so that at
   least a few relevant abstracts plausibly exist.
3. Across all 20 queries: at least 3 per astro-ph subfield
   (CO cosmology, EP earth and planetary, GA galaxies, HE high-energy, IM instrumentation and methods,
   SR solar and stellar), and every kind at least twice:
   - topical: plain subject words
   - identifier: a named object, event, catalogue ID, mission or survey
   - question: natural phrasing ("Warum ...", "Wie ...", "Gibt es ...")
   - synonym: everyday or unusual wording that differs from the jargon papers use
   - method: a technique rather than an object
   - contrarian: the relevant papers argue against the mainstream view
4. Use real German usage: German terms where Germans use them ("Dunkle Materie", "Schwarzes Loch",
   "Sternentstehung"), English loanwords and acronyms where Germans keep them ("JWST", "Fast Radio
   Bursts", "Hubble-Spannung"). Mix formal and casual phrasing; some queries in lower case without
   punctuation, the way people type into search boxes. Vary the length from 2 to 15 words.
5. No time-relative words ("neueste", "aktuell", "neu").
6. The intent is in English, 2 to 3 sentences: what makes a paper relevant, then a sentence starting
   with "Not relevant:" naming close-but-wrong papers.

Output only YAML, no commentary before or after, in exactly this shape:

- id: q061
  lang: de
  query: warum ist die hubble-konstante aus cepheiden höher als aus dem CMB
  intent: >
    Papers that examine the Hubble tension between local distance-ladder measurements and 
    early-universe inferences, either by measuring H0 or by proposing or testing physical 
    explanations. Not relevant: papers that only use H0 as a fixed input, or general dark energy 
    constraints with no H0 discussion.
  subfield: CO
  kind: question
  translation_of: q005

(translation_of only on q061 to q065.) Number the ids q061 to q080.

The 60 English queries:
q001 [CO, topical] cosmic birefringence from CMB polarization
q002 [CO, topical] primordial black holes as dark matter constraints
q003 [CO, identifier] DESI DR2 neutrino mass bound
q004 [CO, identifier] ACT DR6 lensing
q005 [CO, question] why is the Hubble constant from Cepheids higher than from the CMB
q006 [CO, question] can the 21cm signal tell us about the first stars
q007 [CO, synonym] matter in the universe less clumpy than planck predicts
q008 [CO, method] emulators for the nonlinear matter power spectrum
q009 [CO, method] field level inference galaxy clustering
q010 [CO, contrarian] dynamical dark energy preference is due to supernova systematics not new physics
q011 [EP, topical] helium triplet atmospheric escape hot neptunes
q012 [EP, topical] radius valley core powered mass loss vs photoevaporation
q013 [EP, identifier] K2-18b dimethyl sulfide
q014 [EP, identifier] 3I/ATLAS activity
q015 [EP, question] do rocky planets around red dwarfs keep their atmospheres
q016 [EP, synonym] baby planets still forming inside dust rings
q017 [EP, synonym] asteroid samples brought home by spacecraft
q018 [EP, method] gaussian process stellar activity mitigation radial velocity
q019 [EP, method] transit timing variations planet masses
q020 [EP, contrarian] clustering of distant kuiper belt objects is observational bias not planet nine
q021 [GA, topical] overmassive black holes high redshift black hole to stellar mass ratio
q022 [GA, topical] ultra diffuse galaxies globular clusters
q023 [GA, identifier] GN-z11
q024 [GA, identifier] mass of the Large Magellanic Cloud and its effect on the Milky Way halo
q025 [GA, question] what are the little red dots in JWST images
q026 [GA, question] why are there so many bright galaxies at z>10
q027 [GA, synonym] galaxies that stopped making stars very early on
q028 [GA, method] Jeans anisotropic modelling IFU stellar kinematics
q029 [GA, method] nonparametric star formation histories SED fitting
q030 [GA, contrarian] evidence for modified gravity in wide binary stars
q031 [HE, topical] long gamma ray bursts from neutron star mergers kilonova
q032 [HE, topical] x-ray polarimetry corona geometry accreting black holes
q033 [HE, identifier] GW231123
q034 [HE, identifier] KM3-230213A ultra high energy neutrino
q035 [HE, question] where do the highest energy cosmic rays come from
q036 [HE, question] what powers ultraluminous x-ray sources
q037 [HE, synonym] x-ray flashes repeating every few hours from galaxy nuclei
q038 [HE, method] pulse profile modeling NICER neutron star radius
q039 [HE, method] neural posterior estimation gravitational wave parameters
q040 [HE, contrarian] fast radio bursts not from magnetars
q041 [IM, topical] satellite constellations radio frequency interference
q042 [IM, topical] wavefront sensing and control for high contrast imaging
q043 [IM, identifier] Rubin Observatory LSST data preview pipeline
q044 [IM, identifier] Euclid Q1 data release
q045 [IM, question] how to remove galactic foregrounds from 21cm intensity mapping
q046 [IM, synonym] telescopes on the far side of the moon
q047 [IM, synonym] telling real transients from junk in survey images
q048 [IM, method] deep learning deblending overlapping galaxies
q049 [IM, method] anomaly detection in alert streams
q050 [IM, contrarian] large language models unreliable for astronomy research
q051 [SR, topical] stripped stars in massive binaries
q052 [SR, topical] small scale coronal heating events solar orbiter
q053 [SR, identifier] Betelgeuse companion
q054 [SR, identifier] T Coronae Borealis nova eruption
q055 [SR, question] how do stars lose spin as they get older
q056 [SR, question] why was solar cycle 25 stronger than predicted
q057 [SR, synonym] starquakes reveal what's inside red giants
q058 [SR, method] machine learning solar flare forecasting from magnetograms
q059 [SR, method] zeeman doppler imaging starspots
q060 [SR, contrarian] red supergiant problem is not real
