from pathlib import Path
import json,sys
from jsonschema import Draft202012Validator
root=Path(__file__).resolve().parents[1]/'contracts';bad=[]
for p in sorted(root.glob('*.schema.json')):
 try:Draft202012Validator.check_schema(json.loads(p.read_text()))
 except Exception as e:bad.append(f'{p.name}:{e}')
print(json.dumps({'schemas':len(list(root.glob('*.schema.json'))),'status':'PASS' if not bad else 'FAIL','errors':bad},indent=2));sys.exit(bool(bad))
