"""Freeze validated training-free mapper outputs for reproducible downstream runs."""
from __future__ import annotations
import json, sys, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=sys.argv[1] if len(sys.argv)>1 else 'v2'
run=ROOT/f'results/summaries/mapper_eval_zh_{version}'
out=run/'frozen_mapper_artifact.jsonl'
rows=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()]
written=0
with out.open('w',encoding='utf-8') as f:
 for r in rows:
  rec={'id':r['id'],'model':r['model'],'input_sha256':r['input_sha256'],'status':'allow_to_compile' if r.get('ok') else 'abstain','ir':r.get('ir'),'error':r.get('error')}
  rec['artifact_sha256']=hashlib.sha256(json.dumps(rec,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  f.write(json.dumps(rec,ensure_ascii=False)+'\n'); written+=1
print(json.dumps({'version':version,'records':written,'compiled':sum(r.get('ok',False) for r in rows),'abstain':sum(not r.get('ok',False) for r in rows),'path':str(out)},ensure_ascii=False))
