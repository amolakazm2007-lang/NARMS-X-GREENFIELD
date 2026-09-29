from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Any

from packages.phase1_qualification import canonical, sha256_obj
from packages.phase1_attestation import verify_closure_attestation


@dataclass(frozen=True)
class ClosureChallenge:
    version: str
    source_root: str
    workflow_identity: str
    nonce: str
    scope: str = 'phase1-closure-handoff-challenge-v1'

    def __post_init__(self) -> None:
        if len(self.source_root) != 64 or len(self.nonce) < 32:
            raise ValueError('invalid closure challenge binding')

    @property
    def root(self) -> str:
        return sha256_obj(asdict(self))


def build_handoff_packet(report: dict[str, Any], attestation: dict[str, Any], challenge: ClosureChallenge) -> dict[str, Any]:
    verified = verify_closure_attestation(attestation, report, expected_workflow_identity=challenge.workflow_identity)
    if not verified['valid']:
        raise RuntimeError('handoff forbidden: invalid attestation: ' + ','.join(verified['reasons']))
    if report.get('version') != challenge.version:
        raise RuntimeError('handoff forbidden: version mismatch')
    if report.get('source_root') != challenge.source_root:
        raise RuntimeError('handoff forbidden: source root mismatch')
    body = {
        'phase': 'PHASE_1',
        'version': challenge.version,
        'source_root': challenge.source_root,
        'qualification_root': report['report_root'],
        'closure_attestation_root': attestation['attestation_root'],
        'workflow_identity': challenge.workflow_identity,
        'challenge_root': challenge.root,
        'nonce_digest': hashlib.sha256(challenge.nonce.encode()).hexdigest(),
        'scope': 'phase1-closure-handoff-packet-v1',
    }
    body['packet_root'] = sha256_obj(body)
    return body


def verify_handoff_packet(packet: dict[str, Any], report: dict[str, Any], attestation: dict[str, Any], challenge: ClosureChallenge) -> dict[str, Any]:
    reasons: list[str] = []
    av = verify_closure_attestation(attestation, report, expected_workflow_identity=challenge.workflow_identity)
    if not av['valid']:
        reasons.extend('attestation_' + r for r in av['reasons'])
    expected = {
        'phase': 'PHASE_1',
        'version': challenge.version,
        'source_root': challenge.source_root,
        'qualification_root': report.get('report_root'),
        'closure_attestation_root': attestation.get('attestation_root'),
        'workflow_identity': challenge.workflow_identity,
        'challenge_root': challenge.root,
        'nonce_digest': hashlib.sha256(challenge.nonce.encode()).hexdigest(),
        'scope': 'phase1-closure-handoff-packet-v1',
    }
    body = dict(packet); claimed = body.pop('packet_root', None)
    if body != expected:
        reasons.append('handoff_binding_mismatch')
    calculated = sha256_obj(expected)
    if claimed != calculated:
        reasons.append('handoff_packet_root_mismatch')
    if report.get('source_root') != challenge.source_root:
        reasons.append('handoff_source_root_mismatch')
    result = {'valid': not reasons, 'reasons': sorted(set(reasons)), 'packet_root': calculated, 'challenge_root': challenge.root}
    result['verification_root'] = sha256_obj(result)
    return result
