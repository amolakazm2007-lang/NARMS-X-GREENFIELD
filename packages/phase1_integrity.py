from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from packages.phase1_qualification import REQUIRED_GATES, sha256_obj
from packages.phase1_attestation import verify_closure_attestation
from packages.phase1_handoff import ClosureChallenge, verify_handoff_packet

_EXCLUDED_PARTS = {'.git', '__pycache__', '.pytest_cache', 'node_modules', 'dist'}
_EXCLUDED_FILES = {'MANIFEST.sha256'}


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _EXCLUDED_PARTS for part in rel.parts):
            continue
        if rel.as_posix().startswith('evidence/'):
            continue
        if path.name in _EXCLUDED_FILES:
            continue
        yield path


@dataclass(frozen=True)
class SourceSnapshot:
    algorithm: str
    files: tuple[tuple[str, int, str], ...]
    root: str


def build_source_snapshot(root: Path) -> SourceSnapshot:
    entries = tuple((p.relative_to(root).as_posix(), p.stat().st_size, _file_sha256(p)) for p in iter_source_files(root))
    body = {'algorithm': 'sha256-path-size-content-v1', 'files': entries}
    return SourceSnapshot(body['algorithm'], entries, sha256_obj(body))


def verify_source_snapshot(root: Path, snapshot: SourceSnapshot) -> dict[str, Any]:
    current = build_source_snapshot(root)
    expected = {p: (size, digest) for p, size, digest in snapshot.files}
    actual = {p: (size, digest) for p, size, digest in current.files}
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    changed = sorted(p for p in set(expected) & set(actual) if expected[p] != actual[p])
    result = {
        'valid': not (missing or unexpected or changed) and hmac.compare_digest(snapshot.root, current.root),
        'expected_root': snapshot.root,
        'actual_root': current.root,
        'missing': missing,
        'unexpected': unexpected,
        'changed': changed,
    }
    result['verification_root'] = sha256_obj(result)
    return result


def verify_evidence_graph(report: dict[str, Any], attestation: dict[str, Any], packet: dict[str, Any], challenge: ClosureChallenge) -> dict[str, Any]:
    reasons: list[str] = []
    gates = report.get('gates', {})
    evidence = report.get('evidence', {})
    if set(gates) != set(REQUIRED_GATES):
        reasons.append('gate_set_mismatch')
    for gate in REQUIRED_GATES:
        if gates.get(gate) != 'PASS':
            reasons.append(f'gate_not_pass:{gate}')
        item = evidence.get(gate)
        if not isinstance(item, dict):
            reasons.append(f'evidence_missing:{gate}')
            continue
        if item.get('gate') != gate or item.get('status') != 'PASS':
            reasons.append(f'evidence_status_mismatch:{gate}')
    av = verify_closure_attestation(attestation, report, expected_workflow_identity=challenge.workflow_identity)
    if not av['valid']:
        reasons.extend('attestation:' + r for r in av['reasons'])
    hv = verify_handoff_packet(packet, report, attestation, challenge)
    if not hv['valid']:
        reasons.extend('handoff:' + r for r in hv['reasons'])
    if packet.get('qualification_root') != report.get('report_root'):
        reasons.append('qualification_root_disconnected')
    if packet.get('closure_attestation_root') != attestation.get('attestation_root'):
        reasons.append('attestation_root_disconnected')
    result = {
        'valid': not reasons,
        'reasons': sorted(set(reasons)),
        'qualification_root': report.get('report_root'),
        'attestation_root': attestation.get('attestation_root'),
        'handoff_root': packet.get('packet_root'),
        'challenge_root': challenge.root,
    }
    result['graph_root'] = sha256_obj(result)
    return result


@dataclass(frozen=True)
class PromotionRequest:
    version: str
    source_snapshot_root: str
    qualification_root: str
    attestation_root: str
    handoff_root: str
    challenge_root: str
    trust_policy_root: str
    scope: str = 'phase1-external-promotion-request-v1'

    @property
    def root(self) -> str:
        return sha256_obj(asdict(self))


def build_promotion_request(*, version: str, snapshot: SourceSnapshot, evidence_graph: dict[str, Any], trust_policy_root: str) -> PromotionRequest:
    if not evidence_graph.get('valid'):
        raise RuntimeError('promotion request forbidden: evidence graph invalid')
    if not trust_policy_root or len(trust_policy_root) != 64:
        raise ValueError('invalid trust policy root')
    return PromotionRequest(
        version=version,
        source_snapshot_root=snapshot.root,
        qualification_root=str(evidence_graph['qualification_root']),
        attestation_root=str(evidence_graph['attestation_root']),
        handoff_root=str(evidence_graph['handoff_root']),
        challenge_root=str(evidence_graph['challenge_root']),
        trust_policy_root=trust_policy_root,
    )
