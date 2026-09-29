from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'results/runs/agentdojo_mapper_pair_smoke'
variants=['manual_clafr','llm_mapper_clafr','llm_mapper_clafr_effectclass']
out={}
for v in variants:
 p=base/v/'qwen-max/clafr/banking'; paths=list(p.glob('user_task_*/*/*.json'))
 rows=[json.loads(x.read_text()) for x in paths]
 clean=[r for x,r in zip(paths,rows) if '/none/' in str(x)]; attack=[r for x,r in zip(paths,rows) if 'important_instructions' in str(x)]
 def count(rs,key): return sum(bool(r.get(key)) for r in rs)
 out[v]={'clean_denominator':len(clean),'clean_utility_success':count(clean,'utility'),'clean_false_block':len(clean)-count(clean,'utility'),
  'attack_denominator':len(attack),'attack_success_security_true':count(attack,'security'),'attack_safe_security_false':len(attack)-count(attack,'security'),
  'attack_utility_success':count(attack,'utility'),'abstain_messages':sum(sum(m.get('error')=='clafr_mapper_abstain' for m in r.get('messages',[])) for r in rows),
  'tool_calls':sum(sum(1 for m in r.get('messages',[]) if m.get('role')=='tool') for r in rows),
  'duration_sec':sum(float(r.get('duration',0) or 0) for r in rows)}
(base/'pair_metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(out,ensure_ascii=False,indent=2))
