# Phase 1 v1.9–v2.2 — Closure Integrity & Promotion Boundary

Phase 2 remains locked. These releases strengthen the last Phase-1 boundary; they do not implement Phase-2 workers.

## v1.9 — Reproducible source snapshot
`packages/phase1_integrity.py` creates a path/size/content SHA-256 snapshot of source-controlled project inputs while excluding mutable evidence, build output, caches and the packaging manifest. Verification reports missing, unexpected and changed files.

## v2.0 — Evidence graph verification
The verifier requires all 32 gate states and gate evidence to agree, then verifies the closure attestation and nonce/workflow/source-bound handoff packet as one connected graph. A disconnected qualification or attestation root is rejected.

## v2.1 — External promotion request
A content-addressed `PromotionRequest` binds source snapshot, qualification, attestation, handoff, challenge and trust-policy roots. It is deliberately **not** an unlock token and exposes no `phase2_allowed` authority.

## v2.2 — CI identity repair and current-version closure
The portable CI workflow now uses version-current qualification/attestation wrappers and one consistent `v2.2.0` evidence path/workflow identity. This closes the prior v1.8 workflow drift where a v1.7 script produced evidence under a different path than the workflow consumed.

## Truth boundary
Local qualification is still blocked where a real PostgreSQL service and real Python typechecker are unavailable. A promotion request cannot replace the externally trusted Ed25519 Phase-1 certificate. Phase 2 remains forbidden until 32/32 fresh gates pass and the trusted certificate verifies.
