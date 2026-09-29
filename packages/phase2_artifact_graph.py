from __future__ import annotations
from dataclasses import asdict,dataclass
from packages.phase2_constitution import sha
@dataclass(frozen=True)
class ArtifactNode:
    artifact_id:str; sha256:str; kind:str; producer_job_id:str; input_roots:tuple[str,...]; evidence_roots:tuple[str,...]
@dataclass(frozen=True)
class ArtifactGraph:
    nodes:tuple[ArtifactNode,...]
    def validate(self)->tuple[bool,tuple[str,...]]:
        r=[]; ids=set(); hashes=set()
        for n in self.nodes:
            if n.artifact_id in ids:r.append('duplicate_artifact_id:'+n.artifact_id)
            ids.add(n.artifact_id)
            if len(n.sha256)!=64:r.append('invalid_sha256:'+n.artifact_id)
            if not n.producer_job_id:r.append('missing_producer:'+n.artifact_id)
            hashes.add(n.sha256)
        for n in self.nodes:
            for x in n.input_roots:
                if x not in hashes:r.append('unknown_input_root:'+n.artifact_id)
        return not r,tuple(sorted(set(r)))
    @property
    def root(self)->str:return sha({'nodes':[asdict(n) for n in sorted(self.nodes,key=lambda x:x.artifact_id)]})
