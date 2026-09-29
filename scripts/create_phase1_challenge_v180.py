#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, secrets
from pathlib import Path
from packages.phase1_handoff import ClosureChallenge

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--source-root',required=True); ap.add_argument('--output',required=True); ns=ap.parse_args()
    c=ClosureChallenge('1.8.0',ns.source_root,'phase1-closure.yml@v1.8.0',secrets.token_hex(32))
    Path(ns.output).write_text(json.dumps({'version':c.version,'source_root':c.source_root,'workflow_identity':c.workflow_identity,'nonce':c.nonce,'scope':c.scope},indent=2,sort_keys=True)+'\n')
    print(c.root); return 0
if __name__=='__main__': raise SystemExit(main())
