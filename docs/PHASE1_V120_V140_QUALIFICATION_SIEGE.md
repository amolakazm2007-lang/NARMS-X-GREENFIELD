# Phase 1 v1.2–v1.4 — Qualification Siege

This release deliberately does not open Phase 2. It attacks concurrency, recovery and qualification semantics while preserving the two external evidence blockers.

## v1.2 — Lease / recovery interleavings

- 32-worker cross-connection lease contention campaign.
- Heartbeat extends only the currently fenced lease.
- Expired leases recover to READY atomically.
- A stale worker cannot heartbeat or commit after recovery and re-claim.

## v1.3 — Delivery / realtime / audit siege

- Outbox retry accounting remains unpublished until acknowledgement.
- Repeated ACK is idempotent and preserves the original publication timestamp.
- SSE waits across an initially empty poll window and returns newly-arrived events after `Last-Event-ID`.
- 24 concurrent audit writers preserve one valid per-workspace hash chain.
- Eight concurrent bootstrap rotations admit one winner and invalidate outstanding old-generation pairing codes.

## v1.4 — Deep schema parity + qualification authority

The SQLite reference schema and PostgreSQL migration are now audited beyond columns:

- critical foreign keys,
- critical indexes,
- check constraints,
- existing table/column/uniqueness contract.

This is **structural evidence only**. It does not satisfy `DB_MIGRATIONS`; that gate still requires execution against a real PostgreSQL instance. Likewise, `compileall` is not Python typechecking and cannot satisfy `PYTHON_TYPECHECK`.

Phase 1 certificate issuance remains fail-closed until all 32 required gates have real evidence.
