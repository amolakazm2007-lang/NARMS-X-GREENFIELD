from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_closure import issue_phase1_certificate_from_report

def main()->int:
    report_path=ROOT/'evidence/phase1-v1.5.0/qualification-report.json'
    if not report_path.exists(): raise SystemExit('run phase1_qualify_v150.py first')
    key=os.getenv('NARMS_PHASE1_SIGNING_KEY_HEX','')
    if not key: raise SystemExit('NARMS_PHASE1_SIGNING_KEY_HEX is required; private keys are never stored in the repository')
    cert=issue_phase1_certificate_from_report(json.loads(report_path.read_text()),key)
    out=ROOT/'evidence/phase1-v1.5.0/phase1-certificate.json';out.write_text(json.dumps(cert,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'ISSUED','fingerprint':cert['fingerprint'],'path':str(out.relative_to(ROOT))},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
