"""Deterministic effect-class adapter; never invents side-effect authorization."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'results/summaries/agentdojo_mapper_banking_v1/artifact.jsonl'
out=ROOT/'results/summaries/agentdojo_mapper_banking_v1/artifact_effectclass_v1.jsonl'
read_only={'get_iban','get_balance','get_most_recent_transactions','get_scheduled_transactions','get_user_info','read_file'}
rows=[]
for line in src.read_text().splitlines():
 r=json.loads(line); name=r['tool_name']; ir=r.get('ir') if isinstance(r.get('ir'),dict) else {}
 # Only accept exact tool identity and schema-valid field names. Unknown model schema is dropped.
 ir={'version':'1','tool_name':name,'roles':{},'preconditions':[],'risk_budgets':[],'forbidden_effects':[],'provenance':'llm_effectclass_adapter'}
 if r.get('status') == 'candidate':
  raw=r.get('ir',{})
  if raw.get('tool_name') == name:
   roles=raw.get('roles',{}) if isinstance(raw.get('roles',{}),dict) else {}
   ir['roles']={k:v for k,v in roles.items() if k in r.get('fields',[]) and v in {'object','destination','data','amount','time','effect','scope'}}
   if name not in read_only:
    pre=raw.get('preconditions',[])
    if isinstance(pre,list) and all(isinstance(x,dict) and x.get('type') in {'authorization','confirmation','trusted_grounding','state_freshness','prerequisite'} for x in pre):
     for p in pre:
      fields=[f for f in p.get('fields',p.get('affected_fields',[])) if f in r.get('fields',[])]
      if p.get('type') in {'authorization','confirmation','trusted_grounding'} and not fields: continue
      ir['preconditions'].append({'type':p['type'],'fields':fields,'minimum':float(p.get('minimum',1.0)),'source':'trusted'})
    else:
     r['status']='abstain'
  else: r['status']='abstain'
 if name in read_only:
  r['status']='allow_to_compile'
 r['ir']=ir
 rows.append(r)
out.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n')
print(json.dumps({'total':len(rows),'allow':sum(r['status']=='allow_to_compile' for r in rows),'abstain':sum(r['status']=='abstain' for r in rows),'read_only':len(read_only)},ensure_ascii=False))
