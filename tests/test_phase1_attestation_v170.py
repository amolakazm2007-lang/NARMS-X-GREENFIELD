from __future__ import annotations
from copy import deepcopy
import pytest
from packages.phase1_attestation import ToolchainReceipt, build_closure_attestation, verify_closure_attestation
from packages.phase1_qualification import REQUIRED_GATES, sha256_obj


def report():
    r={'phase':'PHASE_1','version':'1.7.0','source_root':'a'*64,'gates':{g:'PASS' for g in REQUIRED_GATES},'evidence':{g:{'gate':g,'status':'PASS','receipt_root':sha256_obj({'g':g})} for g in REQUIRED_GATES},'blockers':{}}
    r['report_root']=sha256_obj(r)
    return r


def tools(): return ToolchainReceipt('3.11.9','v22.0.0','10.0.0','mypy 1.0','psql 16','postgres 16')

def test_attestation_binds_every_gate_and_toolchain():
    r=report();a=build_closure_attestation(r,tools(),workflow_identity='wf@sha')
    v=verify_closure_attestation(a,r,expected_workflow_identity='wf@sha')
    assert v['valid']
    tampered=deepcopy(r);tampered['evidence'][REQUIRED_GATES[0]]['receipt_root']='0'*64
    assert not verify_closure_attestation(a,tampered,expected_workflow_identity='wf@sha')['valid']

def test_toolchain_tamper_is_rejected():
    r=report();a=build_closure_attestation(r,tools(),workflow_identity='wf@sha')
    a['toolchain']['python']='9.9.9'
    v=verify_closure_attestation(a,r,expected_workflow_identity='wf@sha')
    assert not v['valid'] and 'attestation_toolchain_root_mismatch' in v['reasons']

def test_workflow_identity_is_bound():
    r=report();a=build_closure_attestation(r,tools(),workflow_identity='trusted@sha')
    v=verify_closure_attestation(a,r,expected_workflow_identity='other@sha')
    assert not v['valid'] and 'attestation_workflow_identity_mismatch' in v['reasons']

def test_blocked_report_cannot_be_attested():
    r=report();r['gates'][REQUIRED_GATES[0]]='BLOCKED';r['blockers']={REQUIRED_GATES[0]:'missing'}
    with pytest.raises(ValueError): build_closure_attestation(r,tools(),workflow_identity='wf@sha')

def test_attested_certificate_binds_closure_and_rejects_self_signed_attacker():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from packages.phase1_attestation import issue_attested_phase1_certificate, verify_attested_phase1_certificate
    r=report();a=build_closure_attestation(r,tools(),workflow_identity='wf@sha')
    trusted=Ed25519PrivateKey.generate(); trusted_hex=trusted.private_bytes_raw().hex(); trusted_pub=trusted.public_key().public_bytes_raw().hex()
    cert=issue_attested_phase1_certificate(r,a,trusted_hex)
    assert verify_attested_phase1_certificate(cert,r,a,trusted_pub)['phase2_allowed']
    attacker=Ed25519PrivateKey.generate(); forged=issue_attested_phase1_certificate(r,a,attacker.private_bytes_raw().hex())
    v=verify_attested_phase1_certificate(forged,r,a,trusted_pub)
    assert not v['phase2_allowed'] and 'certificate_public_key_not_trusted' in v['reasons']


def test_attested_certificate_dies_if_attestation_changes():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from packages.phase1_attestation import issue_attested_phase1_certificate, verify_attested_phase1_certificate
    r=report();a=build_closure_attestation(r,tools(),workflow_identity='wf@sha')
    key=Ed25519PrivateKey.generate(); cert=issue_attested_phase1_certificate(r,a,key.private_bytes_raw().hex())
    a2=deepcopy(a);a2['workflow_identity']='evil@sha'
    v=verify_attested_phase1_certificate(cert,r,a2,key.public_key().public_bytes_raw().hex())
    assert not v['phase2_allowed']
