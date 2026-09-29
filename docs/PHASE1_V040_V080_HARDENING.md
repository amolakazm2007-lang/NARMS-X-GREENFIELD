# Phase 1 v0.4.0–v0.8.0 Hardening

This release deliberately remains inside Phase 1. It does not implement Phase 2 model/GPU/runtime components.

## v0.4 — Workspace bootstrap capability
Pairing-code issuance is no longer authorized by knowledge of a workspace UUID. Workspace creation provisions a high-entropy bootstrap capability; only its SHA-256 digest is stored. Pairing issuance requires that capability and uses constant-time digest comparison.

## v0.5 — Resource ownership closure
Artifacts and evidence receipts validate mission/workspace ownership before persistence. Client chat input is restricted to the `user` role. Audit hash chains are scoped per workspace instead of coupling tenants through one global predecessor hash.

## v0.6 — Source-bound evidence freshness
Qualification evidence is bound to a composite root covering source, architecture policy, contracts, and migrations. Evidence from a previous source binding is stale by construction and cannot be treated as current evidence.

## v0.7 — Fresh qualification replay
`phase1_qualify_v080.py` reruns local gates instead of carrying PASS strings from an older baseline. Functional gates are backed by the fresh full regression receipt. Architecture, contracts, secret scan, backend compile, TypeScript typecheck, and frontend build each receive their own fresh command receipt. Python typechecking and real PostgreSQL migration execution remain BLOCKED when the required tools/services are absent.

## v0.8 — External certificate trust anchor
A certificate's embedded public key is metadata, not a trust anchor. `verify_certificate` now requires an out-of-band trusted Ed25519 public key and rejects a valid certificate self-signed by an untrusted attacker.

## Current boundary
Phase 1 is still not certified. Phase 2 is forbidden. The two remaining environmental qualification gates are Python static typechecking with mypy/pyright and execution of the migration against a real PostgreSQL instance.
