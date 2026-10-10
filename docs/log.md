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

