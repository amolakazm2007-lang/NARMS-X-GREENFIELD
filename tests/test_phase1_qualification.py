from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packages.phase1_qualification import REQUIRED_GATES, GateEvidence, QualificationReport, audit_migration_sql, issue_certificate, verify_certificate

def report(status='PASS'):
 e={g:GateEvidence(g,status,'0'*64,'x') for g in REQUIRED_GATES}
 gates={g:status for g in REQUIRED_GATES}
 return QualificationReport('PHASE_1','0.3.0',gates,e,{} if status=='PASS' else {'x':'x'},'1'*64,'2'*64)

def test_gate_count_is_exactly_32(): assert len(REQUIRED_GATES)==32

def test_migration_static_contract():
 sql=Path('migrations/0001_phase1.sql').read_text(); a=audit_migration_sql(sql); assert a['static_pass']; assert not a['missing_tables']; assert a['has_fencing_token']; assert a['has_jsonb']; assert a['has_timestamptz']

def test_certificate_is_fail_closed():
 with pytest.raises(RuntimeError): issue_certificate(report('BLOCKED'),Ed25519PrivateKey.generate())

def test_certificate_signs_and_detects_tamper():
 k=Ed25519PrivateKey.generate(); c=issue_certificate(report(),k); trusted=k.public_key().public_bytes_raw(); assert verify_certificate(c,trusted); c['body']=c['body'].replace('PHASE_1','PHASE_X'); assert not verify_certificate(c,trusted)

def test_self_signed_attacker_certificate_is_not_trusted():
 trusted=Ed25519PrivateKey.generate(); attacker=Ed25519PrivateKey.generate(); forged=issue_certificate(report(),attacker); assert not verify_certificate(forged,trusted.public_key().public_bytes_raw())
