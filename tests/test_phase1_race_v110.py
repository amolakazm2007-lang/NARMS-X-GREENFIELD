import json, tempfile, threading, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packages.phase1_runtime import Store, PairingService
from packages.phase1_qualification import audit_sqlite_runtime_schema, audit_migration_sql, qualification_policy_root, issue_policy_bound_certificate, QualificationReport, GateEvidence, REQUIRED_GATES
from packages.phase1_trust import QualificationTrustStore, TrustKey


def seeded_store(path=':memory:'):
    s=Store(path); w=s.workspace('w'); p=s.project(w,'p'); c=s.conversation(w,p); m=s.mission(w,p,c,'x','m'); j=s.job(m,'j'); return s,w,p,c,m,j

def test_concurrent_lease_race_has_one_winner():
    with tempfile.TemporaryDirectory() as d:
        path=str(Path(d)/'race.db'); s,w,p,c,m,j=seeded_store(path); s.db.close()
        barrier=threading.Barrier(3); results=[]; lock=threading.Lock()
        def worker(name):
            st=Store(path); barrier.wait()
            try: out=('ok',name,st.claim(j,name,100,30))
            except Exception as e: out=('err',name,type(e).__name__)
            with lock: results.append(out)
            st.db.close()
        ts=[threading.Thread(target=worker,args=(x,)) for x in ('A','B')]
        [t.start() for t in ts]; barrier.wait(); [t.join() for t in ts]
        assert sum(r[0]=='ok' for r in results)==1
        check=Store(path); row=check.db.execute('select fencing_token,attempt from jobs where id=?',(j,)).fetchone(); assert row['fencing_token']==1 and row['attempt']==1

def test_session_rotation_race_only_one_successor():
    s=Store(); w=s.workspace('w'); q=PairingService(s); b=q.provision_workspace(w); token=q.enroll(q.issue(w,b)); barrier=threading.Barrier(3); results=[]; lock=threading.Lock()
    def rotate():
        barrier.wait()
        try: out=('ok',q.rotate_session(token))
        except Exception as e: out=('err',type(e).__name__)
        with lock: results.append(out)
    ts=[threading.Thread(target=rotate) for _ in range(2)]; [t.start() for t in ts]; barrier.wait(); [t.join() for t in ts]
    assert sum(r[0]=='ok' for r in results)==1
    active=s.db.execute('select count(*) from device_sessions where workspace_id=? and revoked_at is null',(w,)).fetchone()[0]; assert active==1

def test_pairing_code_enroll_race_is_single_use():
    s=Store(); w=s.workspace('w'); q=PairingService(s); b=q.provision_workspace(w); code=q.issue(w,b); barrier=threading.Barrier(3); results=[]; lock=threading.Lock()
    def enroll():
        barrier.wait()
        try: out=('ok',q.enroll(code))
        except Exception as e: out=('err',type(e).__name__)
        with lock: results.append(out)
    ts=[threading.Thread(target=enroll) for _ in range(2)]; [t.start() for t in ts]; barrier.wait(); [t.join() for t in ts]
    assert sum(r[0]=='ok' for r in results)==1
    assert s.db.execute('select count(*) from device_sessions where workspace_id=?',(w,)).fetchone()[0]==1

def test_runtime_and_postgres_contract_have_same_required_columns():
    s=Store(); live=audit_sqlite_runtime_schema(s.db); assert live['static_pass']
    sql=(Path(__file__).parents[1]/'migrations/0001_phase1.sql').read_text(); pg=audit_migration_sql(sql); assert pg['static_pass']
    assert not live['missing_tables'] and not live['missing_columns'] and not pg['missing_tables'] and not pg['missing_columns']

def test_sse_last_event_id_reconnect_and_workspace_isolation(monkeypatch):
    import importlib
    appmod=importlib.import_module('control-plane.api.app')
    appmod.store=Store(); appmod.pairing=PairingService(appmod.store)
    w=appmod.store.workspace('w'); b=appmod.pairing.provision_workspace(w); token=appmod.pairing.enroll(appmod.pairing.issue(w,b)); p=appmod.store.project(w,'p'); rows=appmod.store.events_after(); cursor=rows[-2]['seq']
    client=TestClient(appmod.app); r=client.get('/api/v1/events',headers={'Authorization':'Bearer '+token,'Last-Event-ID':str(cursor)})
    assert r.status_code==200; ids=[int(x.split(':',1)[1]) for x in r.text.splitlines() if x.startswith('id:')]; assert ids and all(x>cursor for x in ids) and ids==sorted(set(ids))
    bad=client.get('/api/v1/events',headers={'Authorization':'Bearer '+token,'Last-Event-ID':'oops'}); assert bad.status_code==400

def _report():
    ev={g:GateEvidence(g,'PASS','a'*64,'ok') for g in REQUIRED_GATES}; return QualificationReport('PHASE_1','1.1.0',{g:'PASS' for g in REQUIRED_GATES},ev,{},'b'*64,'c'*64)

def test_policy_bound_certificate_binds_key_and_policy():
    key=Ed25519PrivateKey.generate(); pub=key.public_key().public_bytes_raw(); kid=QualificationTrustStore.key_id(pub); policy=qualification_policy_root(); cert=issue_policy_bound_certificate(_report(),key,kid,policy); body=json.loads(cert['body']); assert body['authority_key_id']==kid and body['qualification_policy_root']==policy
    store=QualificationTrustStore([TrustKey(kid,pub,'ACTIVE')]); assert store.verify(kid,cert['body'].encode(),bytes.fromhex(cert['signature']))
    assert cert['qualification_policy_root']==policy
