# Phase 1 v1.1.0 — Concurrency, Recovery, and Authority Hardening

Phase 1 remains closed to Phase 2. This increment hardens reference semantics without implementing Phase-2 workers or routing.

## Changes

- Serialized SQLite reference transactions with an explicit re-entrant transaction lock.
- Pairing enrollment is now a single atomic transaction; a code cannot be consumed without the session being committed.
- Session rotation is atomic and one-way; concurrent rotation of one bearer yields at most one successor.
- Bootstrap rotation re-validates the capability inside the write transaction and atomically invalidates outstanding pairing codes.
- `Last-Event-ID` is supported for SSE reconnect, with monotonic cursor semantics and invalid-header rejection.
- Cross-connection lease race campaign proves a single live lease winner and monotonic fencing token in the SQLite reference runtime.
- Crash matrix covers job+outbox, inbox receipt+consumer callback, enrollment, session rotation, and bootstrap rotation rollback boundaries.
- Live SQLite logical schema is audited against the same required Phase-1 columns as the PostgreSQL migration static contract.
- Qualification certificates have a policy-bound reference form that binds authority key id and qualification-policy root.

## Truth boundary

The concurrency tests validate the SQLite reference semantics, not PostgreSQL concurrency behavior. PostgreSQL migration execution remains BLOCKED until a real PostgreSQL instance is used. Python static typechecking remains BLOCKED until an approved typechecker is available. Therefore no Phase-1 certificate is issued and Phase 2 remains forbidden.
