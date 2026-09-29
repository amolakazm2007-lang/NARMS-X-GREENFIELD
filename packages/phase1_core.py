from dataclasses import dataclass,field
from hashlib import sha256
from datetime import datetime,timedelta,timezone
from enum import Enum
import json,secrets

class MissionState(str,Enum):
 DRAFT='DRAFT'; READY='READY'; RUNNING='RUNNING'; RECOVERING='RECOVERING'; COMPLETED='COMPLETED'; FAILED='FAILED'; CANCELLED='CANCELLED'
TRANS={MissionState.DRAFT:{MissionState.READY},MissionState.READY:{MissionState.RUNNING},MissionState.RUNNING:{MissionState.RECOVERING,MissionState.COMPLETED,MissionState.FAILED,MissionState.CANCELLED},MissionState.RECOVERING:{MissionState.RUNNING,MissionState.FAILED,MissionState.CANCELLED}}
@dataclass
class Mission:
 id:str; workspace_id:str; trace_id:str; state:MissionState=MissionState.DRAFT
 def move(self,n):
  if n not in TRANS.get(self.state,set()): raise ValueError('invalid mission transition')
  self.state=n
@dataclass
class Job:
 id:str; mission_id:str; idempotency_key:str; fencing_token:int=0; lease_owner:str|None=None; lease_expires_at:datetime|None=None; output_root:str|None=None
 def claim(self,owner,now,ttl=30):
  if self.lease_expires_at and self.lease_expires_at>now and self.lease_owner!=owner: raise RuntimeError('lease active')
  self.fencing_token+=1; self.lease_owner=owner; self.lease_expires_at=now+timedelta(seconds=ttl); return self.fencing_token
 def commit(self,token,payload:bytes):
  if token!=self.fencing_token: raise RuntimeError('stale fencing token')
  self.output_root=sha256(payload).hexdigest(); return self.output_root
class Inbox:
 def __init__(self): self.seen=set()
 def apply_once(self,consumer,event_id,fn):
  k=(consumer,event_id)
  if k in self.seen:return False
  fn(); self.seen.add(k); return True
class Pairing:
 def __init__(self): self.codes={}; self.sessions={}
 def issue(self):
  c=secrets.token_urlsafe(18); self.codes[c]=True; return c
 def enroll(self,code):
  if not self.codes.pop(code,None): raise RuntimeError('invalid/replayed pairing code')
  t=secrets.token_urlsafe(32); self.sessions[sha256(t.encode()).hexdigest()]=True; return t
 def valid(self,t): return self.sessions.get(sha256(t.encode()).hexdigest(),False)
def artifact(payload:bytes): return {'sha256':sha256(payload).hexdigest(),'size':len(payload)}
def deterministic_reference_task(text:str): return text.strip().encode('utf-8')[::-1]
