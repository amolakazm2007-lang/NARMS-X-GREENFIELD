# NARMS X TITAN OMEGA — Phase 1 Architecture

```text
POCO F6 / Mobile PWA
        | HTTPS + SSE
        v
NARMS Edge/API
        |
        v
TITAN Control Plane -------------------- PostgreSQL
 |       |       |                         |
 |       |       +-- Policy/Approvals      +-- authoritative state
 |       +---------- Mission Engine        +-- transactional outbox/inbox
 +------------------ Durable Job Engine
                         | leases + fencing
                         v
                Reference Worker (Phase 1 only)
                         |
                         v
                 Artifact + Evidence
```

## Boundaries
Control Plane owns durable state. Workers own ephemeral execution only. Realtime is a projection. Phase 1 contains no real model/GPU hosting.

## State ownership
| State | Authoritative owner |
|---|---|
| user/workspace/project | PostgreSQL / Control Plane |
| mission lifecycle | Mission Engine |
| job lifecycle | Durable Job Engine |
| approvals | Policy/Approval Engine |
| artifacts | Artifact Registry/Store |
| evidence/audit | Append-only Evidence subsystem |
| realtime | Projection only |
| worker runtime | Ephemeral worker |

## Trust boundaries
Browser/device, Edge/API, Control Plane, PostgreSQL, and Execution Plane are distinct boundaries. A worker result is accepted only with the current fencing token.
