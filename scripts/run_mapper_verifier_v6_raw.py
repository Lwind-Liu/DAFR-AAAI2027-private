"""Verify frozen v6 DeepSeek mapper candidates with an independent Qwen call."""
import json, re, time
from pathlib import Path
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]
CFG=Path('/Users/haomin/Desktop/code/distill/playground-batch-annotate/platform.env')
DATA=ROOT/'data/mapper_eval_zh_v6_test.jsonl'
ART=ROOT/'results/summaries/mapper_eval_zh_v6_test/valid_deepseek_artifact.jsonl'
OUT=ROOT/'results/summaries/mapper_eval_zh_v6_test/verifier_artifact.jsonl'
cfg={}
for line in CFG.read_text(encoding='utf8').splitlines():
    line=line.strip()
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);cfg[k]=v.strip().strip('"').strip("'")
src=(ROOT/'src/clafr/policy_mapper.py').read_text(encoding='utf8')
system=re.search(r'VERIFIER_SYSTEM_PROMPT = """(.*?)"""',src,re.S).group(1)
cases={}
for x in DATA.read_text(encoding='utf8').splitlines():
    c=json.loads(x); cases[c['id']]=c
rows=[]
for x in ART.read_text(encoding='utf8').splitlines():
    r=json.loads(x)
    if r['model']=='deepseek-v4-flash' and r['status']=='ok': rows.append(r)
def call(c,r):
    body={'model':'qwen-max','temperature':0,'max_tokens':1200,'stream':False,
      'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps({'tool_name':c['tool_name'],'fields':c['fields'],'effect_class':c['effect_class'],'policy':c['policy'],'candidate_ir':r['ir']},ensure_ascii=False)}],
      'app':cfg['APP_NAME'],'quota_id':cfg['QUOTA_ID'],'user_id':cfg['USER_ID'],'access_key':cfg['ACCESS_KEY']}
    req=Request(cfg['API_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer placeholder'})
    with urlopen(req,timeout=180) as x:return json.loads(x.read().decode())
out=[]
for r in rows:
    c=cases[r['id']]; row={'id':r['id'],'mapper_model':r['model'],'verifier_model':'qwen-max'};t=time.time()
    try:
        raw=call(c,r);content=raw['choices'][0]['message']['content'];m=re.search(r'\{.*\}',content,re.S)
        if not m: raise ValueError('no_json')
        obj=json.loads(m.group(0)); row.update({'verdict':'pass' if obj.get('status')=='pass' else 'abstain','response':obj,'usage':raw.get('usage')})
    except Exception as e:row.update({'verdict':'abstain','error':type(e).__name__+':'+str(e)[:180]})
    row['elapsed_sec']=round(time.time()-t,3);out.append(row);print(json.dumps({'id':row['id'],'verdict':row['verdict'],'sec':row['elapsed_sec']},ensure_ascii=False),flush=True)
OUT.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in out)+'\n',encoding='utf8')
print(json.dumps({'total':len(out),'pass':sum(x['verdict']=='pass' for x in out),'abstain':sum(x['verdict']=='abstain' for x in out)},ensure_ascii=False))
