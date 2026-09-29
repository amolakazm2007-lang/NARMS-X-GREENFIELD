# Phase 1 v2.3–v2.8 — Native qualification and Phase-2 design closure

This release does not implement Phase 2 and does not weaken the 32-gate Phase-1 lock.

- The version-current qualifier now invokes the qualification engine with the current version directly. It no longer copies a legacy v1.5 report and rewrites its version field.
- The CI workflow, evidence path and workflow identity are consistently bound to v2.8.0.
- `packages/phase2_design.py` validates a design-only capability catalog. The catalog cannot authorize implementation.
- Sixteen future capabilities are organized into nine dependency waves. Every capability declares owner, risk class, resource class, dependencies and the full Phase-1 boundary set.
- The validator rejects unknown/future dependencies, dependency cycles, missing boundaries, malformed risk/resource classes and any attempt to set `implementation_allowed=true`.
- `scripts/phase2_design_preflight.py` emits a content-addressed design report. It is planning evidence, not an unlock certificate.

Local truth boundary remains 30/32 because this environment lacks a real Python typechecker and a real PostgreSQL execution target. Phase 2 remains locked until 32/32 fresh evidence and the externally trusted Ed25519 certificate verify.
