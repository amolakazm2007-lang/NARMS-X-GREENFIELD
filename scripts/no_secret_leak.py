from pathlib import Path
import re,json,sys
root=Path(__file__).resolve().parents[1]; pats=[re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(r'(?i)(?:api[_-]?key|secret|password)\s*[=:]\s*["\'][A-Za-z0-9_\-]{16,}')];bad=[]
for p in root.rglob('*'):
 if not p.is_file() or any(x in p.parts for x in {'.git','__pycache__','dist'}):continue
 try:s=p.read_text(errors='ignore')
 except:continue
 for pat in pats:
  if pat.search(s):bad.append(str(p.relative_to(root)));break
print(json.dumps({'status':'PASS' if not bad else 'FAIL','matches':bad},indent=2));sys.exit(bool(bad))
