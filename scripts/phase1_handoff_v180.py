#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from packages.phase1_handoff import ClosureChallenge, build_handoff_packet, verify_handoff_packet


def load(p: str): return json.loads(Path(p).read_text())

def main() -> int:
    ap=argparse.ArgumentParser(description='Build/verify Phase-1 v1.8 closure handoff packet')
    ap.add_argument('--report', required=True); ap.add_argument('--attestation', required=True)
    ap.add_argument('--challenge', required=True); ap.add_argument('--output', required=True)
    ns=ap.parse_args(); r=load(ns.report); a=load(ns.attestation); c=ClosureChallenge(**load(ns.challenge))
    packet=build_handoff_packet(r,a,c); v=verify_handoff_packet(packet,r,a,c)
    if not v['valid']: raise SystemExit('handoff verification failed: '+','.join(v['reasons']))
    Path(ns.output).write_text(json.dumps(packet,indent=2,sort_keys=True)+'\n')
    print(packet['packet_root']); return 0
if __name__=='__main__': raise SystemExit(main())
