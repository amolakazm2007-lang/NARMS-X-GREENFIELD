# Contract First

## Context
Phase 1 requires a durable, recoverable and auditable foundation.

## Decision
Canonical versioned schemas precede broad implementation.

## Alternatives
A monolithic process, in-memory ownership, or implicit contracts were rejected because they weaken recovery and auditability.

## Consequences
More explicit schemas, migrations, tests and operational evidence are required.

## Security implications
Authority boundaries and fail-closed validation are mandatory; no silent fallback is allowed.

## Migration implications
Breaking changes require explicit schema/data migration and a new evidence root.
