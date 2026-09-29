"""Gold-scored mapper pilot; labels are hand-written for this smoke set only."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'results/summaries/mapper_smoke_20260929'
GOLD={
 'email': {'roles': {'recipient':'destination','body':'data'}, 'preconditions': {('authorization',frozenset({'recipient','body'})),('trusted_grounding',frozenset({'recipient','body'}))}},
 'payment': {'roles': {'destination_account':'destination','amount':'amount','currency':'data'}, 'preconditions': {('confirmation',frozenset({'destination_account','amount'})),('trusted_grounding',frozenset({'destination_account','amount'}))}},
 'delete': {'roles': {'record_id':'object'}, 'preconditions': {('authorization',frozenset({'record_id'})),('state_freshness',frozenset({'record_id'}))}},
 'publish': {'roles': {'channel':'destination','content':'data','visibility':'scope'}, 'preconditions': {('authorization',frozenset({'channel','content','visibility'}))}},
}

def main():
 rows=json.loads((RUN/'results.json').read_text()); out=[]
 for row in rows:
  gold=GOLD[row['case_id']]; ir=row.get('ir',{}); pred=ir.get('roles',{})
  keys=set(gold['roles'])|set(pred)
  role_correct=sum(pred.get(k)==gold['roles'].get(k) for k in keys)
  pre={(p.get('type'),frozenset(p.get('fields',()))) for p in ir.get('preconditions',())}
  out.append({'case_id':row['case_id'],'valid':row['ok'],'role_accuracy':role_correct/max(1,len(keys)), 'precondition_exact':pre==gold['preconditions'], 'role_missing':sorted(set(gold['roles'])-set(pred)), 'role_extra':sorted(set(pred)-set(gold['roles']))})
 report={'cases':len(out),'valid_rate':sum(x['valid'] for x in out)/len(out),'mean_role_accuracy':sum(x['role_accuracy'] for x in out)/len(out),'precondition_exact_rate':sum(x['precondition_exact'] for x in out)/len(out),'scope':'4-case smoke pilot with hand-written gold labels; not a benchmark claim','cases_detail':out}
 (RUN/'gold_eval.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
