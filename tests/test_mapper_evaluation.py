from clafr.mapper_evaluation import public_input, score


def case():
    return {'tool_name': 'send', 'fields': ['to', 'body'], 'policy': 'trusted authorization',
            'id': 'x', 'gold': {'roles': {'to': 'destination', 'body': 'data'},
            'requirements': [{'type': 'authorization', 'fields': ['to', 'body'], 'minimum': 1.0}]}}


def row(fields, minimum=1):
    return {'backend_compilable': True, 'ir': {'roles': case()['gold']['roles'],
            'preconditions': [{'type': 'authorization', 'fields': fields, 'minimum': minimum}]}}


def test_gold_and_case_id_do_not_enter_request():
    assert set(public_input(case())) == {'tool_name', 'fields', 'policy'}


def test_subset_is_underconstraint_not_overconstraint():
    s = score(case(), row(['to']))
    assert s['underconstrained'] and not s['overconstrained']


def test_superset_is_overconstraint_not_underconstraint():
    s = score(case(), row(['to', 'body', 'subject']))
    assert s['overconstrained'] and not s['underconstrained']


def test_threshold_matters_and_abstention_is_not_unsafe_execution():
    assert score(case(), row(['to', 'body'], .5))['underconstrained']
    assert not score(case(), row(['to', 'body'], .5))['precondition_exact']
    s = score(case(), {'backend_compilable': False})
    assert s['abstain'] and s['underconstrained'] is None


def test_split_requirements_are_equivalent():
    r = row(['to'])
    r['ir']['preconditions'].append({'type': 'authorization', 'fields': ['body'], 'minimum': 1})
    assert score(case(), r)['semantic_exact']
