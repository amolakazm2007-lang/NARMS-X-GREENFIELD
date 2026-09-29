from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from packages.phase1_attestation import verify_attested_phase1_certificate
from packages.phase2_design import validate_catalog
from packages.phase2_constitution import Phase2Constitution,sha
@dataclass(frozen=True)
class OpeningDecision:
    allowed:bool; reasons:tuple[str,...]; unlock_root:str|None; constitution_root:str; catalog_root:str
    @property
    def root(self)->str:return sha({'allowed':self.allowed,'reasons':self.reasons,'unlock_root':self.unlock_root,'constitution_root':self.constitution_root,'catalog_root':self.catalog_root})

def evaluate(*,certificate:dict[str,Any]|None,report:dict[str,Any],attestation:dict[str,Any]|None,trusted_public_key_hex:str|None,catalog:dict[str,Any])->OpeningDecision:
    dr=validate_catalog(catalog); reasons=list(dr.reasons)
    unlock=None
    if not certificate or not attestation or not trusted_public_key_hex:
        reasons.append('phase1_trusted_certificate_missing')
    else:
        vr=verify_attested_phase1_certificate(certificate,report,attestation,trusted_public_key_hex)
        if not vr['phase2_allowed']: reasons.extend('phase1:'+x for x in vr['reasons'])
        else: unlock=vr['unlock_root']
    c=Phase2Constitution()
    return OpeningDecision(not reasons,tuple(sorted(set(reasons))),unlock,c.root,dr.graph_root)
