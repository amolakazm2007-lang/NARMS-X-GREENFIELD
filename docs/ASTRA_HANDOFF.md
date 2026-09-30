# ASTRA HANDOFF — NARMS X GREENFIELD

## Repository
- Repository: `amolakazm2007-lang/NARMS-X-GREENFIELD`
- Start from: `main`
- Verified Wave-1 merge baseline: `33cd029fa2fd807a4062782d37d46eb05122b0d0`
- Do not rebuild from scratch.
- Do not resurrect the old simulated GPU/B200 project.
- Do not weaken any Phase-1 or Phase-2 gate to make CI green.

## Verified state
Phase 1 is closed by real GitHub Actions:
- CPython 3.11: PASS
- real mypy: PASS
- PostgreSQL 16 / psql 16: PASS
- migrations/apply/reapply/live schema validation/rollback/final reapply: PASS
- Phase-1 qualification: 32/32 PASS
- closure attestation: PASS

Phase 2 opening is recorded as PASS.

Phase 2 Wave 1 is real executable code and is merged:
- `mission.workspace`
- `capability.registry`

Key files:
- `packages/phase2_wave1.py`
- `migrations/0002_phase2_wave1.sql`
- `migrations/0002_phase2_wave1.down.sql`
- `contracts/phase2-wave1.runtime.json`
- `tests/test_phase2_wave1.py`
- `scripts/phase2_wave1_qualify.py`
- `.github/workflows/phase2-wave1.yml`
- `docs/PHASE2_WAVE1_RUNTIME.md`

Both `phase1-closure` and `phase2-wave1` must remain green.

## Security/trust rule
Wave-1 runtime verifies the pinned Ed25519 trust anchor, signed Phase-1 certificate, authority verification material, unlock root and Phase-2 opening decision before it starts.

No private signing key is stored in the repository.

Before any production promotion, replace the current release-authority process with independently controlled KMS/HSM/secret-backed signing, key rotation and revocation. Do not pretend the repository itself is an external authority.

## Your next assignment: Phase 2 Wave 2 only
Implement, in this order:
1. `worker.protocol`
2. `tool.protocol`
3. `artifact.graph`

Do not start Wave 3+.

### Wave-2 non-negotiable properties
- PostgreSQL-authoritative durable state where state is required.
- Workspace/mission/job identity binding.
- Lease + fencing semantics for worker execution.
- Typed request/result/error envelopes.
- Capability registry integration; no unregistered executor may run.
- Tool risk classes: read / write / external_side_effect / privileged.
- Approval receipt required for external_side_effect and privileged actions.
- Idempotency and replay safety.
- Artifact content addressing, parent/child graph, provenance, evidence roots and immutable revisions.
- Outbox/audit integration.
- Quota and compute-policy hooks.
- Fail closed on stale opening root, stale fencing token, missing approval, unknown capability/tool, invalid artifact hash or source drift.
- Upgrade + rollback migration.
- Health/failure/recovery contracts.
- No fake PASS, synthetic production evidence, or silent fallback.

### Required Wave-2 files
Design the exact structure after inspecting the repo, but at minimum deliver:
- Wave-2 PostgreSQL up/down migration.
- Runtime implementation(s) for worker protocol, tool protocol and artifact graph.
- Versioned runtime manifest/contract.
- Real PostgreSQL tests.
- Concurrency/fencing/adversarial tests.
- Separate `phase2-wave2.yml` CI.
- Qualification script + content-addressed evidence artifact.
- Rollback + final reapply proof.
- Documentation.
- Updated `MANIFEST.sha256`.

### CI admission rule
Before merging Wave 2:
- existing `phase1-closure`: PASS
- existing `phase2-wave1`: PASS
- new `phase2-wave2`: PASS
- mypy: PASS
- real PostgreSQL 16 migration: PASS
- tests: PASS
- rollback: PASS
- final reapply: PASS
- no architecture-policy violations

Use a feature branch and PR. Merge only after all required checks are green.

## Architecture direction after Wave 2
Wave 3 will be code.repository + build.test.
Wave 4 browser/computer.
Wave 5 research + documents/data.
Wave 6 model.router + gpu.runtime.
Wave 7 media + android.lab.
Wave 8 automation.sdk.
Wave 9 cross-domain qualification.

Do not skip directly to models/GPU. The execution protocols and artifact graph must exist first.

## Product target
NARMS X is a unified AI operating platform controlled from mobile, with remote/local compute workers. Later model hosting must use self-hosted/open-weight runtimes where possible, without mandatory paid third-party model APIs. The phone is the control center; heavy compute belongs on workers/servers.

## First response expected from Astra
Do not start coding immediately. First:
1. inspect `main` and verify the files/status above;
2. report any mismatch;
3. propose the exact Wave-2 file tree, migrations, interfaces, tests and CI;
4. state the acceptance gates;
5. then implement Wave 2 only.
