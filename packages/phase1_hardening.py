from __future__ import annotations
import hashlib, hmac, json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode('utf-8')).hexdigest()


def constant_time_secret_match(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(secret_hash(secret), expected_hash)

@dataclass(frozen=True)
class SourceBinding:
    source_root: str
    policy_root: str
    contracts_root: str
    migration_root: str

    @property
    def root(self) -> str:
        return sha256_obj(asdict(self))

@dataclass(frozen=True)
class EvidenceFreshness:
    gate: str
    evidence_root: str
    source_binding_root: str
    fresh: bool
    reason: str


def tree_root(root: Path, rel: str) -> str:
    base = root / rel
    rows: list[str] = []
    if base.is_file():
        return hashlib.sha256(base.read_bytes()).hexdigest()
    if not base.exists():
        return hashlib.sha256(b'ABSENT').hexdigest()
    for p in sorted(x for x in base.rglob('*') if x.is_file() and '__pycache__' not in x.parts):
        rows.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(base).as_posix()}")
    return hashlib.sha256('\n'.join(rows).encode()).hexdigest()


def build_source_binding(root: Path, source_root: str) -> SourceBinding:
    return SourceBinding(
        source_root=source_root,
        policy_root=tree_root(root, 'docs/architecture-policy.json'),
        contracts_root=tree_root(root, 'contracts'),
        migration_root=tree_root(root, 'migrations'),
    )


def bind_gate_evidence(gate: str, payload: Any, binding: SourceBinding) -> dict[str, Any]:
    body = {'gate': gate, 'payload': payload, 'source_binding_root': binding.root}
    return {**body, 'evidence_root': sha256_obj(body)}


def verify_bound_gate_evidence(receipt: dict[str, Any], binding: SourceBinding) -> EvidenceFreshness:
    gate = str(receipt.get('gate', ''))
    claimed = str(receipt.get('evidence_root', ''))
    expected_binding = binding.root
    actual_binding = str(receipt.get('source_binding_root', ''))
    body = {'gate': gate, 'payload': receipt.get('payload'), 'source_binding_root': actual_binding}
    expected_evidence = sha256_obj(body)
    if actual_binding != expected_binding:
        return EvidenceFreshness(gate, claimed, actual_binding, False, 'source-binding-mismatch')
    if not hmac.compare_digest(claimed, expected_evidence):
        return EvidenceFreshness(gate, claimed, actual_binding, False, 'evidence-root-mismatch')
    return EvidenceFreshness(gate, claimed, actual_binding, True, 'fresh')
