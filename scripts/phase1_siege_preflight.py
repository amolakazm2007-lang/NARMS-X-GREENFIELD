from __future__ import annotations
import json, tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from packages.phase1_runtime import Store
from packages.phase1_siege import concurrent_campaign, audit_chain_snapshot, phase1_siege_policy_root, sha256_obj
from packages.phase1_qualification import audit_sqlite_deep_schema, audit_postgres_deep_contract

def seed(path):
    s=Store(path); w=s.workspace('siege'); p=s.project(w,'p'); c=s.conversation(w,p); m=s.mission(w,p,c,'stress','m'); j=s.job(m,'j'); return s,w,j

def main():
    with tempfile.TemporaryDirectory() as d:
        lease_path=str(Path(d)/'lease.db'); s,w,j=seed(lease_path); s.db.close()
        def claim(i):
            st=Store(lease_path)
            try: st.claim(j,f'w{i}',100,30); return True
            finally: st.db.close()
        lease=concurrent_campaign('lease-contention',32,claim)
        check=Store(lease_path); lease_row=dict(check.db.execute('select attempt,fencing_token,lease_owner,state from jobs where id=?',(j,)).fetchone()); check.db.close()

        audit_path=str(Path(d)/'audit.db'); a=Store(audit_path); aw=a.workspace('audit'); a.db.close()
        def append(i):
            st=Store(audit_path)
            try:
                with st.transaction() as c: st.audit(c,aw,f'w{i}','siege.append',f't{i}',{'i':i})
                return True
            finally: st.db.close()
        audit=concurrent_campaign('audit-concurrent-append',24,append); verify=Store(audit_path); audit_valid=verify.audit_valid(); audit_snap=audit_chain_snapshot(verify.db); verify.db.close()

        schema=Store(); sqlite_deep=audit_sqlite_deep_schema(schema.db); schema.db.close(); pg_deep=audit_postgres_deep_contract((ROOT/'migrations/0001_phase1.sql').read_text())
        body={'version':'1.4.0','policy_root':phase1_siege_policy_root(),'lease':lease.__dict__,'lease_row':lease_row,'audit':audit.__dict__,'audit_chain_valid':audit_valid,'audit_snapshot':audit_snap,'sqlite_deep_pass':sqlite_deep['pass'],'postgres_deep_static_pass':pg_deep['pass'],'truth_boundary':{'real_postgres_executed':False,'python_typechecker_executed':False,'phase1_certificate_issued':False,'phase2_allowed':False}}
        body['report_root']=sha256_obj(body)
        out=ROOT/'evidence/phase1-v1.4.0/siege-report.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(body,indent=2,sort_keys=True)+'\n')
        print(json.dumps(body,indent=2,sort_keys=True))
if __name__=='__main__': main()
