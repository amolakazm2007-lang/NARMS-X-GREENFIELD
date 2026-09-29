# Phase 1 Status — v0.8.0

**Status: BLOCKED / not certified. Phase 2 forbidden.**

Fresh v0.8 qualification replay: **30 / 32 gates PASS**.

Remaining blockers:
1. `PYTHON_TYPECHECK` — no mypy or pyright executable is available in the current environment. `compileall` passes but is explicitly not accepted as a substitute.
2. `DB_MIGRATIONS` — the PostgreSQL migration passes the static migration contract, but no real PostgreSQL server/client is available here, so execution/rollback/catalog verification has not been performed.

Security hardening added through v0.8: workspace bootstrap capability for pairing issuance; cross-workspace artifact/evidence ownership checks; user-only client chat role; per-workspace audit chains; source-bound qualification evidence; fresh qualification replay; out-of-band trusted Ed25519 certificate verification.

No Phase 2 implementation is present or authorized.

## v1.4.0 Qualification Siege

- Full regression: 69/69 PASS.
- JSON contracts: 16/16 PASS.
- 32-worker lease contention: exactly one winner; fencing token and attempt remain 1.
- Heartbeat/expiry/recovery and stale-worker rejection: PASS.
- Outbox retry + idempotent ACK: PASS.
- SSE arrival after reconnect cursor while stream is waiting: PASS.
- 24 concurrent audit writers: one valid hash chain.
- Adversarial bootstrap rotation: one winner; old-generation pairing code invalidated.
- Deep SQLite/PostgreSQL structural contract (FK/index/check): PASS.
- `PYTHON_TYPECHECK`: BLOCKED because mypy/pyright is not available.
- `DB_MIGRATIONS`: BLOCKED because a real PostgreSQL service/client is not available.
- Phase-1 certificate: NOT ISSUED. Phase 2: FORBIDDEN.
