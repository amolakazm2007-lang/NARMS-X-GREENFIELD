from __future__ import annotations
from dataclasses import dataclass,asdict
from packages.phase2_constitution import sha

REQUIRED_DOMAINS=('build','browser','research','data','gpu','media','android','automation')
@dataclass(frozen=True)
class DomainReceipt:
    domain:str; capability_root:str; isolation_passed:bool; evidence_root:str; failure_containment_root:str
    @property
    def root(self)->str:return sha(asdict(self))
@dataclass(frozen=True)
class CrossDomainDecision:
    qualified:bool; reasons:tuple[str,...]; domain_roots:tuple[tuple[str,str],...]; scope:str='phase2-cross-domain-qualification-v1'
    @property
    def root(self)->str:return sha(asdict(self))

def qualify(receipts:tuple[DomainReceipt,...])->CrossDomainDecision:
    reasons=[]
    if len({r.domain for r in receipts})!=len(receipts): reasons.append('duplicate_domain')
    m={r.domain:r for r in receipts}
    for d in REQUIRED_DOMAINS:
        r=m.get(d)
        if not r: reasons.append('missing:'+d); continue
        if not r.isolation_passed: reasons.append('isolation_failed:'+d)
        if not r.evidence_root: reasons.append('evidence_missing:'+d)
        if not r.failure_containment_root: reasons.append('containment_missing:'+d)
    unknown=set(m)-set(REQUIRED_DOMAINS)
    if unknown: reasons.append('unknown_domains:'+','.join(sorted(unknown)))
    roots=tuple((d,m[d].root) for d in sorted(m))
    return CrossDomainDecision(not reasons,tuple(sorted(set(reasons))),roots)
