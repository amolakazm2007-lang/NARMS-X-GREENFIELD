from pathlib import Path
import copy
import pytest

from packages.phase1_integrity import build_source_snapshot, verify_source_snapshot, verify_evidence_graph, build_promotion_request
from packages.phase1_handoff import ClosureChallenge, build_handoff_packet
from packages.phase1_attestation import ToolchainReceipt, build_closure_attestation
from packages.phase1_qualification import REQUIRED_GATES, sha256_obj


def full_report():
    ev={g:{'gate':g,'status':'PASS','evidence_root':sha256_obj({'g':g}),'detail':'ok'} for g in REQUIRED_GATES}
    r={'phase':'PHASE_1','version':'2.0.0','gates':{g:'PASS' for g in REQUIRED_GATES},'evidence':ev,'blockers':{},'source_root':'a'*64}
    body=dict(r); body.pop('report_root',None); r['report_root']=sha256_obj(body)
    return r


def attested_graph():
    r=full_report(); t=ToolchainReceipt('3.11','22','10','mypy 1','psql 16','postgres 16')
    a=build_closure_attestation(r,t,workflow_identity='phase1-closure.yml@v2.0.0')
    c=ClosureChallenge('2.0.0','a'*64,'phase1-closure.yml@v2.0.0','n'*32)
    p=build_handoff_packet(r,a,c)
    return r,a,c,p


def test_source_snapshot_detects_tamper(tmp_path: Path):
    (tmp_path/'a.txt').write_text('alpha')
    (tmp_path/'b.txt').write_text('beta')
    s=build_source_snapshot(tmp_path)
    assert verify_source_snapshot(tmp_path,s)['valid']
    (tmp_path/'a.txt').write_text('ALPHA')
    v=verify_source_snapshot(tmp_path,s)
    assert not v['valid'] and v['changed']==['a.txt']


def test_snapshot_excludes_evidence_and_manifest(tmp_path: Path):
    (tmp_path/'src.py').write_text('x=1')
    (tmp_path/'evidence').mkdir(); (tmp_path/'evidence'/'run.json').write_text('{}')
    (tmp_path/'MANIFEST.sha256').write_text('mutable packaging manifest')
    s1=build_source_snapshot(tmp_path)
    (tmp_path/'evidence'/'run.json').write_text('{"changed":true}')
    (tmp_path/'MANIFEST.sha256').write_text('changed')
    s2=build_source_snapshot(tmp_path)
    assert s1.root==s2.root


def test_evidence_graph_accepts_only_connected_roots():
    r,a,c,p=attested_graph()
    v=verify_evidence_graph(r,a,p,c)
    assert v['valid']
    bad=copy.deepcopy(p); bad['qualification_root']='b'*64
    v2=verify_evidence_graph(r,a,bad,c)
    assert not v2['valid']


def test_evidence_graph_rejects_gate_evidence_status_drift():
    r,a,c,p=attested_graph()
    r2=copy.deepcopy(r); r2['evidence'][REQUIRED_GATES[0]]['status']='BLOCKED'
    v=verify_evidence_graph(r2,a,p,c)
    assert not v['valid']


def test_promotion_request_is_not_unlock(tmp_path: Path):
    (tmp_path/'x').write_text('x')
    s=build_source_snapshot(tmp_path)
    r,a,c,p=attested_graph(); g=verify_evidence_graph(r,a,p,c)
    req=build_promotion_request(version='2.0.0',snapshot=s,evidence_graph=g,trust_policy_root='c'*64)
    assert req.scope=='phase1-external-promotion-request-v1'
    assert not hasattr(req,'phase2_allowed')
    assert len(req.root)==64


def test_promotion_request_rejects_invalid_graph(tmp_path: Path):
    (tmp_path/'x').write_text('x'); s=build_source_snapshot(tmp_path)
    with pytest.raises(RuntimeError):
        build_promotion_request(version='2.0.0',snapshot=s,evidence_graph={'valid':False},trust_policy_root='c'*64)
