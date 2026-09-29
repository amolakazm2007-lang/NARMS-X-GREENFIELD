import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from packages.phase2_sealed import compile_sealed_skeletons,assert_non_executable
from packages.phase2_conformance import REQUIRED_CHECKS,issue_receipt,conformance_matrix
from packages.phase2_admission import evaluate_wave
from packages.phase2_cross_domain import DomainReceipt,qualify,REQUIRED_DOMAINS
from packages.phase2_constitution import sha
cat=json.loads((ROOT/'docs/phase2/capability-catalog.json').read_text())
ss=compile_sealed_skeletons(cat)
def rec(s): return issue_receipt(s.capability_id,s.root,{x:True for x in REQUIRED_CHECKS},{x:sha({'cap':s.capability_id,'check':x}) for x in REQUIRED_CHECKS},sha({'environment':'reference-conformance-only'}))
rs=tuple(rec(s) for s in ss)
blocked=evaluate_wave(wave=1,catalog=cat,opening_allowed=False,opening_root=None,receipts=tuple(r for r in rs if next(s for s in ss if s.capability_id==r.capability_id).wave==1))
dom=tuple(DomainReceipt(d,sha({'d':d}),True,sha({'e':d}),sha({'f':d})) for d in REQUIRED_DOMAINS)
report={'version':'4.2.0','phase1_qualification_identity':'v2.8.0','sealed_skeletons':len(ss),'sealed_root':assert_non_executable(ss),'all_non_executable':all(not s.executable for s in ss),'reference_conformance_passed':sum(r.passed for r in rs),'conformance_matrix_root':conformance_matrix(rs)['matrix_root'],'cross_domain_reference_qualified':qualify(dom).qualified,'wave1_currently_allowed':blocked.allowed,'wave1_block_reasons':list(blocked.reasons),'phase2_runtime_started':False,'truth_boundary':'Reference contracts and synthetic conformance evidence only. Phase 1 remains 30/32 locally; no Phase-2 runtime or production capability is started or authorized.'}
report['report_root']=sha(report)
out=ROOT/'evidence/phase2-sealed-v4.2.0/preflight.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps(report,indent=2,sort_keys=True))
