# Phase 1 v1.5 Closure Harness

v1.5 does not weaken the 32-gate qualification policy and does not implement Phase 2.
It turns the two remaining environment-dependent blockers into executable, fail-closed qualification procedures.

## Python typechecking
`python scripts/phase1_closure.py` discovers **real** `pyright` or `mypy`. `compileall` is never substituted.
The tool executable, version, command identity, return code and output digest are captured as evidence.

## PostgreSQL migration qualification
Set `NARMS_PHASE1_POSTGRES_DSN` to an isolated PostgreSQL database. The harness requires a real `psql` client and server and performs:
1. server version probe;
2. migration apply;
3. idempotent reapply;
4. live catalog introspection for 16 Phase-1 tables and 4 critical indexes;
5. transactional rollback with `0001_phase1.down.sql`;
6. verification that Phase-1 tables are gone;
7. final reapply.

The DSN itself is never persisted; only a SHA-256 fingerprint is stored.

## Boundary
If either external capability is unavailable, Phase 1 remains BLOCKED. No certificate is issued and Phase 2 remains forbidden.
