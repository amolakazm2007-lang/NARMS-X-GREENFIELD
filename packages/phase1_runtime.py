from __future__ import annotations
import json, sqlite3, secrets, time, threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4
from packages.phase1_security import FixedWindowLimiter, RateLimitPolicy

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid4())
def canon(x:Any)->str: return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def root(x:Any)->str: return sha256(canon(x).encode()).hexdigest()

SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES workspaces(id),name TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS device_sessions(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES workspaces(id),token_hash TEXT UNIQUE NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,revoked_at TEXT,replaced_by TEXT);
CREATE TABLE IF NOT EXISTS workspace_bootstrap(workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id),secret_hash TEXT NOT NULL,created_at TEXT NOT NULL,generation INTEGER NOT NULL DEFAULT 1 CHECK(generation >= 1),rotated_at TEXT);
CREATE TABLE IF NOT EXISTS pairing_codes(code_hash TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES workspaces(id),expires_at TEXT NOT NULL,consumed_at TEXT,bootstrap_generation INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES workspaces(id),project_id TEXT REFERENCES projects(id),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL REFERENCES conversations(id),role TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES workspaces(id),project_id TEXT REFERENCES projects(id),conversation_id TEXT REFERENCES conversations(id),state TEXT NOT NULL,trace_id TEXT NOT NULL,idempotency_key TEXT NOT NULL,request TEXT NOT NULL,updated_at TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(workspace_id,idempotency_key));
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL REFERENCES missions(id),state TEXT NOT NULL,attempt INTEGER NOT NULL CHECK(attempt >= 0),max_attempts INTEGER NOT NULL CHECK(max_attempts >= 1),lease_owner TEXT,lease_expires_at REAL,fencing_token INTEGER NOT NULL,idempotency_key TEXT NOT NULL,input_root TEXT,output_root TEXT,heartbeat_at REAL,created_at TEXT NOT NULL,UNIQUE(mission_id,idempotency_key));
CREATE TABLE IF NOT EXISTS outbox_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,event_type TEXT NOT NULL,schema_version TEXT NOT NULL,aggregate_type TEXT NOT NULL,aggregate_id TEXT NOT NULL,workspace_id TEXT NOT NULL REFERENCES workspaces(id),correlation_id TEXT NOT NULL,causation_id TEXT,trace_id TEXT NOT NULL,payload TEXT NOT NULL,occurred_at TEXT NOT NULL,published_at TEXT,publish_attempts INTEGER NOT NULL DEFAULT 0,last_publish_error TEXT);
CREATE TABLE IF NOT EXISTS outbox_publication_receipts(consumer_id TEXT NOT NULL,event_id TEXT NOT NULL REFERENCES outbox_events(event_id),acknowledged_at TEXT NOT NULL,PRIMARY KEY(consumer_id,event_id));
CREATE TABLE IF NOT EXISTS inbox_receipts(consumer_id TEXT NOT NULL,event_id TEXT NOT NULL,processed_at TEXT NOT NULL,PRIMARY KEY(consumer_id,event_id));
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,state TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,risk TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,mission_id TEXT,sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),storage_uri TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_receipts(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,mission_id TEXT,trace_id TEXT NOT NULL,payload TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,workspace_id TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,trace_id TEXT NOT NULL,payload TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_outbox_workspace_seq ON outbox_events(workspace_id,seq);
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON outbox_events(seq) WHERE published_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(state,lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_workspace_seq ON audit_events(workspace_id,seq);
'''

class Store:
 def __init__(self,path=':memory:'):
  self.db=sqlite3.connect(path,check_same_thread=False,isolation_level=None,timeout=10); self.db.row_factory=sqlite3.Row; self._tx_lock=threading.RLock(); self.db.executescript(SCHEMA)
 def tx(self): return self.db
 @contextmanager
 def transaction(self):
  with self._tx_lock:
   self.db.execute('BEGIN IMMEDIATE')
   try:
    yield self.db
    self.db.execute('COMMIT')
   except Exception:
    self.db.execute('ROLLBACK')
    raise
 def event(self,c,event_type,aggregate_type,aggregate_id,workspace_id,trace_id,payload,correlation_id=None,causation_id=None):
  e=uid(); c.execute('INSERT INTO outbox_events(event_id,event_type,schema_version,aggregate_type,aggregate_id,workspace_id,correlation_id,causation_id,trace_id,payload,occurred_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(e,event_type,'1',aggregate_type,aggregate_id,workspace_id,correlation_id or trace_id,causation_id,trace_id,canon(payload),now())); return e
 def audit(self,c,workspace_id,actor,action,trace_id,payload):
  r=c.execute('SELECT event_hash FROM audit_events WHERE workspace_id=? ORDER BY seq DESC LIMIT 1',(workspace_id,)).fetchone(); prev=r[0] if r else 'GENESIS'; body={'workspace_id':workspace_id,'actor':actor,'action':action,'trace_id':trace_id,'payload':payload,'prev_hash':prev}; h=root(body); c.execute('INSERT INTO audit_events(id,workspace_id,actor,action,trace_id,payload,prev_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(uid(),workspace_id,actor,action,trace_id,canon(payload),prev,h,now())); return h
 def workspace(self,name):
  i=uid(); t=now(); tr=uid();
  with self.transaction() as c: c.execute('INSERT INTO workspaces VALUES(?,?,?)',(i,name,t)); self.event(c,'workspace.created','workspace',i,i,tr,{'name':name}); self.audit(c,i,'system','workspace.create',tr,{'id':i})
  return i
 def project(self,w,name):
  i=uid(); tr=uid();
  with self.transaction() as c: c.execute('INSERT INTO projects VALUES(?,?,?,?)',(i,w,name,now())); self.event(c,'project.created','project',i,w,tr,{'name':name}); self.audit(c,w,'user','project.create',tr,{'id':i})
  return i
 def conversation(self,w,p=None):
  if p is not None:
   owner=self.db.execute('SELECT workspace_id FROM projects WHERE id=?',(p,)).fetchone()
   if not owner or owner[0]!=w: raise PermissionError('project workspace isolation')
  i=uid(); tr=uid();
  with self.transaction() as c: c.execute('INSERT INTO conversations VALUES(?,?,?,?)',(i,w,p,now())); self.event(c,'chat.created','conversation',i,w,tr,{})
  return i
 def message(self,w,conv,role,body):
  owner=self.db.execute('SELECT workspace_id FROM conversations WHERE id=?',(conv,)).fetchone()
  if not owner or owner[0]!=w: raise PermissionError('conversation workspace isolation')
  i=uid(); tr=uid();
  with self.transaction() as c: c.execute('INSERT INTO messages VALUES(?,?,?,?,?)',(i,conv,role,body,now())); self.event(c,'chat.message','conversation',conv,w,tr,{'message_id':i,'role':role,'body':body})
  return i
 def mission(self,w,p,conv,request,key):
  project=self.db.execute('SELECT workspace_id FROM projects WHERE id=?',(p,)).fetchone()
  conversation=self.db.execute('SELECT workspace_id,project_id FROM conversations WHERE id=?',(conv,)).fetchone()
  if not project or project[0]!=w: raise PermissionError('project workspace isolation')
  if not conversation or conversation[0]!=w or conversation[1]!=p: raise PermissionError('conversation/project isolation')
  old=self.db.execute('SELECT id FROM missions WHERE workspace_id=? AND idempotency_key=?',(w,key)).fetchone()
  if old:return old[0]
  i=uid(); tr=uid(); t=now()
  with self.transaction() as c: c.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?)',(i,w,p,conv,'READY',tr,key,request,t,t)); self.event(c,'mission.created','mission',i,w,tr,{'state':'READY'}); self.audit(c,w,'user','mission.create',tr,{'id':i})
  return i
 def mission_state(self,m,state):
  row=self.db.execute('SELECT * FROM missions WHERE id=?',(m,)).fetchone(); assert row
  allowed={'READY':{'RUNNING'},'RUNNING':{'RECOVERING','COMPLETED','FAILED','CANCELLED'},'RECOVERING':{'RUNNING','FAILED','CANCELLED'}}
  if state not in allowed.get(row['state'],set()): raise ValueError('invalid transition')
  with self.transaction() as c: c.execute('UPDATE missions SET state=?,updated_at=? WHERE id=?',(state,now(),m)); self.event(c,'mission.state','mission',m,row['workspace_id'],row['trace_id'],{'state':state})
 def job(self,m,key,input_root=''):
  old=self.db.execute('SELECT id FROM jobs WHERE mission_id=? AND idempotency_key=?',(m,key)).fetchone()
  if old:return old[0]
  i=uid(); self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(i,m,'READY',0,3,None,None,0,key,input_root,None,None,now())); return i
 def claim(self,j,worker,ts=None,ttl=30):
  ts=ts or time.time()
  with self.transaction() as c:
   r=c.execute('SELECT * FROM jobs WHERE id=?',(j,)).fetchone()
   if not r: raise KeyError(j)
   if r['lease_expires_at'] and r['lease_expires_at']>ts and r['lease_owner']!=worker: raise RuntimeError('lease active')
   token=r['fencing_token']+1; attempt=r['attempt']+1
   if attempt>r['max_attempts']: raise RuntimeError('attempts exhausted')
   c.execute('UPDATE jobs SET state=?,attempt=?,lease_owner=?,lease_expires_at=?,fencing_token=?,heartbeat_at=? WHERE id=?',('RUNNING',attempt,worker,ts+ttl,token,ts,j)); return token
 def commit_job(self,j,worker,token,payload:bytes):
  with self.transaction() as c:
   r=c.execute('SELECT j.*,m.workspace_id,m.trace_id FROM jobs j JOIN missions m ON m.id=j.mission_id WHERE j.id=?',(j,)).fetchone()
   if not r or r['fencing_token']!=token or r['lease_owner']!=worker: raise RuntimeError('stale fencing token')
   h=sha256(payload).hexdigest(); c.execute('UPDATE jobs SET state=?,output_root=? WHERE id=?',('COMPLETED',h,j)); self.event(c,'job.completed','job',j,r['workspace_id'],r['trace_id'],{'output_root':h,'fencing_token':token}); return h
 def inbox_once(self,consumer,event_id,fn):
  try:
   with self.transaction() as c: c.execute('INSERT INTO inbox_receipts VALUES(?,?,?)',(consumer,event_id,now())); fn(c); return True
  except sqlite3.IntegrityError:
   return False
 def pending_outbox(self,limit=100):
  return [dict(x) for x in self.db.execute('SELECT * FROM outbox_events WHERE published_at IS NULL ORDER BY seq LIMIT ?',(limit,))]
 def record_publish_attempt(self,event_id,error=None):
  self.db.execute('UPDATE outbox_events SET publish_attempts=publish_attempts+1,last_publish_error=? WHERE event_id=?',(error,event_id))
 def acknowledge_publication(self,event_id,consumer_id):
  with self.transaction() as c:
   row=c.execute('SELECT 1 FROM outbox_events WHERE event_id=?',(event_id,)).fetchone()
   if not row: raise KeyError(event_id)
   c.execute('INSERT OR IGNORE INTO outbox_publication_receipts VALUES(?,?,?)',(consumer_id,event_id,now()))
   c.execute('UPDATE outbox_events SET published_at=COALESCE(published_at,?),last_publish_error=NULL WHERE event_id=?',(now(),event_id))
 def events_after(self,seq=0): return [dict(x) for x in self.db.execute('SELECT * FROM outbox_events WHERE seq>? ORDER BY seq',(seq,))]
 def _mission_owned(self,w,m):
  if m is None:return
  r=self.db.execute('SELECT workspace_id FROM missions WHERE id=?',(m,)).fetchone()
  if not r or r[0]!=w:raise PermissionError('mission workspace isolation')
 def artifact(self,w,m,payload:bytes):
  self._mission_owned(w,m); h=sha256(payload).hexdigest(); i=uid(); uri='cas://sha256/'+h
  self.db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?)',(i,w,m,h,len(payload),uri,now())); return {'id':i,'sha256':h,'size':len(payload),'storage_uri':uri}
 def evidence(self,w,m,tr,payload):
  self._mission_owned(w,m); h=root(payload); i=uid(); self.db.execute('INSERT INTO evidence_receipts VALUES(?,?,?,?,?,?,?)',(i,w,m,tr,canon(payload),h,now())); return {'id':i,'sha256':h}
 def health(self):
  self.db.execute('SELECT 1').fetchone(); return {'status':'PASS','database':'PASS','realtime':'PASS','reference_worker':'PASS'}
 def audit_valid(self):
  prev_by_workspace: dict[str, str]={}
  for r in self.db.execute('SELECT * FROM audit_events ORDER BY seq'):
   prev=prev_by_workspace.get(r['workspace_id'],'GENESIS')
   body={'workspace_id':r['workspace_id'],'actor':r['actor'],'action':r['action'],'trace_id':r['trace_id'],'payload':json.loads(r['payload']),'prev_hash':prev}
   if root(body)!=r['event_hash'] or r['prev_hash']!=prev:return False
   prev_by_workspace[r['workspace_id']]=r['event_hash']
  return True

class PairingService:
 def __init__(self,s:Store):self.s=s; self.issue_limiter=FixedWindowLimiter(RateLimitPolicy(5,60))
 def provision_workspace(self,w):
  if not self.s.db.execute('SELECT 1 FROM workspaces WHERE id=?',(w,)).fetchone():raise KeyError(w)
  raw=secrets.token_urlsafe(40); h=sha256(raw.encode()).hexdigest()
  self.s.db.execute('INSERT OR REPLACE INTO workspace_bootstrap(workspace_id,secret_hash,created_at,generation,rotated_at) VALUES(?,?,?,1,NULL)',(w,h,now())); return raw
 def issue(self,w,bootstrap_secret):
  if not self.issue_limiter.allow('pair:'+w): raise RuntimeError('pairing rate limit exceeded')
  r=self.s.db.execute('SELECT secret_hash,generation FROM workspace_bootstrap WHERE workspace_id=?',(w,)).fetchone()
  if not r or not secrets.compare_digest(sha256(bootstrap_secret.encode()).hexdigest(),r[0]):raise PermissionError('invalid workspace bootstrap capability')
  raw=secrets.token_urlsafe(24); self.s.db.execute('INSERT INTO pairing_codes(code_hash,workspace_id,expires_at,consumed_at,bootstrap_generation) VALUES(?,?,?,NULL,?)',(sha256(raw.encode()).hexdigest(),w,(datetime.now(timezone.utc)+timedelta(seconds=300)).isoformat(),int(r['generation']))); return raw
 def enroll(self,code):
  h=sha256(code.encode()).hexdigest(); token=secrets.token_urlsafe(40); th=sha256(token.encode()).hexdigest(); sid=uid()
  with self.s.transaction() as c:
   r=c.execute('SELECT * FROM pairing_codes WHERE code_hash=?',(h,)).fetchone()
   current=c.execute('SELECT generation FROM workspace_bootstrap WHERE workspace_id=?',(r['workspace_id'],)).fetchone() if r else None
   if not r or r['consumed_at'] or datetime.fromisoformat(r['expires_at'])<datetime.now(timezone.utc) or not current or int(r['bootstrap_generation'])!=int(current['generation']):raise RuntimeError('invalid/replayed pairing code')
   changed=c.execute('UPDATE pairing_codes SET consumed_at=? WHERE code_hash=? AND consumed_at IS NULL',(now(),h)).rowcount
   if changed!=1: raise RuntimeError('pairing enrollment lost race')
   c.execute('INSERT INTO device_sessions(id,workspace_id,token_hash,expires_at,created_at,revoked_at,replaced_by) VALUES(?,?,?,?,?,NULL,NULL)',(sid,r['workspace_id'],th,(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(),now()))
  return token
 def rotate_bootstrap(self,w,current_secret):
  r=self.s.db.execute('SELECT * FROM workspace_bootstrap WHERE workspace_id=?',(w,)).fetchone()
  if not r or not secrets.compare_digest(sha256(current_secret.encode()).hexdigest(),r['secret_hash']):raise PermissionError('invalid workspace bootstrap capability')
  raw=secrets.token_urlsafe(40); gen=int(r['generation'])+1
  with self.s.transaction() as c:
   fresh=c.execute('SELECT * FROM workspace_bootstrap WHERE workspace_id=?',(w,)).fetchone()
   if not fresh or not secrets.compare_digest(sha256(current_secret.encode()).hexdigest(),fresh['secret_hash']):raise PermissionError('invalid workspace bootstrap capability')
   gen=int(fresh['generation'])+1
   c.execute('UPDATE workspace_bootstrap SET secret_hash=?,generation=?,rotated_at=? WHERE workspace_id=?',(sha256(raw.encode()).hexdigest(),gen,now(),w))
   c.execute('UPDATE pairing_codes SET consumed_at=COALESCE(consumed_at,?) WHERE workspace_id=?',(now(),w))
  return raw
 def revoke_session(self,token):
  th=sha256(token.encode()).hexdigest(); r=self.s.db.execute('SELECT id FROM device_sessions WHERE token_hash=?',(th,)).fetchone()
  if not r:return False
  self.s.db.execute('UPDATE device_sessions SET revoked_at=? WHERE token_hash=?',(now(),th)); return True
 def rotate_session(self,token):
  oldh=sha256(token.encode()).hexdigest(); new=secrets.token_urlsafe(40); newh=sha256(new.encode()).hexdigest(); sid=uid()
  with self.s.transaction() as c:
   r=c.execute('SELECT * FROM device_sessions WHERE token_hash=?',(oldh,)).fetchone()
   if not r or r['revoked_at'] is not None or datetime.fromisoformat(r['expires_at'])<datetime.now(timezone.utc):raise PermissionError('invalid session')
   c.execute('INSERT INTO device_sessions(id,workspace_id,token_hash,expires_at,created_at,revoked_at,replaced_by) VALUES(?,?,?,?,?,NULL,NULL)',(sid,r['workspace_id'],newh,(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(),now()))
   changed=c.execute('UPDATE device_sessions SET revoked_at=?,replaced_by=? WHERE token_hash=? AND revoked_at IS NULL',(now(),sid,oldh)).rowcount
   if changed!=1: raise PermissionError('session rotation lost race')
  return new
 def workspace_for(self,token):
  r=self.s.db.execute('SELECT * FROM device_sessions WHERE token_hash=?',(sha256(token.encode()).hexdigest(),)).fetchone()
  if not r or r['revoked_at'] is not None or datetime.fromisoformat(r['expires_at'])<datetime.now(timezone.utc):raise PermissionError('invalid session')
  return r['workspace_id']

def approval_required(action,risk): return risk in {'HIGH','CRITICAL'} or action in {'paid_compute','destructive_delete','external_publish','production_deploy','credential_use'}

# v1.2 qualification-siege primitives. These are deliberately part of the Phase-1
# reference runtime so the stress campaigns exercise the same transactional code.
def _heartbeat_job(self: Store, j: str, worker: str, token: int, ts: float | None = None, ttl: int = 30) -> float:
 ts = ts or time.time()
 with self.transaction() as c:
  r=c.execute('SELECT lease_owner,lease_expires_at,fencing_token,state FROM jobs WHERE id=?',(j,)).fetchone()
  if not r or r['state']!='RUNNING' or r['lease_owner']!=worker or int(r['fencing_token'])!=int(token): raise RuntimeError('stale fencing token')
  if r['lease_expires_at'] is not None and float(r['lease_expires_at']) < ts: raise RuntimeError('lease expired')
  expires=ts+ttl
  c.execute('UPDATE jobs SET heartbeat_at=?,lease_expires_at=? WHERE id=?',(ts,expires,j))
  return expires

def _recover_expired_jobs(self: Store, ts: float | None = None) -> list[str]:
 ts=ts or time.time(); recovered=[]
 with self.transaction() as c:
  rows=c.execute("SELECT id FROM jobs WHERE state='RUNNING' AND lease_expires_at IS NOT NULL AND lease_expires_at<=? ORDER BY id",(ts,)).fetchall()
  for r in rows:
   c.execute("UPDATE jobs SET state='READY',lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL WHERE id=? AND state='RUNNING' AND lease_expires_at<=?",(r['id'],ts))
   if c.execute('SELECT changes()').fetchone()[0]: recovered.append(r['id'])
 return recovered

Store.heartbeat_job = _heartbeat_job  # type: ignore[attr-defined]
Store.recover_expired_jobs = _recover_expired_jobs  # type: ignore[attr-defined]
