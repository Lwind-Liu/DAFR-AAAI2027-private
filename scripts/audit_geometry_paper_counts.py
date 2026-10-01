"""Re-run frozen mechanism suites without overwriting historical evidence."""
import hashlib
import json
import random
import subprocess
from pathlib import Path
import run_geometry_repair_benchmark_v1 as bench

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/summaries/geometry_paper_audit_20261001'
OUT.mkdir(parents=True, exist_ok=True)
bench.RNG = random.Random(bench.SEED)
joint, joint_summary = bench.run_joint_suite()
repair, repair_summary = bench.run_action_repair_suite()
risk_names = ('privacy_egress', 'financial_risk', 'state_write_risk', 'scope_risk')
# Independently evaluate the declared unit-budget policy, not geometry outputs.
labels = [sum(r[k] ** 2 for k in risk_names) <= 1.0 for r in joint]
confusion = {}
for name in ('axis_ifelse', 'geometry', 'equivalent_predicate'):
    decisions = [r[name + '_allow'] for r in joint]
    confusion[name] = {
        'safe_allow': sum(a and s for a, s in zip(decisions, labels)),
        'false_block': sum(not a and s for a, s in zip(decisions, labels)),
        'unsafe_block': sum(not a and not s for a, s in zip(decisions, labels)),
        'false_allow': sum(a and not s for a, s in zip(decisions, labels)),
    }
    if name != 'axis_ifelse':
        assert decisions == labels, name
assert len(joint) == 512 and sum(labels) == 487
assert len(repair) == 256
for backend in ('geometry', 'predicate_oracle'):
    assert sum(r[backend + '_repair_success'] for r in repair) == 192
    assert not any(r[backend + '_repair_success'] and not r['repairable_by_removing_optional_destination'] for r in repair)
assert all(r['geometry_blocked'] == r['predicate_blocked'] for r in repair)
assert not any(r['external_side_effect_executed'] for r in joint + repair)
paths = ['scripts/run_geometry_repair_benchmark_v1.py', 'src/clafr/geometry.py', 'src/clafr/predicate.py', 'src/clafr/selector.py', 'src/clafr/compiler.py', 'src/clafr/features.py']
report = {
    'seed': bench.SEED,
    'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'working_tree_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
    'scope': 'Fresh in-process mechanism rerun; no planner/API/external tool executions. Policy labels are specified analytically; not independently annotated safety labels.',
    'safe_cases': sum(labels), 'unsafe_cases': len(labels)-sum(labels),
    'confusion': confusion,
    'joint_risk': joint_summary, 'action_repair': repair_summary,
    'boolean_only_note': 'Zero repair is hard-coded by the no-repair interface; excluded from empirical superiority comparisons.',
}
for name, rows in [('joint_rows', joint), ('repair_rows', repair)]:
    (OUT / (name + '.jsonl')).write_text(''.join(json.dumps(r) + '\n' for r in rows))
(OUT / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'confusion': confusion, 'repair': {k: repair_summary[k] for k in ('cases', 'repairable_cases', 'nonrepairable_cases', 'geometry_predicate_block_disagreements')}, 'output': str(OUT)}, indent=2))
