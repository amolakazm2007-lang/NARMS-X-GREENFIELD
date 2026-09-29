from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_unlock import Phase1TrustPolicy, verify_phase1_certificate


def main()->int:
    evidence=ROOT/'evidence/phase1-v1.6.0'
    report_path=evidence/'qualification-report.json'
    cert_path=evidence/'phase1-certificate.json'
    trusted=os.getenv('NARMS_PHASE1_TRUSTED_PUBLIC_KEY_HEX','')
    if not trusted:
        print(json.dumps({'phase2_allowed':False,'reasons':['trusted_public_key_missing']},indent=2)); return 2
    if not report_path.exists() or not cert_path.exists():
        print(json.dumps({'phase2_allowed':False,'reasons':['qualification_or_certificate_missing']},indent=2)); return 2
    result=verify_phase1_certificate(json.loads(cert_path.read_text()),json.loads(report_path.read_text()),Phase1TrustPolicy(trusted))
    out=evidence/'phase2-unlock.json'; out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result['phase2_allowed'] else 2
if __name__=='__main__': raise SystemExit(main())
