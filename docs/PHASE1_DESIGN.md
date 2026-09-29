# Phase 1 Design Freeze

## Contracts
Canonical JSON Schema is source of truth. Python/TypeScript bindings must be generated or validated from the same schemas. Breaking changes require schema versioning.

## Database outline
users, device_sessions, workspaces, projects, conversations, messages, missions, mission_steps, jobs, job_leases, outbox_events, inbox_receipts, approvals, artifacts, evidence_receipts, audit_events, health_reports.

## Mission state machine
DRAFT -> UNDERSTANDING -> PLANNING -> WAITING_APPROVAL/READY -> RUNNING -> TESTING -> REVIEWING -> COMPLETED. PAUSED/RECOVERING/PARTIAL/FAILED/CANCELLED are explicit branches; invalid transitions fail closed.

## Jobs / leases / fencing
Atomic claim increments fencing_token. Heartbeat extends a live lease. Lease expiry permits a new owner with a newer token. Any result carrying an older token is rejected. Idempotency keys prevent duplicate side effects.

## Outbox / inbox
Aggregate mutation and outbox insertion share one PostgreSQL transaction. Consumers record event_id in inbox before applying idempotent side effects. Transport is at-least-once; effects are effectively-once.

## Pairing
One-time enrollment code -> authenticated device session -> rotating token. Never bypass auth for reconnect. Certificate pinning is applied where deployment topology supports a stable endpoint certificate.

## Mobile Super Chat
Arabic RTL, mobile-first, 44dp targets, durable conversation/mission IDs. SSE reconnect uses Last-Event-ID and reconstructs from durable state rather than client memory.

## Evidence
Every gate records command, exit code, log hash, artifact hash, environment identity, source commit and timestamp. Local signatures mean local integrity only.

## Threat review
Primary Phase 1 threats: session theft, replay, CSRF/XSS, SQL injection, stale workers, duplicate events, path traversal in artifacts, secret leakage, approval bypass, event spoofing and client-side state confusion.

## Phase 2–5 summary
Phase 2 attaches self-hosted model/GPU fabric. Phase 3 adds agents/project engineering. Phase 4 adds factories/research/training. Phase 5 production hardening. None are implemented in Phase 1.

## Risks / blockers
Physical PostgreSQL service, deployment TLS topology and independent security assessment depend on the eventual deployment environment. They must remain BLOCKED/NOT_TESTED until exercised there.
