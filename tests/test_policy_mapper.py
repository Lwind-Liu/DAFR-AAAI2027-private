import pytest

from clafr import (
    ConstraintIR,
    ConstraintIRValidationError,
    StaticPolicyMapper,
    validate_constraint_ir,
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
