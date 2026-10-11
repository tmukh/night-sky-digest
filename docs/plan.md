# Plan

Spec: CAREER-PLAN.md §3 Project B. This file is the working version.

Definition of done for every milestone: merged to main, CI green, deployed (from M5 on),
a line in CAREER-PLAN.md's progress log, and the ledger updated.

## Milestones

| M | Deliverable | Gaps it closes | Core piece I write |
|---|---|---|---|
| M0 ✅ | Skeleton, CI (ruff, pytest), digest-pinned Dockerfile, Trivy + Syft SBOM + cosign, image on ghcr.io | supply chain | the CI gate: which Trivy severities fail the build, and why |
| M1 ✅ | Polite OAI-PMH client (rate limit, resumable, idempotent), schema, ~2 yr astro-ph backfill | data pipeline | the resumption-token loop with the rate limiter |
| M2 ✅ | bge-m3 embeddings, pgvector + full-text search, reciprocal-rank fusion, FastAPI `/search` | RAG, FastAPI | the RRF merge |
| M3 ✅ | 60–100 hand-labelled queries (≥20 non-English), recall@10 / nDCG@10 / MRR, CI gate (fail on >2 pt drop) | evaluation | recall@k and nDCG@k |
<!-- M3 as built: LLM-generated queries + dual-LLM judging, see ADR 0003 -->
| M4 ✅ | Daily digest with citations, faithfulness check, Langfuse traces (cost, latency) | LLM integration, LLM observability | the faithfulness check |
| M5 | Argo CD from homelab-dev, CloudNativePG with MinIO backup and one tested restore, Prometheus / Grafana / Alertmanager / Loki, SLOs + error-budget panel | observability, SLOs, Postgres ops | the SLO PromQL and burn-rate alert |
| M6 | Experiments: pgvector vs Qdrant, reranker on/off; blog post | depth, portfolio | the experiment write-up |

## How to start: M0 in four steps

Each step is a PR on a branch, the same way homelab-dev works.

1. **Skeleton.** `uv init` with Python 3.12, `src/night_sky_digest/` package, a FastAPI app with `/healthz`,
   one pytest test, ruff config. Runs locally with `uv run`.
2. **CI.** `.github/workflows/ci.yml`: ruff + pytest on every PR. Branch protection on main.
3. **Image.** Multi-stage Dockerfile, `python:3.12-slim` pinned by `@sha256:` digest, non-root user
   (PSS restricted needs it later). Build in Actions, push `ghcr.io/tmukh/night-sky-digest:sha-<commit>`.
4. **Supply chain.** Trivy scan (fail on fixable HIGH/CRITICAL), Syft SBOM (SPDX JSON) attached as an
   attestation, keyless cosign signing via GitHub OIDC. Verify the signature locally with `cosign verify`.

Break-it lab for M0 (skipped on 2026-10-10, can be done later): bump the base image to an old digest with known CVEs, watch Trivy fail the build,
read the report, fix with `git revert`.

New concepts in M0 (taught when we start): image digest vs tag (builds on homelab-dev's open
"Why SHA tags"), CVE scanning and severity gates, SBOM, keyless signing (OIDC → Fulcio cert → Rekor log).

## Calendar

Three fixed 2-hour blocks a week (CAREER-PLAN §5). One milestone ≈ 2–4 blocks; M3 and M5 are bigger.
