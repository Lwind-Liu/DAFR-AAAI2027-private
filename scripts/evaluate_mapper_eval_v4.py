from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import sys
from clafr.mapper_evaluation import score
ROOT=Path(__file__).resolve().parents[1]
run=ROOT/'results/summaries/mapper_eval_zh_v4'
cases={json.loads(x)['id']:json.loads(x) for x in (ROOT/'data/mapper_eval_zh_v4.jsonl').read_text().splitlines()}
rows=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()]
agg=defaultdict(list)
for r in rows:
 d=score(cases[r['id']],r); d.update({'model':r['model'],'structural_valid':r['structural_valid'],'backend_compilable':r['backend_compilable'],'elapsed_sec':r['elapsed_sec'],'usage':r.get('usage')}); agg[r['model']].append(d)
out={'scope':'32 explicit-policy cases; gold is held out from request; valid means structural validation plus IRPolicyCompiler.compile', 'total':len(rows),'by_model':{}}
for model,ds in agg.items():
 out['by_model'][model]={
  'backend_compilable':sum(d['backend_compilable'] for d in ds), 'abstain':sum(d['abstain'] for d in ds),
  'roles_exact_rate':sum(d.get('roles_exact',False) for d in ds)/len(ds),
  'precondition_exact_rate':sum(d.get('precondition_exact',False) for d in ds)/len(ds),
  'semantic_exact_rate':sum(d.get('semantic_exact',False) for d in ds)/len(ds),
  'underconstraint_rate':sum(d.get('underconstrained') is True for d in ds)/len(ds),
  'overconstraint_rate':sum(d.get('overconstrained') is True for d in ds)/len(ds),
  'mean_latency_sec':sum(d['elapsed_sec'] for d in ds)/len(ds),
  'prompt_tokens':sum((d['usage'] or {}).get('prompt_tokens',0) for d in ds), 'completion_tokens':sum((d['usage'] or {}).get('completion_tokens',0) for d in ds)}
out['details']=[{'id':r['id'],'model':r['model'],**score(cases[r['id']],r)} for r in rows]
(run/'metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out['by_model'],ensure_ascii=False,indent=2))
