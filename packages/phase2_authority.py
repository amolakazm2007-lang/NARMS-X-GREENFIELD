from __future__ import annotations
import hashlib
from dataclasses import dataclass,asdict
from typing import Any
from packages.phase2_constitution import canonical,sha
from packages.phase2_admission import WaveAdmissionDecision

@dataclass(frozen=True)
class AdmissionCertificateBody:
    wave:int; opening_root:str; catalog_root:str; decision_root:str; prior_certificate_root:str|None; scope:str='phase2-wave-admission-certificate-v1'

def issue(decision:WaveAdmissionDecision,private_key_hex:str,prior_certificate_root:str|None=None)->dict[str,Any]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if not decision.allowed or not decision.opening_root: raise RuntimeError('admission certificate forbidden')
    body=asdict(AdmissionCertificateBody(decision.wave,decision.opening_root,decision.catalog_root,decision.root,prior_certificate_root))
    raw=canonical(body); key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    return {'body':body,'fingerprint':hashlib.sha256(raw).hexdigest(),'signature':key.sign(raw).hex(),'public_key':key.public_key().public_bytes_raw().hex()}

def verify(cert:dict[str,Any],trusted_public_key_hex:str,decision:WaveAdmissionDecision,prior_certificate_root:str|None=None)->dict[str,Any]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    reasons=[]; body=cert.get('body')
    expected=asdict(AdmissionCertificateBody(decision.wave,decision.opening_root or '',decision.catalog_root,decision.root,prior_certificate_root))
    if body!=expected: reasons.append('body_binding_mismatch')
    if str(cert.get('public_key','')).lower()!=trusted_public_key_hex.lower(): reasons.append('untrusted_key')
    raw=canonical(body if isinstance(body,dict) else {})
    if cert.get('fingerprint')!=hashlib.sha256(raw).hexdigest(): reasons.append('fingerprint_mismatch')
    try: Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted_public_key_hex)).verify(bytes.fromhex(str(cert.get('signature',''))),raw)
    except Exception: reasons.append('signature_invalid')
    if not decision.allowed: reasons.append('decision_not_allowed')
    return {'valid':not reasons,'reasons':tuple(sorted(set(reasons))),'certificate_root':sha(cert)}
