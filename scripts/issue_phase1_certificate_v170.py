from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.phase1_attestation import issue_attested_phase1_certificate

def main()->int:
    d=ROOT/'evidence/phase1-v1.7.0';rp=d/'qualification-report.json';ap=d/'closure-attestation.json'
    if not rp.exists() or not ap.exists(): raise SystemExit('qualification report and closure attestation are required')
    key=os.getenv('NARMS_PHASE1_SIGNING_KEY_HEX','')
    if not key: raise SystemExit('NARMS_PHASE1_SIGNING_KEY_HEX is required; private keys are never stored in the repository')
    cert=issue_attested_phase1_certificate(json.loads(rp.read_text()),json.loads(ap.read_text()),key)
    out=d/'phase1-certificate.json';out.write_text(json.dumps(cert,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'ISSUED','fingerprint':cert['fingerprint'],'closure_attestation_root':cert['body']['closure_attestation_root']},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
