from __future__ import annotations
import asyncio,json,os,sys
from pathlib import Path
from fastapi import FastAPI,Header,HTTPException,Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel,Field
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from packages.phase1_runtime import Store,PairingService,approval_required
from packages.phase1_security import RequestBudget
DB=os.getenv('NARMS_REFERENCE_DB',':memory:'); store=Store(DB); pairing=PairingService(store); app=FastAPI(title='NARMS X Phase 1',version='1.4.0'); REQUEST_BUDGET=RequestBudget(); ALLOWED_ORIGINS={x for x in os.getenv('NARMS_ALLOWED_ORIGINS','').split(',') if x}

@app.middleware('http')
async def boundary_guard(request:Request,call_next):
 content_length=request.headers.get('content-length')
 if content_length:
  try:
   if int(content_length)>REQUEST_BUDGET.max_body_bytes:return JSONResponse({'detail':'request body budget exceeded'},status_code=413)
  except ValueError:return JSONResponse({'detail':'invalid content-length'},status_code=400)
 origin=request.headers.get('origin')
 if ALLOWED_ORIGINS and origin and origin not in ALLOWED_ORIGINS:return JSONResponse({'detail':'origin not allowed'},status_code=403)
 return await call_next(request)
class Name(BaseModel):name:str=Field(min_length=1,max_length=120)
class ProjectIn(Name):workspace_id:str
class ChatIn(BaseModel):workspace_id:str;project_id:str|None=None
class MsgIn(BaseModel):workspace_id:str;conversation_id:str;role:str=Field(pattern='^user$');body:str=Field(min_length=1,max_length=20000)
class MissionIn(BaseModel):workspace_id:str;project_id:str;conversation_id:str;request:str;idempotency_key:str
class PairIn(BaseModel):workspace_id:str;bootstrap_secret:str=Field(min_length=20,max_length=256)
class EnrollIn(BaseModel):code:str
class ApprovalIn(BaseModel):workspace_id:str;action:str;risk:str;actor:str='user'
def auth(authorization:str|None):
 if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'missing bearer session')
 try:return pairing.workspace_for(authorization[7:])
 except PermissionError:raise HTTPException(401,'invalid session')
@app.get('/api/v1/system/health')
def health():return store.health()
@app.post('/api/v1/workspaces')
def workspace(x:Name):
 w=store.workspace(x.name); bootstrap=pairing.provision_workspace(w); return {'id':w,'bootstrap_secret':bootstrap}
@app.post('/api/v1/auth/pairing')
def issue(x:PairIn):
 try:return {'code':pairing.issue(x.workspace_id,x.bootstrap_secret)}
 except (PermissionError,KeyError):raise HTTPException(403,'invalid workspace bootstrap capability')
@app.post('/api/v1/auth/enroll')
def enroll(x:EnrollIn):
 try:return {'token':pairing.enroll(x.code)}
 except RuntimeError as e:raise HTTPException(400,str(e))
@app.post('/api/v1/auth/session/rotate')
def rotate_session(authorization:str|None=Header(None)):
 if authorization is None: raise HTTPException(401,'missing bearer session')
 auth(authorization)
 return {'token':pairing.rotate_session(authorization[7:])}
@app.post('/api/v1/auth/session/revoke')
def revoke_session(authorization:str|None=Header(None)):
 if authorization is None: raise HTTPException(401,'missing bearer session')
 auth(authorization); pairing.revoke_session(authorization[7:]); return {'revoked':True}
@app.post('/api/v1/auth/bootstrap/rotate')
def rotate_bootstrap(x:PairIn,authorization:str|None=Header(None)):
 w=auth(authorization)
 if w!=x.workspace_id:raise HTTPException(403,'workspace isolation')
 try:return {'bootstrap_secret':pairing.rotate_bootstrap(w,x.bootstrap_secret)}
 except PermissionError:raise HTTPException(403,'invalid workspace bootstrap capability')
@app.post('/api/v1/projects')
def project(x:ProjectIn,authorization:str|None=Header(None)):
 w=auth(authorization)
 if w!=x.workspace_id:raise HTTPException(403,'workspace isolation')
 return {'id':store.project(w,x.name)}
@app.post('/api/v1/chat')
def chat(x:ChatIn,authorization:str|None=Header(None)):
 w=auth(authorization)
 if w!=x.workspace_id:raise HTTPException(403,'workspace isolation')
 return {'id':store.conversation(w,x.project_id)}
@app.post('/api/v1/chat/messages')
def msg(x:MsgIn,authorization:str|None=Header(None)):
 w=auth(authorization)
 if w!=x.workspace_id:raise HTTPException(403,'workspace isolation')
 return {'id':store.message(w,x.conversation_id,x.role,x.body)}
@app.post('/api/v1/missions')
def mission(x:MissionIn,authorization:str|None=Header(None)):
 w=auth(authorization)
 if w!=x.workspace_id:raise HTTPException(403,'workspace isolation')
 return {'id':store.mission(w,x.project_id,x.conversation_id,x.request,x.idempotency_key)}
@app.get('/api/v1/events')
async def events(after:int=0,authorization:str|None=Header(None),last_event_id:str|None=Header(None,alias='Last-Event-ID')):
 w=auth(authorization)
 try: header_cursor=int(last_event_id) if last_event_id is not None else 0
 except ValueError: raise HTTPException(400,'invalid Last-Event-ID')
 start=max(after,header_cursor)
 async def gen():
  cursor=start
  for _ in range(20):
   rows=[r for r in store.events_after(cursor) if r['workspace_id']==w]
   for r in rows:
    cursor=r['seq']; yield f"id: {cursor}\nevent: {r['event_type']}\ndata: {r['payload']}\n\n"
   if rows:return
   await asyncio.sleep(.05)
  yield ': heartbeat\n\n'
 return StreamingResponse(gen(),media_type='text/event-stream',headers={'Cache-Control':'no-cache'})
@app.post('/api/v1/approvals')
def approval(x:ApprovalIn,authorization:str|None=Header(None)):
 w=auth(authorization)
 if w!=x.workspace_id:raise HTTPException(403,'workspace isolation')
 required=approval_required(x.action,x.risk); return {'approval_required':required}
