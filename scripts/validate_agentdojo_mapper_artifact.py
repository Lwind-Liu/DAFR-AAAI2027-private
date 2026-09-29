from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'results/summaries/agentdojo_mapper_banking_v1/artifact.jsonl'
from clafr.policy_ir import ConstraintIR,validate_constraint_ir
from clafr.ir_compiler import IRPolicyCompiler
rows=[]
for line in p.read_text().splitlines():
 r=json.loads(line)
 try:
  ir=ConstraintIR.from_dict(r['ir']); validate_constraint_ir(ir,schema_fields=r['fields']); IRPolicyCompiler(ir,schema_fields=r['fields']).compile()
  if ir.tool_name!=r['tool_name']: raise ValueError('tool_mismatch')
  r['status']='allow_to_compile'; r['ir']=ir.to_dict()
 except Exception as e:
  r['status']='abstain'; r['validation_error']=type(e).__name__+':'+str(e)[:160]
 rows.append(r)
p.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n')
print(json.dumps({'total':len(rows),'allow':sum(r['status']=='allow_to_compile' for r in rows),'abstain':sum(r['status']=='abstain' for r in rows),'errors':[ (r['tool_name'],r.get('validation_error')) for r in rows if r['status']=='abstain']},ensure_ascii=False,indent=2))
