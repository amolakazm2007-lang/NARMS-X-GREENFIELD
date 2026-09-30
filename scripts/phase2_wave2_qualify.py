from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packages.phase2_wave2 import PostgresWave2Runtime, root

EXPECTED_TABLES={
 "phase2_workers","phase2_worker_leases","phase2_tool_registry","phase2_tool_approval_bindings",
 "phase2_tool_calls","phase2_artifact_objects","phase2_artifact_revisions","phase2_artifact_edges",
 "phase2_wave2_idempotency","phase2_wave2_quotas",
}
EXPECTED_INDEXES={
 "idx_phase2_workers_workspace_state","idx_phase2_worker_leases_job_state","idx_phase2_worker_leases_expiry",
 "idx_phase2_tool_calls_mission_state","idx_phase2_artifact_revisions_mission","idx_phase2_artifact_edges_child",
 "uq_phase2_active_job_lease",
}

def run(cmd:list[str])->dict[str,Any]:
 p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 return {"command":cmd,"returncode":p.returncode,"output_tail":p.stdout[-6000:]}

def main()->int:
 dsn=os.getenv("NARMS_PHASE2_POSTGRES_DSN") or os.getenv("NARMS_PHASE1_POSTGRES_DSN")
 if not dsn: raise SystemExit("real PostgreSQL DSN required")
 rt=PostgresWave2Runtime(dsn); rt.migrate(); rt.bootstrap_capabilities()
 with psycopg.connect(dsn) as conn:
  server=conn.execute("SHOW server_version").fetchone()
  tables={x[0] for x in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'phase2_%'").fetchall()}
  indexes={x[0] for x in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND indexname LIKE '%phase2_%'").fetchall()}
  migration=conn.execute("SELECT name FROM phase2_schema_migrations WHERE version=3").fetchone()
 mypy=run(["mypy","--python-version","3.11","--explicit-package-bases","packages/phase2_wave2.py","tests/test_phase2_wave2.py","tests/test_phase2_wave2_concurrency.py","tests/test_phase2_wave2_adversarial.py","scripts/phase2_wave2_qualify.py"])
 pytest=run([sys.executable,"-m","pytest","-q","tests/test_phase2_wave2.py","tests/test_phase2_wave2_concurrency.py","tests/test_phase2_wave2_adversarial.py"])
 arch=run([sys.executable,"scripts/architecture_doctor.py"])
 gates={
  "PYTHON_311":platform.python_version().startswith("3.11."),
  "POSTGRES_16":bool(server and str(server[0]).startswith("16")),
  "MIGRATION_V3":bool(migration and migration[0]=="phase2-wave2-v1"),
  "WAVE2_TABLES":EXPECTED_TABLES<=tables,
  "WAVE2_INDEXES":EXPECTED_INDEXES<=indexes,
  "MYPY":mypy["returncode"]==0,
  "PYTEST_REAL_POSTGRES":pytest["returncode"]==0,
  "ARCHITECTURE":arch["returncode"]==0,
  "RUNTIME_HEALTH":rt.health()["status"]=="PASS",
 }
 report={"scope":"phase2-wave2-real-qualification-v1","wave":2,"status":"PASS" if all(gates.values()) else "FAIL",
         "gates":gates,"passed":sum(gates.values()),"total":len(gates),"tables":sorted(EXPECTED_TABLES),
         "indexes":sorted(EXPECTED_INDEXES),"runtime_health":rt.health(),
         "tool_outputs":{"mypy":mypy,"pytest":pytest,"architecture":arch},
         "production_evidence":"real-ci-postgresql-16-required"}
 report["report_root"]=root(report)
 out=ROOT/"evidence/phase2-wave2-v1/qualification-report.json"; out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps(report,indent=2,sort_keys=True))
 return 0 if report["status"]=="PASS" else 1

if __name__=="__main__": raise SystemExit(main())
