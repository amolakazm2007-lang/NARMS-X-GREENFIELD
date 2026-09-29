import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import pytest
from packages.phase1_runtime import Store,PairingService


def base():
 s=Store(); w=s.workspace('w'); p=s.project(w,'p'); c=s.conversation(w,p); m=s.mission(w,p,c,'x','m'); return s,w,p,c,m

def test_job_commit_rolls_back_if_outbox_crashes(monkeypatch):
 s,w,p,c,m=base(); j=s.job(m,'j'); token=s.claim(j,'A',100,30)
 def boom(*a,**k): raise RuntimeError('crash')
 monkeypatch.setattr(s,'event',boom)
 with pytest.raises(RuntimeError): s.commit_job(j,'A',token,b'payload')
 row=s.db.execute('select state,output_root from jobs where id=?',(j,)).fetchone(); assert row['state']=='RUNNING' and row['output_root'] is None

def test_inbox_receipt_rolls_back_if_consumer_crashes():
 s=Store()
 def boom(db): raise RuntimeError('consumer crash')
 with pytest.raises(RuntimeError): s.inbox_once('consumer','event',boom)
 assert s.db.execute('select count(*) from inbox_receipts').fetchone()[0]==0

def test_session_rotation_rolls_back_if_insert_fails(monkeypatch):
 s=Store(); w=s.workspace('w'); q=PairingService(s); b=q.provision_workspace(w); old=q.enroll(q.issue(w,b)); original=s.db.execute
 # Force failure through trigger so transaction rollback is exercised below application code.
 s.db.execute("CREATE TRIGGER fail_new_session BEFORE INSERT ON device_sessions BEGIN SELECT RAISE(ABORT,'boom'); END;")
 with pytest.raises(Exception): q.rotate_session(old)
 s.db.execute('DROP TRIGGER fail_new_session')
 assert q.workspace_for(old)==w

def test_bootstrap_rotation_rolls_back_on_pairing_invalidation_failure():
 s=Store(); w=s.workspace('w'); q=PairingService(s); b=q.provision_workspace(w); code=q.issue(w,b)
 s.db.execute("CREATE TRIGGER fail_pair_update BEFORE UPDATE ON pairing_codes BEGIN SELECT RAISE(ABORT,'boom'); END;")
 with pytest.raises(Exception): q.rotate_bootstrap(w,b)
 s.db.execute('DROP TRIGGER fail_pair_update')
 # Original bootstrap and outstanding code remain authoritative after rollback.
 assert q.enroll(code)

def test_enrollment_rolls_back_consumption_if_session_insert_fails():
 s=Store(); w=s.workspace('w'); q=PairingService(s); b=q.provision_workspace(w); code=q.issue(w,b)
 s.db.execute("CREATE TRIGGER fail_enroll BEFORE INSERT ON device_sessions BEGIN SELECT RAISE(ABORT,'boom'); END;")
 with pytest.raises(Exception): q.enroll(code)
 s.db.execute('DROP TRIGGER fail_enroll')
 # Code was not burned by the failed atomic enrollment.
 assert q.enroll(code)
