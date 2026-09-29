import importlib.util, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_runtime import Store, PairingService
from packages.phase1_hardening import build_source_binding, bind_gate_evidence, verify_bound_gate_evidence

class PairingCapabilitySecurity(unittest.TestCase):
 def test_pairing_requires_workspace_bootstrap_capability(self):
  s=Store(); w=s.workspace('secure'); q=PairingService(s); secret=q.provision_workspace(w)
  with self.assertRaises(PermissionError):q.issue(w,'attacker-does-not-know-secret')
  code=q.issue(w,secret); token=q.enroll(code); self.assertEqual(q.workspace_for(token),w)
 def test_bootstrap_is_workspace_scoped(self):
  s=Store(); w1=s.workspace('1'); w2=s.workspace('2'); q=PairingService(s); a=q.provision_workspace(w1); b=q.provision_workspace(w2)
  with self.assertRaises(PermissionError):q.issue(w2,a)
  self.assertTrue(q.issue(w2,b))

class ResourceBindingSecurity(unittest.TestCase):
 def test_artifact_and_evidence_reject_cross_workspace_mission(self):
  s=Store(); w1=s.workspace('1');w2=s.workspace('2');p=s.project(w1,'p');c=s.conversation(w1,p);m=s.mission(w1,p,c,'x','k')
  with self.assertRaises(PermissionError):s.artifact(w2,m,b'x')
  with self.assertRaises(PermissionError):s.evidence(w2,m,'trace',{'x':1})
 def test_audit_chains_are_workspace_local_and_valid(self):
  s=Store(); w1=s.workspace('1'); w2=s.workspace('2'); s.project(w1,'a'); s.project(w2,'b'); s.project(w1,'c'); self.assertTrue(s.audit_valid())
  rows=list(s.db.execute('select workspace_id,prev_hash,event_hash from audit_events order by seq'))
  first={}
  for r in rows:
   if r['workspace_id'] not in first:first[r['workspace_id']]=r['prev_hash']
  self.assertEqual(set(first.values()),{'GENESIS'})

class EvidenceFreshnessTests(unittest.TestCase):
 def test_bound_evidence_invalidates_on_source_change(self):
  binding=build_source_binding(ROOT,'a'*64); receipt=bind_gate_evidence('AUTH',{'status':'PASS'},binding)
  self.assertTrue(verify_bound_gate_evidence(receipt,binding).fresh)
  changed=build_source_binding(ROOT,'b'*64)
  self.assertFalse(verify_bound_gate_evidence(receipt,changed).fresh)
 def test_tampered_evidence_root_rejected(self):
  binding=build_source_binding(ROOT,'a'*64); receipt=bind_gate_evidence('AUTH',{'status':'PASS'},binding); receipt['payload']={'status':'FAIL'}
  self.assertFalse(verify_bound_gate_evidence(receipt,binding).fresh)

class APISecurityRegression(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p=ROOT/'control-plane/api/app.py'; spec=importlib.util.spec_from_file_location('narms_api_hardened',p); cls.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.mod)
  from fastapi.testclient import TestClient
  cls.client=TestClient(cls.mod.app)
 def test_attacker_cannot_pair_with_workspace_id_only(self):
  r=self.client.post('/api/v1/workspaces',json={'name':'victim'}).json()
  bad=self.client.post('/api/v1/auth/pairing',json={'workspace_id':r['id'],'bootstrap_secret':'x'*24})
  self.assertEqual(bad.status_code,403)
 def test_client_cannot_inject_assistant_role(self):
  r=self.client.post('/api/v1/workspaces',json={'name':'roles'}).json(); code=self.client.post('/api/v1/auth/pairing',json={'workspace_id':r['id'],'bootstrap_secret':r['bootstrap_secret']}).json()['code'];tok=self.client.post('/api/v1/auth/enroll',json={'code':code}).json()['token'];h={'Authorization':'Bearer '+tok}
  p=self.client.post('/api/v1/projects',headers=h,json={'workspace_id':r['id'],'name':'p'}).json()['id'];c=self.client.post('/api/v1/chat',headers=h,json={'workspace_id':r['id'],'project_id':p}).json()['id']
  resp=self.client.post('/api/v1/chat/messages',headers=h,json={'workspace_id':r['id'],'conversation_id':c,'role':'assistant','body':'forged'})
  self.assertEqual(resp.status_code,422)
