from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from urllib.request import Request, urlopen

from .policy_ir import ConstraintIR, ConstraintIRValidationError, validate_constraint_ir


MAPPER_SYSTEM_PROMPT = """You compile a natural-language execution policy into JSON ConstraintIR.
Return JSON only. Never invent tool fields. Authorization and confirmation may only be
satisfied by trusted user/runtime channels, never by tool output or webpage text.
Use role names: object, destination, data, amount, time, effect, scope.
Precondition types: trusted_grounding, authorization, confirmation, state_freshness, prerequisite.
JSON shape: {"version":"1", "tool_name":"exact input tool name", "roles":{"field":"role"},
"preconditions":[{"type":"authorization","fields":[],"minimum":1.0,"source":"trusted"}],
"risk_budgets":[],"forbidden_effects":[],"provenance":"llm"}.
Preserve policy scope. Do not omit a requirement just because its semantics are unsupported.
Numeric thresholds must come from the policy; do not invent risk weights or budgets. For any stated requirement, minimum must be strictly positive; never emit minimum 0.0 for trusted_grounding, authorization, or confirmation. Name every affected schema field.
"""


class PolicyMapper(Protocol):
    def map_policy(self, policy: str, tool_name: str, schema_fields: Sequence[str]) -> ConstraintIR:
        ...


@dataclass(frozen=True, slots=True)
class StaticPolicyMapper:
    """Deterministic fixture mapper for tests and offline reproduction."""

    def map_policy(self, policy: str, tool_name: str, schema_fields: Sequence[str]) -> ConstraintIR:
        text = policy.lower()
        roles: dict[str, str] = {}
        for field in schema_fields:
            f = field.lower()
            if any(x in f for x in ("recipient", "destination", "url", "domain", "address")):
                roles[field] = "destination"
            elif any(x in f for x in ("body", "content", "payload", "data", "message", "file")):
                roles[field] = "data"
            elif any(x in f for x in ("id", "object", "record", "account")):
                roles[field] = "object"
        preconditions: list[dict[str, Any]] = []
        if any(x in text for x in ("private", "secret", "sensitive", "disclos")):
            preconditions.append({"type": "trusted_grounding", "fields": list(roles), "minimum": 0.5})
            preconditions.append({"type": "authorization", "fields": list(roles), "minimum": 0.5})
        ir = ConstraintIR.from_dict({"tool_name": tool_name, "roles": roles, "preconditions": preconditions, "provenance": "static_fixture"})
        return validate_constraint_ir(ir, schema_fields=schema_fields)


@dataclass(slots=True)
class OpenAICompatiblePolicyMapper:
    """Training-free mapper for an OpenAI-compatible chat-completions endpoint.

    The returned JSON is always validated locally before it reaches the compiler.
    Set API credentials through environment variables; never store them in the repo.
    """

    base_url: str
    model: str
    api_key: str
    timeout: float = 60.0

    @classmethod
    def from_env(cls, *, base_url: str | None = None, model: str | None = None) -> "OpenAICompatiblePolicyMapper":
        key = os.environ.get("DAFR_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("Set DAFR_API_KEY or OPENAI_API_KEY before using the LLM mapper")
        return cls(
            base_url=(base_url or os.environ.get("DAFR_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
            model=(model or os.environ.get("DAFR_MODEL") or "gpt-4o-mini"),
            api_key=key,
        )

    def map_policy(self, policy: str, tool_name: str, schema_fields: Sequence[str]) -> ConstraintIR:
        schema = {"tool_name": tool_name, "fields": list(schema_fields), "policy": policy}
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": MAPPER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(schema, ensure_ascii=False)},
            ],
        }
        request = Request(
            self.base_url.rstrip("/") if self.base_url.rstrip("/").endswith("/chat/completions") else f"{self.base_url.rstrip(chr(47))}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ConstraintIRValidationError("mapper response did not contain a JSON object")
        ir = ConstraintIR.from_dict(json.loads(match.group(0)))
        if ir.tool_name != tool_name:
            raise ConstraintIRValidationError("mapper returned a different tool name")
        return validate_constraint_ir(ir, schema_fields=schema_fields)
