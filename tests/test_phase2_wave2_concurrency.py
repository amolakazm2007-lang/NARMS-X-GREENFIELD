from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import psycopg
import pytest

from packages.phase2_wave2 import PostgresWave2Runtime, Wave2Error

DSN=os.getenv("NARMS_PHASE2_POSTGRES_DSN") or os.getenv("NARMS_PHASE1_POSTGRES_DSN")
pytestmark=pytest.mark.skipif(not DSN or os.getenv("NARMS_PHASE2_TESTS")!="1",reason="real PostgreSQL 16 required")


def setup_case() -> tuple[PostgresWave2Runtime,str,str,str,list[str]]:
    assert DSN
    r=PostgresWave2Runtime(DSN); r.migrate(); r.bootstrap_capabilities()
    w,p,c,m,j=(str(uuid4()) for _ in range(5))
    with psycopg.connect(r.dsn) as conn:
        conn.execute("INSERT INTO workspaces(id,name) VALUES(%s,'conc')",(w,))
        conn.execute("INSERT INTO projects(id,workspace_id,name) VALUES(%s,%s,'p')",(p,w))
        conn.execute("INSERT INTO conversations(id,workspace_id,project_id) VALUES(%s,%s,%s)",(c,w,p))
        conn.execute("INSERT INTO missions(id,workspace_id,project_id,conversation_id,state,trace_id,idempotency_key,request) VALUES(%s,%s,%s,%s,'READY',%s,%s,'c')",(m,w,p,c,str(uuid4()),str(uuid4())))
        conn.execute("INSERT INTO jobs(id,mission_id,state,max_attempts,idempotency_key) VALUES(%s,%s,'READY',10,%s)",(j,m,str(uuid4())))
    workers=[]
    for i in range(8):
        x=r.register_worker(w,f"race-{i}",["worker.protocol"])
        workers.append(str(x["worker_id"]))
    return r,w,m,j,workers


def test_concurrent_lease_claim_has_single_winner_and_single_fence():
    r,w,m,j,workers=setup_case()
    def claim(i:int):
        try:
            return r.acquire_lease(workspace_id=w,mission_id=m,job_id=j,worker_id=workers[i],capability_id="worker.protocol",idempotency_key=f"race-{i}")
        except Wave2Error:
            return None
    with ThreadPoolExecutor(max_workers=8) as ex:
        results=[x.result() for x in as_completed([ex.submit(claim,i) for i in range(8)])]
    winners=[x for x in results if x]
    assert len(winners)==1
    assert int(winners[0]["fencing_token"])==1
    with psycopg.connect(r.dsn) as conn:
        row=conn.execute("SELECT count(*),max(fencing_token) FROM phase2_worker_leases WHERE job_id=%s AND state='ACTIVE'",(j,)).fetchone()
    assert row == (1,1)


def test_concurrent_artifact_revisions_are_gap_free_and_unique():
    r,w,m,_,_=setup_case()
    logical=str(uuid4())
    def make(i:int):
        return r.create_artifact_revision(workspace_id=w,mission_id=m,logical_artifact_id=logical,content=f"v{i}".encode(),storage_uri=f"cas://{i}",media_type="text/plain",provenance={"i":i},evidence_root=f"{i+1:064x}")
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows=[x.result() for x in as_completed([ex.submit(make,i) for i in range(8)])]
    assert sorted(int(x["revision"]) for x in rows)==list(range(1,9))
