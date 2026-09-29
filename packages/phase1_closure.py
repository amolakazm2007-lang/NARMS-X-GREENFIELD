from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from packages.phase1_qualification import REQUIRED_GATES, QualificationReport, issue_certificate, sha256_obj


@dataclass(frozen=True)
class ToolReceipt:
    tool: str
    executable: str
    version: str
    command_root: str
    output_root: str
    returncode: int


@dataclass(frozen=True)
class PostgresReceipt:
    dsn_fingerprint: str
    server_version: str
    apply_root: str
    reapply_root: str
    introspection_root: str
    schema_validation_root: str
    rollback_root: str
    post_rollback_root: str
    final_reapply_root: str
    table_count: int
    index_count: int
    pass_: bool


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 180) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return p.returncode, p.stdout


def _root(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def python_typecheck(root: Path) -> ToolReceipt:
    mypy = shutil.which('mypy')
    if not mypy:
        raise RuntimeError('real Python typechecker unavailable: install mypy')
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(f'real closure requires Python 3.11 exactly; running {sys.version_info.major}.{sys.version_info.minor}')
    cmd = [mypy, '--python-version', '3.11', 'packages', 'control-plane', 'scripts', 'tests']
    tool = 'mypy'
    vcmd = [mypy, '--version']
    vrc, version = _run(vcmd, root)
    if vrc != 0:
        raise RuntimeError(f'{tool} version probe failed')
    rc, out = _run(cmd, root)
    return ToolReceipt(tool, cmd[0], version.strip(), sha256_obj(cmd), _root(out), rc)


def _psql(root: Path, dsn: str, sql: str) -> tuple[int, str]:
    psql = shutil.which('psql')
    if not psql:
        raise RuntimeError('psql unavailable')
    env = os.environ.copy()
    env['PGOPTIONS'] = '-c statement_timeout=60000 -c lock_timeout=10000'
    return _run([psql, dsn, '-X', '-v', 'ON_ERROR_STOP=1', '-At', '-c', sql], root, env=env)


def postgres_migration_qualification(root: Path, dsn: str) -> PostgresReceipt:
    if not dsn:
        raise RuntimeError('NARMS_PHASE1_POSTGRES_DSN is required')
    # The raw DSN is never persisted in evidence.
    dsn_fp = hashlib.sha256(dsn.encode()).hexdigest()
    up = (root/'migrations/0001_phase1.sql').read_text()
    down = (root/'migrations/0001_phase1.down.sql').read_text()
    rc, client_version = _run([shutil.which('psql') or 'psql', '--version'], root)
    if rc or not re.search(r'\b16(?:\.|\b)', client_version):
        raise RuntimeError('real closure requires psql major version 16')
    rc, version = _psql(root, dsn, 'SHOW server_version;')
    if rc: raise RuntimeError('PostgreSQL server probe failed')
    if not re.match(r'^16(?:\.|$)', version.strip()):
        raise RuntimeError(f'real closure requires PostgreSQL server major version 16; got {version.strip()}')
    rc, a = _psql(root, dsn, up)
    if rc: raise RuntimeError('migration apply failed')
    rc, b = _psql(root, dsn, up)
    if rc: raise RuntimeError('migration idempotent reapply failed')
    introspection_sql = """
SELECT 'T|'||table_name FROM information_schema.tables
 WHERE table_schema='public' AND table_name IN
 ('workspaces','projects','device_sessions','workspace_bootstrap','pairing_codes','conversations','messages','missions','jobs','outbox_events','outbox_publication_receipts','inbox_receipts','approvals','artifacts','evidence_receipts','audit_events')
UNION ALL
SELECT 'I|'||indexname FROM pg_indexes WHERE schemaname='public'
 AND indexname IN ('idx_outbox_workspace_seq','idx_outbox_unpublished','idx_jobs_lease','idx_audit_workspace_seq')
ORDER BY 1;
"""
    rc, intro = _psql(root, dsn, introspection_sql)
    if rc: raise RuntimeError('schema introspection failed')
    rows=[x for x in intro.splitlines() if x]
    tables=[x for x in rows if x.startswith('T|')]; indexes=[x for x in rows if x.startswith('I|')]
    if len(tables)!=16 or len(indexes)!=4:
        raise RuntimeError(f'PostgreSQL schema mismatch tables={len(tables)} indexes={len(indexes)}')
    # Real schema validation: verify the live database exposes every required logical column.
    expected_columns = {
        'workspaces': {'id','name','created_at'}, 'projects': {'id','workspace_id','name','created_at'},
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
    rc, colout = _psql(root, dsn, "SELECT table_name||'|'||column_name FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position;")
    if rc: raise RuntimeError('live PostgreSQL column validation failed')
    live: dict[str,set[str]] = {}
    for line in colout.splitlines():
        if '|' not in line: continue
        table, column = line.split('|',1); live.setdefault(table,set()).add(column)
    missing = {t: sorted(cols-live.get(t,set())) for t,cols in expected_columns.items() if cols-live.get(t,set())}
    if missing: raise RuntimeError(f'live PostgreSQL schema columns mismatch: {missing}')
    schema_validation_root = _root(colout)
    rc, d = _psql(root, dsn, down)
    if rc: raise RuntimeError('migration rollback failed')
    rc, post = _psql(root, dsn, "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='workspaces';")
    if rc or post.strip()!='0': raise RuntimeError('rollback left Phase-1 tables behind')
    rc, e = _psql(root, dsn, up)
    if rc: raise RuntimeError('migration final reapply failed')
    return PostgresReceipt(dsn_fp, version.strip(), _root(a), _root(b), _root(intro), schema_validation_root, _root(d), _root(post), _root(e), len(tables), len(indexes), True)


def closure_environment() -> dict[str, Any]:
    return {
        'python_version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
        'python_311_exact': sys.version_info[:2] == (3, 11),
        'mypy': shutil.which('mypy'),
        'psql': shutil.which('psql'),
        'postgres_dsn_present': bool(os.getenv('NARMS_PHASE1_POSTGRES_DSN')),
    }


def issue_phase1_certificate_from_report(report: dict[str, Any], private_key_hex: str) -> dict[str, Any]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    gates = report.get('gates', {})
    if set(gates) != set(REQUIRED_GATES) or any(gates.get(g) != 'PASS' for g in REQUIRED_GATES):
        raise RuntimeError('certificate forbidden: qualification is not 32/32 PASS')
    if report.get('blockers'):
        raise RuntimeError('certificate forbidden: blockers remain')
    key_bytes = bytes.fromhex(private_key_hex)
    if len(key_bytes) != 32:
        raise ValueError('Ed25519 private key must be 32 raw bytes encoded as hex')
    body = {
        'phase': 'PHASE_1',
        'version': report['version'],
        'qualification_root': report['report_root'],
        'source_root': report['source_root'],
        'scope': 'phase1-complete-phase2-may-open',
    }
    raw = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    key = Ed25519PrivateKey.from_private_bytes(key_bytes)
    return {
        'body': body,
        'fingerprint': hashlib.sha256(raw).hexdigest(),
        'signature': key.sign(raw).hex(),
        'public_key': key.public_key().public_bytes_raw().hex(),
    }
