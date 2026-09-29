from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
from packages.phase2_constitution import sha

REQUIRED_CHECKS=('identity','policy','approvals','leases_fencing','evidence','artifacts','audit','observability','quotas_compute','recovery')
@dataclass(frozen=True)
class ConformanceReceipt:
    capability_id:str; skeleton_root:str; checks:tuple[tuple[str,bool],...]; evidence_roots:tuple[tuple[str,str],...]; environment_root:str; scope:str='phase2-conformance-receipt-v1'
    @property
    def passed(self)->bool:
        d=dict(self.checks); e=dict(self.evidence_roots)
        return all(d.get(x) is True and bool(e.get(x)) for x in REQUIRED_CHECKS)
    @property
    def root(self)->str:return sha(asdict(self))

def issue_receipt(capability_id:str,skeleton_root:str,checks:dict[str,bool],evidence_roots:dict[str,str],environment_root:str)->ConformanceReceipt:
    unknown=(set(checks)|set(evidence_roots))-set(REQUIRED_CHECKS)
    if unknown: raise ValueError('unknown checks:'+','.join(sorted(unknown)))
    return ConformanceReceipt(capability_id,skeleton_root,tuple(sorted(checks.items())),tuple(sorted(evidence_roots.items())),environment_root)

def conformance_matrix(receipts:tuple[ConformanceReceipt,...])->dict[str,Any]:
    if len({r.capability_id for r in receipts})!=len(receipts): raise ValueError('duplicate capability receipt')
    body={'scope':'phase2-conformance-matrix-v1','capabilities':[{ 'capability_id':r.capability_id,'receipt_root':r.root,'passed':r.passed} for r in sorted(receipts,key=lambda x:x.capability_id)]}
    body['matrix_root']=sha(body); return body
