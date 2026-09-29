# Phase-1 Real Closure Environment — v4.3.0

This release does not widen Phase 2. It hardens the two remaining Phase-1 gates.

## Required real environment

- CPython 3.11.x
- real `mypy` execution (`pyright` is not accepted for this closure gate)
- PostgreSQL server major 16
- `psql` client major 16
- project dependencies and web dependencies

`DB_MIGRATIONS` executes the real migration against PostgreSQL 16, performs an idempotent reapply, validates the live table/index/column schema, rolls the migration back, proves Phase-1 tables are gone, and performs a final reapply.

No mock, SQLite, static SQL audit, synthetic receipt, or Digital Twin result can satisfy `PYTHON_TYPECHECK` or `DB_MIGRATIONS`.

## Current environment result

The local execution environment used for this release has Python 3.13.5 and does not expose `mypy`, `psql`, a PostgreSQL 16 server DSN, or the PostgreSQL server binary. Therefore the real closure is intentionally **BLOCKED at 30/32**.

Because Phase 1 is not 32/32, this release does **not** create a closure attestation, does **not** issue a trusted Phase-1 certificate, does **not** open Phase 2, and does **not** implement or start Wave 1.

The GitHub closure workflow remains the portable real-environment execution path and now asserts the exact Python/mypy/psql requirements before qualification.
