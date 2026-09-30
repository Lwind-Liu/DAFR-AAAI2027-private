import pytest

from clafr import (
    ConstraintIR,
    ConstraintIRValidationError,
    StaticPolicyMapper,
    validate_constraint_ir,
    build_mapper_system_prompt,
)


def test_static_mapper_is_schema_grounded_and_deterministic():
    mapper = StaticPolicyMapper()
    ir = mapper.map_policy(
        "Do not disclose private data without authorization.",
        "send_email",
        ("recipient", "body", "subject"),
    )
    assert ir.roles["recipient"] == "destination"
    assert ir.roles["body"] == "data"
    assert {p.type for p in ir.preconditions} == {"trusted_grounding", "authorization"}
    assert ir.to_dict() == mapper.map_policy(
        "Do not disclose private data without authorization.",
        "send_email",
        ("recipient", "body", "subject"),
    ).to_dict()


def test_validator_rejects_unknown_fields_and_roles():
    ir = ConstraintIR.from_dict(
        {"tool_name": "send", "roles": {"evil": "destination"}, "provenance": "llm"}
    )
    with pytest.raises(ConstraintIRValidationError):
        validate_constraint_ir(ir, schema_fields=("recipient",))

    bad_role = ConstraintIR.from_dict(
        {"tool_name": "send", "roles": {"recipient": "permission"}, "provenance": "llm"}
    )
    with pytest.raises(ConstraintIRValidationError):
        validate_constraint_ir(bad_role, schema_fields=("recipient",))


def test_validator_rejects_untrusted_authorization_source_and_out_of_range_budget():
    ir = ConstraintIR.from_dict(
        {
            "tool_name": "send",
            "roles": {"recipient": "destination"},
            "preconditions": [{"type": "authorization", "fields": ["recipient"], "source": "webpage"}],
        }
    )
    with pytest.raises(ConstraintIRValidationError):
        validate_constraint_ir(ir, schema_fields=("recipient",))

    ir2 = ConstraintIR.from_dict(
        {
            "tool_name": "send",
            "risk_budgets": [{"name": "privacy", "limit": 3.0}],
        }
    )
    with pytest.raises(ConstraintIRValidationError):
        validate_constraint_ir(ir2)


def test_validator_rejects_semantically_empty_security_precondition():
    ir = ConstraintIR.from_dict({
        "tool_name": "send", "roles": {"recipient": "destination"},
        "preconditions": [{"type": "trusted_grounding", "fields": ["recipient"], "minimum": 0.0}],
    })
    with pytest.raises(ConstraintIRValidationError):
        validate_constraint_ir(ir, schema_fields=("recipient",))


def test_v5_prompt_freezes_effect_class_and_few_shot_boundaries():
    prompt = build_mapper_system_prompt(
        effect_class="external_side_effect",
        field_descriptions={"recipient": "external recipient", "subject": "ordinary subject"},
    )
    assert "effect_class=external_side_effect" in prompt
    assert "ordinary field" in prompt
    assert "status=abstain" in prompt
    assert "webpage" in prompt


def test_mapper_envelope_and_explicit_abstention():
    import json
    from clafr.policy_mapper import parse_mapper_response, MapperAbstention
    payload = {'tool_name': 'lookup', 'roles': {'key': 'object'}, 'preconditions': []}
    assert parse_mapper_response(json.dumps({'status': 'ok', 'ir': payload}), 'lookup', ['key']).tool_name == 'lookup'
    with pytest.raises(MapperAbstention):
        parse_mapper_response('{"status":"abstain","reason":"ambiguous"}', 'lookup', ['key'])


def test_role_semantics_reject_high_confidence_field_mismatch():
    import json
    from clafr.policy_mapper import parse_mapper_response
    bad = json.dumps({'tool_name': 'post_comment',
                      'roles': {'post_id': 'destination', 'visibility': 'data'},
                      'preconditions': []})
    with pytest.raises(ConstraintIRValidationError):
        parse_mapper_response(bad, 'post_comment', ['post_id', 'visibility'],
                              field_descriptions={'post_id': 'existing post identifier',
                                                  'visibility': 'audience scope'})


def test_read_only_empty_grounding_is_vacuous_but_auth_is_not_removed():
    import json
    from clafr.policy_mapper import parse_mapper_response
    ir = parse_mapper_response(json.dumps({'tool_name': 'get_iban', 'roles': {},
        'preconditions': [{'type': 'trusted_grounding', 'fields': [], 'minimum': 1.0}]}),
        'get_iban', [], effect_class='read_only')
    assert ir.preconditions == ()
    with pytest.raises(ConstraintIRValidationError):
        parse_mapper_response(json.dumps({'tool_name': 'get_iban', 'roles': {},
            'preconditions': [{'type': 'authorization', 'fields': [], 'minimum': 1.0}]}),
            'get_iban', [], effect_class='read_only')


@pytest.mark.parametrize('content', ['[]', 'null', '{"status":"pass"}', 'not json', '{"tool_name":"other"}', '{"tool_name":"lookup","roles":{"key":"ordinary"}}', '{"tool_name":"lookup","forbidden_effects":["delete"]}'])
def test_mapper_rejects_invalid_or_unsupported_output(content):
    from clafr.policy_mapper import parse_mapper_response
    with pytest.raises(ConstraintIRValidationError):
        parse_mapper_response(content, 'lookup', ['key'])
