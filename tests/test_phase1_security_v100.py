import sqlite3
import pytest
from packages.phase1_runtime import Store, PairingService
from packages.phase1_security import FixedWindowLimiter, RateLimitPolicy, RequestBudget
from packages.phase1_qualification import audit_migration_sql

def setup():
    s=Store(); w=s.workspace('w'); p=s.project(w,'p'); c=s.conversation(w,p); return s,w,p,c

def test_session_rotation_revokes_old_token():
    s,w,_,_=setup(); q=PairingService(s); b=q.provision_workspace(w); old=q.enroll(q.issue(w,b)); new=q.rotate_session(old)
    with pytest.raises(PermissionError): q.workspace_for(old)
    assert q.workspace_for(new)==w

def test_session_explicit_revocation():
    s,w,_,_=setup(); q=PairingService(s); b=q.provision_workspace(w); token=q.enroll(q.issue(w,b)); assert q.revoke_session(token)
    with pytest.raises(PermissionError): q.workspace_for(token)

def test_bootstrap_rotation_invalidates_old_secret_and_codes():
    s,w,_,_=setup(); q=PairingService(s); old=q.provision_workspace(w); code=q.issue(w,old); new=q.rotate_bootstrap(w,old)
    with pytest.raises(PermissionError): q.issue(w,old)
    with pytest.raises(RuntimeError): q.enroll(code)
    assert q.workspace_for(q.enroll(q.issue(w,new)))==w

def test_pairing_rate_limit_is_fail_closed():
    s,w,_,_=setup(); q=PairingService(s); b=q.provision_workspace(w)
    for _ in range(5): q.issue(w,b)
    with pytest.raises(RuntimeError,match='rate limit'): q.issue(w,b)

def test_reference_rate_limit_window_reset():
    l=FixedWindowLimiter(RateLimitPolicy(2,10)); assert l.allow('x',1); assert l.allow('x',2); assert not l.allow('x',3); assert l.allow('x',11)

def test_request_budget():
    b=RequestBudget(max_body_bytes=3,max_text_chars=2); b.validate_bytes(b'abc'); b.validate_text('ab')
    with pytest.raises(ValueError): b.validate_bytes(b'abcd')
    with pytest.raises(ValueError): b.validate_text('abc')

def test_outbox_requires_explicit_ack_to_mark_published():
    s,w,p,c=setup(); s.mission(w,p,c,'x','m'); row=s.pending_outbox()[-1]; assert row['published_at'] is None
    s.record_publish_attempt(row['event_id'],'temporary'); after=[x for x in s.pending_outbox() if x['event_id']==row['event_id']][0]; assert after['publish_attempts']==1
    s.acknowledge_publication(row['event_id'],'bus-A'); assert all(x['event_id']!=row['event_id'] for x in s.pending_outbox())
    s.acknowledge_publication(row['event_id'],'bus-A') # idempotent acknowledgement

def test_audit_tamper_is_detected():
    s,w,p,c=setup(); s.mission(w,p,c,'x','m'); assert s.audit_valid()
    s.db.execute("UPDATE audit_events SET payload='{}' WHERE workspace_id=? AND seq=(SELECT MAX(seq) FROM audit_events WHERE workspace_id=?)",(w,w))
    assert not s.audit_valid()

def test_static_migration_audit_detects_column_drift():
    sql=open('migrations/0001_phase1.sql').read(); assert audit_migration_sql(sql)['static_pass']
    broken=sql.replace('conversation_id uuid REFERENCES conversations(id),','')
    a=audit_migration_sql(broken); assert not a['static_pass']; assert 'conversation_id' in a['missing_columns']['missions']

def test_project_transaction_rolls_back_if_outbox_write_crashes(monkeypatch):
    s=Store(); w=s.workspace('w')
    def boom(*args,**kwargs): raise RuntimeError('simulated outbox crash')
    monkeypatch.setattr(s,'event',boom)
    with pytest.raises(RuntimeError): s.project(w,'must-rollback')
    assert s.db.execute("SELECT COUNT(*) FROM projects WHERE workspace_id=? AND name='must-rollback'",(w,)).fetchone()[0]==0

def test_mission_transaction_rolls_back_if_audit_crashes(monkeypatch):
    s,w,p,c=setup()
    def boom(*args,**kwargs): raise RuntimeError('simulated audit crash')
    monkeypatch.setattr(s,'audit',boom)
    with pytest.raises(RuntimeError): s.mission(w,p,c,'x','rollback-key')
    assert s.db.execute("SELECT COUNT(*) FROM missions WHERE workspace_id=? AND idempotency_key='rollback-key'",(w,)).fetchone()[0]==0
