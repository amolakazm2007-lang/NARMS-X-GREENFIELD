from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

REQUIRED_GATES = (
    'MONOREPO_STRUCTURE','ARCHITECTURE_DOCTOR','DEPENDENCY_RULES','CONTRACT_VALIDATION',
    'TS_TYPECHECK','PYTHON_TYPECHECK','BACKEND_BUILD','FRONTEND_BUILD','AUTH','DEVICE_SESSION',
    'WORKSPACE_CREATE','PROJECT_CREATE','CHAT_CREATE','CHAT_STREAM','MISSION_CREATE',
    'MISSION_STATE_MACHINE','MISSION_RESUME','JOB_IDEMPOTENCY','LEASE_EXPIRY_RECOVERY',
    'FENCING_REJECTS_STALE_WORKER','OUTBOX_ATOMICITY','INBOX_DEDUP','EVENT_REPLAY','SSE_RECONNECT',
    'APPROVAL_POLICY','ARTIFACT_HASH','AUDIT_TRAIL','SYSTEM_HEALTH','NO_SECRET_LEAK',
    'CRITICAL_SECURITY_TESTS','PHASE_1_E2E','DB_MIGRATIONS',
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class EnvironmentCapability:
    name: str
    available: bool
    executable: str | None


@dataclass(frozen=True)
class GateEvidence:
    gate: str
    status: str
    evidence_root: str
    detail: str


@dataclass(frozen=True)
class QualificationReport:
    phase: str
    version: str
    gates: dict[str, str]
    evidence: dict[str, GateEvidence]
    blockers: dict[str, str]
    source_root: str
    report_root: str

    @property
    def all_pass(self) -> bool:
        return set(self.gates) == set(REQUIRED_GATES) and all(self.gates[g] == 'PASS' for g in REQUIRED_GATES)


def detect_environment() -> dict[str, EnvironmentCapability]:
    names = ('python','mypy','pyright','psql','postgres','pg_isready')
    return {name: EnvironmentCapability(name, bool(shutil.which(name)), shutil.which(name)) for name in names}


def audit_migration_sql(sql: str) -> dict[str, Any]:
    normalized = re.sub(r'--.*$', '', sql, flags=re.MULTILINE).strip()
    tables = re.findall(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-z_][a-z0-9_]*)', normalized, re.I)
    required_columns = {
        'workspaces': {'id','name','created_at'},
        'projects': {'id','workspace_id','name','created_at'},
        'device_sessions': {'id','workspace_id','token_hash','expires_at','created_at','revoked_at','replaced_by'},
        'workspace_bootstrap': {'workspace_id','secret_hash','created_at','generation','rotated_at'},
        'pairing_codes': {'code_hash','workspace_id','expires_at','consumed_at','bootstrap_generation'},
        'conversations': {'id','workspace_id','project_id','created_at'},
        'messages': {'id','conversation_id','role','body','created_at'},
        'missions': {'id','workspace_id','project_id','conversation_id','state','trace_id','idempotency_key','request','updated_at','created_at'},
        'jobs': {'id','mission_id','state','attempt','max_attempts','lease_owner','lease_expires_at','fencing_token','idempotency_key','input_root','output_root','heartbeat_at','created_at'},
        'outbox_events': {'seq','event_id','event_type','schema_version','aggregate_type','aggregate_id','workspace_id','correlation_id','causation_id','trace_id','payload','occurred_at','published_at','publish_attempts','last_publish_error'},
        'outbox_publication_receipts': {'consumer_id','event_id','acknowledged_at'},
        'inbox_receipts': {'consumer_id','event_id','processed_at'},
        'approvals': {'id','workspace_id','state','actor','action','risk','created_at'},
        'artifacts': {'id','workspace_id','mission_id','sha256','size_bytes','storage_uri','created_at'},
        'evidence_receipts': {'id','workspace_id','mission_id','trace_id','payload','sha256','created_at'},
        'audit_events': {'seq','id','workspace_id','actor','action','trace_id','payload','prev_hash','event_hash','created_at'},
    }
    missing_tables = sorted(set(required_columns) - set(tables))
    missing_columns: dict[str, list[str]] = {}
    for table, expected in required_columns.items():
        m = re.search(rf'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{table}\s*\((.*?)\);', normalized, re.I | re.S)
        if not m: continue
        body=m.group(1)
        found=set(re.findall(r'(?:^|,)\s*([a-z_][a-z0-9_]*)\s+', body, re.I))
        miss=sorted(expected-found)
        if miss: missing_columns[table]=miss
    required_fragments = {
        'mission_workspace_idempotency': 'UNIQUE(workspace_id,idempotency_key)',
        'job_mission_idempotency': 'UNIQUE(mission_id,idempotency_key)',
        'session_token_unique': 'token_hash text UNIQUE NOT NULL',
        'audit_hash_chain': 'prev_hash text NOT NULL',
        'outbox_ack_table': 'outbox_publication_receipts',
    }
    normalized_compact=re.sub(r'\s+',' ',normalized)
    missing_constraints=[name for name,frag in required_fragments.items() if frag.lower() not in normalized_compact.lower()]
    static_pass = (not missing_tables and not missing_columns and not missing_constraints and normalized.upper().startswith('BEGIN;') and normalized.upper().endswith('COMMIT;'))
    return {
        'begins_transaction': normalized.upper().startswith('BEGIN;'), 'commits_transaction': normalized.upper().endswith('COMMIT;'),
        'tables': sorted(set(tables)), 'missing_tables': missing_tables, 'missing_columns': missing_columns,
        'missing_constraints': missing_constraints, 'has_jsonb': 'jsonb' in normalized.lower(),
        'has_timestamptz': 'timestamptz' in normalized.lower(), 'has_fencing_token': 'fencing_token' in normalized.lower(),
        'static_pass': static_pass,
    }


def run_command(command: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    proc = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return proc.returncode, proc.stdout


def evidence(gate: str, status: str, detail: str, payload: Any) -> GateEvidence:
    return GateEvidence(gate, status, sha256_obj({'gate': gate, 'status': status, 'detail': detail, 'payload': payload}), detail)


def issue_certificate(report: QualificationReport, private_key: Ed25519PrivateKey) -> dict[str, str]:
    if not report.all_pass:
        raise RuntimeError('Phase 1 certificate forbidden: not all 32 required gates are PASS')
    body = {'phase': report.phase, 'version': report.version, 'qualification_root': report.report_root, 'source_root': report.source_root}
    body_bytes = canonical(body)
    signature = private_key.sign(body_bytes).hex()
    public_key = private_key.public_key().public_bytes_raw().hex()
    return {'body': body_bytes.decode('utf-8'), 'fingerprint': hashlib.sha256(body_bytes).hexdigest(), 'signature': signature, 'public_key': public_key}


def verify_certificate(certificate: dict[str, str], trusted_public_key: bytes | str) -> bool:
    # Trust is supplied out-of-band. The public key embedded in a certificate is metadata only
    # and is never accepted as its own trust anchor.
    try:
        trusted = bytes.fromhex(trusted_public_key) if isinstance(trusted_public_key, str) else trusted_public_key
        if certificate.get('public_key') and not secrets_compare_hex(certificate['public_key'], trusted.hex()):
            return False
        Ed25519PublicKey.from_public_bytes(trusted).verify(bytes.fromhex(certificate['signature']), certificate['body'].encode('utf-8'))
        return True
    except Exception:
        return False

def secrets_compare_hex(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.lower(), b.lower())


def audit_sqlite_runtime_schema(db: Any) -> dict[str, Any]:
    """Compare the live SQLite reference schema with the Phase-1 logical contract.

    This is deliberately structural: it does not claim PostgreSQL execution parity.
    """
    required = {
        'workspaces': {'id','name','created_at'},
        'projects': {'id','workspace_id','name','created_at'},
        'device_sessions': {'id','workspace_id','token_hash','expires_at','created_at','revoked_at','replaced_by'},
        'workspace_bootstrap': {'workspace_id','secret_hash','created_at','generation','rotated_at'},
        'pairing_codes': {'code_hash','workspace_id','expires_at','consumed_at','bootstrap_generation'},
        'conversations': {'id','workspace_id','project_id','created_at'},
        'messages': {'id','conversation_id','role','body','created_at'},
        'missions': {'id','workspace_id','project_id','conversation_id','state','trace_id','idempotency_key','request','updated_at','created_at'},
        'jobs': {'id','mission_id','state','attempt','max_attempts','lease_owner','lease_expires_at','fencing_token','idempotency_key','input_root','output_root','heartbeat_at','created_at'},
        'outbox_events': {'seq','event_id','event_type','schema_version','aggregate_type','aggregate_id','workspace_id','correlation_id','causation_id','trace_id','payload','occurred_at','published_at','publish_attempts','last_publish_error'},
        'outbox_publication_receipts': {'consumer_id','event_id','acknowledged_at'},
        'inbox_receipts': {'consumer_id','event_id','processed_at'},
        'approvals': {'id','workspace_id','state','actor','action','risk','created_at'},
        'artifacts': {'id','workspace_id','mission_id','sha256','size_bytes','storage_uri','created_at'},
        'evidence_receipts': {'id','workspace_id','mission_id','trace_id','payload','sha256','created_at'},
        'audit_events': {'seq','id','workspace_id','actor','action','trace_id','payload','prev_hash','event_hash','created_at'},
    }
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing_tables=sorted(set(required)-tables); missing_columns={}
    for table, cols in required.items():
        if table not in tables: continue
        found={r[1] for r in db.execute(f'PRAGMA table_info({table})')}
        miss=sorted(cols-found)
        if miss: missing_columns[table]=miss
    return {'missing_tables':missing_tables,'missing_columns':missing_columns,'static_pass':not missing_tables and not missing_columns}


def qualification_policy_root(required_gates: tuple[str, ...] = REQUIRED_GATES) -> str:
    return sha256_obj({'policy':'phase1-qualification','required_gates':list(required_gates),'certificate_semantics':'all-required-gates-pass','trust_states':['ACTIVE','RETIRED','REVOKED'],'issuance_state':'ACTIVE_ONLY','verification_states':['ACTIVE','RETIRED']})


def issue_policy_bound_certificate(report: QualificationReport, private_key: Ed25519PrivateKey, key_id: str, policy_root: str) -> dict[str, str]:
    if not report.all_pass:
        raise RuntimeError('Phase 1 certificate forbidden: not all 32 required gates are PASS')
    body={'phase':report.phase,'version':report.version,'qualification_root':report.report_root,'source_root':report.source_root,'authority_key_id':key_id,'qualification_policy_root':policy_root}
    body_bytes=canonical(body); public_key=private_key.public_key().public_bytes_raw()
    return {'body':body_bytes.decode(),'fingerprint':hashlib.sha256(body_bytes).hexdigest(),'signature':private_key.sign(body_bytes).hex(),'public_key':public_key.hex(),'authority_key_id':key_id,'qualification_policy_root':policy_root}

# v1.3 deep schema-contract qualification. This is stricter structural evidence;
# it still does NOT satisfy DB_MIGRATIONS without a real PostgreSQL execution.
REQUIRED_INDEXES = {
    'idx_outbox_workspace_seq': ('outbox_events', ('workspace_id','seq')),
    'idx_outbox_unpublished': ('outbox_events', ('seq',)),
    'idx_jobs_lease': ('jobs', ('state','lease_expires_at')),
    'idx_audit_workspace_seq': ('audit_events', ('workspace_id','seq')),
}
REQUIRED_FOREIGN_KEYS = {
    ('projects','workspace_id','workspaces','id'),
    ('device_sessions','workspace_id','workspaces','id'),
    ('pairing_codes','workspace_id','workspaces','id'),
    ('conversations','workspace_id','workspaces','id'),
    ('messages','conversation_id','conversations','id'),
    ('missions','workspace_id','workspaces','id'),
    ('jobs','mission_id','missions','id'),
    ('outbox_events','workspace_id','workspaces','id'),
    ('outbox_publication_receipts','event_id','outbox_events','event_id'),
}

def audit_sqlite_deep_schema(db: Any) -> dict[str, Any]:
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    fks=set()
    for table in tables:
        if table.startswith('sqlite_'): continue
        for r in db.execute(f'PRAGMA foreign_key_list({table})'):
            fks.add((table,r[3],r[2],r[4]))
    indexes={}
    for table in tables:
        if table.startswith('sqlite_'): continue
        for r in db.execute(f'PRAGMA index_list({table})'):
            name=r[1]
            if name.startswith('sqlite_'): continue
            cols=tuple(x[2] for x in db.execute(f'PRAGMA index_info({name})'))
            indexes[name]=(table,cols)
    # SQLite reference intentionally has fewer named indexes than PostgreSQL; require logical
    # access paths that exist explicitly in the reference contract.
    sqlite_required={'idx_outbox_workspace_seq','idx_outbox_unpublished','idx_jobs_lease','idx_audit_workspace_seq'}
    sql=' '.join((r[0] or '') for r in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))
    checks={
        'workspace_bootstrap_generation': bool(re.search(r'generation\s+INTEGER[^,)]*',sql,re.I)),
        'jobs_attempt_nonnegative_contract': 'attempt INTEGER NOT NULL' in sql,
        'jobs_max_attempts_contract': 'max_attempts INTEGER NOT NULL' in sql,
        'artifact_size_contract': 'size_bytes INTEGER NOT NULL' in sql,
    }
    return {
        'foreign_keys': sorted(fks),
        'missing_foreign_keys': sorted(REQUIRED_FOREIGN_KEYS-fks),
        'indexes': {k:[v[0],list(v[1])] for k,v in sorted(indexes.items())},
        'missing_indexes': sorted(sqlite_required-set(indexes)),
        'checks': checks,
        'pass': not (REQUIRED_FOREIGN_KEYS-fks) and not (sqlite_required-set(indexes)) and all(checks.values()),
    }

def audit_postgres_deep_contract(sql: str) -> dict[str, Any]:
    compact=re.sub(r'\s+',' ',re.sub(r'--.*$','',sql,flags=re.MULTILINE)).strip()
    fks=set()
    for table, body in re.findall(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-z_][a-z0-9_]*)\s*\((.*?)\);',compact,re.I|re.S):
        for col,target_table,target_col in re.findall(r'([a-z_][a-z0-9_]*)\s+[^,]*?REFERENCES\s+([a-z_][a-z0-9_]*)\s*\(([a-z_][a-z0-9_]*)\)',body,re.I):
            fks.add((table.lower(),col.lower(),target_table.lower(),target_col.lower()))
    indexes={}
    for name,table,cols in re.findall(r'CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+([a-z_][a-z0-9_]*)\s+ON\s+([a-z_][a-z0-9_]*)\s*\(([^)]*)\)',compact,re.I):
        indexes[name.lower()]=(table.lower(),tuple(c.strip().lower() for c in cols.split(',')))
    missing_indexes=[]
    for name,(table,cols) in REQUIRED_INDEXES.items():
        actual=indexes.get(name)
        if not actual or actual!=(table,cols): missing_indexes.append(name)
    checks={
        'bootstrap_generation':'CHECK(generation >= 1)' in compact,
        'job_attempt':'CHECK(attempt >= 0)' in compact,
        'job_max_attempts':'CHECK(max_attempts >= 1)' in compact,
        'artifact_size':'CHECK(size_bytes >= 0)' in compact,
        'message_role':"CHECK(role IN ('user','assistant','system','tool'))" in compact,
    }
    return {'foreign_keys':sorted(fks),'missing_foreign_keys':sorted(REQUIRED_FOREIGN_KEYS-fks),'indexes':{k:[v[0],list(v[1])] for k,v in sorted(indexes.items())},'missing_indexes':missing_indexes,'checks':checks,'pass':not (REQUIRED_FOREIGN_KEYS-fks) and not missing_indexes and all(checks.values())}
