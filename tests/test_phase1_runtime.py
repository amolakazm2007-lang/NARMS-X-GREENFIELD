import importlib.util,sys,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_runtime import *
class Runtime(unittest.TestCase):
 def setUp(self):self.s=Store();self.w=self.s.workspace('w');self.p=self.s.project(self.w,'p');self.c=self.s.conversation(self.w,self.p)
 def test_idempotent_mission_job(self):
  a=self.s.mission(self.w,self.p,self.c,'x','mk');b=self.s.mission(self.w,self.p,self.c,'x','mk');self.assertEqual(a,b); j1=self.s.job(a,'jk');j2=self.s.job(a,'jk');self.assertEqual(j1,j2)
 def test_atomic_outbox(self):
  before=len(self.s.events_after());self.s.project(self.w,'atomic');after=self.s.events_after();self.assertEqual(len(after),before+1);self.assertEqual(after[-1]['event_type'],'project.created')
 def test_lease_recovery_fencing(self):
  m=self.s.mission(self.w,self.p,self.c,'x','m');j=self.s.job(m,'j');a=self.s.claim(j,'A',100,1);b=self.s.claim(j,'B',102,1);self.assertGreater(b,a);self.assertRaises(RuntimeError,self.s.commit_job,j,'A',a,b'x');self.assertTrue(self.s.commit_job(j,'B',b,b'x'))
 def test_inbox(self):
  x=[];self.assertTrue(self.s.inbox_once('c','e',lambda db:x.append(1)));self.assertFalse(self.s.inbox_once('c','e',lambda db:x.append(2)));self.assertEqual(x,[1])
 def test_replay(self):
  rows=self.s.events_after(0);cut=rows[-2]['seq'];self.assertTrue(all(r['seq']>cut for r in self.s.events_after(cut)))
 def test_pairing_replay_and_isolation(self):
  q=PairingService(self.s);bootstrap=q.provision_workspace(self.w);code=q.issue(self.w,bootstrap);token=q.enroll(code);self.assertEqual(q.workspace_for(token),self.w);self.assertRaises(RuntimeError,q.enroll,code);self.assertRaises(PermissionError,q.workspace_for,'bad')
 def test_artifact_evidence_audit(self):
  m=self.s.mission(self.w,self.p,self.c,'x','m');a=self.s.artifact(self.w,m,b'abc');self.assertEqual(a['sha256'],sha256(b'abc').hexdigest());self.s.evidence(self.w,m,'t',{'a':1});self.assertTrue(self.s.audit_valid())
 def test_approval_policy(self):self.assertTrue(approval_required('production_deploy','LOW'));self.assertFalse(approval_required('read','LOW'))
 def test_health(self):self.assertEqual(self.s.health()['status'],'PASS')
 def test_resume_authoritative_state(self):
  m=self.s.mission(self.w,self.p,self.c,'x','m');self.s.mission_state(m,'RUNNING');self.s.mission_state(m,'RECOVERING');self.assertEqual(self.s.db.execute('select state from missions where id=?',(m,)).fetchone()[0],'RECOVERING')
if __name__=='__main__':unittest.main()

class CrossWorkspaceSecurity(unittest.TestCase):
 def test_cross_workspace_resource_injection_is_rejected(self):
  s=Store(); w1=s.workspace('w1'); w2=s.workspace('w2'); p1=s.project(w1,'p1'); p2=s.project(w2,'p2'); c1=s.conversation(w1,p1)
  with self.assertRaises(PermissionError): s.conversation(w1,p2)
  with self.assertRaises(PermissionError): s.message(w2,c1,'user','x')
  with self.assertRaises(PermissionError): s.mission(w2,p2,c1,'x','same-key')
 def test_idempotency_is_scoped_not_global(self):
  s=Store(); w1=s.workspace('w1'); w2=s.workspace('w2'); p1=s.project(w1,'p1'); p2=s.project(w2,'p2'); c1=s.conversation(w1,p1); c2=s.conversation(w2,p2)
  m1=s.mission(w1,p1,c1,'a','same-key'); m2=s.mission(w2,p2,c2,'b','same-key'); self.assertNotEqual(m1,m2)
  j1=s.job(m1,'same-job'); j2=s.job(m2,'same-job'); self.assertNotEqual(j1,j2)
