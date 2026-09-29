from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from packages.phase1_qualification import REQUIRED_GATES, canonical, sha256_obj


@dataclass(frozen=True)
class Phase1TrustPolicy:
    trusted_public_key_hex: str
    expected_scope: str = 'phase1-complete-phase2-may-open'

    def __post_init__(self) -> None:
        raw = bytes.fromhex(self.trusted_public_key_hex)
        if len(raw) != 32:
            raise ValueError('trusted Phase-1 Ed25519 public key must be 32 bytes')

    @property
    def root(self) -> str:
        return sha256_obj({'trusted_public_key_hex': self.trusted_public_key_hex, 'expected_scope': self.expected_scope})


def verify_phase1_certificate(certificate: dict[str, Any], report: dict[str, Any], policy: Phase1TrustPolicy) -> dict[str, Any]:
    reasons: list[str] = []
    body = certificate.get('body')
    if not isinstance(body, dict):
        reasons.append('certificate_body_invalid')
        body = {}
    gates = report.get('gates', {})
    if set(gates) != set(REQUIRED_GATES) or any(gates.get(g) != 'PASS' for g in REQUIRED_GATES):
        reasons.append('qualification_not_32_of_32')
    if report.get('blockers'):
        reasons.append('qualification_blockers_present')
    expected = {
        'phase': 'PHASE_1',
        'version': report.get('version'),
        'qualification_root': report.get('report_root'),
        'source_root': report.get('source_root'),
        'scope': policy.expected_scope,
    }
    if body != expected:
        reasons.append('certificate_body_binding_mismatch')
    embedded = certificate.get('public_key', '')
    if not isinstance(embedded, str) or not hmac.compare_digest(embedded.lower(), policy.trusted_public_key_hex.lower()):
        reasons.append('certificate_public_key_not_trusted')
    body_bytes = canonical(body)
    fingerprint = hashlib.sha256(body_bytes).hexdigest()
    if not hmac.compare_digest(str(certificate.get('fingerprint', '')).lower(), fingerprint):
        reasons.append('certificate_fingerprint_mismatch')
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(policy.trusted_public_key_hex)).verify(
            bytes.fromhex(str(certificate.get('signature', ''))), body_bytes
        )
    except Exception:
        reasons.append('certificate_signature_invalid')
    result = {
        'phase2_allowed': not reasons,
        'reasons': sorted(set(reasons)),
        'certificate_fingerprint': fingerprint,
        'qualification_root': report.get('report_root'),
        'source_root': report.get('source_root'),
        'trust_policy_root': policy.root,
    }
    result['unlock_root'] = sha256_obj(result)
    return result


def assert_phase2_unlocked(certificate: dict[str, Any], report: dict[str, Any], policy: Phase1TrustPolicy) -> str:
    result = verify_phase1_certificate(certificate, report, policy)
    if not result['phase2_allowed']:
        raise RuntimeError('Phase 2 locked: ' + ','.join(result['reasons']))
    return result['unlock_root']


def scan_forbidden_phase2_implementation(root: Path, policy_document: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for rel in policy_document['phase1_forbidden_implementation_roots']:
        directory = root / rel
        if not directory.exists():
            continue
        for item in directory.rglob('*'):
            if item.is_file() and item.name not in {'.gitkeep', 'README.md'}:
                violations.append(item.relative_to(root).as_posix())
    return sorted(violations)
