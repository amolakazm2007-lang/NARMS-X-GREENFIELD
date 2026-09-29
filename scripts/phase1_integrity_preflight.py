from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from packages.phase1_integrity import build_source_snapshot, verify_source_snapshot, build_promotion_request

s=build_source_snapshot(ROOT); v=verify_source_snapshot(ROOT,s)
blocked=False
try:
    build_promotion_request(version='2.2.0',snapshot=s,evidence_graph={'valid':False},trust_policy_root='0'*64)
except RuntimeError:
    blocked=True
report={'version':'2.2.0','source_snapshot_root':s.root,'source_snapshot_files':len(s.files),'snapshot_verifies':v['valid'],
        'invalid_promotion_blocked':blocked,'phase2_allowed':False,'phase2_components_started':False,
        'truth_boundary':'Local integrity mechanics only; no 32/32 trusted Phase-1 certificate is fabricated.'}
out=ROOT/'evidence/phase1-v2.2.0'; out.mkdir(parents=True,exist_ok=True)
(out/'integrity-preflight.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps(report,indent=2,sort_keys=True))
