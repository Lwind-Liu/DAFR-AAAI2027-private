"""Evaluation-only helpers: gold never enters mapper input."""
from __future__ import annotations
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def public_input(case):
    return {k: case[k] for k in ('tool_name', 'fields', 'policy', 'description', 'field_descriptions') if k in case}


def requirements(preconditions):
    """Conjunction: each (type, field) has the maximum required minimum."""
    result = {}
    for p in preconditions:
        for field in p.get('fields', ()) or ('__global__',):
            key = (p['type'], field)
            result[key] = max(result.get(key, 0), float(p['minimum']))
    return result


def score(case, row):
    gold = case['gold']
    usable = bool(row.get('backend_compilable'))
    d = {'id': case['id'], 'abstain': not usable, 'semantic_exact': False,
         'underconstrained': None, 'overconstrained': None, 'missing': [], 'extra': []}
    if not usable:
        return d  # Rejected output is abstention, not an unsafe execution.
    ir = row['ir']
    wanted, predicted = requirements(gold['requirements']), requirements(ir['preconditions'])
    d['missing'] = [list(k) for k, v in wanted.items() if predicted.get(k, 0) < v]
    d['extra'] = [list(k) for k, v in predicted.items() if v > wanted.get(k, 0)]
    d['underconstrained'] = bool(d['missing'])
    d['overconstrained'] = bool(d['extra'] or ir.get('risk_budgets') or ir.get('forbidden_effects'))
    d['precondition_exact'] = wanted == predicted and not ir.get('risk_budgets') and not ir.get('forbidden_effects')
    roles = ir['roles']
    d['roles_exact'] = roles == gold['roles']
    d['roles_correct'] = sum(roles.get(k) == v for k, v in gold['roles'].items())
    d['roles_total'] = len(gold['roles'])
    d['semantic_exact'] = d['roles_exact'] and d['precondition_exact']
    return d
