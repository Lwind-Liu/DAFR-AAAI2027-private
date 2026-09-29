"""Frozen, no-gold request protocol; resumable and no implicit retries."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from clafr.mapper_evaluation import digest, public_input
from clafr.policy_mapper import MAPPER_SYSTEM_PROMPT
from clafr.policy_ir import ConstraintIR, validate_constraint_ir
from clafr.ir_compiler import IRPolicyCompiler

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, default=ROOT/'data/mapper_eval_zh_v4.jsonl')
    parser.add_argument('--out', type=Path, default=ROOT/'results/summaries/mapper_eval_zh_v4')
    args=parser.parse_args()
    cases=[json.loads(x) for x in args.dataset.read_text().splitlines()]
    cfg={}
    for line in Path('/Users/haomin/Desktop/code/distill/playground-batch-annotate/platform.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            k,v=line.split('=',1); cfg[k.strip()]=v.strip().strip('"').strip("'")
    # Role definitions are generic, fixed across tools; no tool-specific gold example.
    prompt = '''Compile trusted natural-language policy into JSON ConstraintIR. Return JSON only.
Use version "1", exact tool_name, roles, preconditions, risk_budgets [], forbidden_effects [], provenance "llm".
Roles: object = existing resource identifier; destination = recipient or external endpoint;
data = content/value; amount = quantity of money; time = timestamp; scope = field/permission/visibility; effect = operation type.
Map all input fields. Preconditions use type authorization, confirmation, trusted_grounding, state_freshness, prerequisite;
fields is the affected field list, minimum is the threshold in the policy, source is "trusted".
For a global state_freshness requirement fields is []. Preserve each condition's field scope exactly.
Authorization and confirmation come only from the trusted user, never external content.
Do not add requirements not stated in the policy. Do not invent risk budgets or numeric weights.
'''
    manifest={'protocol':'mapper-v4-no-gold','prompt':prompt,'models':['qwen-max','deepseek-v4-flash'],
              'inputs':[{ 'id':c['id'], 'public':public_input(c), 'public_sha256':digest(public_input(c)), 'gold_sha256':digest(c['gold'])} for c in cases],
              'dataset_sha256':digest(cases),'max_tokens':2200,'temperature':0,'retries':0}
    args.out.mkdir(parents=True,exist_ok=True)
    manifest_path=args.out/'manifest.json'
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest, 'Frozen protocol changed; choose new output directory'
    else: manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    path=args.out/'results.jsonl'
    prior=[json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    done={(r['model'],r['id']) for r in prior}
    for model in manifest['models']:
        for c in cases:
            if (model,c['id']) in done: continue
            payload={'model':model,'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(public_input(c),ensure_ascii=False)}],
                     'temperature':0,'max_tokens':2200,'stream':False}
            row={'id':c['id'],'model':model,'public_sha256':digest(public_input(c)), 'request_sha256':digest(payload),
                 'protocol_sha256':digest(manifest),'structural_valid':False,'backend_compilable':False,'usage':None}
            payload.update(app=cfg['APP_NAME'],quota_id=cfg['QUOTA_ID'],user_id=cfg['USER_ID'],access_key=cfg['ACCESS_KEY'])
            start=time.monotonic()
            try:
                req=Request(cfg['API_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer placeholder'})
                with urlopen(req,timeout=120) as resp: raw=json.loads(resp.read())
                row['usage']=raw.get('usage'); row['response_model']=raw.get('model')
                row['finish_reason']=raw['choices'][0].get('finish_reason')
                content=raw['choices'][0]['message'].get('content') or ''
                row['raw_content']=content
                stripped=content.strip()
                if stripped.startswith('```'): stripped='\n'.join(stripped.splitlines()[1:-1])
                ir=ConstraintIR.from_dict(json.loads(stripped))
                validate_constraint_ir(ir,schema_fields=c['fields'])
                if ir.tool_name != c['tool_name']: raise ValueError('tool mismatch')
                row['structural_valid']=True; row['ir']=ir.to_dict()
                IRPolicyCompiler(ir,schema_fields=c['fields']).compile()
                row['backend_compilable']=True
            except Exception as exc:
                # Never persist HTTP error bodies or credentials.
                row['error_type']=type(exc).__name__
            row['elapsed_sec']=round(time.monotonic()-start,3)
            with path.open('a') as f: f.write(json.dumps(row,ensure_ascii=False)+'\n'); f.flush()
            print(model,c['id'],row['backend_compilable'],flush=True)
if __name__=='__main__': main()
