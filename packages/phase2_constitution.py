from __future__ import annotations
import hashlib,json
from dataclasses import asdict,dataclass
from typing import Any

def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()

MISSION_STATES=('CREATED','PLANNED','QUEUED','RUNNING','WAITING_APPROVAL','PAUSED','SUCCEEDED','FAILED','CANCELLED')
CAPABILITY_STATES=('DECLARED','QUALIFIED','ENABLED','DEGRADED','QUARANTINED','DISABLED')
WORKER_STATES=('REGISTERED','READY','LEASED','BUSY','DRAINING','OFFLINE','QUARANTINED')
TOOL_RISKS=('read','write','external_side_effect','privileged')

@dataclass(frozen=True)
class Transition:
    source:str; target:str; requires:tuple[str,...]=()

MISSION_TRANSITIONS=(
 Transition('CREATED','PLANNED',('plan_root',)),Transition('PLANNED','QUEUED',('policy_pass',)),
 Transition('QUEUED','RUNNING',('lease','fencing_token')),Transition('RUNNING','WAITING_APPROVAL',('approval_request',)),
 Transition('WAITING_APPROVAL','RUNNING',('approval_receipt',)),Transition('RUNNING','PAUSED',('checkpoint',)),
 Transition('PAUSED','QUEUED',('resume_token',)),Transition('RUNNING','SUCCEEDED',('evidence_root','artifact_root')),
 Transition('RUNNING','FAILED',('failure_receipt',)),Transition('RUNNING','CANCELLED',('cancellation_receipt',)),
)

@dataclass(frozen=True)
class Phase2Constitution:
    scope:str='phase2-contract-constitution-v1'
    implementation_allowed:bool=False
    phase1_unlock_required:bool=True
    mission_states:tuple[str,...]=MISSION_STATES
    capability_states:tuple[str,...]=CAPABILITY_STATES
    worker_states:tuple[str,...]=WORKER_STATES
    tool_risks:tuple[str,...]=TOOL_RISKS
    @property
    def root(self)->str:return sha(asdict(self))

def validate_transition(source:str,target:str,evidence:dict[str,Any])->tuple[bool,tuple[str,...]]:
    match=next((t for t in MISSION_TRANSITIONS if t.source==source and t.target==target),None)
    if match is None:return False,('transition_not_allowed',)
    missing=tuple(x for x in match.requires if not evidence.get(x))
    return not missing,tuple('missing:'+x for x in missing)

def constitution_report()->dict[str,Any]:
    c=Phase2Constitution(); body={'constitution':asdict(c),'mission_transitions':[asdict(x) for x in MISSION_TRANSITIONS]}
    body['root']=sha(body); return body
