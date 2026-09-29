from __future__ import annotations
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest
from packages.phase1_closure import issue_phase1_certificate_from_report
from packages.phase1_qualification import REQUIRED_GATES
from packages.phase1_unlock import Phase1TrustPolicy, verify_phase1_certificate, assert_phase2_unlocked


def report():
    return {'version':'1.6.0','report_root':'q'*64,'source_root':'s'*64,'gates':{g:'PASS' for g in REQUIRED_GATES},'blockers':{}}


def test_valid_trusted_certificate_unlocks_phase2():
    key=Ed25519PrivateKey.generate(); raw=key.private_bytes_raw().hex(); r=report()
    c=issue_phase1_certificate_from_report(r,raw); p=Phase1TrustPolicy(key.public_key().public_bytes_raw().hex())
    result=verify_phase1_certificate(c,r,p)
    assert result['phase2_allowed'] is True and result['reasons']==[]
    assert assert_phase2_unlocked(c,r,p)==result['unlock_root']


def test_attacker_self_signed_certificate_does_not_unlock():
    trusted=Ed25519PrivateKey.generate(); attacker=Ed25519PrivateKey.generate(); r=report()
    c=issue_phase1_certificate_from_report(r,attacker.private_bytes_raw().hex())
    result=verify_phase1_certificate(c,r,Phase1TrustPolicy(trusted.public_key().public_bytes_raw().hex()))
    assert result['phase2_allowed'] is False
    assert 'certificate_public_key_not_trusted' in result['reasons']


def test_tampered_report_breaks_binding():
    key=Ed25519PrivateKey.generate(); r=report(); c=issue_phase1_certificate_from_report(r,key.private_bytes_raw().hex())
    tampered=dict(r); tampered['source_root']='x'*64
    result=verify_phase1_certificate(c,tampered,Phase1TrustPolicy(key.public_key().public_bytes_raw().hex()))
    assert result['phase2_allowed'] is False
    assert 'certificate_body_binding_mismatch' in result['reasons']


def test_blocked_gate_cannot_unlock_even_with_old_valid_certificate():
    key=Ed25519PrivateKey.generate(); r=report(); c=issue_phase1_certificate_from_report(r,key.private_bytes_raw().hex())
    blocked=report(); blocked['gates']=dict(blocked['gates']); blocked['gates']['DB_MIGRATIONS']='BLOCKED'; blocked['blockers']={'DB_MIGRATIONS':'no real postgres'}
    result=verify_phase1_certificate(c,blocked,Phase1TrustPolicy(key.public_key().public_bytes_raw().hex()))
    assert result['phase2_allowed'] is False
    assert 'qualification_not_32_of_32' in result['reasons']
    assert 'qualification_blockers_present' in result['reasons']
