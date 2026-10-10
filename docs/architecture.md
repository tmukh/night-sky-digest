# Architecture

Target state (M5). Each component is tagged with the milestone it arrives in.

## Runtime

Diagram: see [README](../README.md#runtime).

Three workloads, two shared services:

- **ingest** (CronJob): OAI-PMH `ListRecords` for `physics:astro-ph`, following resumption tokens, one
  request per 3 s. Upserts on arXiv ID, so re-running a night is harmless (idempotent). Stores the last
  successful `from` date, so a crash resumes instead of restarting (resumable).
- **digest** (CronJob): picks the day's new papers, asks the LLM for a short digest, rejects any output that
  cites an ID not in the retrieved set (faithfulness check), stores it.
- **api** (Deployment): `/search` runs a pgvector nearest-neighbour query and a Postgres full-text query,
  then merges the two ranked lists with reciprocal-rank fusion. `/digest` serves the latest digest.
  This is the only thing exposed through the Cloudflare tunnel.
- **PostgreSQL + pgvector**: one database for metadata, embeddings, the lexical index and digests.
- **Ollama**: multilingual embeddings (bge-m3) and the summary LLM, on the Windows PC's GPU, reached over
  Tailscale ([ADR 0002](adr/0002-ollama-on-windows-gpu.md)). A hosted LLM API is optional behind a flag.

## Delivery

Diagram: see [README](../README.md#delivery).

Same pattern as application-tracker: the app repo publishes images, homelab-dev decides what runs.

## Decided

- Ollama runs on the Windows PC's GPU, outside the cluster: [ADR 0002](adr/0002-ollama-on-windows-gpu.md).

- Backfill via OAI-PMH, not the bulk snapshot: 2 years of astro-ph is ~95k records in ~75 pages of
  ~1,300, so about 15 minutes at 1 request / 3 s (measured 2026-10-10: one page ≈ 5 MB, ≈ 10 s to generate).

## Open decisions

| Question | Decide by | Notes |
|---|---|---|
| Embedding dimension and index type (HNSW vs IVFFlat) | M2 | bge-m3 dense = 1024 dims. |
| How the frozen eval snapshot gets into CI (pg_dump artifact vs fixture) | M3 | Must be small and deterministic. |
