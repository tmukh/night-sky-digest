# ADR 0003: LLM-generated queries and dual local LLM judges for the eval set

Date: 2026-10-10
Status: accepted

## Context

CAREER-PLAN §3 M3 asks for 60–100 hand-labelled queries. I have no astrophysics background, so
hand-written queries and relevance labels would be slow and unreliable. The goal of M3 is evaluation
methodology (pooling, graded relevance, agreement, a CI gate), not domain expertise.

## Decision

- **Queries:** written by Claude (claude.ai) from the prompt in `eval/prompts/`, without access to
  our corpus, so queries can't copy abstract wording. The prompt, model and date are committed.
  I review every query for realism and duplicates.
- **Pooling:** for each query, the top 20 from lexical, semantic and hybrid search are merged into
  one pool to judge (TREC-style), so relevant papers any method finds get labels.
- **Judging:** two local models from different families, `qwen2.5:7b` (Alibaba) and `gemma4:12b`
  (Google), via Ollama. Graded relevance 0/1/2 with a one-line reason, judged from title + abstract
  against the query's intent.
- **Validation:** inter-judge agreement (Cohen's kappa) is reported. Disagreements are resolved by me
  reading both reasons against the intent; resolved labels are final.
- **CI:** labels and a corpus snapshot are frozen. CI only recomputes metrics; no LLM runs in CI.

## Consequences

- The query writer and the judges are different model families, so one model's blind spots can't
  grade themselves.
- The CV line must say "LLM-generated queries, dual-LLM judged (κ = X)", not "hand-labelled".
- Small local judges make more mistakes than a hosted model would; the kappa makes that visible. If
  it's low, the fallback is a hosted judge behind the flag from ADR 0001.
- Non-English queries (≥ 20, required before M3 is done) come from a second prompt and are checked by
  me for natural phrasing (German, Arabic).
