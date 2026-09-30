from __future__ import annotations
import json, os, platform, shutil, subprocess, sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from packages.phase1_closure import closure_environment, postgres_migration_qualification, python_typecheck
from packages.phase1_qualification import sha256_obj

OUT=ROOT/'evidence/phase1-real-closure-v4.3.0/environment-report.json'

def version(cmd:list[str])->str|None:
    try:
        p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
        return p.stdout.strip().splitlines()[0] if p.returncode==0 and p.stdout.strip() else None
    except (OSError,subprocess.SubprocessError): return None

def main()->int:
    report: dict[str, Any]={
        'scope':'phase1-real-closure-environment-v1',
        'requirements':{'python':'3.11.x','python_typechecker':'mypy-real','postgres_server_major':'16','psql_major':'16','synthetic_evidence_allowed':False},
        'observed':{
            **closure_environment(),
            'platform_python':platform.python_version(),
            'mypy_version':version(['mypy','--version']),
            'psql_version':version(['psql','--version']),
            'postgres_version':version(['postgres','--version']),
        },
        'python_typecheck':None,'postgres_migration':None,'blockers':[],
    }
    try:
        py_result=python_typecheck(ROOT); report['python_typecheck']=asdict(py_result)
        if py_result.returncode: report['blockers'].append('PYTHON_TYPECHECK_FAILED')
    except Exception as e: report['blockers'].append('PYTHON_TYPECHECK:'+str(e))
    try:
        pg_result=postgres_migration_qualification(ROOT,os.getenv('NARMS_PHASE1_POSTGRES_DSN','')); report['postgres_migration']=asdict(pg_result)
        if not pg_result.pass_: report['blockers'].append('DB_MIGRATIONS_FAILED')
    except Exception as e: report['blockers'].append('DB_MIGRATIONS:'+str(e))
    report['status']='PASS' if not report['blockers'] else 'BLOCKED'
    report['report_root']=sha256_obj(report)
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if report['status']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
