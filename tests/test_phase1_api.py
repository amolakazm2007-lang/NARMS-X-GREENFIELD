import importlib.util,sys,unittest
from pathlib import Path
from fastapi.testclient import TestClient
P=Path(__file__).resolve().parents[1]/'control-plane/api/app.py'
spec=importlib.util.spec_from_file_location('narms_api',P)
assert spec is not None and spec.loader is not None
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);c=TestClient(m.app)
class API(unittest.TestCase):
 def test_e2e_control_spine(self):
  wr=c.post('/api/v1/workspaces',json={'name':'اختبار'}).json();w=wr['id'];code=c.post('/api/v1/auth/pairing',json={'workspace_id':w,'bootstrap_secret':wr['bootstrap_secret']}).json()['code'];tok=c.post('/api/v1/auth/enroll',json={'code':code}).json()['token'];h={'Authorization':'Bearer '+tok}
  self.assertEqual(c.post('/api/v1/auth/enroll',json={'code':code}).status_code,400)
  p=c.post('/api/v1/projects',headers=h,json={'workspace_id':w,'name':'مشروع'}).json()['id'];ch=c.post('/api/v1/chat',headers=h,json={'workspace_id':w,'project_id':p}).json()['id'];self.assertEqual(c.post('/api/v1/chat/messages',headers=h,json={'workspace_id':w,'conversation_id':ch,'role':'user','body':'ابدأ'}).status_code,200);mi=c.post('/api/v1/missions',headers=h,json={'workspace_id':w,'project_id':p,'conversation_id':ch,'request':'reference','idempotency_key':'api-m'}).json()['id'];self.assertTrue(mi);self.assertEqual(c.get('/api/v1/system/health').json()['status'],'PASS');stream=c.get('/api/v1/events?after=0',headers=h);self.assertEqual(stream.status_code,200);self.assertIn('event: chat.message',stream.text);self.assertIn('event: mission.created',stream.text)
 def test_workspace_isolation(self):
  r1=c.post('/api/v1/workspaces',json={'name':'1'}).json();r2=c.post('/api/v1/workspaces',json={'name':'2'}).json();w1=r1['id'];w2=r2['id'];code=c.post('/api/v1/auth/pairing',json={'workspace_id':w1,'bootstrap_secret':r1['bootstrap_secret']}).json()['code'];tok=c.post('/api/v1/auth/enroll',json={'code':code}).json()['token'];self.assertEqual(c.post('/api/v1/projects',headers={'Authorization':'Bearer '+tok},json={'workspace_id':w2,'name':'x'}).status_code,403)
if __name__=='__main__':unittest.main()

def test_api_session_rotation_and_revocation():
 r=c.post('/api/v1/workspaces',json={'name':'rotate'}).json(); w=r['id']; code=c.post('/api/v1/auth/pairing',json={'workspace_id':w,'bootstrap_secret':r['bootstrap_secret']}).json()['code']; old=c.post('/api/v1/auth/enroll',json={'code':code}).json()['token']; h={'Authorization':'Bearer '+old}
 rr=c.post('/api/v1/auth/session/rotate',headers=h); assert rr.status_code==200; new=rr.json()['token']; assert c.post('/api/v1/projects',headers=h,json={'workspace_id':w,'name':'old'}).status_code==401
 nh={'Authorization':'Bearer '+new}; assert c.post('/api/v1/projects',headers=nh,json={'workspace_id':w,'name':'new'}).status_code==200; assert c.post('/api/v1/auth/session/revoke',headers=nh).status_code==200; assert c.post('/api/v1/projects',headers=nh,json={'workspace_id':w,'name':'revoked'}).status_code==401

def test_api_request_size_boundary():
 assert c.post('/api/v1/workspaces',content=b'x'*70000,headers={'content-type':'application/json'}).status_code==413
