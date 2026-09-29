# Phase 1 v1.0.0 hardening

This release remains Phase 1. Phase 2 implementation is forbidden until all 32 qualification gates pass and a certificate verifies against an out-of-band trusted authority key.

## Changes
- Session revocation and one-way rotation; old bearer tokens become invalid immediately.
- Workspace bootstrap rotation invalidates outstanding pairing codes and the previous bootstrap capability.
- Pairing issuance has a fail-closed reference rate limit.
- API request-size boundary and optional deployment origin allowlist.
- Outbox publication now distinguishes attempts from explicit acknowledgement and stores idempotent acknowledgement receipts.
- Transaction helper provides real atomic rollback in the SQLite reference runtime. Crash-injection tests prove project/outbox and mission/audit writes roll back together.
- PostgreSQL migration contract was brought into structural parity with the reference runtime for mission request/conversation binding, approval action/risk, audit hash-chain fields, session revocation/rotation, bootstrap generation, and outbox acknowledgement metadata.
- Migration static audit now checks required columns and critical constraints instead of table names alone.
- Qualification trust-store reference supports ACTIVE, RETIRED, and REVOKED authority keys; retired keys may verify historical certificates but cannot issue new ones.

## Truth boundary
`PYTHON_TYPECHECK` remains BLOCKED when neither mypy nor pyright is available. `DB_MIGRATIONS` remains BLOCKED until the migration is executed against a real PostgreSQL service. Static SQL analysis is not treated as PostgreSQL execution evidence.
