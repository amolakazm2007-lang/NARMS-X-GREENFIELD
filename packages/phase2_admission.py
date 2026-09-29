from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
from packages.phase2_constitution import sha
from packages.phase2_design import validate_catalog
from packages.phase2_conformance import ConformanceReceipt

@dataclass(frozen=True)
class WaveAdmissionDecision:
    wave:int; allowed:bool; reasons:tuple[str,...]; catalog_root:str; opening_root:str|None; admitted:tuple[str,...]; scope:str='phase2-wave-admission-v1'
    @property
    def root(self)->str:return sha(asdict(self))

def evaluate_wave(*,wave:int,catalog:dict[str,Any],opening_allowed:bool,opening_root:str|None,receipts:tuple[ConformanceReceipt,...],prior_admitted:tuple[str,...]=())->WaveAdmissionDecision:
    dr=validate_catalog(catalog); reasons=list(dr.reasons)
    if not opening_allowed or not opening_root: reasons.append('trusted_phase2_opening_required')
    rows={str(x['capability_id']):x for x in catalog.get('capabilities',[])}
    target=sorted(k for k,v in rows.items() if int(v['wave'])==wave)
    if not target: reasons.append('wave_empty')
    rmap={r.capability_id:r for r in receipts}
    prior=set(prior_admitted)
    admitted=[]
    for cid in target:
        r=rmap.get(cid)
        if r is None or not r.passed: reasons.append(f'conformance_missing:{cid}'); continue
        for dep in rows[cid].get('depends_on',[]):
            dep_wave=int(rows[dep]['wave'])
            if dep_wave < wave and dep not in prior: reasons.append(f'prior_dependency_not_admitted:{cid}:{dep}')
            if dep_wave == wave and dep not in target: reasons.append(f'same_wave_dependency_invalid:{cid}:{dep}')
        admitted.append(cid)
    allowed=not reasons and set(admitted)==set(target)
    return WaveAdmissionDecision(wave,allowed,tuple(sorted(set(reasons))),dr.graph_root,opening_root,tuple(admitted) if allowed else ())
