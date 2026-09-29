from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import scripts.phase1_qualify_v150 as base
VERSION='2.8.0'

if __name__=='__main__':
    raise SystemExit(base.main(version=VERSION))
