from __future__ import annotations
from dataclasses import asdict,dataclass
from typing import Any
from packages.phase2_constitution import sha

@dataclass(frozen=True)
class WorkerEnvelope:
    protocol_version:str; worker_id:str; capability_id:str; workspace_id:str; mission_id:str; job_id:str
    attempt:int; fencing_token:int; lease_id:str; input_root:str; policy_root:str; trace_id:str; deadline_ms:int
    def validate(self)->tuple[bool,tuple[str,...]]:
        r=[]
        if self.protocol_version!='worker-v1':r.append('protocol_version')
        for k in ('worker_id','capability_id','workspace_id','mission_id','job_id','lease_id','input_root','policy_root','trace_id'):
            if not getattr(self,k):r.append(k)
        if self.attempt<0:r.append('attempt')
        if self.fencing_token<1:r.append('fencing_token')
        if self.deadline_ms<=0:r.append('deadline_ms')
        return not r,tuple(r)
    @property
    def root(self)->str:return sha(asdict(self))

@dataclass(frozen=True)
class ToolEnvelope:
    protocol_version:str; tool_id:str; tool_version:str; workspace_id:str; mission_id:str; invocation_id:str
    risk_class:str; args_root:str; policy_root:str; approval_root:str|None; idempotency_key:str; trace_id:str
    def validate(self)->tuple[bool,tuple[str,...]]:
        r=[]
        if self.protocol_version!='tool-v1':r.append('protocol_version')
        if self.risk_class not in {'read','write','external_side_effect','privileged'}:r.append('risk_class')
        if self.risk_class in {'external_side_effect','privileged'} and not self.approval_root:r.append('approval_required')
        for k in ('tool_id','tool_version','workspace_id','mission_id','invocation_id','args_root','policy_root','idempotency_key','trace_id'):
            if not getattr(self,k):r.append(k)
        return not r,tuple(r)
    @property
    def root(self)->str:return sha(asdict(self))
