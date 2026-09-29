# Phase-2 Contract Fortress — v3.6.0

This release is **design/contract only**. It does not implement or start a Phase-2 runtime.

## Frozen contracts

- Mission state machine with evidence-bearing transitions.
- Capability and worker lifecycle vocabularies.
- Worker envelope bound to workspace/mission/job, lease, fencing token, policy root and trace.
- Tool envelope with mandatory approval binding for external side effects and privileged actions.
- Content-addressed artifact/evidence DAG contract.
- Deterministic resource request/quota admission and placement identity.
- Recovery matrix for leases, retry budgets, idempotency, checkpoints and uncertain side effects.
- Phase-2 opening decision that requires a trusted externally signed Phase-1 closure certificate.

## Non-negotiable boundary

`implementation_allowed=false` remains authoritative in the Phase-2 capability catalog. These contracts may be validated while Phase 1 is 30/32, but no Phase-2 worker, GPU runtime, browser runtime, tool executor, mission workspace runtime or agent runtime is authorized to start.
