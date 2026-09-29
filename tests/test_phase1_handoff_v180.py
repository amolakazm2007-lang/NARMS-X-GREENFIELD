import copy
import secrets
import pytest
from packages.phase1_handoff import ClosureChallenge, build_handoff_packet, verify_handoff_packet
from packages.phase1_attestation import ToolchainReceipt, build_closure_attestation
from packages.phase1_qualification import REQUIRED_GATES, sha256_obj


def report():
    r={'version':'1.8.0','source_root':'a'*64,'gates':{g:'PASS' for g in REQUIRED_GATES},'blockers':[], 'evidence':{g:{'gate':g,'ok':True} for g in REQUIRED_GATES}}
    core={k:v for k,v in r.items() if k!='report_root'}; r['report_root']=sha256_obj(core); return r

def fixtures():
    r=report(); t=ToolchainReceipt('3.11.9','v22','10','mypy 1.18','psql 16','postgres 16')
    a=build_closure_attestation(r,t,workflow_identity='phase1-closure.yml@v1.8.0')
    c=ClosureChallenge('1.8.0',r['source_root'],'phase1-closure.yml@v1.8.0',secrets.token_hex(32))
    return r,a,c

def test_valid_handoff():
    r,a,c=fixtures(); p=build_handoff_packet(r,a,c); assert verify_handoff_packet(p,r,a,c)['valid']

def test_tampered_packet_rejected():
    r,a,c=fixtures(); p=build_handoff_packet(r,a,c); p['qualification_root']='b'*64; assert not verify_handoff_packet(p,r,a,c)['valid']

def test_replayed_nonce_rejected_by_new_challenge():
    r,a,c=fixtures(); p=build_handoff_packet(r,a,c); c2=ClosureChallenge(c.version,c.source_root,c.workflow_identity,secrets.token_hex(32)); assert not verify_handoff_packet(p,r,a,c2)['valid']

def test_wrong_source_cannot_build():
    r,a,c=fixtures(); bad=ClosureChallenge(c.version,'b'*64,c.workflow_identity,c.nonce)
    with pytest.raises(RuntimeError): build_handoff_packet(r,a,bad)

def test_wrong_workflow_cannot_build():
    r,a,c=fixtures(); bad=ClosureChallenge(c.version,c.source_root,'other.yml@v1.8.0',c.nonce)
    with pytest.raises(RuntimeError): build_handoff_packet(r,a,bad)

def test_report_tamper_rejected():
    r,a,c=fixtures(); p=build_handoff_packet(r,a,c); rr=copy.deepcopy(r); rr['evidence'][REQUIRED_GATES[0]]={'gate':'tampered'}; assert not verify_handoff_packet(p,rr,a,c)['valid']

def test_challenge_requires_strong_nonce():
    with pytest.raises(ValueError): ClosureChallenge('1.8.0','a'*64,'wf','short')
