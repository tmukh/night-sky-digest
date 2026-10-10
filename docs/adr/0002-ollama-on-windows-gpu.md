# ADR 0002: Ollama runs on the Windows PC's GPU, outside the cluster

Date: 2026-10-10
Status: accepted

## Context

The k3s cluster runs on the laptop (k3s on WSL2), which has no usable GPU. The Windows desktop has an
NVIDIA GPU and already runs Ollama. bge-m3 embeddings are fine on CPU for nightly batches, but LLM
summaries on a laptop CPU would be slow and would compete with Postgres and the monitoring stack for memory.

## Decision

Ollama (bge-m3 embeddings and the summary LLM) runs on the Windows PC. Workloads in the cluster reach it
over Tailscale, using the Tailscale operator already installed from homelab-dev (an egress Service, so
pods call a normal in-cluster name). Ollama is not exposed to the LAN or the internet, only to the tailnet.

## Consequences

- Every Ollama call leaves the cluster. Each workload's NetworkPolicy needs an explicit egress rule for it.
- **The Windows PC becomes a dependency.** If it is off or asleep at 02:00 / 06:00, ingest cannot embed
  and the digest cannot be written. This counts against the freshness SLO (digest by 07:00 on 99% of days),
  so the jobs need retries with backoff, and M5 needs a metric/alert for "Ollama unreachable".
- Ingest should store papers even when embedding fails and backfill the missing embeddings on the next run,
  so an offline PC delays search freshness without losing data.
- Embeddings must always come from the same model, because query and document vectors have to share one
  vector space. The model name and dimension are stored with each embedding.
- The hosted-LLM flag from ADR 0001 is the fallback if the PC turns out to be offline too often.
