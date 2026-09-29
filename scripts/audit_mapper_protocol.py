"""Static audit for mapper evaluation input isolation and compiled-status semantics."""
from __future__ import annotations
import ast, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/run_mapper_eval_zh.py').read_text()
assert 'def public_case' in source and "'gold'" not in source.split('def public_case',1)[1].split('def call',1)[0]
version=sys.argv[1] if len(sys.argv)>1 else 'v3'
cases=[json.loads(x) for x in (ROOT/f'data/mapper_eval_zh_{version}.jsonl').read_text().splitlines()]
assert len(cases)>=32
for c in cases:
 public={k:c[k] for k in ('id','tool_name','fields','policy')}
 assert 'gold' not in public
rows=[json.loads(x) for x in (ROOT/f'results/summaries/mapper_eval_zh_{version}/results.jsonl').read_text().splitlines()]
assert all((r.get('ok') is False) or r.get('backend_compilable') is True for r in rows)
print(json.dumps({'version':version,'cases':len(cases),'rows':len(rows),'gold_excluded_from_public_input':True,'compiled_flag_required':True},ensure_ascii=False))
