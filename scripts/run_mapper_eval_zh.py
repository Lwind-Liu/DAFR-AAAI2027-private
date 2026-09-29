from __future__ import annotations
import hashlib,json,re,time,sys
from pathlib import Path
from urllib.request import Request,urlopen
from clafr.policy_mapper import MAPPER_SYSTEM_PROMPT
from clafr.policy_ir import ConstraintIR,validate_constraint_ir
from clafr.ir_compiler import IRPolicyCompiler
ROOT=Path(__file__).resolve().parents[1]; CFG=Path('/Users/haomin/Desktop/code/distill/playground-batch-annotate/platform.env')
VERSION=sys.argv[1] if len(sys.argv)>1 else 'v1'
OUT=ROOT/f'results/summaries/mapper_eval_zh_{VERSION}';OUT.mkdir(parents=True,exist_ok=True)
cfg={}
for line in CFG.read_text().splitlines():
 line=line.strip()
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);cfg[k]=v.strip().strip('"').strip("'")
CASES=[json.loads(x) for x in (ROOT/f'data/mapper_eval_zh_{VERSION}.jsonl').read_text().splitlines()]
MODELS=['qwen-max','deepseek-v4-flash']
def public_case(case):
 return {'id':case['id'],'tool_name':case['tool_name'],'fields':case['fields'],'policy':case['policy']}
def call(case,model):
 public=public_case(case)
 payload={'model':model,'messages':[{'role':'system','content':MAPPER_SYSTEM_PROMPT},{'role':'user','content':json.dumps(public,ensure_ascii=False)}],'max_tokens':2200,'stream':False,'app':cfg['APP_NAME'],'quota_id':cfg['QUOTA_ID'],'user_id':cfg['USER_ID'],'access_key':cfg['ACCESS_KEY']}
 req=Request(cfg['API_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer placeholder'})
 with urlopen(req,timeout=120) as x:return json.loads(x.read())
def main():
 results=[]; path=OUT/'results.jsonl'
 for model in MODELS:
  for case in CASES:
   t=time.time();public=public_case(case)
   r={'id':case['id'],'model':model,'input_sha256':hashlib.sha256(json.dumps(public,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'gold_sha256':hashlib.sha256(json.dumps(case['gold'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
   try:
    raw=call(case,model);content=raw['choices'][0]['message']['content'];m=re.search(r'\{.*\}',content,re.S)
    if not m: raise ValueError('no_json')
    ir=ConstraintIR.from_dict(json.loads(m.group(0)));validate_constraint_ir(ir,schema_fields=case['fields'])
    if ir.tool_name!=case['tool_name']:raise ValueError('tool_mismatch')
    try:
     IRPolicyCompiler(ir, schema_fields=case['fields']).compile()
    except Exception as exc:
     raise ValueError(f'backend_compile:{type(exc).__name__}:{exc}') from exc
    r.update({'ok':True,'backend_compilable':True,'ir':ir.to_dict(),'usage':raw.get('usage'),'finish_reason':raw['choices'][0].get('finish_reason')})
   except Exception as e:r.update({'ok':False,'error_type':type(e).__name__,'error':str(e)[:180]})
   r['elapsed_sec']=round(time.time()-t,3);results.append(r)
   print(json.dumps({'id':r['id'],'model':model,'ok':r['ok'],'sec':r['elapsed_sec']},ensure_ascii=False),flush=True)
   path.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in results)+'\n')
 print({'total':len(results),'valid':sum(x['ok'] for x in results)})
if __name__=='__main__':main()
