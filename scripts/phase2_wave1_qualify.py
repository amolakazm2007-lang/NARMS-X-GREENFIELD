from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.phase2_wave1 import PostgresWave1Runtime, load_opening, root

EXPECTED_TABLES = {
    "phase2_schema_migrations",
    "phase2_workspace_runtime",
    "phase2_mission_workspace",
    "phase2_mission_history",
    "phase2_capability_registry",
    "phase2_capability_history",
}
EXPECTED_INDEXES = {
    "idx_phase2_mission_workspace_workspace_state",
    "idx_phase2_mission_history_mission_seq",
    "idx_phase2_capability_registry_state",
    "idx_phase2_capability_history_capability_seq",
}


def run(cmd: list[str]) -> dict[str, Any]:
    p = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"command": cmd, "returncode": p.returncode, "output_tail": p.stdout[-4000:]}


def main() -> int:
    dsn = os.getenv("NARMS_PHASE2_POSTGRES_DSN") or os.getenv("NARMS_PHASE1_POSTGRES_DSN")
    if not dsn:
        raise SystemExit("real PostgreSQL DSN required")
    opening = load_opening()
    runtime = PostgresWave1Runtime(dsn)
    runtime.migrate()
    with psycopg.connect(dsn) as conn:
        server = conn.execute("SHOW server_version").fetchone()
        if not server or not str(server[0]).startswith("16"):
            raise SystemExit(f"PostgreSQL 16 required; got {server}")
        table_rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
            "AND table_name LIKE 'phase2_%' ORDER BY table_name"
        ).fetchall()
        index_rows = conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
            "AND indexname LIKE 'idx_phase2_%' ORDER BY indexname"
        ).fetchall()
    tables = {x[0] for x in table_rows}
    indexes = {x[0] for x in index_rows}
    # Qualification owns a clean Wave-1 schema before rerunning the stateful real tests.
    # Phase-1 tables remain intact; only Wave-1 state is reset.
    runtime.rollback()
    runtime.migrate()

    gates = {
        "OPENING_TRUST": bool(opening.opening_decision_root),
        "PYTHON_311": platform.python_version().startswith("3.11."),
        "POSTGRES_16": bool(server and str(server[0]).startswith("16")),
        "WAVE1_TABLES": EXPECTED_TABLES <= tables,
        "WAVE1_INDEXES": EXPECTED_INDEXES <= indexes,
        "MYPY": run(["mypy", "--python-version", "3.11", "--explicit-package-bases", "packages/phase2_wave1.py", "tests/test_phase2_wave1.py"])["returncode"] == 0,
        "PYTEST": run([sys.executable, "-m", "pytest", "-q", "tests/test_phase2_wave1.py"])["returncode"] == 0,
        "RUNTIME_HEALTH": runtime.health()["status"] == "PASS",
    }
    report = {
        "scope": "phase2-wave1-real-qualification-v1",
        "wave": 1,
        "status": "PASS" if all(gates.values()) else "FAIL",
        "gates": gates,
        "passed": sum(gates.values()),
        "total": len(gates),
        "opening_decision_root": opening.opening_decision_root,
        "runtime_health": runtime.health(),
        "tables": sorted(tables),
        "indexes": sorted(indexes),
    }
    report["report_root"] = root(report)
    out = ROOT / "evidence/phase2-wave1-v1/qualification-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
