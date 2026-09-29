import json
from pathlib import Path
from packages.phase2_constitution import Phase2Constitution,validate_transition,constitution_report
from packages.phase2_protocols import WorkerEnvelope,ToolEnvelope
from packages.phase2_artifact_graph import ArtifactNode,ArtifactGraph
from packages.phase2_scheduler import ResourceRequest,Quota,admit,placement_key
from packages.phase2_recovery import decide
from packages.phase2_opening import evaluate
ROOT=Path(__file__).resolve().parents[1]

def test_constitution_is_locked_and_deterministic():
 c=Phase2Constitution(); assert c.implementation_allowed is False; assert c.phase1_unlock_required; assert c.root==Phase2Constitution().root; assert constitution_report()==constitution_report()

def test_mission_transition_requires_evidence():
 ok,r=validate_transition('RUNNING','SUCCEEDED',{}); assert not ok and 'missing:evidence_root' in r
 ok,r=validate_transition('RUNNING','SUCCEEDED',{'evidence_root':'e','artifact_root':'a'}); assert ok and not r
 assert not validate_transition('CREATED','SUCCEEDED',{})[0]

def test_worker_protocol_fencing_and_identity_required():
 w=WorkerEnvelope('worker-v1','w','build.test','ws','m','j',0,4,'l','i','p','t',1000); assert w.validate()[0]; assert len(w.root)==64
 bad=WorkerEnvelope('worker-v1','w','build.test','ws','m','j',0,0,'l','i','p','t',1000); assert not bad.validate()[0]

def test_tool_protocol_requires_approval_for_side_effects():
 t=ToolEnvelope('tool-v1','git.push','1','ws','m','i','external_side_effect','a','p',None,'idem','trace'); assert not t.validate()[0]
 t=ToolEnvelope('tool-v1','git.push','1','ws','m','i','external_side_effect','a','p','approve','idem','trace'); assert t.validate()[0]

def test_artifact_graph_is_content_addressed_and_rejects_unknown_parent():
 a=ArtifactNode('a','a'*64,'source','j',(),('e',)); b=ArtifactNode('b','b'*64,'build','j2',('a'*64,),('e2',)); g=ArtifactGraph((b,a)); assert g.validate()[0]; assert g.root==ArtifactGraph((a,b)).root
 bad=ArtifactGraph((ArtifactNode('x','c'*64,'x','j',('d'*64,),()),)); assert not bad.validate()[0]

def test_scheduler_fail_closed_on_quota():
 q=Quota(4000,8192,1,1,1,3600); assert admit(ResourceRequest(1000,1024,0,0,0,60),q)[0]; assert not admit(ResourceRequest(1000,1024,2,0,0,60),q)[0]
 assert placement_key('w','m','c',ResourceRequest(1,2,0,0,0,3))==placement_key('w','m','c',ResourceRequest(1,2,0,0,0,3))

def test_recovery_is_idempotency_aware():
 assert decide(attempt=1,max_attempts=3,lease_expired=True,checkpoint_present=False,idempotent=True,side_effect_committed=False).action=='RETRY'
 assert decide(attempt=1,max_attempts=3,lease_expired=True,checkpoint_present=False,idempotent=False,side_effect_committed=False).action=='ESCALATE'
 assert decide(attempt=1,max_attempts=3,lease_expired=True,checkpoint_present=True,idempotent=True,side_effect_committed=True).action=='RECONCILE'

def test_phase2_opening_cannot_be_self_authorized():
 catalog=json.loads((ROOT/'docs/phase2/capability-catalog.json').read_text()); report={'gates':{},'blockers':{}}
 d=evaluate(certificate=None,report=report,attestation=None,trusted_public_key_hex=None,catalog=catalog)
 assert not d.allowed; assert 'phase1_trusted_certificate_missing' in d.reasons
