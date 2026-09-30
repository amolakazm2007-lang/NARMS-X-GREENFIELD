from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest

from packages.phase2_wave2 import (
    ApprovalRequired, IdempotencyConflict, IsolationViolation, PostgresWave2Runtime,
    RequestEnvelope, ResultEnvelope, StaleFence,
)

DSN = os.getenv("NARMS_PHASE2_POSTGRES_DSN") or os.getenv("NARMS_PHASE1_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN or os.getenv("NARMS_PHASE2_TESTS") != "1", reason="real PostgreSQL 16 required")


def runtime() -> PostgresWave2Runtime:
    assert DSN
    r = PostgresWave2Runtime(DSN)
    r.migrate()
    r.bootstrap_capabilities()
    return r


def seed(r: PostgresWave2Runtime) -> tuple[str, str, str]:
    w, p, c, m, j = (str(uuid4()) for _ in range(5))
    with psycopg.connect(r.dsn) as conn:
        conn.execute("INSERT INTO workspaces(id,name) VALUES(%s,'w2')", (w,))
        conn.execute("INSERT INTO projects(id,workspace_id,name) VALUES(%s,%s,'p')", (p,w))
        conn.execute("INSERT INTO conversations(id,workspace_id,project_id) VALUES(%s,%s,%s)", (c,w,p))
        conn.execute("INSERT INTO missions(id,workspace_id,project_id,conversation_id,state,trace_id,idempotency_key,request) VALUES(%s,%s,%s,%s,'READY',%s,%s,'w2')", (m,w,p,c,str(uuid4()),str(uuid4())))
        conn.execute("INSERT INTO jobs(id,mission_id,state,max_attempts,idempotency_key) VALUES(%s,%s,'READY',3,%s)", (j,m,str(uuid4())))
        conn.execute("INSERT INTO phase2_wave2_quotas(workspace_id,max_active_leases,max_tool_calls_per_mission,max_artifact_bytes) VALUES(%s,8,50,1000000)", (w,))
    return w,m,j


def test_worker_lease_fencing_and_stale_completion():
    r=runtime(); w,m,j=seed(r)
    worker=r.register_worker(w,"worker-a",["worker.protocol","tool.protocol","artifact.graph"])
    lease=r.acquire_lease(workspace_id=w,mission_id=m,job_id=j,worker_id=str(worker["worker_id"]),capability_id="worker.protocol",idempotency_key="lease-1",ttl_seconds=30)
    assert int(lease["fencing_token"]) == 1
    r.heartbeat_lease(str(lease["lease_id"]),str(worker["worker_id"]),1)
    with pytest.raises(StaleFence):
        r.heartbeat_lease(str(lease["lease_id"]),str(worker["worker_id"]),0)
    r.release_lease(str(lease["lease_id"]),str(worker["worker_id"]),1,success=False)
    lease2=r.acquire_lease(workspace_id=w,mission_id=m,job_id=j,worker_id=str(worker["worker_id"]),capability_id="worker.protocol",idempotency_key="lease-2",ttl_seconds=30)
    assert int(lease2["fencing_token"]) == 2


def test_tool_typed_idempotency_and_sensitive_approval():
    r=runtime(); w,m,j=seed(r)
    worker=r.register_worker(w,"worker-tool",["tool.protocol"])
    lease=r.acquire_lease(workspace_id=w,mission_id=m,job_id=j,worker_id=str(worker["worker_id"]),capability_id="tool.protocol",idempotency_key="tool-lease")
    r.register_tool(tool_id="safe.read",capability_id="tool.protocol",risk_class="read",permissions=["read"],input_schema={"type":"object"},output_schema={"type":"object"},implementation_version="1")
    env=RequestEnvelope("tool.request",1,w,m,j,"call-key",{"q":"x"})
    call=r.accept_tool_call(env,lease_id=str(lease["lease_id"]),worker_id=str(worker["worker_id"]),fencing_token=int(lease["fencing_token"]),tool_id="safe.read")
    replay=r.accept_tool_call(env,lease_id=str(lease["lease_id"]),worker_id=str(worker["worker_id"]),fencing_token=int(lease["fencing_token"]),tool_id="safe.read")
    assert call["call_id"] == replay["call_id"]
    bad=RequestEnvelope("tool.request",1,w,m,j,"call-key",{"q":"changed"})
    with pytest.raises(IdempotencyConflict):
        r.accept_tool_call(bad,lease_id=str(lease["lease_id"]),worker_id=str(worker["worker_id"]),fencing_token=int(lease["fencing_token"]),tool_id="safe.read")
    done=r.complete_tool_call(str(call["call_id"]),str(worker["worker_id"]),int(lease["fencing_token"]),ResultEnvelope("tool.result",1,{"ok":True}))
    assert done["state"] == "SUCCEEDED"

    r.register_tool(tool_id="danger.exec",capability_id="tool.protocol",risk_class="privileged",permissions=["exec"],input_schema={"type":"object"},output_schema={"type":"object"},implementation_version="1")
    env2=RequestEnvelope("tool.request",1,w,m,j,"danger-key",{"cmd":"bounded"})
    with pytest.raises(ApprovalRequired):
        r.accept_tool_call(env2,lease_id=str(lease["lease_id"]),worker_id=str(worker["worker_id"]),fencing_token=int(lease["fencing_token"]),tool_id="danger.exec")
    approval=str(uuid4())
    with psycopg.connect(r.dsn) as conn:
        conn.execute("INSERT INTO approvals(id,workspace_id,state,actor,action,risk) VALUES(%s,%s,'APPROVED','operator','danger.exec','privileged')",(approval,w))
        conn.execute("INSERT INTO phase2_tool_approval_bindings(approval_id,workspace_id,mission_id,tool_id,request_root,expires_at) VALUES(%s,%s,%s,'danger.exec',%s,now()+interval '5 minutes')",(approval,w,m,env2.request_root))
    accepted=r.accept_tool_call(env2,lease_id=str(lease["lease_id"]),worker_id=str(worker["worker_id"]),fencing_token=int(lease["fencing_token"]),tool_id="danger.exec",approval_id=approval)
    assert accepted["state"] == "ACCEPTED"


def test_artifact_content_addressing_revisions_lineage_and_immutability():
    r=runtime(); w,m,_=seed(r)
    logical=str(uuid4())
    a=r.create_artifact_revision(workspace_id=w,mission_id=m,logical_artifact_id=logical,content=b"alpha",storage_uri="cas://alpha",media_type="text/plain",provenance={"source":"tool"},evidence_root="a"*64)
    b=r.create_artifact_revision(workspace_id=w,mission_id=m,logical_artifact_id=logical,content=b"beta",storage_uri="cas://beta",media_type="text/plain",provenance={"source":"tool","parent":str(a["artifact_revision_id"])},evidence_root="b"*64,parents=[str(a["artifact_revision_id"])])
    assert a["content_sha256"] != b["content_sha256"]
    assert int(a["revision"]) == 1 and int(b["revision"]) == 2
    with psycopg.connect(r.dsn) as conn:
        edge=conn.execute("SELECT count(*) FROM phase2_artifact_edges WHERE parent_revision_id=%s AND child_revision_id=%s",(a["artifact_revision_id"],b["artifact_revision_id"])).fetchone()
        assert edge and edge[0] == 1
        with pytest.raises(psycopg.Error):
            conn.execute("UPDATE phase2_artifact_revisions SET evidence_root=%s WHERE artifact_revision_id=%s",("c"*64,a["artifact_revision_id"]))


def test_workspace_isolation_for_tool_and_artifact():
    r=runtime(); w,m,j=seed(r)
    w2,m2,j2=seed(r)
    worker=r.register_worker(w,"isolated",["tool.protocol"])
    with pytest.raises(IsolationViolation):
        r.acquire_lease(workspace_id=w2,mission_id=m,job_id=j,worker_id=str(worker["worker_id"]),capability_id="tool.protocol",idempotency_key="bad")
    with pytest.raises(IsolationViolation):
        r.create_artifact_revision(workspace_id=w2,mission_id=m,logical_artifact_id=str(uuid4()),content=b"x",storage_uri="cas://x",media_type="text/plain",provenance={},evidence_root="d"*64)


def test_real_audit_and_outbox_are_written():
    r=runtime(); w,m,j=seed(r)
    worker=r.register_worker(w,"audited",["worker.protocol"])
    r.acquire_lease(workspace_id=w,mission_id=m,job_id=j,worker_id=str(worker["worker_id"]),capability_id="worker.protocol",idempotency_key="audit-lease")
    with psycopg.connect(r.dsn) as conn:
        audit=conn.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s",(w,)).fetchone()
        outbox=conn.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND schema_version='2'",(w,)).fetchone()
    assert audit and audit[0] >= 2
    assert outbox and outbox[0] >= 2


def test_health_and_recovery_contract():
    r=runtime(); r.bootstrap_capabilities()
    h=r.health()
    assert h["status"] == "PASS"
    assert {x["capability_id"] for x in h["capabilities"]} == {"worker.protocol","tool.protocol","artifact.graph"}
    rec=r.recover()
    assert set(rec) == {"expired_leases","offline_workers"}
