from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from packages.phase2_wave1 import (
    DEFAULT_AUTHORITY_VERIFICATION,
    DEFAULT_CERTIFICATE,
    DEFAULT_TRUST_ANCHOR,
    ConcurrencyConflict,
    DependencyBlocked,
    OpeningDenied,
    PostgresWave1Runtime,
    load_opening,
)

ROOT = Path(__file__).resolve().parents[1]
DSN = os.getenv("NARMS_PHASE2_POSTGRES_DSN") or os.getenv("NARMS_PHASE1_POSTGRES_DSN")


pytestmark = pytest.mark.skipif(not DSN or os.getenv("NARMS_PHASE2_TESTS") != "1", reason="real Phase-2 PostgreSQL test environment required")


def runtime() -> PostgresWave1Runtime:
    assert DSN
    r = PostgresWave1Runtime(DSN)
    r.migrate()
    return r


def seed_phase1(r: PostgresWave1Runtime) -> tuple[str, str]:
    workspace_id = str(uuid4())
    project_id = str(uuid4())
    conversation_id = str(uuid4())
    mission_id = str(uuid4())
    with psycopg.connect(r.dsn) as conn:
        conn.execute("INSERT INTO workspaces(id,name) VALUES(%s,%s)", (workspace_id, "wave1-test"))
        conn.execute(
            "INSERT INTO projects(id,workspace_id,name) VALUES(%s,%s,%s)",
            (project_id, workspace_id, "p"),
        )
        conn.execute(
            "INSERT INTO conversations(id,workspace_id,project_id) VALUES(%s,%s,%s)",
            (conversation_id, workspace_id, project_id),
        )
        conn.execute(
            "INSERT INTO missions(id,workspace_id,project_id,conversation_id,state,trace_id,idempotency_key,request) "
            "VALUES(%s,%s,%s,%s,'READY',%s,%s,'wave1')",
            (mission_id, workspace_id, project_id, conversation_id, str(uuid4()), str(uuid4())),
        )
    return workspace_id, mission_id


def test_opening_fails_closed_on_tamper(tmp_path: Path):
    original = json.loads((ROOT / "evidence/phase2-opening-v1/opening-decision.json").read_text())
    original["opening_decision"]["allowed"] = False
    p = tmp_path / "opening.json"
    p.write_text(json.dumps(original))
    with pytest.raises(OpeningDenied):
        load_opening(p)




def test_opening_rejects_tampered_certificate(tmp_path: Path):
    cert = json.loads(DEFAULT_CERTIFICATE.read_text())
    cert["body"]["source_root"] = "0" * 64
    cert_path = tmp_path / "certificate.json"
    cert_path.write_text(json.dumps(cert))
    with pytest.raises(OpeningDenied):
        load_opening(
            certificate_path=cert_path,
            trust_anchor_path=DEFAULT_TRUST_ANCHOR,
            authority_verification_path=DEFAULT_AUTHORITY_VERIFICATION,
        )

def test_wave1_runtime_mission_workspace_and_history():
    r = runtime()
    workspace_id, mission_id = seed_phase1(r)
    active = r.activate_workspace(workspace_id)
    assert active["state"] == "ACTIVE"
    attached = r.attach_mission(mission_id, expected_workspace_id=workspace_id)
    assert attached["state"] == "CREATED"
    planned = r.transition_mission(
        mission_id,
        "PLANNED",
        {"plan_root": "a" * 64},
        expected_revision=int(attached["revision"]),
    )
    assert planned["state"] == "PLANNED"
    queued = r.transition_mission(
        mission_id,
        "QUEUED",
        {"policy_pass": True, "policy_root": "b" * 64},
        expected_revision=int(planned["revision"]),
    )
    assert queued["state"] == "QUEUED"
    with pytest.raises(ConcurrencyConflict):
        r.transition_mission(
            mission_id,
            "RUNNING",
            {"lease": "lease-1", "fencing_token": 1},
            expected_revision=int(planned["revision"]),
        )
    running = r.transition_mission(
        mission_id,
        "RUNNING",
        {"lease": "lease-1", "fencing_token": 1},
        expected_revision=int(queued["revision"]),
    )
    assert running["state"] == "RUNNING"
    with psycopg.connect(r.dsn) as conn:
        history = conn.execute(
            "SELECT count(*) FROM phase2_mission_history WHERE mission_id=%s",
            (mission_id,),
        ).fetchone()
        outbox = conn.execute(
            "SELECT count(*) FROM outbox_events WHERE aggregate_id=%s AND schema_version='2'",
            (mission_id,),
        ).fetchone()
    assert history and history[0] >= 4
    assert outbox and outbox[0] >= 4


def test_capability_registry_dependency_and_enablement():
    r = runtime()
    rows = {x["capability_id"]: x for x in r.bootstrap_capabilities()}
    assert set(rows) == {"mission.workspace", "capability.registry"}
    with pytest.raises(DependencyBlocked):
        r.transition_capability(
            "capability.registry",
            "ENABLED",
            expected_revision=int(rows["capability.registry"]["revision"]),
            evidence={"reason": "must-block"},
        )
    mission_cap = r.transition_capability(
        "mission.workspace",
        "ENABLED",
        expected_revision=int(rows["mission.workspace"]["revision"]),
        evidence={"reason": "test"},
    )
    assert mission_cap["state"] == "ENABLED"
    registry_cap = r.transition_capability(
        "capability.registry",
        "ENABLED",
        expected_revision=int(rows["capability.registry"]["revision"]),
        evidence={"reason": "test"},
    )
    assert registry_cap["state"] == "ENABLED"
    health = r.health()
    assert health["status"] == "PASS"
    assert {x["state"] for x in health["capabilities"]} == {"ENABLED"}


def test_workspace_isolation_is_enforced():
    r = runtime()
    workspace_id, mission_id = seed_phase1(r)
    other_workspace = str(uuid4())
    with psycopg.connect(r.dsn) as conn:
        conn.execute("INSERT INTO workspaces(id,name) VALUES(%s,'other')", (other_workspace,))
    r.activate_workspace(workspace_id)
    with pytest.raises(PermissionError):
        r.attach_mission(mission_id, expected_workspace_id=other_workspace)
