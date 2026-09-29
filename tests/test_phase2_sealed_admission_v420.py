import json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packages.phase2_sealed import compile_sealed_skeletons,assert_non_executable
from packages.phase2_conformance import REQUIRED_CHECKS,issue_receipt,conformance_matrix
from packages.phase2_admission import evaluate_wave
from packages.phase2_cross_domain import DomainReceipt,qualify,REQUIRED_DOMAINS
from packages.phase2_authority import issue,verify
ROOT=Path(__file__).resolve().parents[1]
def catalog(): return json.loads((ROOT/'docs/phase2/capability-catalog.json').read_text())
def good_receipt(s):
 checks={x:True for x in REQUIRED_CHECKS}; ev={x:(x+'0'*64)[:64] for x in REQUIRED_CHECKS}
 return issue_receipt(s.capability_id,s.root,checks,ev,'e'*64)

def test_skeletons_are_complete_deterministic_and_non_executable():
 a=compile_sealed_skeletons(catalog()); b=compile_sealed_skeletons(catalog()); assert len(a)==16; assert [x.root for x in a]==[x.root for x in b]; assert assert_non_executable(a)==assert_non_executable(b); assert all(not x.executable for x in a)
def test_conformance_requires_every_evidence_family():
 s=compile_sealed_skeletons(catalog())[0]; r=good_receipt(s); assert r.passed
 checks={x:True for x in REQUIRED_CHECKS}; ev={x:'e'*64 for x in REQUIRED_CHECKS if x!='recovery'}; assert not issue_receipt(s.capability_id,s.root,checks,ev,'e'*64).passed
def test_conformance_matrix_rejects_duplicate_identity():
 s=compile_sealed_skeletons(catalog())[0]; r=good_receipt(s)
 try: conformance_matrix((r,r)); assert False
 except ValueError: pass
def test_wave_cannot_open_without_trusted_phase2_opening():
 ss=compile_sealed_skeletons(catalog()); rs=tuple(good_receipt(x) for x in ss if x.wave==1)
 d=evaluate_wave(wave=1,catalog=catalog(),opening_allowed=False,opening_root=None,receipts=rs); assert not d.allowed and 'trusted_phase2_opening_required' in d.reasons
def test_wave1_can_be_admitted_only_under_explicit_opening_decision():
 ss=compile_sealed_skeletons(catalog()); rs=tuple(good_receipt(x) for x in ss if x.wave==1)
 d=evaluate_wave(wave=1,catalog=catalog(),opening_allowed=True,opening_root='o'*64,receipts=rs); assert d.allowed; assert set(d.admitted)=={'mission.workspace','capability.registry'}
def test_wave3_refuses_missing_prior_dependency_admission():
 ss=compile_sealed_skeletons(catalog()); rs=tuple(good_receipt(x) for x in ss if x.wave==3)
 d=evaluate_wave(wave=3,catalog=catalog(),opening_allowed=True,opening_root='o'*64,receipts=rs,prior_admitted=()); assert not d.allowed; assert any(x.startswith('prior_dependency_not_admitted') for x in d.reasons)
def test_cross_domain_requires_all_domains_and_containment():
 rs=tuple(DomainReceipt(d,'c'*64,True,'e'*64,'f'*64) for d in REQUIRED_DOMAINS); assert qualify(rs).qualified
 bad=tuple(DomainReceipt(d,'c'*64,d!='gpu','e'*64,'f'*64) for d in REQUIRED_DOMAINS); q=qualify(bad); assert not q.qualified and 'isolation_failed:gpu' in q.reasons
def test_admission_certificate_is_bound_and_untrusted_key_fails():
 ss=compile_sealed_skeletons(catalog()); rs=tuple(good_receipt(x) for x in ss if x.wave==1); d=evaluate_wave(wave=1,catalog=catalog(),opening_allowed=True,opening_root='o'*64,receipts=rs)
 k=Ed25519PrivateKey.generate(); raw=k.private_bytes_raw(); pub=k.public_key().public_bytes_raw().hex(); cert=issue(d,raw.hex()); assert verify(cert,pub,d)['valid']
 attacker=Ed25519PrivateKey.generate(); assert not verify(cert,attacker.public_key().public_bytes_raw().hex(),d)['valid']
def test_cannot_issue_certificate_for_blocked_decision():
 d=evaluate_wave(wave=1,catalog=catalog(),opening_allowed=False,opening_root=None,receipts=())
 try: issue(d,Ed25519PrivateKey.generate().private_bytes_raw().hex()); assert False
 except RuntimeError: pass
