# Phase 1 v1.6.0 — Portable Closure and Cryptographic Phase Lock

## Purpose
v1.6.0 closes the operational gap between the local 30/32 qualification and a host capable of proving the two remaining gates. It does not weaken either gate and does not implement Phase 2.

## Portable qualification
The CI workflow provisions PostgreSQL 16 and installs a real Python typechecker. The same qualification code must observe 32/32 PASS. PostgreSQL qualification performs apply → idempotent reapply → live catalog introspection → rollback → absence verification → final reapply.

## Trust boundary
A Phase-1 certificate is not self-trusting. Unlock verification requires an Ed25519 public key supplied out-of-band. The certificate body is bound to phase, version, qualification root, source root, and the fixed `phase1-complete-phase2-may-open` scope.

The embedded certificate public key is metadata only. A self-signed certificate from an attacker does not establish trust.

## Phase-2 invariant
Until trusted verification succeeds, production source under the Phase-2 implementation roots remains forbidden. Design documents and `.gitkeep`/README placeholders are permitted; executable implementation is not.

## Current truth boundary
The present local environment has neither mypy/pyright nor a PostgreSQL client/server/DSN. Local qualification therefore remains 30/32. v1.6.0 adds the path to produce the missing evidence on a capable host; it does not manufacture that evidence.
