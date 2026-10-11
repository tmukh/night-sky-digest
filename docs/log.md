# Log

Short notes on what I did each day and what I got stuck on. Break-it labs get two lines: the symptom,
and the command that exposed it.

## 2026-10-10

Created the repo. Wrote the plan, architecture and ADR 0001. No code yet.

First Trivy scan of the image (python:3.12-slim-trixie, Debian 13.7):
- Debian: 166 findings, 0 CRITICAL, 44 HIGH. The 44 HIGH are only 8 distinct CVEs, because util-linux
  builds 9 binary packages and Trivy counts each one. None of the 44 has a fixed version yet.
- Python: 6 (MEDIUM/LOW), all in the base image's pip 25.0.1. Our own dependencies: 0.

M0 shipped. Trivy gate: fail on fixable HIGH/CRITICAL only, full report alongside. Removed pip from the
runtime image (all 6 Python findings gone). First signed image:
`ghcr.io/tmukh/night-sky-digest@sha256:650fb7fb397bdc061cfdf22c1bf2bb0ab81ae84aa562445e8b88fb00907697d2`.
`cosign verify` passes with this repo's workflow identity and fails with any other.
Required checks on main: `test`, `image`. Break-it lab skipped.

M1: backfill of two years of astro-ph (2024-10-10 .. 2026-10-09) from this PC into the cluster
Postgres over the tailnet. 52 pages in 24 windows, 51,282 papers (43,256 with astro-ph as primary
category, the rest cross-lists), 8 min 40 s, no 503s. Recent windows are bigger than old ones because
datestamp is the last change, so re-versioned older papers pile up in recent months.
Second run right after: 1 request (the checkpoint day 2026-10-09 again), 166 unchanged, 0 inserted,
0 updated. That is the idempotent upsert working.

M2: embedded all 51,282 abstracts with bge-m3 on the RTX 3060 Ti (~20 min, ~43/s). First queries
against /search on this PC (cluster Postgres over the tailnet):
- "Gravitationswellen von verschmelzenden Neutronensternen": lexical 0 hits (English stemming can't
  match German words), semantic top 5 all about gravitational waves from neutron-star mergers.
- "GW170817": lexical matches the exact token, including papers that only cite it as a constraint;
  semantic finds afterglow/jet papers; hybrid puts papers found by both first (lex 6 / sem 3 etc.).
- Russian FRB-localisation query: top 3 all FRB localisation. Arabic "dark matter in dwarf galaxies":
  dark-matter papers, only one about dwarf spheroidals. Weakest language, matches the lower cosine
  seen earlier (0.62). M3 needs non-English queries to measure this properly.
- Latency 16-230 ms per query, mostly the query embedding.

## 2026-10-10 / 10-11: M3

Eval set: 60 English + 20 German queries from Claude (ADR 0003), pooled from all three search modes
(1,971 pairs), judged by qwen2.5:7b and gemma4:12b (kappa 0.47 on grades, 0.63 relevant-or-not),
545 + 91 disagreements tie-broken by llama3.1:8b. My audit of 30 random labels: 90% exact, kappa 0.81.
Gemma crashed once with CUDA out of memory (8.9 GB model on an 8 GB card); added retries on Ollama 5xx.
Results: hybrid nDCG@10 0.74 English, 0.67 German; full-text search finds nothing for German. CI now
runs an eval gate on a 9 MB frozen snapshot and fails on a > 2 point drop.

## 2026-10-11 / 10-12: M4

Digest: one qwen2.5:7b call per subfield with JSON-schema output, citation check with retries.
- First digest looked fine but was wrong: 23 of 79 "new" papers were revisions of 2024/2025 papers.
  arXiv's `created` is the latest version's date. New = announced that day + ID from that month or the one before.
  Exposed by: `SELECT left(arxiv_id,4), count(*) ... WHERE created = '2026-10-08' GROUP BY 1`.
- LaTeX in abstracts broke the model's JSON ("	extit" came back as a tab + "extit"). Inputs are stripped of LaTeX now.
- 2026-10-09: 102 papers, 6 calls, 14 highlights, 0 citation problems, 36 s, 29.8k prompt tokens.
Langfuse self-hosted on k3s (homelab-dev #22-#24): trace = 1 span + 6 generations with tokens and latency.
Langfuse v4 runs "events only": the old /api/public/traces endpoints are off, /api/public/v2/observations works.

