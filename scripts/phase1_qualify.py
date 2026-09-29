from __future__ import annotations
import argparse, hashlib, json, sys
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from packages.phase1_qualification import REQUIRED_GATES,audit_migration_sql,canonical,detect_environment,evidence,sha256_obj

def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument('--baseline',default='evidence/phase1-v0.2.0/evidence-bundle.json'); p.add_argument('--out',default='evidence/phase1-v0.3.0/qualification-report.json'); a=p.parse_args()
 baseline=json.loads((ROOT/a.baseline).read_text())
 env=detect_environment(); migration=(ROOT/'migrations/0001_phase1.sql').read_text(); ma=audit_migration_sql(migration)
 gates=dict(baseline['gates']); blockers={}
 ev={}
 for g in REQUIRED_GATES:
  status=gates.get(g,'BLOCKED'); detail='carried forward from verified v0.2.0 baseline'
  if g=='PYTHON_TYPECHECK':
   if env['pyright'].available or env['mypy'].available: detail='static typechecker available; execution required before PASS'; status='BLOCKED'
   else: detail='mypy/pyright unavailable in current environment'; status='BLOCKED'; blockers[g]=detail
  elif g=='DB_MIGRATIONS':
   detail='migration static contract PASS, but real PostgreSQL execution unavailable' if ma['static_pass'] else 'migration static contract failed'
   status='BLOCKED'; blockers[g]=detail
  ev[g]=asdict(evidence(g,status,detail,{'baseline':baseline['gates'].get(g),'migration_audit':ma if g=='DB_MIGRATIONS' else None}))
 source_files=sorted(str(x.relative_to(ROOT)) for x in ROOT.rglob('*') if x.is_file() and not any(part in {'.git','evidence','node_modules','dist','__pycache__','.pytest_cache'} for part in x.relative_to(ROOT).parts) and x.name not in {'MANIFEST.sha256','RELEASE.json'})
 source_root=hashlib.sha256('\n'.join(f'{hashlib.sha256((ROOT/f).read_bytes()).hexdigest()}  {f}' for f in source_files).encode()).hexdigest()
 payload={'phase':'PHASE_1','version':'0.3.0','gates':{g:ev[g]['status'] for g in REQUIRED_GATES},'evidence':ev,'blockers':blockers,'environment':{k:asdict(v) for k,v in env.items()},'migration_static_audit':ma,'source_root':source_root,'phase_1_certificate_issued':False,'phase_2_allowed':False}
 payload['report_root']=sha256_obj(payload)
 out=ROOT/a.out; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':'BLOCKED' if blockers else 'REQUIRES_GATE_EXECUTION','blockers':blockers,'report_root':payload['report_root'],'migration_static_pass':ma['static_pass']},indent=2))
 return 0
if __name__=='__main__': raise SystemExit(main())
