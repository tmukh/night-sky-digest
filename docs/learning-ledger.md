# Learning ledger

Status: **new** (introduced), **used** (used it, not explained back yet), **confident** (explained back correctly, or predicted right twice).
Concepts already confident in homelab-dev's ledger are not repeated here.

| Concept | Introduced in | Status | Last checked | Notes |
|---|---|---|---|---|
| Image tag vs digest (`@sha256:`) | M0 | new | 2026-10-10 | prediction inverted (thought the digest follows new releases and the tag stays frozen). Re-check in quiz |
| Pinning actions by commit SHA | M0 | new | 2026-10-10 | same idea as image digests, for CI dependencies |
| CVE scanning and severity gates (Trivy) | M0 | new | 2026-10-10 | predicted counts right (0 CRIT / ~40 HIGH vs 0 / 44) and Debian as the source; missed that 0 of 44 HIGH have a fix |
| SBOM (SPDX, Syft) | M0 | new | 2026-10-10 | |
| Keyless signing (OIDC → Fulcio → Rekor, cosign) | M0 | new | 2026-10-10 | |
