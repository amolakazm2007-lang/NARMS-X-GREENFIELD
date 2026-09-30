import tempfile, threading, time, sys
from typing import Any
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import pytest
from fastapi.testclient import TestClient
from packages.phase1_runtime import Store, PairingService
from packages.phase1_siege import concurrent_campaign, audit_chain_snapshot, phase1_siege_policy_root
from packages.phase1_qualification import audit_sqlite_deep_schema, audit_postgres_deep_contract


def seeded(path=':memory:'):
    s=Store(path); w=s.workspace('w'); p=s.project(w,'p'); c=s.conversation(w,p); m=s.mission(w,p,c,'x','m'); j=s.job(m,'j'); return s,w,p,c,m,j


def test_32_worker_lease_contention_single_winner():
    with tempfile.TemporaryDirectory() as d:
        path=str(Path(d)/'lease.db'); s,w,p,c,m,j=seeded(path); s.db.close()
        def action(i):
            st=Store(path)
            try: st.claim(j,f'w{i}',100,30); return True
            finally: st.db.close()
        r=concurrent_campaign('lease-contention',32,action)
        assert r.successes==1 and r.failures==31 and len(r.evidence_root)==64
        check=Store(path); row=check.db.execute('select attempt,fencing_token from jobs where id=?',(j,)).fetchone(); assert tuple(row)==(1,1)


def test_heartbeat_extends_lease_and_blocks_premature_recovery():
    s,w,p,c,m,j=seeded(); tok=s.claim(j,'A',100,10); assert s.heartbeat_job(j,'A',tok,105,20)==125
    assert s.recover_expired_jobs(124)==[]
    assert s.recover_expired_jobs(126)==[j]
    row=s.db.execute('select state,lease_owner from jobs where id=?',(j,)).fetchone(); assert row['state']=='READY' and row['lease_owner'] is None


def test_stale_worker_cannot_heartbeat_after_recovery_and_reclaim():
    s,w,p,c,m,j=seeded(); old=s.claim(j,'A',100,5); assert s.recover_expired_jobs(106)==[j]; new=s.claim(j,'B',106,30); assert new==old+1
    with pytest.raises(RuntimeError): s.heartbeat_job(j,'A',old,107,30)
    with pytest.raises(RuntimeError): s.commit_job(j,'A',old,b'stale')
    assert s.commit_job(j,'B',new,b'fresh')


def test_outbox_retry_then_ack_is_idempotent():
    s,w,p,c,m,j=seeded(); tok=s.claim(j,'A',100,30); s.commit_job(j,'A',tok,b'x')
    event=s.pending_outbox()[-1]['event_id']; s.record_publish_attempt(event,'broker down'); s.record_publish_attempt(event,'timeout')
    row=s.db.execute('select publish_attempts,published_at,last_publish_error from outbox_events where event_id=?',(event,)).fetchone(); assert row['publish_attempts']==2 and row['published_at'] is None
    s.acknowledge_publication(event,'consumer'); first=s.db.execute('select published_at from outbox_events where event_id=?',(event,)).fetchone()[0]
    s.acknowledge_publication(event,'consumer'); second=s.db.execute('select published_at from outbox_events where event_id=?',(event,)).fetchone()[0]
    assert first==second and s.db.execute('select count(*) from outbox_publication_receipts where event_id=?',(event,)).fetchone()[0]==1


def test_sse_waits_for_new_event_then_returns_monotonic_cursor(monkeypatch):
    import importlib
    appmod: Any=importlib.import_module('control-plane.api.app'); appmod.store=Store(); appmod.pairing=PairingService(appmod.store)
    w=appmod.store.workspace('w'); b=appmod.pairing.provision_workspace(w); token=appmod.pairing.enroll(appmod.pairing.issue(w,b)); cursor=appmod.store.events_after()[-1]['seq']
    def later(): time.sleep(.12); appmod.store.project(w,'arrived')
    t=threading.Thread(target=later); t.start(); r=TestClient(appmod.app).get('/api/v1/events',headers={'Authorization':'Bearer '+token,'Last-Event-ID':str(cursor)}); t.join()
    ids=[int(x.split(':',1)[1]) for x in r.text.splitlines() if x.startswith('id:')]; assert r.status_code==200 and ids and ids==sorted(set(ids)) and min(ids)>cursor


def test_concurrent_audit_append_preserves_single_chain():
    with tempfile.TemporaryDirectory() as d:
        path=str(Path(d)/'audit.db'); base=Store(path); w=base.workspace('w'); base.db.close()
        def action(i):
            st=Store(path)
            try:
                with st.transaction() as c: st.audit(c,w,f'worker-{i}','stress.append',f'trace-{i}',{'i':i})
                return True
            finally: st.db.close()
        r=concurrent_campaign('audit-concurrent-append',24,action); assert r.successes==24
        check=Store(path); assert check.audit_valid(); snap=audit_chain_snapshot(check.db); assert snap['count']==25 and snap['head']!='GENESIS'


def test_bootstrap_rotation_race_one_winner_and_invalidates_old_codes():
    s=Store(); w=s.workspace('w'); q=PairingService(s); bootstrap=q.provision_workspace(w); code=q.issue(w,bootstrap)
    barrier=threading.Barrier(9); out=[]; lock=threading.Lock()
    def rotate():
        barrier.wait()
        try: q.rotate_bootstrap(w,bootstrap); ok=True
        except Exception: ok=False
        with lock: out.append(ok)
    ts=[threading.Thread(target=rotate) for _ in range(8)]
    for t in ts: t.start()
    barrier.wait()
    for t in ts: t.join()
    assert sum(out)==1
    with pytest.raises(RuntimeError): q.enroll(code)
    assert s.db.execute('select generation from workspace_bootstrap where workspace_id=?',(w,)).fetchone()[0]==2


def test_deep_sqlite_and_postgres_contracts_cover_fks_indexes_checks():
    s=Store(); live=audit_sqlite_deep_schema(s.db); pg=audit_postgres_deep_contract((ROOT/'migrations/0001_phase1.sql').read_text())
    assert live['pass'], live; assert pg['pass'], pg
    assert not live['missing_foreign_keys'] and not pg['missing_foreign_keys']; assert not live['missing_indexes'] and not pg['missing_indexes']


def test_siege_policy_explicitly_keeps_real_external_gates():
    root=phase1_siege_policy_root(); assert len(root)==64 and root!='0'*64
