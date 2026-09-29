from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from packages.phase1_qualification import REQUIRED_GATES, canonical, sha256_obj


def _version(cmd: list[str]) -> str | None:
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return p.stdout.strip().splitlines()[0][:500] if p.stdout.strip() else None


@dataclass(frozen=True)
class ToolchainReceipt:
    python: str
    node: str | None
    npm: str | None
    python_typechecker: str | None
    psql: str | None
    postgres_server: str | None

    @property
    def root(self) -> str:
        return sha256_obj(asdict(self))


def capture_toolchain_receipt() -> ToolchainReceipt:
    mypy = _version(['mypy', '--version'])
    return ToolchainReceipt(
        python=platform.python_version(),
        node=_version(['node', '--version']),
        npm=_version(['npm', '--version']),
        python_typechecker=mypy,
        psql=_version(['psql', '--version']),
        postgres_server=_version(['postgres', '--version']),
    )


def gate_evidence_roots(report: dict[str, Any]) -> dict[str, str]:
    evidence = report.get('evidence')
    if not isinstance(evidence, dict):
        raise ValueError('qualification evidence missing')
    roots: dict[str, str] = {}
    for gate in REQUIRED_GATES:
        payload = evidence.get(gate)
        if not isinstance(payload, dict):
            raise ValueError(f'missing evidence for {gate}')
        roots[gate] = sha256_obj(payload)
    return roots


def build_closure_attestation(report: dict[str, Any], toolchain: ToolchainReceipt, *, workflow_identity: str) -> dict[str, Any]:
    gates = report.get('gates', {})
    if set(gates) != set(REQUIRED_GATES) or any(gates.get(g) != 'PASS' for g in REQUIRED_GATES):
        raise ValueError('closure attestation requires 32/32 PASS')
    if report.get('blockers'):
        raise ValueError('closure attestation refuses qualification blockers')
    if not report.get('report_root') or not report.get('source_root'):
        raise ValueError('qualification roots missing')
    roots = gate_evidence_roots(report)
    body = {
        'phase': 'PHASE_1',
        'version': report.get('version'),
        'qualification_root': report['report_root'],
        'source_root': report['source_root'],
        'gate_evidence_roots': roots,
        'toolchain': asdict(toolchain),
        'toolchain_root': toolchain.root,
        'workflow_identity': workflow_identity,
        'scope': 'phase1-closure-attestation-v1',
    }
    body['attestation_root'] = sha256_obj(body)
    return body


def verify_closure_attestation(attestation: dict[str, Any], report: dict[str, Any], *, expected_workflow_identity: str | None = None) -> dict[str, Any]:
    reasons: list[str] = []
    if attestation.get('phase') != 'PHASE_1': reasons.append('attestation_phase_mismatch')
    if attestation.get('version') != report.get('version'): reasons.append('attestation_version_mismatch')
    if attestation.get('qualification_root') != report.get('report_root'): reasons.append('attestation_qualification_root_mismatch')
    if attestation.get('source_root') != report.get('source_root'): reasons.append('attestation_source_root_mismatch')
    if attestation.get('scope') != 'phase1-closure-attestation-v1': reasons.append('attestation_scope_mismatch')
    if expected_workflow_identity is not None and attestation.get('workflow_identity') != expected_workflow_identity:
        reasons.append('attestation_workflow_identity_mismatch')
    try:
        expected_gate_roots = gate_evidence_roots(report)
    except ValueError:
        expected_gate_roots = {}
        reasons.append('attestation_report_evidence_invalid')
    if attestation.get('gate_evidence_roots') != expected_gate_roots:
        reasons.append('attestation_gate_evidence_mismatch')
    toolchain = attestation.get('toolchain')
    if not isinstance(toolchain, dict):
        reasons.append('attestation_toolchain_invalid')
    elif attestation.get('toolchain_root') != sha256_obj(toolchain):
        reasons.append('attestation_toolchain_root_mismatch')
    body = dict(attestation); claimed = body.pop('attestation_root', None)
    calculated = sha256_obj(body)
    if claimed != calculated: reasons.append('attestation_root_mismatch')
    return {'valid': not reasons, 'reasons': sorted(set(reasons)), 'attestation_root': calculated}


def issue_attested_phase1_certificate(report: dict[str, Any], attestation: dict[str, Any], private_key_hex: str) -> dict[str, Any]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    verified = verify_closure_attestation(attestation, report)
    if not verified['valid']:
        raise RuntimeError('certificate forbidden: invalid closure attestation: ' + ','.join(verified['reasons']))
    gates = report.get('gates', {})
    if set(gates) != set(REQUIRED_GATES) or any(gates.get(g) != 'PASS' for g in REQUIRED_GATES) or report.get('blockers'):
        raise RuntimeError('certificate forbidden: qualification is not 32/32 PASS')
    key_bytes = bytes.fromhex(private_key_hex)
    if len(key_bytes) != 32:
        raise ValueError('Ed25519 private key must be 32 raw bytes encoded as hex')
    body = {
        'phase': 'PHASE_1',
        'version': report['version'],
        'qualification_root': report['report_root'],
        'source_root': report['source_root'],
        'closure_attestation_root': attestation['attestation_root'],
        'scope': 'phase1-attested-complete-phase2-may-open-v1',
    }
    raw = canonical(body)
    key = Ed25519PrivateKey.from_private_bytes(key_bytes)
    return {
        'body': body,
        'fingerprint': hashlib.sha256(raw).hexdigest(),
        'signature': key.sign(raw).hex(),
        'public_key': key.public_key().public_bytes_raw().hex(),
    }


def verify_attested_phase1_certificate(certificate: dict[str, Any], report: dict[str, Any], attestation: dict[str, Any], trusted_public_key_hex: str) -> dict[str, Any]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    reasons: list[str] = []
    av = verify_closure_attestation(attestation, report)
    if not av['valid']:
        reasons.extend('closure_' + x for x in av['reasons'])
    expected = {
        'phase': 'PHASE_1', 'version': report.get('version'),
        'qualification_root': report.get('report_root'), 'source_root': report.get('source_root'),
        'closure_attestation_root': attestation.get('attestation_root'),
        'scope': 'phase1-attested-complete-phase2-may-open-v1',
    }
    body = certificate.get('body')
    if body != expected: reasons.append('certificate_body_binding_mismatch')
    if str(certificate.get('public_key','')).lower() != trusted_public_key_hex.lower():
        reasons.append('certificate_public_key_not_trusted')
    raw = canonical(body if isinstance(body, dict) else {})
    fp = hashlib.sha256(raw).hexdigest()
    if certificate.get('fingerprint') != fp: reasons.append('certificate_fingerprint_mismatch')
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted_public_key_hex)).verify(bytes.fromhex(str(certificate.get('signature',''))), raw)
    except Exception:
        reasons.append('certificate_signature_invalid')
    result={'phase2_allowed':not reasons,'reasons':sorted(set(reasons)),'certificate_fingerprint':fp,
            'qualification_root':report.get('report_root'),'source_root':report.get('source_root'),
            'closure_attestation_root':attestation.get('attestation_root')}
    result['unlock_root']=sha256_obj(result)
    return result
