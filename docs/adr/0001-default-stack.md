# ADR 0001: Default stack

Date: 2026-10-10
Status: accepted

## Context

The project has to close DevOps/SRE gaps (Postgres on k8s, observability, supply chain) and AI-engineer
gaps (retrieval, evaluation, LLM integration) in one repo, run on a single-node k3s homelab, and stay cheap.

## Decision

Python 3.12, FastAPI, PostgreSQL + pgvector (also Postgres full-text search for the lexical half),
multilingual embeddings via Ollama (bge-m3), a local LLM via Ollama for summaries (hosted API optional
behind a flag), Langfuse for LLM traces, pytest, uv for dependencies.

## Consequences

- One database to run, back up and restore, instead of Postgres plus a separate vector DB.
  Qdrant comes back only as an M6 comparison.
- Hybrid search stays inside SQL, so the eval in M3 tests one system.
- Local models mean no per-token cost, but latency depends on where Ollama runs (open question, ADR 0002).
- Any change to this stack needs a new ADR.
