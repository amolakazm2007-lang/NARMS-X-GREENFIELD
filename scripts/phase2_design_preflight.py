from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from packages.phase2_design import load_catalog, validate_catalog, compile_opening_plan
if __name__=='__main__':
    catalog=load_catalog(ROOT/'docs/phase2/capability-catalog.json')
    report=validate_catalog(catalog); plan=compile_opening_plan(catalog)
    out={'version':'2.8.0','design_valid':report.valid,'design_reasons':list(report.reasons),'capability_count':report.capability_count,'waves':list(report.waves),'catalog_root':report.graph_root,'opening_plan_root':plan['plan_root'],'implementation_allowed':False,'phase2_started':False}
    p=ROOT/'evidence/phase2-design-v2.8.0'; p.mkdir(parents=True,exist_ok=True); (p/'preflight.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2)); raise SystemExit(0 if report.valid else 1)
