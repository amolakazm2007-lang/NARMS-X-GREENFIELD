from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

REQUIRED_BOUNDARIES = frozenset({
    'identity','policy','approvals','durable_jobs','leases_fencing','events',
    'evidence','artifacts','audit','observability','quotas_compute'
})


def canonical(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha(v: Any) -> str:
    return hashlib.sha256(canonical(v)).hexdigest()

@dataclass(frozen=True)
class Capability:
    capability_id: str
    owner: str
    wave: int
    depends_on: tuple[str, ...]
    boundaries: tuple[str, ...]
    runtime_kind: str
    risk_class: str
    resource_class: str

@dataclass(frozen=True)
class DesignReport:
    valid: bool
    reasons: tuple[str, ...]
    capability_count: int
    waves: tuple[int, ...]
    graph_root: str
    implementation_allowed: bool = False
    scope: str = 'phase2-design-only-v1'


def load_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _cycle(nodes: dict[str, Capability]) -> bool:
    visiting:set[str]=set(); done:set[str]=set()
    def visit(n:str)->bool:
        if n in visiting: return True
        if n in done: return False
        visiting.add(n)
        for d in nodes[n].depends_on:
            if d in nodes and visit(d): return True
        visiting.remove(n); done.add(n); return False
    return any(visit(n) for n in sorted(nodes))


def validate_catalog(catalog: dict[str, Any]) -> DesignReport:
    reasons:list[str]=[]
    if catalog.get('scope') != 'phase2-design-only-v1': reasons.append('invalid_scope')
    if catalog.get('implementation_allowed') is not False: reasons.append('implementation_must_remain_locked')
    raw=catalog.get('capabilities')
    if not isinstance(raw,list) or not raw: reasons.append('capabilities_missing'); raw=[]
    nodes:dict[str,Capability]={}
    for row in raw:
        try:
            c=Capability(
                str(row['capability_id']),str(row['owner']),int(row['wave']),
                tuple(sorted(set(row.get('depends_on',[])))),
                tuple(sorted(set(row.get('boundaries',[])))),str(row['runtime_kind']),str(row['risk_class']),str(row['resource_class']))
        except Exception:
            reasons.append('malformed_capability'); continue
        if c.capability_id in nodes: reasons.append(f'duplicate:{c.capability_id}')
        if c.wave < 1 or c.wave > 9: reasons.append(f'invalid_wave:{c.capability_id}')
        if c.risk_class not in {'low','medium','high','critical'}: reasons.append(f'invalid_risk:{c.capability_id}')
        if c.resource_class not in {'control','cpu','browser','gpu','device','mixed'}: reasons.append(f'invalid_resource:{c.capability_id}')
        missing=REQUIRED_BOUNDARIES-set(c.boundaries)
        if missing: reasons.append(f'missing_boundaries:{c.capability_id}:{",".join(sorted(missing))}')
        nodes[c.capability_id]=c
    for cid,c in nodes.items():
        for dep in c.depends_on:
            if dep not in nodes: reasons.append(f'unknown_dependency:{cid}:{dep}')
            elif nodes[dep].wave > c.wave: reasons.append(f'future_dependency:{cid}:{dep}')
    if nodes and _cycle(nodes): reasons.append('dependency_cycle')
    normalized={
        'scope':'phase2-design-only-v1','implementation_allowed':False,
        'capabilities':[asdict(nodes[k]) for k in sorted(nodes)],
        'required_boundaries':sorted(REQUIRED_BOUNDARIES),
    }
    return DesignReport(not reasons,tuple(sorted(set(reasons))),len(nodes),tuple(sorted({c.wave for c in nodes.values()})),sha(normalized))


def compile_opening_plan(catalog: dict[str, Any]) -> dict[str, Any]:
    report=validate_catalog(catalog)
    if not report.valid: raise ValueError(';'.join(report.reasons))
    caps=sorted(catalog['capabilities'],key=lambda x:(int(x['wave']),str(x['capability_id'])))
    waves=[]
    for w in sorted({int(x['wave']) for x in caps}):
        waves.append({'wave':w,'capabilities':[x['capability_id'] for x in caps if int(x['wave'])==w]})
    body={'scope':'phase2-opening-plan-design-only-v1','implementation_allowed':False,'catalog_root':report.graph_root,'waves':waves}
    body['plan_root']=sha(body)
    return body
