# NARMS X — Phase 2 Wave 2 Runtime

Status: implementation candidate on `phase2-wave2-runtime`.

Wave 2 implements only `worker.protocol`, `tool.protocol`, and `artifact.graph`. Wave 3+ remains unopened.

## Runtime invariants

- PostgreSQL is authoritative for durable worker, lease, tool-call, artifact, quota and idempotency state.
- Workers are workspace-bound and may execute only ENABLED capabilities pinned to the trusted Phase-2 opening root.
- Job acquisition is serialized by PostgreSQL row locking. Every acquisition increments the job fencing token; stale/expired tokens cannot heartbeat, authorize tools, complete calls or release newer work.
- Retry attempts are bounded by the Phase-1 job `max_attempts`.
- Tool requests/results are versioned typed envelopes and are JSON-Schema validated.
- Tool risks are `read`, `write`, `external_side_effect`, and `privileged`.
- Sensitive tool calls require an APPROVED Phase-1 approval plus a Wave-2 binding to the exact workspace, mission, tool, request root and expiry.
- Tool idempotency is scoped by workspace + mission; key reuse with a different request root fails closed.
- Artifacts are SHA-256 content addressed. Revisions, objects and lineage edges are append-only in PostgreSQL.
- Artifact revisions are workspace/mission isolated, provenance/evidence rooted, and parent edges form an append-only derivation graph.
- Audit and outbox records are written in the same transaction as authoritative state transitions.
- Quota hooks bound active leases, tool calls and artifact bytes.
- Recovery expires stale leases, returns their jobs to retry, and marks stale workers offline.

## Migration and rollback

`0003_phase2_wave2.sql` upgrades the Wave-1 capability registry to admit Waves 1–2 and adds Wave-2 state. The down migration removes only Wave-2 state/capabilities and restores the Wave-1-only registry constraint. Phase-1 and Wave-1 tables remain intact.

## Qualification

`.github/workflows/phase2-wave2.yml` uses CPython 3.11, real mypy and a real PostgreSQL 16 service. It applies Phase 1 → Wave 1 → Wave 2, runs Wave-1 regression and Wave-2 PostgreSQL/concurrency/adversarial tests, emits content-addressed qualification evidence, rolls Wave 2 back while proving Wave 1 survives, then reapplies Wave 2.

No repository private signing key is introduced. Production promotion still requires independent secret/KMS/HSM signing authority with rotation/revocation.

Wave 3 must not begin until the PR is merged with phase1-closure, phase2-wave1 and phase2-wave2 green.
