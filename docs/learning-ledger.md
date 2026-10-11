# Learning ledger

Status: **new** (introduced), **used** (used it, not explained back yet), **confident** (explained back correctly, or predicted right twice).
Concepts already confident in homelab-dev's ledger are not repeated here.

| Concept | Introduced in | Status | Last checked | Notes |
|---|---|---|---|---|
| Image tag vs digest (`@sha256:`) | M0 | confident | 2026-10-10 | prediction was inverted, then quiz Q1 explained back correctly: pinned build stays on the old digest until a commit bumps it |
| Pinning actions by commit SHA | M0 | new | 2026-10-10 | re-quiz: knows tags can move; missed that the risk is running someone else's code with our CI secrets and push token |
| CVE scanning and severity gates (Trivy) | M0 | confident | 2026-10-10 | re-quiz correct: a Debian fix turns an ignored finding into a fixable one, the gate goes red, we bump the digest |
| SBOM (SPDX, Syft) | M0 | confident | 2026-10-10 | re-quiz correct: SBOM is bound to one digest; a Dockerfile builds different images over time |
| Keyless signing (OIDC → Fulcio → Rekor, cosign) | M0 | new | 2026-10-10 | re-quiz: didn't know the stolen-password case. Weak spot, lab candidate |
| OAI-PMH: verbs, sets, datestamp, resumption tokens | M1 | used | 2026-10-10 | harvest() written by Claude on request; explained the page/attempt loops and why it yields |
| Polite rate limiting (interval between request starts, monotonic clock, Retry-After) | M1 | new | 2026-10-10 | harvest() written by Claude on request; explain-back skipped max(remaining, server_wait) |
| Dependency injection for testability (fake clock, scripted server) | M1 | new | 2026-10-10 | |
| Idempotent upsert (ON CONFLICT ... DO UPDATE ... WHERE) | M1 | new | 2026-10-10 | prediction about 2406.10062 not answered yet |
| Checkpoint / high-water mark, resumable windows | M1 | new | 2026-10-10 | |
| Schema migrations (numbered SQL, schema_migrations, advisory lock) | M1 | new | 2026-10-10 | |
| Transactional DDL (Postgres) vs implicit commit (Oracle) | M1 | new | 2026-10-10 | |
| Embeddings, cosine similarity, normalised vectors | M2 | new | 2026-10-10 | |
| Cross-lingual embeddings (bge-m3) | M2 | new | 2026-10-10 | saw de/ru/ar queries score 0.62-0.71 vs 0.43 for unrelated English |
| Full-text search: tsvector, tsquery, stemming, weights, GIN | M2 | new | 2026-10-10 | |
| Approximate nearest neighbours: HNSW, ef_search | M2 | new | 2026-10-10 | |
| Reciprocal-rank fusion (RRF) | M2 | new | 2026-10-10 | rrf() written by Claude on request |
| Pooling (TREC-style) for relevance judgements | M3 | new | 2026-10-10 | |
| LLM-as-judge: graded relevance, structured output, reason before grade | M3 | used | 2026-10-11 | audited 30 labels by hand: 90% exact, kappa 0.81 vs final labels |
| Cohen's kappa (unweighted, linear-weighted) | M3 | new | 2026-10-10 | |
| recall@k, MRR, nDCG@k | M3 | new | 2026-10-10 | metrics written by Claude on request |
| Structured LLM output (JSON schema, constrained decoding) | M4 | new | 2026-10-11 | |
| Faithfulness check: citations must come from the given context, retry with feedback | M4 | new | 2026-10-11 | written by Claude |
| Context budgeting: per-section prompts, shortening abstracts to fit num_ctx | M4 | new | 2026-10-11 | |
| LLM tracing: traces, generations, token usage, latency, scores (Langfuse) | M4 | new | 2026-10-11 | |
| Data semantics: arXiv `created` = latest version; new = announced + fresh ID | M4 | new | 2026-10-11 | found from a wrong first digest |

