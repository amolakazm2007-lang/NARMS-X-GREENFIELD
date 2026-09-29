from __future__ import annotations
import hashlib, secrets, time
from dataclasses import dataclass

@dataclass(frozen=True)
class RateLimitPolicy:
    capacity: int = 5
    window_seconds: int = 60

class FixedWindowLimiter:
    """Deterministic reference limiter. Production deployment may replace storage, not semantics."""
    def __init__(self, policy: RateLimitPolicy = RateLimitPolicy()):
        if policy.capacity < 1 or policy.window_seconds < 1: raise ValueError('invalid rate limit policy')
        self.policy=policy; self._state: dict[str, tuple[int,int]]={}
    def allow(self,key:str,now:float|None=None)->bool:
        now=time.time() if now is None else now; bucket=int(now//self.policy.window_seconds)
        old_bucket,count=self._state.get(key,(bucket,0))
        if old_bucket!=bucket: count=0
        if count>=self.policy.capacity: self._state[key]=(bucket,count); return False
        self._state[key]=(bucket,count+1); return True

@dataclass(frozen=True)
class RequestBudget:
    max_body_bytes:int=64*1024
    max_text_chars:int=20_000
    def validate_bytes(self,payload:bytes)->None:
        if len(payload)>self.max_body_bytes: raise ValueError('request body budget exceeded')
    def validate_text(self,text:str)->None:
        if len(text)>self.max_text_chars: raise ValueError('request text budget exceeded')

def fingerprint_secret(secret:str)->str:
    return hashlib.sha256(secret.encode()).hexdigest()

def new_capability(nbytes:int=32)->str:
    return secrets.token_urlsafe(nbytes)
