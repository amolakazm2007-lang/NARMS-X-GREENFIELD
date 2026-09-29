import unittest,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from packages.phase1_core import *
class T(unittest.TestCase):
 def test_pairing_one_time(self):
  p=Pairing(); c=p.issue(); t=p.enroll(c); self.assertTrue(p.valid(t)); self.assertRaises(RuntimeError,p.enroll,c)
 def test_mission_machine(self):
  m=Mission('m','w','t'); m.move(MissionState.READY); m.move(MissionState.RUNNING); m.move(MissionState.COMPLETED); self.assertEqual(m.state,MissionState.COMPLETED)
 def test_stale_worker_rejected_after_recovery(self):
  j=Job('j','m','k'); n=datetime.now(timezone.utc); old=j.claim('a',n,1); new=j.claim('b',n+timedelta(seconds=2),1); self.assertGreater(new,old); self.assertRaises(RuntimeError,j.commit,old,b'x'); self.assertEqual(j.commit(new,b'x'),sha256(b'x').hexdigest())
 def test_inbox_dedup(self):
  i=Inbox(); x=[]; self.assertTrue(i.apply_once('c','e',lambda:x.append(1))); self.assertFalse(i.apply_once('c','e',lambda:x.append(2))); self.assertEqual(x,[1])
 def test_artifact_hash(self): self.assertEqual(artifact(b'abc')['sha256'],sha256(b'abc').hexdigest())
 def test_reference_worker_deterministic(self): self.assertEqual(deterministic_reference_task('abc'),b'cba')
if __name__=='__main__': unittest.main()
