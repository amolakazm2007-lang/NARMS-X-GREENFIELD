from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
from packages.phase2_constitution import sha
from packages.phase2_design import validate_catalog

@dataclass(frozen=True)
class SealedSkeleton:
    capability_id:str; owner:str; wave:int; runtime_kind:str; risk_class:str; contract_root:str
    executable:bool=False
    scope:str='phase2-sealed-skeleton-v1'
    @property
    def root(self)->str:return sha(asdict(self))

def compile_sealed_skeletons(catalog:dict[str,Any])->tuple[SealedSkeleton,...]:
    report=validate_catalog(catalog)
    if not report.valid: raise ValueError(';'.join(report.reasons))
    out=[]
    for row in sorted(catalog['capabilities'],key=lambda x:(int(x['wave']),str(x['capability_id']))):
        contract={'capability_id':row['capability_id'],'depends_on':sorted(row.get('depends_on',[])),'boundaries':sorted(row.get('boundaries',[])),'resource_class':row['resource_class']}
        out.append(SealedSkeleton(str(row['capability_id']),str(row['owner']),int(row['wave']),str(row['runtime_kind']),str(row['risk_class']),sha(contract)))
    return tuple(out)

def assert_non_executable(skeletons:tuple[SealedSkeleton,...])->str:
    if any(x.executable for x in skeletons): raise RuntimeError('sealed skeleton became executable')
    return sha([x.root for x in skeletons])
