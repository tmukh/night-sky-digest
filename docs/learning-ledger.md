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
