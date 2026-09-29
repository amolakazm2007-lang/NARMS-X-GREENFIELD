# Phase 1 Qualification Authority

`packages/phase1_qualification.py` defines the exact 32 mandatory Phase-1 gates. `scripts/phase1_qualify.py` emits canonical evidence roots and environment capability evidence.

Certificate issuance is fail-closed: an Ed25519 Phase-1 certificate can be created only when the report contains exactly the required gate set and every gate is `PASS`. A BLOCKED/FAIL gate raises instead of producing a certificate.

The PostgreSQL migration static audit is intentionally not the `DB_MIGRATIONS` gate. That gate requires execution against real PostgreSQL. Likewise `compileall` is not the `PYTHON_TYPECHECK` gate.
