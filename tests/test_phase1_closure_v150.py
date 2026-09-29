from pathlib import Path
import pytest
from packages.phase1_closure import closure_environment, postgres_migration_qualification, python_typecheck

ROOT=Path(__file__).resolve().parents[1]

def test_closure_environment_is_explicit():
    x=closure_environment(); assert set(x)=={'python_version','python_311_exact','mypy','psql','postgres_dsn_present'}

def test_python_typecheck_fails_closed_when_unavailable(monkeypatch):
    import packages.phase1_closure as m
    monkeypatch.setattr(m.shutil,'which',lambda _:None)
    with pytest.raises(RuntimeError,match='typechecker unavailable'): python_typecheck(ROOT)

def test_postgres_requires_real_dsn():
    with pytest.raises(RuntimeError,match='DSN is required'): postgres_migration_qualification(ROOT,'')

def test_down_migration_is_transactional_and_complete():
    s=(ROOT/'migrations/0001_phase1.down.sql').read_text()
    assert s.startswith('BEGIN;') and s.rstrip().endswith('COMMIT;')
    assert s.count('DROP TABLE IF EXISTS')==16

def test_certificate_refuses_30_of_32_report():
    from packages.phase1_closure import issue_phase1_certificate_from_report
    from packages.phase1_qualification import REQUIRED_GATES
    report={'version':'1.5.0','report_root':'r','source_root':'s','gates':{g:'PASS' for g in REQUIRED_GATES},'blockers':{'DB_MIGRATIONS':'blocked'}}
    report['gates']['DB_MIGRATIONS']='BLOCKED'
    with pytest.raises(RuntimeError,match='32/32'): issue_phase1_certificate_from_report(report,'00'*32)
