from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packages.phase2_constitution import Phase2Constitution,constitution_report,validate_transition
from packages.phase2_protocols import WorkerEnvelope,ToolEnvelope
from packages.phase2_scheduler import ResourceRequest,Quota,admit
from packages.phase2_recovery import decide
from packages.phase2_opening import evaluate
from packages.phase2_design import load_catalog
catalog=load_catalog(ROOT/'docs/phase2/capability-catalog.json')
worker=WorkerEnvelope('worker-v1','worker-ref','build.test','ws','mission','job',0,7,'lease','input','policy','trace',30000)
tool=ToolEnvelope('tool-v1','repo.read','1','ws','mission','invoke','read','args','policy',None,'idem','trace')
opening=evaluate(certificate=None,report={'gates':{},'blockers':{}},attestation=None,trusted_public_key_hex=None,catalog=catalog)
out={
 'release_version':'3.6.0','phase1_local_status':'30/32 BLOCKED','phase2_runtime_started':False,
 'implementation_allowed':False,'constitution_root':Phase2Constitution().root,
 'constitution_report_root':constitution_report()['root'],'worker_contract_valid':worker.validate()[0],
 'worker_root':worker.root,'tool_contract_valid':tool.validate()[0],'tool_root':tool.root,
 'success_transition_without_evidence_allowed':validate_transition('RUNNING','SUCCEEDED',{})[0],
 'quota_overage_allowed':admit(ResourceRequest(gpu_units=2),Quota(4000,8192,1,1,1,3600))[0],
 'unsafe_non_idempotent_replay_action':decide(attempt=1,max_attempts=3,lease_expired=True,checkpoint_present=False,idempotent=False,side_effect_committed=False).action,
 'phase2_opening_allowed_without_trusted_phase1_certificate':opening.allowed,
 'phase2_opening_reasons':list(opening.reasons),'phase2_opening_root':opening.root,
}
p=ROOT/'evidence/phase2-contract-v3.6.0'; p.mkdir(parents=True,exist_ok=True); (p/'preflight.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,indent=2,sort_keys=True))
