from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_attestation import build_closure_attestation, capture_toolchain_receipt

def main()->int:
    report_path=ROOT/'evidence/phase1-v1.7.0/qualification-report.json'
    if not report_path.exists(): raise SystemExit('run phase1_qualify_v170.py first')
    report=json.loads(report_path.read_text())
    identity=os.getenv('NARMS_PHASE1_WORKFLOW_IDENTITY','phase1-closure.yml@v1.7.0')
    att=build_closure_attestation(report,capture_toolchain_receipt(),workflow_identity=identity)
    out=ROOT/'evidence/phase1-v1.7.0/closure-attestation.json'
    out.write_text(json.dumps(att,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'ATTESTED','attestation_root':att['attestation_root'],'path':str(out.relative_to(ROOT))},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
