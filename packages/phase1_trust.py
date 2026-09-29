from __future__ import annotations
import hashlib
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

@dataclass(frozen=True)
class TrustKey:
    key_id:str
    public_key:bytes
    state:str='ACTIVE'  # ACTIVE, RETIRED, REVOKED

class QualificationTrustStore:
    def __init__(self,keys:list[TrustKey]):
        self._keys={k.key_id:k for k in keys}
        if len(self._keys)!=len(keys): raise ValueError('duplicate trust key id')
    @staticmethod
    def key_id(public_key:bytes)->str: return hashlib.sha256(public_key).hexdigest()[:24]
    def verify(self,key_id:str,message:bytes,signature:bytes)->bool:
        key=self._keys.get(key_id)
        if not key or key.state not in {'ACTIVE','RETIRED'}: return False
        try: Ed25519PublicKey.from_public_bytes(key.public_key).verify(signature,message); return True
        except Exception: return False
    def can_issue(self,key_id:str)->bool:
        key=self._keys.get(key_id); return bool(key and key.state=='ACTIVE')
