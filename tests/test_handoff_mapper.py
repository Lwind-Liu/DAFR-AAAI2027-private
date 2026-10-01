import json

from dafr_mapper import HandoffMapper, MapperContext


def context(candidate_policy="Only transfer an authorized account amount."):
    return MapperContext(
        tool_name="transfer",
        fields=("amount", "recipient"),
        effect_class="external_side_effect",
        field_descriptions={"amount": "amount to transfer", "recipient": "destination account"},
        policy=candidate_policy,
    )


def test_region_is_candidate_independent():
    mapper = HandoffMapper()
    a = mapper.region(context())
    b = mapper.region(context())
    assert a == b


def test_llm_prompt_keeps_policy_context_separate():
    messages = HandoffMapper().llm_messages(context(), {"amount": 10, "recipient": "acct-1"})
    assert messages[0]["role"] == "system"
    assert "candidate arguments" in messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert payload["trusted_context"]["policy"] == context().policy
    assert payload["candidate_call"]["recipient"] == "acct-1"


def test_pilot_maps_existing_ir_response():
    response = json.dumps({
        "status": "ok", "tool_name": "transfer", "roles": {"amount": "amount", "recipient": "destination"},
        "preconditions": [{"type": "authorization", "fields": ["amount", "recipient"], "minimum": 1.0, "source": "trusted"}],
        "risk_budgets": [], "forbidden_effects": []
    })
    output = HandoffMapper().map_response(response, context())
    assert HandoffMapper.check_region_membership(output)
    assert output.ir.tool_name == "transfer"
