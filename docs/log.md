# Log

Short notes on what I did each day and what I got stuck on. Break-it labs get two lines: the symptom,
and the command that exposed it.

## 2026-10-10

Created the repo. Wrote the plan, architecture and ADR 0001. No code yet.

First Trivy scan of the image (python:3.12-slim-trixie, Debian 13.7):
- Debian: 166 findings, 0 CRITICAL, 44 HIGH. The 44 HIGH are only 8 distinct CVEs, because util-linux
  builds 9 binary packages and Trivy counts each one. None of the 44 has a fixed version yet.
- Python: 6 (MEDIUM/LOW), all in the base image's pip 25.0.1. Our own dependencies: 0.
