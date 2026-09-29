"""Separate syntactic acceptance from executable constraints and obvious omissions."""
import json
from pathlib import Path
from run_mapper_smoke import CASES
from clafr.policy_ir import ConstraintIR
from clafr.ir_compiler import IRPolicyCompiler

root = Path(__file__).resolve().parents[1]
folder = root / 'results/summaries/mapper_smoke_20260929'
rows = json.loads((folder / 'results.json').read_text())
cases = {c['id']: c for c in CASES}
audits = []
for row in rows:
    result = {'case_id': row['case_id'], 'structurally_valid': row['ok']}
    if row['ok']:
        ir = ConstraintIR.from_dict(row['ir'])
        result['zero_grounding_requirements'] = sum(p.type == 'trusted_grounding' and p.minimum == 0 for p in ir.preconditions)
        try:
            IRPolicyCompiler(ir, schema_fields=cases[row['case_id']]['fields'])
            result['backend_supported'] = True
        except ValueError as exc:
            result['backend_supported'] = False
            result['backend_reason'] = str(exc)
    audits.append(result)
report = {'cases': len(rows), 'audit': audits,
          'scope': 'No human gold labels; zero grounding thresholds are policy omissions, not measured security outcomes.'}
(folder / 'audit.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
