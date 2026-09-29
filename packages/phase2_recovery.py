from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class RecoveryDecision:
    action:str; reason:str; next_attempt:int; requires_checkpoint:bool

def decide(*,attempt:int,max_attempts:int,lease_expired:bool,checkpoint_present:bool,idempotent:bool,side_effect_committed:bool)->RecoveryDecision:
    if side_effect_committed:return RecoveryDecision('RECONCILE','side_effect_commit_uncertain',attempt,True)
    if not lease_expired:return RecoveryDecision('WAIT','lease_still_active',attempt,False)
    if attempt>=max_attempts:return RecoveryDecision('DEAD_LETTER','attempt_budget_exhausted',attempt,False)
    if not idempotent and not checkpoint_present:return RecoveryDecision('ESCALATE','unsafe_replay_without_checkpoint',attempt,True)
    return RecoveryDecision('RETRY','safe_replay',attempt+1,not idempotent)
