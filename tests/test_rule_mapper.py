import pytest

from clafr import SchemaRulePolicyMapper
from clafr.policy_mapper import MapperAbstention


def test_schema_rule_mapper_uses_descriptions_and_shared_ir():
    ir = SchemaRulePolicyMapper().map_policy(
        "发布报告前必须明确授权 audience 和 body；report_id 必须来自可信状态。",
        "publish_report",
        ["report_id", "audience", "body", "format"],
        field_descriptions={
            "report_id": "existing report identifier",
            "audience": "visibility audience",
            "body": "report body",
            "format": "publication format setting",
        },
    )
    assert ir.roles == {"report_id": "object", "audience": "scope", "body": "data", "format": "scope"}
    assert {(p.type, p.fields) for p in ir.preconditions} == {
        ("authorization", ("audience", "body")),
        ("trusted_grounding", ("report_id",)),
    }


def test_schema_rule_mapper_scopes_combined_authorize_then_confirm_clause():
    ir = SchemaRulePolicyMapper().map_policy(
        "发表评论前必须获得用户对 post_id 和 comment 的明确授权，并确认 visibility。",
        "post_comment",
        ["post_id", "comment", "visibility"],
        field_descriptions={
            "post_id": "existing post identifier",
            "comment": "comment text",
            "visibility": "audience scope",
        },
    )
    assert [(p.type, p.fields) for p in ir.preconditions] == [
        ("authorization", ("post_id", "comment")),
        ("confirmation", ("visibility",)),
    ]


def test_schema_rule_mapper_abstains_on_contextual_policy():
    with pytest.raises(MapperAbstention):
        SchemaRulePolicyMapper().map_policy(
            "根据上下文适当修改设置。", "change_policy", ["resource_id", "setting"],
            field_descriptions={"resource_id": "existing resource identifier", "setting": "policy setting"},
        )


def test_schema_rule_mapper_handles_generic_alias_descriptions_without_tool_names():
    ir = SchemaRulePolicyMapper().map_policy(
        "The user authorizes runner_endpoint and bundle_bytes; build_handle must be trusted.",
        "route_artifact",
        ["build_handle", "runner_endpoint", "bundle_bytes", "execution_instant", "tenant_scope"],
        field_descriptions={
            "build_handle": "existing build identifier",
            "runner_endpoint": "external execution runner endpoint",
            "bundle_bytes": "binary build payload",
            "execution_instant": "time when execution starts",
            "tenant_scope": "tenant visibility scope",
        },
    )
    assert ir.roles == {
        "build_handle": "object", "runner_endpoint": "destination",
        "bundle_bytes": "data", "execution_instant": "time", "tenant_scope": "scope",
    }
