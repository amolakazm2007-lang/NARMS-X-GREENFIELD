from __future__ import annotations
import json, os, sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_closure import closure_environment, postgres_migration_qualification, python_typecheck
from packages.phase1_qualification import sha256_obj

def main()->int:
    env=closure_environment(); out: dict[str, Any]={'environment':env,'python_typecheck':None,'postgres':None,'status':'BLOCKED','blockers':[]}
    try:
        py_result=python_typecheck(ROOT); out['python_typecheck']=asdict(py_result)
        if py_result.returncode: out['blockers'].append('PYTHON_TYPECHECK_FAILED')
    except Exception as e: out['blockers'].append(f'PYTHON_TYPECHECK:{e}')
    try:
        pg_result=postgres_migration_qualification(ROOT,os.getenv('NARMS_PHASE1_POSTGRES_DSN','')); out['postgres']=asdict(pg_result)
    except Exception as e: out['blockers'].append(f'DB_MIGRATIONS:{e}')
    out['status']='PASS' if not out['blockers'] else 'BLOCKED';out['report_root']=sha256_obj(out)
    p=ROOT/'evidence/phase1-v1.5.0/closure-report.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True));return 0 if out['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
