from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from packages.phase2_wave1 import OpeningReceipt, load_opening, root

ROOT = Path(__file__).resolve().parents[1]
UP_MIGRATION = ROOT / "migrations/0003_phase2_wave2.sql"
DOWN_MIGRATION = ROOT / "migrations/0003_phase2_wave2.down.sql"
MANIFEST = ROOT / "contracts/phase2-wave2.runtime.json"
WAVE2_CAPABILITIES = ("worker.protocol", "tool.protocol", "artifact.graph")
RISK_CLASSES = {"read", "write", "external_side_effect", "privileged"}
SENSITIVE_RISKS = {"external_side_effect", "privileged"}


class Wave2Error(RuntimeError):
    pass


class StaleFence(Wave2Error):
    pass


class ApprovalRequired(Wave2Error):
    pass


class IdempotencyConflict(Wave2Error):
    pass


class IsolationViolation(Wave2Error):
    pass


class QuotaExceeded(Wave2Error):
    pass


class ArtifactViolation(Wave2Error):
    pass


class CapabilityBlocked(Wave2Error):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hex64(value: str) -> bool:
    try:
        return len(value) == 64 and int(value, 16) >= 0
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class RequestEnvelope:
    request_type: str
    version: int
    workspace_id: str
    mission_id: str
    job_id: str
    idempotency_key: str
    payload: Mapping[str, Any]

    @property
    def request_root(self) -> str:
        return root({
            "request_type": self.request_type,
            "version": self.version,
            "workspace_id": self.workspace_id,
            "mission_id": self.mission_id,
            "job_id": self.job_id,
            "idempotency_key": self.idempotency_key,
            "payload": dict(self.payload),
        })


@dataclass(frozen=True)
class ResultEnvelope:
    result_type: str
    version: int
    payload: Mapping[str, Any]

    @property
    def result_root(self) -> str:
        return root({"result_type": self.result_type, "version": self.version, "payload": dict(self.payload)})


class PostgresWave2Runtime:
    def __init__(self, dsn: str, opening: OpeningReceipt | None = None):
        self.dsn = dsn
        self.opening = opening or load_opening()

    def migrate(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(UP_MIGRATION.read_text())

    def rollback(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(DOWN_MIGRATION.read_text())

    def _event(self, cur: psycopg.Cursor[Any], *, workspace_id: str, actor: str, action: str,
               aggregate_type: str, aggregate_id: str, payload: Mapping[str, Any]) -> None:
        trace_id = str(payload.get("trace_id") or uuid4())
        event_id = str(uuid4())
        cur.execute(
            "INSERT INTO outbox_events(event_id,event_type,schema_version,aggregate_type,aggregate_id,"
            "workspace_id,correlation_id,trace_id,payload,occurred_at) "
            "VALUES(%s,%s,'2',%s,%s,%s,%s,%s,%s,now())",
            (event_id, action, aggregate_type, aggregate_id, workspace_id, trace_id, trace_id, json.dumps(dict(payload))),
        )
        prev = cur.execute(
            "SELECT event_hash FROM audit_events WHERE workspace_id=%s ORDER BY seq DESC LIMIT 1 FOR UPDATE",
            (workspace_id,),
        ).fetchone()
        prev_hash = str(prev[0]) if prev else "0" * 64
        audit_payload = {"action": action, "aggregate_type": aggregate_type, "aggregate_id": aggregate_id, **dict(payload)}
        event_hash = root({"workspace_id": workspace_id, "actor": actor, "trace_id": trace_id,
                           "payload": audit_payload, "prev_hash": prev_hash})
        cur.execute(
            "INSERT INTO audit_events(id,workspace_id,actor,action,trace_id,payload,prev_hash,event_hash) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(uuid4()), workspace_id, actor, action, trace_id, json.dumps(audit_payload), prev_hash, event_hash),
        )

    def bootstrap_capabilities(self) -> list[dict[str, Any]]:
        manifest = json.loads(MANIFEST.read_text())
        contract_root = root(manifest)
        rows: list[dict[str, Any]] = []
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                for capability_id in WAVE2_CAPABILITIES:
                    cur.execute(
                        "INSERT INTO phase2_capability_registry(capability_id,owner,wave,runtime_kind,risk_class,"
                        "resource_class,state,implementation_version,contract_root,opening_root,metadata) "
                        "VALUES(%s,'execution-core',2,'protocol','high','control','ENABLED','1.0.0',%s,%s,%s) "
                        "ON CONFLICT(capability_id) DO UPDATE SET contract_root=EXCLUDED.contract_root,"
                        "opening_root=EXCLUDED.opening_root RETURNING *",
                        (capability_id, contract_root, self.opening.opening_decision_root,
                         json.dumps({"wave": 2, "production_evidence_must_be_real": True})),
                    )
                    row = cur.fetchone()
                    assert row
                    rows.append(dict(row))
        return rows

    def _assert_capability(self, cur: psycopg.Cursor[Any], capability_id: str) -> None:
        row = cur.execute(
            "SELECT state,opening_root FROM phase2_capability_registry WHERE capability_id=%s", (capability_id,)
        ).fetchone()
        if not row or row[0] != "ENABLED" or row[1] != self.opening.opening_decision_root:
            raise CapabilityBlocked(capability_id)

    def _assert_binding(self, cur: psycopg.Cursor[Any], workspace_id: str, mission_id: str, job_id: str) -> None:
        row = cur.execute(
            "SELECT m.workspace_id,j.mission_id FROM missions m JOIN jobs j ON j.mission_id=m.id "
            "WHERE m.id=%s AND j.id=%s", (mission_id, job_id)
        ).fetchone()
        if not row or str(row[0]) != workspace_id or str(row[1]) != mission_id:
            raise IsolationViolation("workspace/mission/job binding mismatch")

    def register_worker(self, workspace_id: str, worker_name: str, capabilities: Sequence[str],
                        metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        worker_id = str(uuid4())
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                for cap in capabilities:
                    self._assert_capability(cur, cap)
                cur.execute(
                    "INSERT INTO phase2_workers(worker_id,workspace_id,worker_name,state,capabilities,opening_root,metadata) "
                    "VALUES(%s,%s,%s,'READY',%s,%s,%s) RETURNING *",
                    (worker_id, workspace_id, worker_name, list(capabilities),
                     self.opening.opening_decision_root, json.dumps(dict(metadata or {}))),
                )
                row = cur.fetchone()
                assert row
                self._event(cur, workspace_id=workspace_id, actor=worker_name, action="phase2.worker.registered",
                            aggregate_type="worker", aggregate_id=worker_id, payload={"capabilities": list(capabilities)})
                return dict(row)

    def heartbeat_worker(self, worker_id: str, workspace_id: str) -> dict[str, Any]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                "UPDATE phase2_workers SET last_heartbeat_at=now(),revision=revision+1 "
                "WHERE worker_id=%s AND workspace_id=%s AND state NOT IN ('OFFLINE','QUARANTINED') RETURNING *",
                (worker_id, workspace_id),
            ).fetchone()
            if not row:
                raise IsolationViolation("worker unavailable or wrong workspace")
            return dict(row)

    def acquire_lease(self, *, workspace_id: str, mission_id: str, job_id: str, worker_id: str,
                      capability_id: str, idempotency_key: str, ttl_seconds: int = 30) -> dict[str, Any]:
        if ttl_seconds < 1 or ttl_seconds > 3600:
            raise ValueError("ttl_seconds out of range")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                self._assert_capability(cur, capability_id)
                self._assert_binding(cur, workspace_id, mission_id, job_id)
                worker = cur.execute(
                    "SELECT state,capabilities,opening_root FROM phase2_workers WHERE worker_id=%s AND workspace_id=%s FOR UPDATE",
                    (worker_id, workspace_id),
                ).fetchone()
                if not worker or worker["state"] not in ("READY", "BUSY") or capability_id not in worker["capabilities"]:
                    raise CapabilityBlocked("worker cannot execute capability")
                if worker["opening_root"] != self.opening.opening_decision_root:
                    raise CapabilityBlocked("stale worker opening root")
                quota = cur.execute(
                    "SELECT max_active_leases FROM phase2_wave2_quotas WHERE workspace_id=%s", (workspace_id,)
                ).fetchone()
                max_active = int(quota["max_active_leases"]) if quota else 32
                active = cur.execute(
                    "SELECT count(*) AS n FROM phase2_worker_leases WHERE workspace_id=%s AND state='ACTIVE' "
                    "AND lease_expires_at>now()", (workspace_id,)
                ).fetchone()
                if active and int(active["n"]) >= max_active:
                    raise QuotaExceeded("active lease quota")
                prior = cur.execute(
                    "SELECT * FROM phase2_worker_leases WHERE workspace_id=%s AND idempotency_key=%s",
                    (workspace_id, idempotency_key),
                ).fetchone()
                if prior:
                    return dict(prior)
                job = cur.execute("SELECT fencing_token,attempt,max_attempts FROM jobs WHERE id=%s FOR UPDATE", (job_id,)).fetchone()
                if not job:
                    raise IsolationViolation("job missing")
                cur.execute(
                    "UPDATE phase2_worker_leases SET state='EXPIRED' WHERE job_id=%s AND state='ACTIVE' AND lease_expires_at<=now()",
                    (job_id,),
                )
                still = cur.execute(
                    "SELECT lease_id FROM phase2_worker_leases WHERE job_id=%s AND state='ACTIVE' FOR UPDATE", (job_id,)
                ).fetchone()
                if still:
                    raise Wave2Error("job already leased")
                attempt = int(job["attempt"]) + 1
                if attempt > int(job["max_attempts"]):
                    raise Wave2Error("retry budget exhausted")
                fence = int(job["fencing_token"]) + 1
                lease_id = str(uuid4())
                expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
                cur.execute(
                    "UPDATE jobs SET attempt=%s,fencing_token=%s,lease_owner=%s,heartbeat_at=extract(epoch from now()),"
                    "lease_expires_at=extract(epoch from %s::timestamptz),state='RUNNING' WHERE id=%s",
                    (attempt, fence, worker_id, expiry, job_id),
                )
                cur.execute(
                    "INSERT INTO phase2_worker_leases(lease_id,workspace_id,mission_id,job_id,worker_id,capability_id,"
                    "fencing_token,state,attempt,max_attempts,lease_expires_at,idempotency_key,opening_root) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,'ACTIVE',%s,%s,%s,%s,%s) RETURNING *",
                    (lease_id, workspace_id, mission_id, job_id, worker_id, capability_id, fence, attempt,
                     int(job["max_attempts"]), expiry, idempotency_key, self.opening.opening_decision_root),
                )
                row = cur.fetchone()
                assert row
                self._event(cur, workspace_id=workspace_id, actor=worker_id, action="phase2.lease.acquired",
                            aggregate_type="job", aggregate_id=job_id,
                            payload={"lease_id": lease_id, "fencing_token": fence, "attempt": attempt})
                return dict(row)

    def heartbeat_lease(self, lease_id: str, worker_id: str, fencing_token: int, ttl_seconds: int = 30) -> dict[str, Any]:
        expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                "UPDATE phase2_worker_leases SET heartbeat_at=now(),lease_expires_at=%s "
                "WHERE lease_id=%s AND worker_id=%s AND fencing_token=%s AND state='ACTIVE' "
                "AND lease_expires_at>now() RETURNING *",
                (expiry, lease_id, worker_id, fencing_token),
            ).fetchone()
            if not row:
                raise StaleFence("stale/expired lease")
            return dict(row)

    def release_lease(self, lease_id: str, worker_id: str, fencing_token: int, *, success: bool) -> None:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                row = cur.execute(
                    "UPDATE phase2_worker_leases SET state='RELEASED' WHERE lease_id=%s AND worker_id=%s "
                    "AND fencing_token=%s AND state='ACTIVE' RETURNING workspace_id,job_id", (lease_id, worker_id, fencing_token)
                ).fetchone()
                if not row:
                    raise StaleFence("stale lease release")
                cur.execute("UPDATE jobs SET state=%s,lease_owner=NULL WHERE id=%s AND fencing_token=%s",
                            ("SUCCEEDED" if success else "RETRY", row[1], fencing_token))
                self._event(cur, workspace_id=str(row[0]), actor=worker_id, action="phase2.lease.released",
                            aggregate_type="job", aggregate_id=str(row[1]), payload={"success": success, "fencing_token": fencing_token})

    def register_tool(self, *, tool_id: str, capability_id: str, risk_class: str, permissions: Sequence[str],
                      input_schema: Mapping[str, Any], output_schema: Mapping[str, Any],
                      implementation_version: str) -> dict[str, Any]:
        if risk_class not in RISK_CLASSES:
            raise ValueError("invalid risk class")
        contract_root = root({"tool_id": tool_id, "capability_id": capability_id, "risk_class": risk_class,
                              "permissions": sorted(permissions), "input_schema": dict(input_schema),
                              "output_schema": dict(output_schema), "implementation_version": implementation_version})
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                self._assert_capability(cur, capability_id)
                row = cur.execute(
                    "INSERT INTO phase2_tool_registry(tool_id,capability_id,risk_class,permissions,input_schema,output_schema,"
                    "implementation_version,contract_root,opening_root,enabled) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,true) "
                    "ON CONFLICT(tool_id) DO UPDATE SET enabled=true RETURNING *",
                    (tool_id, capability_id, risk_class, list(permissions), json.dumps(dict(input_schema)),
                     json.dumps(dict(output_schema)), implementation_version, contract_root, self.opening.opening_decision_root),
                ).fetchone()
                assert row
                return dict(row)

    def _approval(self, cur: psycopg.Cursor[Any], approval_id: str | None, workspace_id: str,
                  tool_id: str, risk_class: str) -> None:
        if risk_class not in SENSITIVE_RISKS:
            return
        if not approval_id:
            raise ApprovalRequired("approval required")
        row = cur.execute(
            "SELECT workspace_id,state,action,risk FROM approvals WHERE id=%s", (approval_id,)
        ).fetchone()
        if not row or str(row[0]) != workspace_id or row[1] != "APPROVED" or row[2] != tool_id or row[3] != risk_class:
            raise ApprovalRequired("approval receipt mismatch")

    def accept_tool_call(self, envelope: RequestEnvelope, *, lease_id: str, worker_id: str,
                         fencing_token: int, tool_id: str, approval_id: str | None = None) -> dict[str, Any]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                self._assert_binding(cur, envelope.workspace_id, envelope.mission_id, envelope.job_id)
                lease = cur.execute(
                    "SELECT * FROM phase2_worker_leases WHERE lease_id=%s AND worker_id=%s AND fencing_token=%s "
                    "AND state='ACTIVE' AND lease_expires_at>now() FOR UPDATE", (lease_id, worker_id, fencing_token)
                ).fetchone()
                if not lease or str(lease["workspace_id"]) != envelope.workspace_id or str(lease["mission_id"]) != envelope.mission_id:
                    raise StaleFence("lease/fence/binding invalid")
                tool = cur.execute(
                    "SELECT * FROM phase2_tool_registry WHERE tool_id=%s AND enabled=true", (tool_id,)
                ).fetchone()
                if not tool or tool["opening_root"] != self.opening.opening_decision_root:
                    raise CapabilityBlocked("unknown/disabled/stale tool")
                self._assert_capability(cur, str(tool["capability_id"]))
                self._approval(cur, approval_id, envelope.workspace_id, tool_id, str(tool["risk_class"]))
                prior = cur.execute(
                    "SELECT * FROM phase2_tool_calls WHERE workspace_id=%s AND mission_id=%s AND idempotency_key=%s",
                    (envelope.workspace_id, envelope.mission_id, envelope.idempotency_key),
                ).fetchone()
                if prior:
                    if prior["request_root"] != envelope.request_root:
                        raise IdempotencyConflict("same idempotency key with different request")
                    return dict(prior)
                quota = cur.execute(
                    "SELECT max_tool_calls_per_mission FROM phase2_wave2_quotas WHERE workspace_id=%s",
                    (envelope.workspace_id,),
                ).fetchone()
                limit = int(quota["max_tool_calls_per_mission"]) if quota else 1000
                count = cur.execute("SELECT count(*) AS n FROM phase2_tool_calls WHERE mission_id=%s", (envelope.mission_id,)).fetchone()
                if count and int(count["n"]) >= limit:
                    raise QuotaExceeded("tool-call quota")
                call_id = str(uuid4())
                row = cur.execute(
                    "INSERT INTO phase2_tool_calls(call_id,workspace_id,mission_id,job_id,lease_id,tool_id,request_type,"
                    "request_version,request_payload,request_root,approval_id,state,idempotency_key,fencing_token) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACCEPTED',%s,%s) RETURNING *",
                    (call_id, envelope.workspace_id, envelope.mission_id, envelope.job_id, lease_id, tool_id,
                     envelope.request_type, envelope.version, json.dumps(dict(envelope.payload)), envelope.request_root,
                     approval_id, envelope.idempotency_key, fencing_token),
                ).fetchone()
                assert row
                self._event(cur, workspace_id=envelope.workspace_id, actor=worker_id, action="phase2.tool.accepted",
                            aggregate_type="tool_call", aggregate_id=call_id,
                            payload={"tool_id": tool_id, "request_root": envelope.request_root, "fencing_token": fencing_token})
                return dict(row)

    def complete_tool_call(self, call_id: str, worker_id: str, fencing_token: int,
                           result: ResultEnvelope | None = None,
                           error: Mapping[str, Any] | None = None, retryable: bool = False) -> dict[str, Any]:
        if (result is None) == (error is None):
            raise ValueError("exactly one of result or error required")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                call = cur.execute(
                    "SELECT c.*,l.worker_id,l.state AS lease_state,l.lease_expires_at FROM phase2_tool_calls c "
                    "JOIN phase2_worker_leases l ON l.lease_id=c.lease_id WHERE c.call_id=%s FOR UPDATE", (call_id,)
                ).fetchone()
                if not call or str(call["worker_id"]) != worker_id or int(call["fencing_token"]) != fencing_token:
                    raise StaleFence("stale tool completion")
                if call["lease_state"] != "ACTIVE" or call["lease_expires_at"] <= datetime.now(timezone.utc):
                    raise StaleFence("expired lease")
                state = "SUCCEEDED" if result else ("RETRYABLE" if retryable else "FAILED")
                payload = dict(result.payload) if result else None
                result_root = result.result_root if result else None
                row = cur.execute(
                    "UPDATE phase2_tool_calls SET state=%s,result_payload=%s,result_root=%s,error_payload=%s,updated_at=now() "
                    "WHERE call_id=%s RETURNING *",
                    (state, json.dumps(payload) if payload is not None else None, result_root,
                     json.dumps(dict(error or {})) if error is not None else None, call_id),
                ).fetchone()
                assert row
                self._event(cur, workspace_id=str(call["workspace_id"]), actor=worker_id,
                            action="phase2.tool.completed", aggregate_type="tool_call", aggregate_id=call_id,
                            payload={"state": state, "result_root": result_root, "fencing_token": fencing_token})
                return dict(row)

    def create_artifact_revision(self, *, workspace_id: str, mission_id: str, logical_artifact_id: str,
                                 content: bytes, storage_uri: str, media_type: str,
                                 provenance: Mapping[str, Any], evidence_root: str,
                                 parents: Sequence[str] = ()) -> dict[str, Any]:
        if not _hex64(evidence_root):
            raise ArtifactViolation("invalid evidence root")
        content_sha = sha256_bytes(content)
        provenance_root = root(dict(provenance))
        revision_id = str(uuid4())
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                mission = cur.execute("SELECT workspace_id FROM missions WHERE id=%s", (mission_id,)).fetchone()
                if not mission or str(mission["workspace_id"]) != workspace_id:
                    raise IsolationViolation("artifact mission/workspace mismatch")
                quota = cur.execute("SELECT max_artifact_bytes FROM phase2_wave2_quotas WHERE workspace_id=%s", (workspace_id,)).fetchone()
                limit = int(quota["max_artifact_bytes"]) if quota else 10737418240
                used = cur.execute(
                    "SELECT coalesce(sum(o.size_bytes),0) AS n FROM phase2_artifact_revisions r "
                    "JOIN phase2_artifact_objects o ON o.content_sha256=r.content_sha256 WHERE r.workspace_id=%s",
                    (workspace_id,),
                ).fetchone()
                if used and int(used["n"]) + len(content) > limit:
                    raise QuotaExceeded("artifact byte quota")
                cur.execute(
                    "INSERT INTO phase2_artifact_objects(content_sha256,size_bytes,media_type,storage_uri) VALUES(%s,%s,%s,%s) "
                    "ON CONFLICT(content_sha256) DO NOTHING", (content_sha, len(content), media_type, storage_uri)
                )
                rev = cur.execute(
                    "SELECT coalesce(max(revision),0)+1 AS n FROM phase2_artifact_revisions "
                    "WHERE workspace_id=%s AND logical_artifact_id=%s FOR UPDATE",
                    (workspace_id, logical_artifact_id),
                ).fetchone()
                revision = int(rev["n"]) if rev else 1
                row = cur.execute(
                    "INSERT INTO phase2_artifact_revisions(artifact_revision_id,workspace_id,mission_id,logical_artifact_id,"
                    "revision,content_sha256,provenance,provenance_root,evidence_root,opening_root) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (revision_id, workspace_id, mission_id, logical_artifact_id, revision, content_sha,
                     json.dumps(dict(provenance)), provenance_root, evidence_root, self.opening.opening_decision_root),
                ).fetchone()
                assert row
                for parent_id in parents:
                    parent = cur.execute(
                        "SELECT workspace_id,mission_id FROM phase2_artifact_revisions WHERE artifact_revision_id=%s",
                        (parent_id,),
                    ).fetchone()
                    if not parent or str(parent["workspace_id"]) != workspace_id or str(parent["mission_id"]) != mission_id:
                        raise IsolationViolation("artifact parent isolation mismatch")
                    cycle = cur.execute(
                        "WITH RECURSIVE reach(id) AS (SELECT child_revision_id FROM phase2_artifact_edges WHERE parent_revision_id=%s "
                        "UNION SELECT e.child_revision_id FROM phase2_artifact_edges e JOIN reach r ON e.parent_revision_id=r.id) "
                        "SELECT 1 FROM reach WHERE id=%s LIMIT 1", (revision_id, parent_id)
                    ).fetchone()
                    if cycle or parent_id == revision_id:
                        raise ArtifactViolation("artifact cycle")
                    cur.execute(
                        "INSERT INTO phase2_artifact_edges(workspace_id,mission_id,parent_revision_id,child_revision_id,relation,evidence_root) "
                        "VALUES(%s,%s,%s,%s,'derived_from',%s)",
                        (workspace_id, mission_id, parent_id, revision_id, evidence_root),
                    )
                self._event(cur, workspace_id=workspace_id, actor="artifact.graph", action="phase2.artifact.revision.created",
                            aggregate_type="artifact", aggregate_id=revision_id,
                            payload={"content_sha256": content_sha, "provenance_root": provenance_root,
                                     "evidence_root": evidence_root, "revision": revision})
                return dict(row)

    def recover(self) -> dict[str, int]:
        with psycopg.connect(self.dsn) as conn:
            expired = conn.execute(
                "UPDATE phase2_worker_leases SET state='EXPIRED' WHERE state='ACTIVE' AND lease_expires_at<=now() RETURNING job_id"
            ).fetchall()
            for (job_id,) in expired:
                conn.execute("UPDATE jobs SET state='RETRY',lease_owner=NULL WHERE id=%s", (job_id,))
            offline = conn.execute(
                "UPDATE phase2_workers SET state='OFFLINE',revision=revision+1 WHERE state IN ('READY','BUSY') "
                "AND last_heartbeat_at < now()-interval '2 minutes' RETURNING worker_id"
            ).fetchall()
            return {"expired_leases": len(expired), "offline_workers": len(offline)}

    def health(self) -> dict[str, Any]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            server = conn.execute("SHOW server_version").fetchone()
            migration = conn.execute("SELECT name FROM phase2_schema_migrations WHERE version=3").fetchone()
            caps = conn.execute(
                "SELECT capability_id,state FROM phase2_capability_registry WHERE wave=2 ORDER BY capability_id"
            ).fetchall()
            return {
                "status": "PASS" if server and migration and len(caps) == 3 and all(x["state"] == "ENABLED" for x in caps) else "FAIL",
                "postgres_version": server["server_version"] if server else None,
                "migration": migration["name"] if migration else None,
                "capabilities": [dict(x) for x in caps],
                "opening_root": self.opening.opening_decision_root,
            }
