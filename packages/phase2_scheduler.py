from __future__ import annotations
from dataclasses import asdict,dataclass
from packages.phase2_constitution import sha
@dataclass(frozen=True)
class ResourceRequest:
    cpu_millis:int=0; memory_mb:int=0; gpu_units:int=0; browser_slots:int=0; device_slots:int=0; max_runtime_s:int=0
@dataclass(frozen=True)
class Quota:
    cpu_millis:int; memory_mb:int; gpu_units:int; browser_slots:int; device_slots:int; max_runtime_s:int

def admit(req:ResourceRequest,quota:Quota)->tuple[bool,tuple[str,...]]:
    r=[]
    for k in ('cpu_millis','memory_mb','gpu_units','browser_slots','device_slots','max_runtime_s'):
        v=getattr(req,k); q=getattr(quota,k)
        if v<0:r.append('negative:'+k)
        if v>q:r.append('quota:'+k)
    return not r,tuple(r)

def placement_key(workspace_id:str,mission_id:str,capability_id:str,req:ResourceRequest)->str:
    return sha({'workspace_id':workspace_id,'mission_id':mission_id,'capability_id':capability_id,'request':asdict(req)})
