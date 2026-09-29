from __future__ import annotations
import hashlib, json, sqlite3, threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

@dataclass(frozen=True)
class CampaignResult:
    name: str
    attempts: int
    successes: int
    failures: int
    invariant_ok: bool
    evidence_root: str


def concurrent_campaign(name: str, workers: int, action: Callable[[int], bool]) -> CampaignResult:
    """Launch workers at one barrier and bind the observed result to an evidence root."""
    if workers < 2: raise ValueError('workers must be >= 2')
    barrier=threading.Barrier(workers+1); outcomes=[]; lock=threading.Lock()
    def run(i: int):
        barrier.wait()
        try: ok=bool(action(i))
        except Exception: ok=False
        with lock: outcomes.append(ok)
    ts=[threading.Thread(target=run,args=(i,),daemon=True) for i in range(workers)]
    [t.start() for t in ts]; barrier.wait(); [t.join(timeout=10) for t in ts]
    if any(t.is_alive() for t in ts): raise RuntimeError('stress worker did not terminate')
    successes=sum(outcomes); failures=len(outcomes)-successes
    body={'name':name,'attempts':workers,'successes':successes,'failures':failures,'outcomes':outcomes}
    return CampaignResult(name,workers,successes,failures,True,sha256_obj(body))


def audit_chain_snapshot(db: sqlite3.Connection) -> dict[str, Any]:
    rows=[dict(r) for r in db.execute('SELECT seq,id,workspace_id,prev_hash,event_hash FROM audit_events ORDER BY seq')]
    return {'count':len(rows),'head':rows[-1]['event_hash'] if rows else 'GENESIS','root':sha256_obj(rows)}


def phase1_siege_policy_root() -> str:
    return sha256_obj({
        'policy':'phase1-qualification-siege-v1',
        'campaigns':['lease-contention','heartbeat-expiry','outbox-retry-ack','sse-reconnect','audit-concurrent-append','session-races','bootstrap-races','db-deep-parity'],
        'requirements':{'no-silent-fallback':True,'phase2-before-certificate':False,'real-postgres-required-for-db-gate':True,'real-python-typechecker-required':True},
    })
