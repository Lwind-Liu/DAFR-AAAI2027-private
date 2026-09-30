"""Schema-aware deterministic policy mapper used as a matched baseline.

This baseline consumes the same public inputs as the LLM mapper and produces the
same ConstraintIR.  Field descriptions drive role inference and explicit policy
phrases drive preconditions.  Ambiguous policy text abstains instead of guessing.
It is intended for protocol-faithful comparison, not as a claim that regular
expressions solve open-ended policy interpretation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .ir_compiler import IRPolicyCompiler
from .policy_ir import ConstraintIR, validate_constraint_ir
from .policy_mapper import MapperAbstention


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _field_in(text: str, field: str) -> bool:
    # Schema fields in the benchmark are ASCII identifiers. Boundaries avoid
    # matching ``id`` inside ``candidate`` while allowing snake_case names.
    return re.search(r"(?<![a-z0-9_])" + re.escape(field.lower()) + r"(?![a-z0-9_])", text) is not None


def _dedupe_fields(fields: Sequence[str], schema_fields: Sequence[str]) -> list[str]:
    wanted = set(fields)
    return [f for f in schema_fields if f in wanted]


def _role_for_field(field: str, description: str) -> str | None:
    text = _normalise(f"{field} {description}")
    # Description semantics have priority over bare names for collisions such
    # as destination (an arrival airport) and channel (endpoint vs setting).
    if re.search(r"arrival airport|publication endpoint|external publication endpoint", text):
        return "destination"
    if re.search(r"delivery channel(?! setting)|external (?:delivery )?channel|scope flag|visibility|audience|access (?:level|setting)|urgency|priority|severity|importance|retention|format|time zone|timezone|policy setting", text):
        if re.search(r"delivery channel(?! setting)|external (?:delivery )?channel", text):
            return "destination"
        return "scope"
    if re.search(r"external (?:[a-z]+ )?(?:recipient|destination|endpoint|operator|account|storage)|assigned (?:[a-z]+ )*(?:recipient|operator|owner|assignee|responder)|external (?:event )?(?:guest|attendee)", text):
        return "destination"
    if re.search(r"departure airport", text):
        return "object"
    if re.search(r"delivery region|routing queue|queue setting", text):
        return "scope"
    if re.search(r"(?:money|credit|payment|transfer) amount|passenger count|\bamount\b|\bquantity\b", text):
        return "amount"
    if re.search(r"event instant|(?:travel|reminder|meeting|event|execution) (?:date|time|instant)|time zone context", text):
        return "time" if "time zone context" not in text else "scope"
    if re.search(r"(?:body|content|comment|memo|subject|reason|payload|text|details?|summary|note|message|title|description)", text):
        return "data"
    if re.search(r"(?:existing|local) (?:[a-z]+ )?(?:resource|record|file|account|document|dataset|profile|case|member|project|workspace)|\b(?:identifier|resource id|record id|file id|document id|dataset id|profile id|case id|member id|team id|event id|task id|credit id|asset id|notice id|report id|post id|contact id|tracking id|transfer id|workspace id)\b", text):
        return "object"
    # Conservative fallbacks for common schema names. Unknown fields cause an
    # explicit abstention instead of silently dropping a security-relevant role.
    name = field.lower()
    if name.endswith("_id") or name in {"id", "path", "origin"}:
        return "object"
    if name in {"recipient", "destination", "payee", "assignee", "attendee", "attendees", "guests", "guest", "owner", "operator", "endpoint"}:
        return "destination"
    if name in {"amount", "quantity", "passengers"}:
        return "amount"
    if name in {"date", "time", "start_at", "start_time", "execute_at", "remind_at"}:
        return "time"
    if name in {"visibility", "audience", "priority", "urgency", "severity", "importance", "format", "retention", "retention_days", "retention_policy", "timezone", "delivery_mode", "include_private", "include_sensitive", "include_metadata", "include_line_items", "include_phone", "channel", "queue", "access_level", "new_visibility", "level", "setting"}:
        return "scope"
    if name in {"body", "content", "comment", "memo", "subject", "reason", "payload", "text", "details", "summary", "note", "message", "title", "description"}:
        return "data"
    return None


def _sentences(policy: str) -> list[str]:
    # Preserve ASCII field names while separating Chinese and English clauses.
    return [x.strip() for x in re.split(r"[。！？!?.;；\n]+", _normalise(policy)) if x.strip()]


def _positive_authorization(sentence: str) -> bool:
    if "授权" not in sentence:
        return False
    if re.search(r"(?:不能|不可|不提供|不额外|不需要|无需|不要|禁止).{0,10}授权", sentence):
        return False
    return bool(re.search(r"(?:明确|必须|需要|获得|用户|要求).{0,18}授权|授权.{0,18}(?:字段|后|才能|操作)", sentence))


def _positive_confirmation(sentence: str) -> bool:
    if "确认" not in sentence:
        return False
    return not bool(re.search(r"(?:不需要|无需|不能|不要|不额外).{0,8}确认", sentence))


def _positive_grounding(sentence: str) -> bool:
    # A negative source statement such as “不可信就停止” is still an explicit
    # grounding requirement; a webpage/tool-output warning alone is not.
    if not ("可信" in sentence or "来源" in sentence):
        return False
    return not bool(re.search(r"(?:不能|不可|不提供).{0,10}(?:可信|来源)", sentence))


def _positive_freshness(sentence: str) -> bool:
    return bool(re.search(r"(?:最新|新鲜|过期|fresh(?:ness)?|fresh)", sentence))


def _clause_requirements(clause: str, fields: Sequence[str]) -> dict[str, list[str]]:
    """Return field scopes without assigning a combined clause to both verbs."""
    result = {"authorization": [], "confirmation": [], "trusted_grounding": [], "state_freshness": []}
    auth = _positive_authorization(clause)
    confirm = _positive_confirmation(clause)
    mentioned = [field for field in fields if _field_in(clause, field)]
    if auth and confirm:
        # “授权并确认 visibility” scopes authorization to the left span and
        # confirmation to the right span. “授权与确认 recipient 和 amount”
        # scopes both requirements to the shared list before the conjunction.
        if re.search(r"并确认", clause):
            left, right = re.split(r"并确认", clause, maxsplit=1)
            left_fields = [field for field in fields if _field_in(left, field)]
            right_fields = [field for field in fields if _field_in(right, field)]
            result["authorization"] = left_fields
            result["confirmation"] = right_fields or left_fields
        elif re.search(r"(?:与|和)确认", clause):
            result["authorization"] = mentioned
            result["confirmation"] = mentioned
        else:
            result["authorization"] = mentioned
            result["confirmation"] = mentioned
    elif auth:
        result["authorization"] = mentioned
    elif confirm:
        result["confirmation"] = mentioned
    if _positive_grounding(clause):
        result["trusted_grounding"] = mentioned
    if _positive_freshness(clause):
        result["state_freshness"] = mentioned
    return result


@dataclass(frozen=True, slots=True)
class SchemaRulePolicyMapper:
    """Deterministic schema-aware mapper with explicit abstention."""

    provenance: str = "schema_rule_v1"

    def map_policy(self, policy: str, tool_name: str, schema_fields: Sequence[str], *,
                   effect_class: str | None = None,
                   field_descriptions: Mapping[str, str] | None = None) -> ConstraintIR:
        fields = tuple(schema_fields)
        text = _normalise(policy)
        # “根据上下文适当...” is intentionally under-specified. Treating it as
        # allow would make this baseline unsafe and hide mapping ambiguity.
        if re.search(r"根据上下文.{0,24}(?:适当|合理|修改|删除|清理|设置|执行)", text) and not re.search(r"(?:必须|需要|明确|确认|授权|可信|来源|不可信)", text):
            raise MapperAbstention("underspecified contextual policy")

        descriptions = {str(k): str(v) for k, v in (field_descriptions or {}).items()}
        roles: dict[str, str] = {}
        for field in fields:
            role = _role_for_field(field, descriptions.get(field, ""))
            if role is None:
                raise MapperAbstention(f"unknown role semantics for field {field}")
            roles[field] = role

        clauses = _sentences(policy)
        required: dict[str, list[str]] = {
            "authorization": [], "confirmation": [], "trusted_grounding": [],
            "state_freshness": [], "prerequisite": [],
        }
        for clause in clauses:
            parsed = _clause_requirements(clause, fields)
            for ptype, values in parsed.items():
                required[ptype].extend(values)

        preconditions: list[dict[str, Any]] = []
        for ptype in ("authorization", "confirmation", "trusted_grounding", "state_freshness", "prerequisite"):
            pfields = _dedupe_fields(required[ptype], fields)
            if pfields:
                preconditions.append({"type": ptype, "fields": pfields, "minimum": 1.0, "source": "trusted"})
        ir = ConstraintIR.from_dict({
            "version": "1", "tool_name": tool_name, "roles": roles,
            "preconditions": preconditions, "risk_budgets": [],
            "forbidden_effects": [], "provenance": self.provenance,
        })
        validate_constraint_ir(ir, schema_fields=fields)
        IRPolicyCompiler(ir, schema_fields=fields).compile()
        return ir


__all__ = ["SchemaRulePolicyMapper"]
