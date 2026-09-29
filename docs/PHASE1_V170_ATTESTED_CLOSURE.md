# Phase 1 v1.7 — Attested Closure Envelope

Phase 1 remains locked until all 32 qualification gates pass with real evidence. v1.7 strengthens the closure boundary; it does not implement Phase 2.

## New trust chain

`source root -> 32 gate evidence roots -> qualification root -> toolchain receipt -> workflow identity -> closure attestation root -> externally trusted Ed25519 certificate -> Phase-2 unlock`

The closure attestation binds every gate's evidence object, the qualification/source roots, Python/Node/npm/typechecker/PostgreSQL tool versions available in the qualifying environment, and the expected closure-workflow identity.

A 32/32 report cannot be attested if blockers remain. A certificate cannot be issued from an invalid/tampered attestation. A certificate signed by an attacker-controlled key remains invalid under the out-of-band trusted public key.

## Current local truth boundary

The current sandbox has no `mypy`/`pyright` executable and no PostgreSQL client/server. Therefore local qualification remains 30/32. `compileall` is not substituted for Python type checking, and SQLite/static SQL checks are not substituted for real PostgreSQL migration execution.

The portable CI workflow installs the missing qualification tools and PostgreSQL 16, requires 32/32, then creates the closure-attestation envelope. Private signing keys are intentionally absent from the repository and CI evidence artifact.
