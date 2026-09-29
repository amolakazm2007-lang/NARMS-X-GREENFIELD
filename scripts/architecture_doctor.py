from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[1]
p=json.loads((root/'docs/architecture-policy.json').read_text())
allowed=set(p['allowed_roots'])|{'README.md','pyproject.toml','package.json','.gitignore','MANIFEST.sha256','RELEASE.json'}
viol=[]
for x in root.iterdir():
    if x.name.startswith('.') and x.name!='.gitignore': continue
    if x.name not in allowed: viol.append(f'root-sprawl:{x.name}')
# Phase 1 future directories may exist but must not contain production source.
for rel in p['phase1_forbidden_implementation_roots']:
    d=root/rel
    if d.exists():
        for f in d.rglob('*'):
            if f.is_file() and f.name not in {'.gitkeep','README.md'}:
                viol.append(f'phase1-forbidden:{f.relative_to(root)}')
print(json.dumps({'status':'PASS' if not viol else 'FAIL','violations':viol},indent=2))
sys.exit(1 if viol else 0)
