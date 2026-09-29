from __future__ import annotations
from collections import namedtuple
from pathlib import Path
import pytest
import packages.phase1_closure as c
ROOT=Path(__file__).resolve().parents[1]

V=namedtuple('V','major minor micro releaselevel serial')

def test_pyright_is_not_accepted_as_real_closure_typechecker(monkeypatch):
    monkeypatch.setattr(c.shutil,'which',lambda name:'/usr/bin/pyright' if name=='pyright' else None)
    with pytest.raises(RuntimeError,match='install mypy'):
        c.python_typecheck(ROOT)

def test_real_typecheck_requires_python_311(monkeypatch):
    monkeypatch.setattr(c.shutil,'which',lambda name:'/usr/bin/mypy' if name=='mypy' else None)
    monkeypatch.setattr(c.sys,'version_info',V(3,12,0,'final',0))
    with pytest.raises(RuntimeError,match='Python 3.11 exactly'):
        c.python_typecheck(ROOT)

def test_real_db_gate_rejects_non_16_psql(monkeypatch):
    monkeypatch.setattr(c.shutil,'which',lambda name:'/usr/bin/psql' if name=='psql' else None)
    monkeypatch.setattr(c,'_run',lambda *a,**k:(0,'psql (PostgreSQL) 15.9'))
    with pytest.raises(RuntimeError,match='psql major version 16'):
        c.postgres_migration_qualification(ROOT,'postgresql://example')

def test_real_db_gate_rejects_non_16_server(monkeypatch):
    monkeypatch.setattr(c.shutil,'which',lambda name:'/usr/bin/psql' if name=='psql' else None)
    monkeypatch.setattr(c,'_run',lambda *a,**k:(0,'psql (PostgreSQL) 16.4'))
    monkeypatch.setattr(c,'_psql',lambda root,dsn,sql:(0,'15.9') if sql=='SHOW server_version;' else (0,''))
    with pytest.raises(RuntimeError,match='server major version 16'):
        c.postgres_migration_qualification(ROOT,'postgresql://example')
