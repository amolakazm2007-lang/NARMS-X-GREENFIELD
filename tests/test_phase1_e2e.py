import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_runtime import Store,PairingService
from packages.phase1_core import deterministic_reference_task
class E2E(unittest.TestCase):
 def test_mobile_to_recovery_artifact_reconnect(self):
  s=Store(); w=s.workspace('mobile'); pair=PairingService(s); bootstrap=pair.provision_workspace(w); code=pair.issue(w,bootstrap); token=pair.enroll(code); self.assertEqual(pair.workspace_for(token),w)
  p=s.project(w,'project'); c=s.conversation(w,p); s.message(w,c,'user','reference mission'); m=s.mission(w,p,c,'reference mission','e2e-mission'); s.mission_state(m,'RUNNING'); j=s.job(m,'e2e-job')
  token_a=s.claim(j,'worker-A',100,1)
  # simulated interruption: lease expires, mission recovers, newer worker claims
  s.mission_state(m,'RECOVERING'); token_b=s.claim(j,'worker-B',102,10); self.assertGreater(token_b,token_a)
  payload=deterministic_reference_task('NARMS')
  with self.assertRaises(RuntimeError):s.commit_job(j,'worker-A',token_a,payload)
  output=s.commit_job(j,'worker-B',token_b,payload); s.mission_state(m,'RUNNING'); s.mission_state(m,'COMPLETED')
  art=s.artifact(w,m,payload); ev=s.evidence(w,m,s.db.execute('select trace_id from missions where id=?',(m,)).fetchone()[0],{'job':j,'output_root':output,'artifact_root':art['sha256'],'stale_worker_rejected':True})
  cursor=s.events_after(0)[-2]['seq']; replay=s.events_after(cursor); self.assertTrue(replay)
  # reconnect is a new authentication lookup; durable mission remains authoritative
  self.assertEqual(pair.workspace_for(token),w); state=s.db.execute('select state from missions where id=?',(m,)).fetchone()[0]; self.assertEqual(state,'COMPLETED'); self.assertEqual(art['sha256'],output); self.assertTrue(ev['sha256']); self.assertTrue(s.audit_valid())
