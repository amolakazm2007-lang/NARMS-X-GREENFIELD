# NARMS X GREENFIELD v4.3.0

## Real Phase-1 closure hardening

v4.3.0 keeps Phase 2 sealed and tightens the two remaining Phase-1 gates to the requested real environment: Python 3.11 + mypy and PostgreSQL/psql 16. The current execution environment cannot satisfy them, so Phase 1 remains 30/32 BLOCKED and Wave 1 has not started. See `docs/PHASE1_REAL_CLOSURE_V430.md`.

# NARMS X GREENFIELD v4.2.0 — Sealed Admission Fortress

**Phase-1 local qualification remains 30/32. Phase-2 runtime remains locked and not started.**

v4.2 adds non-executable sealed skeletons for all 16 Phase-2 capabilities, capability conformance receipts, dependency-aware wave admission, cross-domain qualification, and Ed25519 admission certificates. These are control/assurance contracts only; they cannot bypass the trusted Phase-1 opening boundary. See `docs/PHASE2_SEALED_ADMISSION_V420.md`.

# NARMS X Greenfield — Phase 1 / Phase-2 Contract Fortress v3.6.0

**Current local status remains 30/32; Phase 2 runtime remains cryptographically locked.**

v2.9–v3.6 harden the pre-opening design surface without bypassing Phase 1: mission/capability state machines, worker/tool envelopes, artifact/evidence DAG, deterministic resource admission, recovery/idempotency policy, and a trusted Phase-2 opening decision. No Phase-2 runtime component is started or authorized. See `docs/PHASE2_CONTRACT_FORTRESS_V360.md`.

# NARMS X Greenfield — Phase 1 v2.8.0

**Current local status: 30/32; Phase 2 remains cryptographically locked.**

v2.3–v2.8 remove the legacy current-qualification report rewrite and add a machine-validated Phase-2 design constitution without implementing Phase 2. The current qualifier now emits the current version directly from fresh source-bound evidence. The design compiler defines 16 capability domains across 9 opening waves, explicit ownership/risk/resource classes, a dependency DAG, and the mandatory Phase-1 boundaries every future capability must cross. The catalog and opening plan are non-authoritative by construction: `implementation_allowed=false`.

See `docs/PHASE2_BLUEPRINT.md`, `docs/PHASE2_UNIVERSAL_PRODUCT_ARCHITECTURE_V170.md`, and `docs/phase2/capability-catalog.json`.

# NARMS X Greenfield — Phase 1 v2.2.0

**Current local status remains fail-closed; Phase 2 is cryptographically locked.**

v1.9–v2.2 harden the final Phase-1 closure boundary: reproducible source snapshots, connected evidence-graph verification, a non-authoritative external promotion request, and repaired version-current CI qualification/attestation paths. No Phase-2 worker, model runtime, GPU runtime, browser runtime, training runtime, media runtime, code-server runtime, or model registry implementation is added.

See `docs/PHASE1_V190_V220_INTEGRITY.md`.

# NARMS X Greenfield — Phase 1 v1.8.0

**Current status: 30/32 locally; Phase 2 remains cryptographically locked.**

v1.7 adds an attested closure envelope that binds all 32 gate-evidence roots, qualification/source roots, qualifying toolchain receipt, and workflow identity before an externally trusted Ed25519 Phase-1 certificate can authorize Phase 2. It does not weaken the two remaining local blockers and does not implement Phase 2.

# NARMS X Greenfield — Phase 1 v1.5.0

## v1.5 Closure Harness
Phase 1 remains **30/32 BLOCKED**; no gate was weakened. v1.5 adds executable real-tool closure for Python typechecking and PostgreSQL migration apply/reapply/introspection/rollback/reapply, plus fail-closed certificate issuance. `docs/PHASE2_BLUEPRINT.md` is design-only and Phase-2 implementation remains forbidden.

Current qualification-siege milestone: 32-worker lease contention, heartbeat/expiry/reclaim fencing, outbox retry/ACK idempotency, live SSE arrival/reconnect behavior, concurrent audit-chain append, adversarial bootstrap rotation, and deep SQLite/PostgreSQL structural parity. Phase 2 remains forbidden until the Phase-1 certificate is actually issued.

**Truth boundary:** deep PostgreSQL SQL auditing is not real PostgreSQL migration execution; Python `compileall` is not a Python typechecker. Those external gates remain blocked when the required tools/services are absent.

Phase 1 hardening release. Phase 2 remains locked. This version closes reference-runtime transaction atomicity gaps, adds session/bootstrap rotation and revocation, pairing rate limits, request budgets, explicit outbox acknowledgement semantics, PostgreSQL schema-parity auditing, and qualification authority key-rotation policy.

**Qualification remains fail-closed:** 30/32 gates are currently PASS in this environment. `PYTHON_TYPECHECK` is BLOCKED because mypy/pyright is unavailable; `DB_MIGRATIONS` is BLOCKED because no real PostgreSQL service is available. No Phase-1 certificate is issued and Phase 2 is not allowed.

# NARMS X Greenfield — Phase 1 v0.8.0

Hardened greenfield implementation. Phase 1 remains intentionally **BLOCKED**, not certified. Phase 2 is forbidden until all 32 mandatory Phase 1 gates pass with fresh evidence.

The Phase-1 control spine includes contracts, architecture policy, PostgreSQL migration definition, workspace bootstrap capability, one-time device pairing, workspace/project/chat isolation, durable missions/jobs, leases/fencing/idempotency, outbox/inbox, replay/SSE, approvals, artifacts/evidence, per-workspace tamper-evident audit chains, health, Arabic RTL shell, and security/recovery/E2E tests.

v0.4–v0.8 hardening closes workspace-ID-only pairing authorization, cross-workspace artifact/evidence binding, client role injection, stale qualification evidence, and self-signed certificate trust. See `docs/PHASE1_V040_V080_HARDENING.md`.

No GPU worker, model registry/runtime, inference, training worker, browser worker, factories, or final Android application has been implemented. Those remain Phase 2+ work.
## v1.6.0 — Portable Phase-1 Closure & Cryptographic Phase Lock

v1.6.0 does **not** implement Phase 2. It makes the remaining Phase-1 qualification portable to a real CI host and makes the Phase-2 boundary cryptographic rather than procedural.

- `.github/workflows/phase1-closure.yml` provisions PostgreSQL 16, installs a real Python typechecker, runs the existing 32-gate qualification, and refuses success unless all 32 gates PASS.
- `packages/phase1_unlock.py` verifies the signed Phase-1 certificate against an out-of-band trusted Ed25519 public key and binds it to the exact qualification/source roots.
- `scripts/verify_phase1_unlock.py` produces a content-addressed unlock receipt only after trusted verification.
- Self-signed attacker certificates, tampered source roots, stale qualification reports, and any blocked gate keep Phase 2 locked.
- This local execution environment still lacks a real Python typechecker and PostgreSQL, therefore the repository remains truthfully at **30/32** here. No Phase-1 certificate is issued and Phase 2 remains forbidden.
