from __future__ import annotations

import os
from uuid import uuid4

import psycopg
import pytest

from packages.phase2_wave2 import (
    ApprovalRequired, ArtifactViolation, CapabilityBlocked, PostgresWave2Runtime,
    RequestEnvelope, StaleFence,
)

DSN=os.getenv("NARMS_PHASE2_POSTGRES_DSN") or os.getenv("NARMS_PHASE1_POSTGRES_DSN")
pytestmark=pytest.mark.skipif(not DSN or os.getenv("NARMS_PHASE2_TESTS")!="1",reason="real PostgreSQL 16 required")


def seed() -> tuple[PostgresWave2Runtime,str,str,str]:
    assert DSN
    r=PostgresWave2Runtime(DSN); r.migrate(); r.bootstrap_capabilities()
    w,p,c,m,j=(str(uuid4()) for _ in range(5))
    with psycopg.connect(r.dsn) as conn:
        conn.execute("INSERT INTO workspaces(id,name) VALUES(%s,'adv')",(w,))
        conn.execute("INSERT INTO projects(id,workspace_id,name) VALUES(%s,%s,'p')",(p,w))
        conn.execute("INSERT INTO conversations(id,workspace_id,project_id) VALUES(%s,%s,%s)",(c,w,p))
        conn.execute("INSERT INTO missions(id,workspace_id,project_id,conversation_id,state,trace_id,idempotency_key,request) VALUES(%s,%s,%s,%s,'READY',%s,%s,'a')",(m,w,p,c,str(uuid4()),str(uuid4())))
        conn.execute("INSERT INTO jobs(id,mission_id,state,max_attempts,idempotency_key) VALUES(%s,%s,'READY',3,%s)",(j,m,str(uuid4())))
    return r,w,m,j


def test_stale_opening_root_blocks_worker_execution():
    r,w,m,j=seed()
    worker=r.register_worker(w,"stale",["worker.protocol"])
    with psycopg.connect(r.dsn) as conn:
        conn.execute("UPDATE phase2_workers SET opening_root=%s WHERE worker_id=%s",("0"*64,worker["worker_id"]))
    with pytest.raises(CapabilityBlocked):
        r.acquire_lease(workspace_id=w,mission_id=m,job_id=j,worker_id=str(worker["worker_id"]),capability_id="worker.protocol",idempotency_key="stale")


def test_wrong_workspace_approval_is_rejected():
    r,w,m,j=seed()
    worker=r.register_worker(w,"approval",["tool.protocol"])
    lease=r.acquire_lease(workspace_id=w,mission_id=m,job_id=j,worker_id=str(worker["worker_id"]),capability_id="tool.protocol",idempotency_key="lease")
    r.register_tool(tool_id="external.send",capability_id="tool.protocol",risk_class="external_side_effect",permissions=["network"],input_schema={},output_schema={},implementation_version="1")
    other=str(uuid4()); approval=str(uuid4())
    with psycopg.connect(r.dsn) as conn:
        conn.execute("INSERT INTO workspaces(id,name) VALUES(%s,'other')",(other,))
        conn.execute("INSERT INTO approvals(id,workspace_id,state,actor,action,risk) VALUES(%s,%s,'APPROVED','attacker','external.send','external_side_effect')",(approval,other))
    env=RequestEnvelope("tool.request",1,w,m,j,"x",{"target":"bounded"})
    with pytest.raises(ApprovalRequired):
        r.accept_tool_call(env,lease_id=str(lease["lease_id"]),worker_id=str(worker["worker_id"]),fencing_token=int(lease["fencing_token"]),tool_id="external.send",approval_id=approval)


def test_artifact_declared_hash_drift_is_rejected():
    r,w,m,_=seed()
    with pytest.raises(ArtifactViolation):
        r.create_artifact_revision(workspace_id=w,mission_id=m,logical_artifact_id=str(uuid4()),content=b"real",storage_uri="cas://real",media_type="application/octet-stream",provenance={"source":"real"},evidence_root="a"*64,expected_content_sha256="0"*64)


def test_expired_or_released_fence_cannot_authorize_tool_call():
    r,w,m,j=seed()
    worker=r.register_worker(w,"fence",["tool.protocol"])
    lease=r.acquire_lease(workspace_id=w,mission_id=m,job_id=j,worker_id=str(worker["worker_id"]),capability_id="tool.protocol",idempotency_key="fence")
    r.register_tool(tool_id="read.one",capability_id="tool.protocol",risk_class="read",permissions=["read"],input_schema={},output_schema={},implementation_version="1")
    r.release_lease(str(lease["lease_id"]),str(worker["worker_id"]),int(lease["fencing_token"]),success=False)
    env=RequestEnvelope("tool.request",1,w,m,j,"after-release",{})
    with pytest.raises(StaleFence):
        r.accept_tool_call(env,lease_id=str(lease["lease_id"]),worker_id=str(worker["worker_id"]),fencing_token=int(lease["fencing_token"]),tool_id="read.one")
