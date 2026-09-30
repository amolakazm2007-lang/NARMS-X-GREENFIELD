from __future__ import annotations
import hashlib, json, shutil, subprocess, sys, re
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_qualification import REQUIRED_GATES, audit_migration_sql, audit_sqlite_runtime_schema, audit_sqlite_deep_schema, audit_postgres_deep_contract, qualification_policy_root, sha256_obj
from packages.phase1_runtime import Store
from packages.phase1_hardening import build_source_binding, bind_gate_evidence
from packages.phase1_siege import phase1_siege_policy_root
from packages.phase1_closure import python_typecheck, postgres_migration_qualification

FUNCTIONAL_GATES=set(REQUIRED_GATES)-{'PYTHON_TYPECHECK','DB_MIGRATIONS','MONOREPO_STRUCTURE','ARCHITECTURE_DOCTOR','DEPENDENCY_RULES','CONTRACT_VALIDATION','TS_TYPECHECK','BACKEND_BUILD','FRONTEND_BUILD','NO_SECRET_LEAK'}

def run(cmd,cwd=ROOT):
 p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
 normalized=re.sub(r'\b(?:in\s+)?\d+(?:\.\d+)?s\b','<duration>',p.stdout)
 normalized=re.sub(r'\b\d+(?:\.\d+)? seconds?\b','<duration>',normalized)
 return {'command':cmd,'returncode':p.returncode,'normalized_output_sha256':hashlib.sha256(normalized.encode()).hexdigest(),'normalized_output_tail':normalized[-2000:]}

def source_root():
 excluded={'.git','evidence','node_modules','dist','__pycache__','.pytest_cache','.mypy_cache'}; rows=[]
 for p in sorted(x for x in ROOT.rglob('*') if x.is_file()):
  rel=p.relative_to(ROOT)
  if any(part in excluded for part in rel.parts) or p.name in {'MANIFEST.sha256','RELEASE.json'}:continue
  rows.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel.as_posix()}')
 return hashlib.sha256('\n'.join(rows).encode()).hexdigest()

def main(*, version: str = '1.5.0', output_dir: str | None = None):
 sr=source_root(); binding=build_source_binding(ROOT,sr)
 checks={
  'pytest':run([sys.executable,'-m','pytest','-q']),
  'architecture':run([sys.executable,'scripts/architecture_doctor.py']),
  'contracts':run([sys.executable,'scripts/validate_contracts.py']),
  'secrets':run([sys.executable,'scripts/no_secret_leak.py']),
  'compileall':run([sys.executable,'-m','compileall','-q','packages','control-plane','scripts','tests']),
  'ts_typecheck':run(['npm','run','typecheck'],ROOT/'apps/web'),
  'frontend_build':run(['npm','run','build'],ROOT/'apps/web'),
 }
 sql=(ROOT/'migrations/0001_phase1.sql').read_text(); migration=audit_migration_sql(sql); runtime_store=Store(); runtime_schema=audit_sqlite_runtime_schema(runtime_store.db); runtime_deep=audit_sqlite_deep_schema(runtime_store.db); runtime_store.db.close(); postgres_deep=audit_postgres_deep_contract(sql); policy_root=qualification_policy_root(); siege_root=phase1_siege_policy_root()
 pychecker=shutil.which('mypy')
 psql=shutil.which('psql'); postgres=shutil.which('postgres')
 typecheck_receipt=None; postgres_receipt=None
 if pychecker:
  try: typecheck_receipt=python_typecheck(ROOT)
  except Exception: typecheck_receipt=None
 if psql and __import__('os').getenv('NARMS_PHASE1_POSTGRES_DSN'):
  try: postgres_receipt=postgres_migration_qualification(ROOT,__import__('os').environ['NARMS_PHASE1_POSTGRES_DSN'])
  except Exception: postgres_receipt=None
 gates={}; evidence={}; blockers={}
 def setgate(g,status,detail,payload):
  gates[g]=status; evidence[g]=bind_gate_evidence(g,{'status':status,'detail':detail,'receipt':payload},binding)
  if status!='PASS':blockers[g]=detail
 functional_pass=checks['pytest']['returncode']==0
 for g in REQUIRED_GATES:
  if g in FUNCTIONAL_GATES:setgate(g,'PASS' if functional_pass else 'FAIL','fresh full Phase-1 regression suite' if functional_pass else 'regression suite failed',checks['pytest'])
  elif g in {'MONOREPO_STRUCTURE','ARCHITECTURE_DOCTOR','DEPENDENCY_RULES'}:
   ok=checks['architecture']['returncode']==0;setgate(g,'PASS' if ok else 'FAIL','fresh architecture doctor',checks['architecture'])
  elif g=='CONTRACT_VALIDATION':
   ok=checks['contracts']['returncode']==0;setgate(g,'PASS' if ok else 'FAIL','fresh JSON-schema validation',checks['contracts'])
  elif g=='TS_TYPECHECK':
   ok=checks['ts_typecheck']['returncode']==0;setgate(g,'PASS' if ok else 'FAIL','fresh TypeScript typecheck',checks['ts_typecheck'])
  elif g=='BACKEND_BUILD':
   ok=checks['compileall']['returncode']==0;setgate(g,'PASS' if ok else 'FAIL','fresh Python compileall build check (not a typecheck)',checks['compileall'])
  elif g=='FRONTEND_BUILD':
   ok=checks['frontend_build']['returncode']==0;setgate(g,'PASS' if ok else 'FAIL','fresh frontend build',checks['frontend_build'])
  elif g=='NO_SECRET_LEAK':
   ok=checks['secrets']['returncode']==0;setgate(g,'PASS' if ok else 'FAIL','fresh repository secret scan',checks['secrets'])
  elif g=='PYTHON_TYPECHECK':
   setgate(g,'PASS' if typecheck_receipt and typecheck_receipt.returncode==0 else 'BLOCKED','real Python typechecker passed' if typecheck_receipt and typecheck_receipt.returncode==0 else 'Python 3.11 + real mypy unavailable or failed; compileall/pyright are not accepted for this closure gate',asdict(typecheck_receipt) if typecheck_receipt else {'mypy':shutil.which('mypy'),'required_python':'3.11'})
  elif g=='DB_MIGRATIONS':
   setgate(g,'PASS' if postgres_receipt and postgres_receipt.pass_ else 'BLOCKED','real PostgreSQL apply/reapply/introspection/rollback/reapply passed' if postgres_receipt and postgres_receipt.pass_ else 'real PostgreSQL execution unavailable or failed',asdict(postgres_receipt) if postgres_receipt else {'static_audit':migration,'psql':psql,'postgres':postgres,'dsn_present':bool(__import__('os').getenv('NARMS_PHASE1_POSTGRES_DSN'))})
 payload={'phase':'PHASE_1','version':version,'source_root':sr,'source_binding':asdict(binding),'source_binding_root':binding.root,'gates':gates,'evidence':evidence,'blockers':blockers,'checks':checks,'migration_static_audit':migration,'runtime_schema_audit':runtime_schema,'runtime_deep_schema_audit':runtime_deep,'postgres_deep_contract_audit':postgres_deep,'qualification_policy_root':policy_root,'qualification_siege_policy_root':siege_root,'phase_1_certificate_issued':False,'phase_2_allowed':False}
 payload['report_root']=sha256_obj(payload)
 outdir = ROOT/(output_dir or f'evidence/phase1-v{version}')
 out=outdir/'qualification-report.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':'BLOCKED' if blockers else 'PASS','passed':sum(v=='PASS' for v in gates.values()),'total':len(gates),'blockers':blockers,'source_binding_root':binding.root,'report_root':payload['report_root']},indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())
