from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; VERSION=sys.argv[1] if len(sys.argv)>1 else 'v1'
run=ROOT/f'results/summaries/mapper_eval_zh_{VERSION}'
rows=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()]
cases={json.loads(x)['id']:json.loads(x) for x in (ROOT/f'data/mapper_eval_zh_{VERSION}.jsonl').read_text().splitlines()}
agg=defaultdict(list); details=[]
for row in rows:
    case=cases[row['id']]; gold=case['gold']; d={'id':row['id'],'model':row['model'],'valid':row['ok']}
    gold_pre={(x,frozenset(gold['critical_fields'])) for x in gold['preconditions']}
    if row['ok']:
        ir=row['ir']; roles=ir.get('roles',{}); keys=set(gold['roles'])|set(roles)
        d['role_acc']=sum(roles.get(k)==gold['roles'].get(k) for k in keys)/max(1,len(keys))
        d['missing_role']=len(set(gold['roles'])-set(roles)); d['extra_role']=len(set(roles)-set(gold['roles']))
        pred={(p.get('type'),frozenset(p.get('fields',())),float(p.get('minimum',0.0))) for p in ir.get('preconditions',())}
        pred_types={(x,f) for x,f,_ in pred}; d['precondition_exact']=pred_types==gold_pre
        d['unsafe_relaxation']=any(not any(pt==gt and pf <= gf and pm >= 1.0 for pt,pf,pm in pred) for gt,gf in gold_pre)
        d['over_constraint']=any(not any(pt==gt and gf <= pf for pt,pf,pm in pred) for gt,gf in gold_pre) or any(pt not in {x for x,_ in gold_pre} for pt,_,_ in pred)
    else:
        d.update({'role_acc':0.,'missing_role':len(gold['roles']),'extra_role':0,'precondition_exact':False,'unsafe_relaxation':True,'over_constraint':False})
    agg[row['model']].append(d); details.append(d)
report={'total':len(rows),'by_model':{},'scope':f'32-case Chinese paraphrase pilot ({VERSION}), hand-written gold; not end-to-end ASR'}
for model, ds in agg.items():
    report['by_model'][model]={
      'valid_rate':sum(x['valid'] for x in ds)/len(ds), 'role_accuracy':sum(x['role_acc'] for x in ds)/len(ds),
      'precondition_exact_rate':sum(x['precondition_exact'] for x in ds)/len(ds),
      'unsafe_relaxation_rate':sum(x['unsafe_relaxation'] for x in ds)/len(ds),
      'over_constraint_rate':sum(x.get('over_constraint',False) for x in ds)/len(ds),
      'mean_missing_roles':sum(x['missing_role'] for x in ds)/len(ds),
      'mean_extra_roles':sum(x['extra_role'] for x in ds)/len(ds),
      'mean_latency_sec':sum(next(r['elapsed_sec'] for r in rows if r['id']==x['id'] and r['model']==model) for x in ds)/len(ds)}
report['details']=details;(run/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
