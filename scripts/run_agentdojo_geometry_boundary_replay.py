"""Replay saved AgentDojo action/evidence boundaries through geometry controls.

This is a no-execution audit: it reuses the frozen 610 valid calls from the
existing fixed-prefix replay and compares the recorded geometric decision with
an equivalent predicate over the same constraint margins. It does not claim a
new planner run or utility result.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'results/summaries/agentdojo_mapper_boundary_replay_v1/rows.jsonl'
OUT=ROOT/'results/summaries/agentdojo_geometry_boundary_replay_v1'

def main():
    rows=[json.loads(x) for x in SRC.read_text().splitlines() if x.strip()]
    valid=[r for r in rows if r.get('status')=='compared']
    out=[]; loc=Counter(); disagreements=0; cert_ok=0
    for r in valid:
        arm=r['mapper']; margins=arm.get('margins') or []
        predicate=all(float(m.get('slack', 0.0)) >= 0.0 for m in margins if not m.get('soft',False))
        geometry=bool(arm.get('feasible'))
        disagreements += int(predicate != geometry)
        cert_ok += int(bool(arm.get('decision')) and isinstance(arm.get('execution_margin'), (int,float)))
        if not geometry:
            for m in margins:
                if not m.get('soft',False) and float(m.get('slack',0.0)) < 0:
                    loc[str(m.get('constraint_id'))] += 1
        out.append({'id':r['id'],'tool_name':r.get('tool_name'),'geometry_feasible':geometry,'equivalent_predicate_feasible':predicate,'decision':arm.get('decision'),'execution_margin':arm.get('execution_margin'),'violated_constraints':arm.get('violated_constraints',[])})
    summary={'schema':'agentdojo-geometry-boundary-replay-v1','source':str(SRC.relative_to(ROOT)),'saved_rows':len(rows),'valid_rows':len(valid),'external_tool_executions':0,'api_calls':0,'geometry_vs_equivalent_predicate_disagreements':disagreements,'certificate_rows':cert_ok,'geometry_allow':sum(x['geometry_feasible'] for x in out),'geometry_block_or_clarify':sum(not x['geometry_feasible'] for x in out),'top_blocking_facets':loc.most_common(10),'scope':'saved AgentDojo action/evidence boundaries; no new planner or external execution'}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'rows.jsonl').write_text('\n'.join(json.dumps(x,sort_keys=True) for x in out)+'\n')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
