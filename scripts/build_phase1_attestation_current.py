from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from packages.phase1_attestation import build_closure_attestation, capture_toolchain_receipt
VERSION='2.8.0'; IDENTITY='phase1-closure.yml@v2.8.0'
if __name__=='__main__':
    report_path=ROOT/f'evidence/phase1-v{VERSION}/qualification-report.json'
    if not report_path.exists(): raise SystemExit('run phase1_qualify_current.py first')
    report=json.loads(report_path.read_text())
    att=build_closure_attestation(report,capture_toolchain_receipt(),workflow_identity=os.getenv('NARMS_PHASE1_WORKFLOW_IDENTITY',IDENTITY))
    out=report_path.parent/'closure-attestation.json'; out.write_text(json.dumps(att,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'attestation_root':att['attestation_root'],'workflow_identity':att['workflow_identity']},indent=2))
