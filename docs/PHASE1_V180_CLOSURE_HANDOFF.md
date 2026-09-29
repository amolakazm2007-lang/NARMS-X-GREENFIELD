# Phase 1 v1.8 — Attested Closure Handoff

v1.8 does **not** weaken the 32/32 Phase-1 lock and does not implement Phase 2.
It hardens the boundary between the qualifying CI environment and the trusted Phase-2 unlock authority.

The handoff protocol binds a one-use challenge to the exact source root, release version, workflow identity, qualification root, closure-attestation root and a high-entropy nonce. A packet from a different source tree, workflow, qualification run, or challenge is rejected. The packet itself is not authority: the existing out-of-band trusted Ed25519 certificate remains mandatory for Phase-2 unlock.

Current local truth remains blocked until a real Python typechecker and real PostgreSQL qualification are executed. Synthetic or substituted evidence is forbidden.
