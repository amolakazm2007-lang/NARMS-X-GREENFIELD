from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from packages.phase2_constitution import validate_transition

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPENING = ROOT / "evidence/phase2-opening-v1/opening-decision.json"
DEFAULT_MANIFEST = ROOT / "contracts/phase2-wave1.runtime.json"
UP_MIGRATION = ROOT / "migrations/0002_phase2_wave1.sql"
DOWN_MIGRATION = ROOT / "migrations/0002_phase2_wave1.down.sql"

WAVE1_CAPABILITIES = ("mission.workspace", "capability.registry")
CAPABILITY_TRANSITIONS: dict[str, set[str]] = {
    "DECLARED": {"QUALIFIED", "DISABLED"},
    "QUALIFIED": {"ENABLED", "QUARANTINED", "DISABLED"},
    "ENABLED": {"DEGRADED", "QUARANTINED", "DISABLED"},
    "DEGRADED": {"ENABLED", "QUARANTINED", "DISABLED"},
    "QUARANTINED": {"QUALIFIED", "DISABLED"},
    "DISABLED": set(),
}


class Wave1Error(RuntimeError):
    pass


class OpeningDenied(Wave1Error):
    pass


class ConcurrencyConflict(Wave1Error):
    pass


class DependencyBlocked(Wave1Error):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _hex64(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class OpeningReceipt:
    opening_decision_root: str
    unlock_root: str
    qualification_root: str
    source_root: str
    closure_attestation_root: str
    certificate_fingerprint: str


def load_opening(path: Path = DEFAULT_OPENING) -> OpeningReceipt:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        raise OpeningDenied(f"opening evidence unavailable: {exc}") from exc
    decision = payload.get("opening_decision")
    reasons: list[str] = []
    if payload.get("scope") != "phase2-opening-evidence-v1":
        reasons.append("opening_scope_invalid")
    if payload.get("status") != "PASS":
        reasons.append("opening_status_not_pass")
    if not isinstance(decision, dict) or decision.get("allowed") is not True:
        reasons.append("opening_not_allowed")
    if isinstance(decision, dict) and decision.get("reasons"):
        reasons.append("opening_has_reasons")
    fields = {
        "opening_decision_root": payload.get("opening_decision_root"),
        "unlock_root": decision.get("unlock_root") if isinstance(decision, dict) else None,
        "qualification_root": payload.get("qualification_root"),
        "source_root": payload.get("source_root"),
        "closure_attestation_root": payload.get("closure_attestation_root"),
        "certificate_fingerprint": payload.get("certificate_fingerprint"),
    }
    for name, value in fields.items():
        if not _hex64(value):
            reasons.append(f"{name}_invalid")
    if isinstance(decision, dict):
        calculated = root(
            {
                "allowed": decision.get("allowed"),
                "reasons": decision.get("reasons"),
                "unlock_root": decision.get("unlock_root"),
                "constitution_root": decision.get("constitution_root"),
                "catalog_root": decision.get("catalog_root"),
            }
        )
        if calculated != payload.get("opening_decision_root"):
            reasons.append("opening_decision_root_mismatch")
    if reasons:
        raise OpeningDenied(",".join(sorted(set(reasons))))
    return OpeningReceipt(**fields)


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if payload.get("scope") != "phase2-wave1-runtime-manifest-v1":
        raise Wave1Error("wave1 manifest scope invalid")
    if payload.get("wave") != 1:
        raise Wave1Error("wave1 manifest wave invalid")
    ids = tuple(str(x.get("capability_id")) for x in payload.get("capabilities", []))
    if ids != WAVE1_CAPABILITIES:
        raise Wave1Error(f"wave1 manifest capability order/identity invalid: {ids}")
    return payload


class PostgresWave1Runtime:
    def __init__(
        self,
        dsn: str,
        *,
        opening_path: Path = DEFAULT_OPENING,
        manifest_path: Path = DEFAULT_MANIFEST,
    ):
        if not dsn:
            raise Wave1Error("PostgreSQL DSN is required")
        self.dsn = dsn
        self.opening = load_opening(opening_path)
        self.manifest = load_manifest(manifest_path)
        if self.manifest.get("opening_decision_root") != self.opening.opening_decision_root:
            raise OpeningDenied("runtime manifest is not bound to the trusted opening decision")

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def migrate(self) -> None:
        with self._connect() as conn:
            conn.execute(UP_MIGRATION.read_text())

    def rollback(self) -> None:
        with self._connect() as conn:
            conn.execute(DOWN_MIGRATION.read_text())

    def _audit(self, cur: Any, workspace_id: str, actor: str, action: str, trace_id: str, payload: Mapping[str, Any]) -> str:
        row = cur.execute(
            "SELECT event_hash FROM audit_events WHERE workspace_id=%s ORDER BY seq DESC LIMIT 1",
            (workspace_id,),
        ).fetchone()
        prev = str(row["event_hash"]) if row else "GENESIS"
        body = {
            "workspace_id": workspace_id,
            "actor": actor,
            "action": action,
            "trace_id": trace_id,
            "payload": dict(payload),
            "prev_hash": prev,
        }
        event_hash = root(body)
        cur.execute(
            "INSERT INTO audit_events(id,workspace_id,actor,action,trace_id,payload,prev_hash,event_hash,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,now())",
            (str(uuid4()), workspace_id, actor, action, trace_id, json.dumps(dict(payload)), prev, event_hash),
        )
        return event_hash

    def _event(
        self,
        cur: Any,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        workspace_id: str,
        trace_id: str,
        payload: Mapping[str, Any],
    ) -> str:
        event_id = str(uuid4())
        cur.execute(
            "INSERT INTO outbox_events(event_id,event_type,schema_version,aggregate_type,aggregate_id,workspace_id,"
            "correlation_id,causation_id,trace_id,payload,occurred_at) "
            "VALUES(%s,%s,'2',%s,%s,%s,%s,NULL,%s,%s::jsonb,now())",
            (
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                workspace_id,
                trace_id,
                trace_id,
                json.dumps(dict(payload)),
            ),
        )
        return event_id

    def activate_workspace(self, workspace_id: str, *, actor: str = "system", trace_id: str | None = None) -> dict[str, Any]:
        trace_id = trace_id or str(uuid4())
        with self._connect() as conn:
            with conn.transaction():
                cur = conn.cursor()
                if not cur.execute("SELECT 1 FROM workspaces WHERE id=%s", (workspace_id,)).fetchone():
                    raise KeyError(workspace_id)
                existing = cur.execute(
                    "SELECT * FROM phase2_workspace_runtime WHERE workspace_id=%s FOR UPDATE",
                    (workspace_id,),
                ).fetchone()
                if existing and existing["opening_root"] != self.opening.opening_decision_root:
                    raise OpeningDenied("workspace is bound to a different Phase-2 opening")
                if not existing:
                    cur.execute(
                        "INSERT INTO phase2_workspace_runtime(workspace_id,opening_root,state,revision) VALUES(%s,%s,'ACTIVE',1)",
                        (workspace_id, self.opening.opening_decision_root),
                    )
                    self._event(
                        cur,
                        event_type="phase2.workspace.activated",
                        aggregate_type="workspace",
                        aggregate_id=workspace_id,
                        workspace_id=workspace_id,
                        trace_id=trace_id,
                        payload={"opening_root": self.opening.opening_decision_root, "revision": 1},
                    )
                    self._audit(
                        cur,
                        workspace_id,
                        actor,
                        "phase2.workspace.activate",
                        trace_id,
                        {"opening_root": self.opening.opening_decision_root},
                    )
                row = cur.execute(
                    "SELECT * FROM phase2_workspace_runtime WHERE workspace_id=%s",
                    (workspace_id,),
                ).fetchone()
                return dict(row)

    def attach_mission(
        self,
        mission_id: str,
        *,
        expected_workspace_id: str | None = None,
        actor: str = "system",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        trace_id = trace_id or str(uuid4())
        with self._connect() as conn:
            with conn.transaction():
                cur = conn.cursor()
                mission = cur.execute("SELECT id,workspace_id FROM missions WHERE id=%s", (mission_id,)).fetchone()
                if not mission:
                    raise KeyError(mission_id)
                workspace_id = str(mission["workspace_id"])
                if expected_workspace_id is not None and expected_workspace_id != workspace_id:
                    raise PermissionError("mission workspace isolation")
                active = cur.execute(
                    "SELECT * FROM phase2_workspace_runtime WHERE workspace_id=%s AND state='ACTIVE'",
                    (workspace_id,),
                ).fetchone()
                if not active:
                    raise Wave1Error("workspace must be active in Phase-2 before mission attachment")
                existing = cur.execute(
                    "SELECT * FROM phase2_mission_workspace WHERE mission_id=%s FOR UPDATE",
                    (mission_id,),
                ).fetchone()
                if not existing:
                    cur.execute(
                        "INSERT INTO phase2_mission_workspace(mission_id,workspace_id,state,opening_root,revision) "
                        "VALUES(%s,%s,'CREATED',%s,1)",
                        (mission_id, workspace_id, self.opening.opening_decision_root),
                    )
                    evidence = {"mission_id": mission_id, "state": "CREATED"}
                    cur.execute(
                        "INSERT INTO phase2_mission_history(mission_id,workspace_id,event_type,from_state,to_state,evidence,"
                        "evidence_root,opening_root,revision) VALUES(%s,%s,'ATTACHED',NULL,'CREATED',%s::jsonb,%s,%s,1)",
                        (
                            mission_id,
                            workspace_id,
                            json.dumps(evidence),
                            root(evidence),
                            self.opening.opening_decision_root,
                        ),
                    )
                    self._event(
                        cur,
                        event_type="phase2.mission.attached",
                        aggregate_type="mission",
                        aggregate_id=mission_id,
                        workspace_id=workspace_id,
                        trace_id=trace_id,
                        payload=evidence,
                    )
                    self._audit(cur, workspace_id, actor, "phase2.mission.attach", trace_id, evidence)
                row = cur.execute(
                    "SELECT * FROM phase2_mission_workspace WHERE mission_id=%s",
                    (mission_id,),
                ).fetchone()
                if row["opening_root"] != self.opening.opening_decision_root:
                    raise OpeningDenied("mission is bound to a different Phase-2 opening")
                return dict(row)

    def transition_mission(
        self,
        mission_id: str,
        target: str,
        evidence: Mapping[str, Any],
        *,
        expected_revision: int,
        actor: str = "system",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        trace_id = trace_id or str(uuid4())
        with self._connect() as conn:
            with conn.transaction():
                cur = conn.cursor()
                row = cur.execute(
                    "SELECT * FROM phase2_mission_workspace WHERE mission_id=%s FOR UPDATE",
                    (mission_id,),
                ).fetchone()
                if not row:
                    raise KeyError(mission_id)
                if int(row["revision"]) != expected_revision:
                    raise ConcurrencyConflict(
                        f"mission revision changed: expected={expected_revision} actual={row['revision']}"
                    )
                valid, missing = validate_transition(str(row["state"]), target, dict(evidence))
                if not valid:
                    raise Wave1Error("mission transition denied: " + ",".join(missing))
                revision = expected_revision + 1
                columns = {
                    "plan_root": evidence.get("plan_root"),
                    "policy_root": evidence.get("policy_root"),
                    "checkpoint_root": evidence.get("checkpoint"),
                    "artifact_root": evidence.get("artifact_root"),
                    "evidence_root": evidence.get("evidence_root"),
                }
                cur.execute(
                    "UPDATE phase2_mission_workspace SET state=%s,plan_root=COALESCE(%s,plan_root),"
                    "policy_root=COALESCE(%s,policy_root),checkpoint_root=COALESCE(%s,checkpoint_root),"
                    "artifact_root=COALESCE(%s,artifact_root),evidence_root=COALESCE(%s,evidence_root),"
                    "revision=%s,updated_at=now() WHERE mission_id=%s",
                    (
                        target,
                        columns["plan_root"],
                        columns["policy_root"],
                        columns["checkpoint_root"],
                        columns["artifact_root"],
                        columns["evidence_root"],
                        revision,
                        mission_id,
                    ),
                )
                evidence_body = dict(evidence)
                evidence_body.update({"from": row["state"], "to": target, "revision": revision})
                cur.execute(
                    "INSERT INTO phase2_mission_history(mission_id,workspace_id,event_type,from_state,to_state,evidence,"
                    "evidence_root,opening_root,revision) VALUES(%s,%s,'STATE_TRANSITION',%s,%s,%s::jsonb,%s,%s,%s)",
                    (
                        mission_id,
                        row["workspace_id"],
                        row["state"],
                        target,
                        json.dumps(evidence_body),
                        root(evidence_body),
                        self.opening.opening_decision_root,
                        revision,
                    ),
                )
                self._event(
                    cur,
                    event_type="phase2.mission.state",
                    aggregate_type="mission",
                    aggregate_id=mission_id,
                    workspace_id=str(row["workspace_id"]),
                    trace_id=trace_id,
                    payload=evidence_body,
                )
                self._audit(
                    cur,
                    str(row["workspace_id"]),
                    actor,
                    "phase2.mission.transition",
                    trace_id,
                    evidence_body,
                )
                updated = cur.execute(
                    "SELECT * FROM phase2_mission_workspace WHERE mission_id=%s",
                    (mission_id,),
                ).fetchone()
                return dict(updated)

    def _capability_row(self, cur: Any, capability_id: str) -> dict[str, Any] | None:
        row = cur.execute(
            "SELECT * FROM phase2_capability_registry WHERE capability_id=%s",
            (capability_id,),
        ).fetchone()
        return dict(row) if row else None

    def bootstrap_capabilities(self) -> list[dict[str, Any]]:
        capabilities = self.manifest["capabilities"]
        with self._connect() as conn:
            with conn.transaction():
                cur = conn.cursor()
                for cap in capabilities:
                    contract = {
                        "capability_id": cap["capability_id"],
                        "depends_on": sorted(cap.get("depends_on", [])),
                        "boundaries": sorted(cap.get("boundaries", [])),
                        "resource_class": cap["resource_class"],
                    }
                    contract_root = root(contract)
                    existing = self._capability_row(cur, cap["capability_id"])
                    if existing and existing["contract_root"] != contract_root:
                        raise Wave1Error(f"capability contract drift: {cap['capability_id']}")
                    if existing and existing["opening_root"] != self.opening.opening_decision_root:
                        raise OpeningDenied(f"capability opening drift: {cap['capability_id']}")
                    if not existing:
                        cur.execute(
                            "INSERT INTO phase2_capability_registry(capability_id,owner,wave,runtime_kind,risk_class,"
                            "resource_class,state,implementation_version,contract_root,opening_root,metadata,revision) "
                            "VALUES(%s,%s,1,%s,%s,%s,'QUALIFIED',%s,%s,%s,%s::jsonb,1)",
                            (
                                cap["capability_id"],
                                cap["owner"],
                                cap["runtime_kind"],
                                cap["risk_class"],
                                cap["resource_class"],
                                cap["implementation_version"],
                                contract_root,
                                self.opening.opening_decision_root,
                                json.dumps({"depends_on": cap.get("depends_on", []), "boundaries": cap["boundaries"]}),
                            ),
                        )
                        ev = {"state": "QUALIFIED", "contract_root": contract_root, "revision": 1}
                        cur.execute(
                            "INSERT INTO phase2_capability_history(capability_id,event_type,from_state,to_state,"
                            "implementation_version,contract_root,evidence_root,opening_root,revision) "
                            "VALUES(%s,'BOOTSTRAP',NULL,'QUALIFIED',%s,%s,%s,%s,1)",
                            (
                                cap["capability_id"],
                                cap["implementation_version"],
                                contract_root,
                                root(ev),
                                self.opening.opening_decision_root,
                            ),
                        )
                return [
                    dict(x)
                    for x in cur.execute(
                        "SELECT * FROM phase2_capability_registry WHERE wave=1 ORDER BY capability_id"
                    ).fetchall()
                ]

    def transition_capability(
        self,
        capability_id: str,
        target: str,
        *,
        expected_revision: int,
        evidence: Mapping[str, Any],
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction():
                cur = conn.cursor()
                row = cur.execute(
                    "SELECT * FROM phase2_capability_registry WHERE capability_id=%s FOR UPDATE",
                    (capability_id,),
                ).fetchone()
                if not row:
                    raise KeyError(capability_id)
                source = str(row["state"])
                if target not in CAPABILITY_TRANSITIONS.get(source, set()):
                    raise Wave1Error(f"capability transition denied: {source}->{target}")
                if int(row["revision"]) != expected_revision:
                    raise ConcurrencyConflict(
                        f"capability revision changed: expected={expected_revision} actual={row['revision']}"
                    )
                if target == "ENABLED":
                    meta = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"])
                    for dep in meta.get("depends_on", []):
                        dep_row = cur.execute(
                            "SELECT state FROM phase2_capability_registry WHERE capability_id=%s",
                            (dep,),
                        ).fetchone()
                        if not dep_row or dep_row["state"] != "ENABLED":
                            raise DependencyBlocked(f"dependency not enabled: {dep}")
                revision = expected_revision + 1
                cur.execute(
                    "UPDATE phase2_capability_registry SET state=%s,revision=%s,updated_at=now() WHERE capability_id=%s",
                    (target, revision, capability_id),
                )
                ev = dict(evidence)
                ev.update({"from": source, "to": target, "revision": revision})
                cur.execute(
                    "INSERT INTO phase2_capability_history(capability_id,event_type,from_state,to_state,"
                    "implementation_version,contract_root,evidence_root,opening_root,revision) "
                    "VALUES(%s,'STATE_TRANSITION',%s,%s,%s,%s,%s,%s,%s)",
                    (
                        capability_id,
                        source,
                        target,
                        row["implementation_version"],
                        row["contract_root"],
                        root(ev),
                        self.opening.opening_decision_root,
                        revision,
                    ),
                )
                updated = cur.execute(
                    "SELECT * FROM phase2_capability_registry WHERE capability_id=%s",
                    (capability_id,),
                ).fetchone()
                return dict(updated)

    def enable_wave1(self) -> list[dict[str, Any]]:
        rows = {x["capability_id"]: x for x in self.bootstrap_capabilities()}
        for capability_id in WAVE1_CAPABILITIES:
            row = rows[capability_id]
            if row["state"] == "QUALIFIED":
                row = self.transition_capability(
                    capability_id,
                    "ENABLED",
                    expected_revision=int(row["revision"]),
                    evidence={"reason": "wave1-runtime-qualified"},
                )
            rows[capability_id] = row
        return [rows[x] for x in WAVE1_CAPABILITIES]

    def health(self) -> dict[str, Any]:
        with self._connect() as conn:
            version = conn.execute("SHOW server_version").fetchone()
            caps = conn.execute(
                "SELECT capability_id,state,revision FROM phase2_capability_registry WHERE wave=1 ORDER BY capability_id"
            ).fetchall()
            schema = conn.execute(
                "SELECT version,name FROM phase2_schema_migrations WHERE version=2"
            ).fetchone()
        return {
            "status": "PASS" if schema else "FAIL",
            "postgres_server": str(version["server_version"]) if version else None,
            "opening_decision_root": self.opening.opening_decision_root,
            "schema_migration": dict(schema) if schema else None,
            "capabilities": [dict(x) for x in caps],
        }
