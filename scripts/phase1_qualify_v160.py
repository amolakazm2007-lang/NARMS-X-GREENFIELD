from __future__ import annotations
# v1.6 deliberately reuses the v1.5 qualification semantics; the difference is
# portable CI execution and a cryptographically verified Phase-2 unlock boundary.
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import scripts.phase1_qualify_v150 as q

if __name__=='__main__':
    rc=q.main()
    old=ROOT/'evidence/phase1-v1.5.0/qualification-report.json'
    newdir=ROOT/'evidence/phase1-v1.6.0'; newdir.mkdir(parents=True,exist_ok=True)
    if old.exists():
        data=json.loads(old.read_text()); data['version']='1.6.0'
        # report_root must bind the version change.
        from packages.phase1_qualification import sha256_obj
        data.pop('report_root',None); data['report_root']=sha256_obj(data)
        (newdir/'qualification-report.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    raise SystemExit(rc)
