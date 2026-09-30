# NARMS X — Phase 2 Wave 1 Runtime

Status: implementation candidate on `phase2-wave1-runtime`.

Wave 1 is deliberately small and executable. It implements only:

- `mission.workspace`
- `capability.registry`

The runtime remains behind the trusted Phase-2 opening decision. It does not start worker/tool/GPU/browser/media/model execution.

## Runtime

`packages/phase2_wave1.py` is PostgreSQL-authoritative and provides:

- fail-closed opening verification;
- workspace activation bound to the opening root;
- Phase-2 mission attachment over Phase-1 mission identity;
- evidence-bearing mission transitions using the Phase-2 constitution;
- optimistic revision checks;
- capability registration, dependency checks and lifecycle transitions;
- Phase-1 outbox/audit integration for mission/workspace operations;
- live health and schema state.

## Database

`migrations/0002_phase2_wave1.sql` adds only the Wave-1 state and history tables. The down migration removes them without touching Phase-1 state.

## Qualification

`.github/workflows/phase2-wave1.yml` requires:

- CPython 3.11;
- PostgreSQL/psql 16;
- real mypy;
- real PostgreSQL migration;
- real Wave-1 tests;
- Wave-1 qualification report;
- rollback proof;
- final reapply.

Wave 2 must not be implemented until Wave 1 is merged to `main` with both the existing Phase-1 closure workflow and the Wave-1 workflow green.
