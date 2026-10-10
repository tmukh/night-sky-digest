# Learning ledger

Status: **new** (introduced), **used** (used it, not explained back yet), **confident** (explained back correctly, or predicted right twice).
Concepts already confident in homelab-dev's ledger are not repeated here.

| Concept | Introduced in | Status | Last checked | Notes |
|---|---|---|---|---|
| Image tag vs digest (`@sha256:`) | M0 | confident | 2026-10-10 | prediction was inverted, then quiz Q1 explained back correctly: pinned build stays on the old digest until a commit bumps it |
| Pinning actions by commit SHA | M0 | new | 2026-10-10 | quiz Q2: didn't know. Re-taught with tj-actions/changed-files (2025) |
| CVE scanning and severity gates (Trivy) | M0 | new | 2026-10-10 | predicted counts right, missed fix availability; gate written by Claude on request; quiz Q3: didn't know. Re-taught |
| SBOM (SPDX, Syft) | M0 | new | 2026-10-10 | quiz Q4: didn't know. Re-taught with the real attestation (110 packages, idna 3.20) |
| Keyless signing (OIDC → Fulcio → Rekor, cosign) | M0 | new | 2026-10-10 | quiz Q5: didn't know. Re-taught with the real certificate (10-minute validity, workflow identity, Rekor entry) |
