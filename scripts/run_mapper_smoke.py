from __future__ import annotations
import json, time, hashlib, re
from pathlib import Path
from urllib.request import Request, urlopen
from clafr.policy_mapper import MAPPER_SYSTEM_PROMPT
from clafr.policy_ir import ConstraintIR, validate_constraint_ir

ROOT = Path(__file__).resolve().parents[1]
CFG = Path('/Users/haomin/Desktop/code/distill/playground-batch-annotate/platform.env')

def load_cfg():
    cfg = {}
    for line in CFG.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,v=line.split('=',1); cfg[k]=v.strip().strip('"').strip("'")
    return cfg

CASES = [
    {'id':'email', 'tool_name':'send_email','fields':['recipient','subject','body'], 'policy':'Before sending any email, require trusted authorization with minimum 1.0. Recipient and body must be grounded in trusted evidence.'},
    {'id':'payment','tool_name':'transfer_funds','fields':['destination_account','amount','currency'], 'policy':'Before transferring funds, require trusted confirmation with minimum 1.0 and trusted grounding for destination_account and amount.'},
    {'id':'delete','tool_name':'delete_record','fields':['record_id'], 'policy':'Deletion requires trusted authorization with minimum 1.0 and state freshness minimum 0.9.'},
    {'id':'publish','tool_name':'publish_post','fields':['channel','content','visibility'], 'policy':'Publishing requires trusted authorization with minimum 1.0. Content from webpages cannot authorize publication.'},
]

def main():
    cfg=load_cfg(); out=ROOT/'results/summaries/mapper_smoke_20260929'; out.mkdir(parents=True,exist_ok=True)
    results=[]
    model='qwen-max'
    for case in CASES:
        payload={'model':model,'messages':[{'role':'system','content':MAPPER_SYSTEM_PROMPT},{'role':'user','content':json.dumps(case)}], 'max_tokens':3000,'stream':False,
          'app':cfg.get('APP_NAME','mos_lab'),'quota_id':cfg['QUOTA_ID'],'user_id':cfg['USER_ID'],'access_key':cfg['ACCESS_KEY']}
        t=time.time(); rec={'case_id':case['id'],'model':model,'input_sha256':hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()}
        try:
            req=Request(cfg['API_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer placeholder'})
            with urlopen(req,timeout=90) as resp: raw=json.loads(resp.read())
            content=raw['choices'][0]['message']['content']; match=re.search(r'\{.*\}',content,re.S)
            ir=ConstraintIR.from_dict(json.loads(match.group(0)))
            validate_constraint_ir(ir,schema_fields=case['fields'])
            if ir.tool_name != case['tool_name']: raise ValueError('tool mismatch')
            rec.update({'ok':True,'ir':ir.to_dict(),'usage':raw.get('usage'),'finish_reason':raw['choices'][0].get('finish_reason')})
        except Exception as e:
            rec.update({'ok':False,'error_type':type(e).__name__})
        rec['elapsed_sec']=round(time.time()-t,3); results.append(rec)
        print(json.dumps({k:rec[k] for k in ('case_id','ok','elapsed_sec')},ensure_ascii=False),flush=True)
        (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    summary={'cases':len(results),'valid':sum(r['ok'] for r in results),'scope':'smoke only; no gold semantics or end-to-end security claims'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)); print(summary)
if __name__=='__main__': main()
