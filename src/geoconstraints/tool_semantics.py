from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from geoconstraints.text import flatten_value, lexicalize


META_TOOL_CALL_RE = re.compile(
    r"\b(?:mcp\s+)?tool\s+call\b|\bwith\s+parameters?\b|\bplanned\s+tool\b|\bexecute\s+tool\b",
    re.I,
)
PURE_COMPUTATION_RE = re.compile(
    r"\b("
    r"compute|calculate|calculator|convert|conversion|transform|translate|parse|format|validate|evaluate|compare|"
    r"estimate|derive|solve|measure|average|sum|multiply|divide|subtract|add|normalize|rank|score|"
    r"unit|timezone|time\s*zone|currency|math|formula|equation|tensor|matrix|vector|array"
    r")\b",
    re.I,
)
COMPUTATIONAL_CREATE_RE = re.compile(
    r"\b(?:create|build|construct|generate)\b.{0,32}\b(?:tensor|matrix|vector|array)\b",
    re.I,
)
READ_ONLY_RE = re.compile(
    r"(?:^|[ /_.:-])"
    r"(get|read|search|query|list|retrieve|check|checker|show|find|lookup|view|fetch|verify|verifier|"
    r"validate|validation|validator|details?|reviews?|images?|similar)"
    r"(?:$|[ /_.:-])",
    re.I,
)
SIDE_EFFECT_RE = re.compile(
    r"\b("
    r"send|sms|call|book|reserve|order|delete|update|modify|transfer|pay|purchase|cancel|submit|post|"
    r"create|refund|return|exchange|issue|credit|charge|debit|waive|grant|compensate|enable|disable|"
    r"activate|deactivate|resume|suspend|write|set|remove|invite|upload|publish"
    r")\b",
    re.I,
)
STRONG_SIDE_EFFECT_RE = re.compile(
    r"\b("
    r"send|sms|call|book|reserve|delete|update|modify|transfer|pay|cancel|submit|post|"
    r"create|refund|exchange|issue|credit|charge|debit|waive|grant|compensate|enable|disable|"
    r"activate|deactivate|resume|suspend|write|set|remove|invite|upload|publish"
    r")\b",
    re.I,
)
DISCLOSURE_RE = re.compile(r"\b(send|email|sms|message|share|forward|publish|upload|post)\b", re.I)
MARKET_DATA_READ_RE = re.compile(
    r"\b(order\s+book|merged\s+order\s+book|net\s+share\s+purchase\s+activity|purchase\s+activity|market\s+data)\b",
    re.I,
)
DATA_CALL_READ_RE = re.compile(
    r"\bcall\b.{0,64}\b(api|data|forecast|weather|endpoint|service)\b"
    r"|\b(api|data|forecast|weather|endpoint|service)\b.{0,64}\bcall\b"
    r"|\b(zip/post\s+code|post\s+code|postal\s+code|coordinates?\s+by|by\s+geographic\s+coordinates?)\b",
    re.I,
)


@dataclass(frozen=True)
class ToolSemantics:
    pure_computation: bool = False
    read_only: bool = False
    side_effect: bool = False
    external_disclosure: bool = False
    stateful_write: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "pure_computation": self.pure_computation,
            "read_only": self.read_only,
            "side_effect": self.side_effect,
            "external_disclosure": self.external_disclosure,
            "stateful_write": self.stateful_write,
        }


def _operation_name(tool_name: str) -> str:
    return str(tool_name or "").rsplit(":", 1)[-1].rsplit(".", 1)[-1]


def _semantic_text(tool_name: str, action_text: str = "", arguments: Mapping[str, Any] | None = None) -> str:
    operation = _operation_name(tool_name)
    args_text = flatten_value(arguments or {})
    text = lexicalize(" ".join((operation, str(action_text or ""), args_text))).replace("/", " ")
    return META_TOOL_CALL_RE.sub(" ", text)


def _operation_semantic_text(tool_name: str, action_text: str = "") -> str:
    operation = _operation_name(tool_name)
    text = lexicalize(" ".join((operation, str(action_text or "")))).replace("/", " ")
    return META_TOOL_CALL_RE.sub(" ", text)


def classify_tool_semantics(
    tool_name: str,
    action_text: str = "",
    arguments: Mapping[str, Any] | None = None,
) -> ToolSemantics:
    text = _semantic_text(tool_name, action_text, arguments)
    operation_text = _operation_semantic_text(tool_name, action_text)
    market_data_read = bool(MARKET_DATA_READ_RE.search(operation_text))
    data_call_read = bool(DATA_CALL_READ_RE.search(operation_text))
    computational_create = bool(COMPUTATIONAL_CREATE_RE.search(operation_text))
    read_only_signal = bool(READ_ONLY_RE.search(operation_text) or market_data_read or data_call_read)
    side_effect_signal = bool(SIDE_EFFECT_RE.search(operation_text))
    strong_side_effect = bool(STRONG_SIDE_EFFECT_RE.search(operation_text))
    side_effect = (
        False
        if market_data_read or data_call_read or computational_create
        else strong_side_effect or (side_effect_signal and not read_only_signal)
    )
    pure_computation = (bool(PURE_COMPUTATION_RE.search(text)) or computational_create) and not side_effect
    read_only = pure_computation or (read_only_signal and not side_effect)
    external_disclosure = bool(DISCLOSURE_RE.search(operation_text))
    stateful_write = side_effect and not pure_computation
    return ToolSemantics(
        pure_computation=pure_computation,
        read_only=read_only,
        side_effect=side_effect,
        external_disclosure=external_disclosure,
        stateful_write=stateful_write,
    )


def tool_semantics_from_raw(raw: Mapping[str, Any] | None) -> ToolSemantics | None:
    if not raw:
        return None
    value = raw.get("tool_semantics")
    if not isinstance(value, Mapping) and isinstance(raw.get("raw"), Mapping):
        value = raw["raw"].get("tool_semantics")
    if not isinstance(value, Mapping):
        return None
    return ToolSemantics(
        pure_computation=bool(value.get("pure_computation", False)),
        read_only=bool(value.get("read_only", False)),
        side_effect=bool(value.get("side_effect", False)),
        external_disclosure=bool(value.get("external_disclosure", False)),
        stateful_write=bool(value.get("stateful_write", False)),
    )
