from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from geoconstraints.embeddings import HashingTextEncoder, TextEncoder
from geoconstraints.schemas import ToolAction
from geoconstraints.text import (
    ASK_CONFIRM_RE,
    EXTERNAL_RECIPIENT_RE,
    FINANCIAL_RE,
    HUMAN_ESCALATION_RE,
    IRREVERSIBLE_RE,
    POLICY_LOOKUP_RE,
    PRIVACY_RE,
    READ_RE,
    REDACT_RE,
    SENSITIVE_VALUE_RE,
    SIDE_EFFECT_RE,
    STATE_RE,
    STATE_READ_RE,
    TARGET_RE,
    USER_RECIPIENT_RE,
    WRITE_RE,
    flatten_value,
    lexicalize,
)
from geoconstraints.tool_semantics import classify_tool_semantics, tool_semantics_from_raw
from geoconstraints.trust import trusted_evidence_summary


NEGATED_PRIVACY_CONTEXT_RE = re.compile(
    r"\b(no|not|without|none)\b.{0,32}\b(private|personal|sensitive|account|phone|email|token|contact|data)\b",
    re.I,
)
REDACTED_CONTENT_RE = re.compile(
    r"\b(redacted|masked|anonymi[sz]ed|de[- ]identified|without\s+(?:personal|private|sensitive)\s+(?:data|information|identifiers?)|"
    r"no\s+(?:personal|private|sensitive)\s+(?:data|information|identifiers?))\b"
    r"|\[(?:redacted|masked|hidden)\]",
    re.I,
)
INTERNAL_RECIPIENT_RE = re.compile(
    r"\b(internal|employee|staff|coworker|colleague|support team|company approved|approved internal)\b"
    r"|@[^\s@]+\.(?:internal|corp|local)\b",
    re.I,
)
READ_ONLY_ACTION_RE = re.compile(
    r"(?:^|[ /_.:-])"
    r"(get|read|search|query|list|retrieve|check|checker|show|find|lookup|view|fetch|verify|verifier|"
    r"validate|validation|validator|details?|reviews?|images?|similar)"
    r"(?:$|[ /_.:-])",
    re.I,
)
EXTERNAL_WEB_ACCESS_TOOL_RE = re.compile(
    r"\b(?:get|fetch|open|visit|browse|request|read|retrieve|load|crawl|download)[ _.-]*(?:webpage|web_page|website|site|url|uri|link|file)\b"
    r"|\b(?:webpage|web_page|website|site|url|uri|link|browser|web)\b.{0,32}\b"
    r"(?:get|fetch|open|visit|browse|request|read|retrieve|load|crawl|download)\b",
    re.I,
)
EXTERNAL_WEB_ACCESS_ACTION_RE = re.compile(
    r"\b(?:get|fetch|open|visit|browse|request|read|retrieve|load|crawl|download|click|follow)\b.{0,80}\b"
    r"(?:webpage|web page|website|site|url|uri|link|http|https)\b"
    r"|\b(?:http|https)://",
    re.I,
)
URL_LIKE_RE = re.compile(r"\b(?:https?://|www\.|[a-z0-9.-]+\.(?:com|org|net|io|ai|co|edu|gov|dev|app)(?:/|\b))", re.I)
INTERNAL_URL_RE = re.compile(
    r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0|::1)\b"
    r"|(?:^|[./])(?:internal|corp|local|intranet|policy-store|policy_store)(?:[./:]|$)",
    re.I,
)
EXPLICIT_MUTATION_RE = re.compile(
    r"\b(create|add|insert|update|modify|delete|remove|set|change|book|reserve|cancel|refund|return|send|submit|purchase|pay|withdraw|exchange|"
    r"enable|disable|activate|deactivate|resume|suspend)\b",
    re.I,
)
STRONG_MUTATION_RE = re.compile(
    r"\b(create|add|insert|update|modify|delete|remove|set|change|book|reserve|cancel|refund|send|submit|pay|withdraw|exchange|"
    r"enable|disable|activate|deactivate|resume|suspend)\b",
    re.I,
)
COMPUTATIONAL_ACTION_RE = re.compile(
    r"\b(compute|calculate|convert|analy[sz]e|summari[sz]e|extract|compare|classify|estimate|predict|derive|evaluate|"
    r"measure|trend|average|avg|price|candlestick|forecast|recommend|transform|change basis|linear algebra)\b",
    re.I,
)
ANALYTIC_CHANGE_RE = re.compile(r"\b(volume|price|percent(?:age)?|rate)\s+change\b|\brate\s+of\s+change\b", re.I)
MARKET_DATA_READ_ACTION_RE = re.compile(
    r"\b(order\s+book|merged\s+order\s+book|net\s+share\s+purchase\s+activity|purchase\s+activity|market\s+data)\b",
    re.I,
)
DATA_CALL_READ_ACTION_RE = re.compile(
    r"\bcall\b.{0,64}\b(api|data|forecast|weather|endpoint|service)\b"
    r"|\b(api|data|forecast|weather|endpoint|service)\b.{0,64}\bcall\b"
    r"|\b(zip/post\s+code|post\s+code|postal\s+code|coordinates?\s+by|by\s+geographic\s+coordinates?)\b",
    re.I,
)
IDENTIFIER_LOOKUP_OPERATION_RE = re.compile(r"^[a-z0-9_]*_id$", re.I)
USER_INTENT_REQUEST_ACTION_RE = re.compile(
    r"\b(ask|clarify|check|confirm|request)\b.{0,72}\b"
    r"(want|need|request|accept|agree|complain|compensation|refund|payment|insurance|offer|proceed)\b",
    re.I,
)
SAFE_RESPONSE_ACTION_RE = re.compile(
    r"\b(draft|compose|prepare|write)\b.{0,56}\b(?:safe|non[- ]?side[- ]?effect|read[- ]?only)\b.{0,56}\b"
    r"(?:response|reply|plan|message)\b",
    re.I,
)
INTENT_GATED_ACTION_RE = re.compile(
    r"\b(offer|compensate|refund|payment|pay|purchase|book|reserve|send|apply|submit|accept|change|cancel|use|add)\b",
    re.I,
)
EXISTING_RECORD_ACTION_RE = re.compile(
    r"\b(update|modify|delete|remove|set|change|cancel|return|exchange|enable|disable|activate|deactivate|resume|suspend)\b",
    re.I,
)


STRUCTURED_FEATURE_NAMES = [
    "tool_is_write",
    "tool_is_read",
    "irreversibility",
    "financial_risk",
    "privacy_risk",
    "external_side_effect",
    "confirmation_missing",
    "authorization_missing",
    "read_before_write_gap",
    "policy_evidence_gap",
    "state_dependency_gap",
    "argument_sensitivity",
    "recipient_or_target_risk",
    "amount_or_quantity_risk",
    "history_conflict",
    "previous_tool_count",
    "write_count",
    "same_target_modified_before",
    "loop_or_retry_count",
    "is_clarification_action",
    "is_user_confirmation_request",
    "is_policy_lookup",
    "is_state_read",
    "is_identity_verification_action",
    "is_user_intent_request_action",
    "is_redaction_action",
    "is_human_escalation",
    "recipient_is_user",
    "recipient_is_external",
    "is_private_data_disclosure",
    "is_private_data_access",
    "is_external_web_access",
    "is_existing_record_write",
    "irreversible_without_confirmation",
    "side_effect_without_confirmation",
    "privacy_disclosure_without_auth",
    "existing_record_write_without_read",
    "financial_action_without_auth",
    "private_data_access_without_auth",
    "external_web_access_without_user_intent",
    "user_intent_missing",
    "instruction_in_untrusted_context",
    "policy_override_attempt",
    "evidence_from_untrusted_source",
    "trusted_action_family_mismatch",
    "trusted_confirmation_seen",
    "trusted_authorization_seen",
    "trusted_identity_seen",
    "trusted_source_grounding_seen",
    "trusted_user_intent_seen",
    "trusted_state_seen",
    "trusted_manager_approval_seen",
]


def _numeric_amount_score(arguments: Mapping[str, Any]) -> float:
    best = 0.0
    for key, value in arguments.items():
        key_text = str(key).lower()
        if not any(tok in key_text for tok in ("amount", "quantity", "price", "total", "count", "num", "limit")):
            continue
        try:
            num = abs(float(value))
        except (TypeError, ValueError):
            continue
        best = max(best, min(1.0, math.log1p(num) / math.log1p(1000.0)))
    return best


def _history_target_seen(action: ToolAction, target: str) -> bool:
    if not target:
        return False
    for item in action.history:
        text = lexicalize(flatten_value(item))
        if target in text and WRITE_RE.search(text):
            return True
    return False


def _target_key(arguments: Mapping[str, Any]) -> str:
    for key in ("target", "user_id", "account_id", "email", "phone", "recipient", "to", "id"):
        if key in arguments:
            return f"{key} {arguments[key]}"
    return flatten_value(arguments)[:80]


def _recipient_text(action_text: str, arguments: Mapping[str, Any]) -> str:
    recipient_keys = ["to", "recipient", "receiver"]
    if re.search(r"\b(send|email|message|sms|call|notify|share|forward|post|publish|upload|webpage|website)\b", action_text, re.I):
        recipient_keys.extend(["email", "phone_number", "phone"])
    if re.search(r"\b(post|publish|upload|webpage|website|url|link)\b", action_text, re.I):
        recipient_keys.extend(["url", "link", "website", "site"])
    return lexicalize(" ".join(str(arguments.get(key, "")) for key in recipient_keys))


def _operation_text(tool_name: str, action_text: str) -> str:
    operation = str(tool_name).rsplit(":", 1)[-1].rsplit(".", 1)[-1]
    return lexicalize(" ".join([operation, action_text]))


def _history_text(action: ToolAction) -> str:
    return " ".join(lexicalize(flatten_value(item)) for item in action.history[-12:])


def _is_external_web_access(
    *,
    operation_name: str,
    direct_action_text: str,
    args_text: str,
    policy_lookup: float,
    state_read: float,
    safe_repair: float,
) -> float:
    if policy_lookup or state_read or safe_repair:
        return 0.0
    operation = lexicalize(operation_name)
    operation_and_direct_text = " ".join([operation, direct_action_text])
    combined = " ".join([operation_and_direct_text, args_text])
    web_tool = bool(EXTERNAL_WEB_ACCESS_TOOL_RE.search(operation_and_direct_text))
    web_action = bool(EXTERNAL_WEB_ACCESS_ACTION_RE.search(combined))
    url_like = bool(URL_LIKE_RE.search(args_text))
    internal_url = bool(INTERNAL_URL_RE.search(args_text))
    if internal_url and not (web_tool or web_action):
        return 0.0
    if web_tool or web_action:
        return 0.0 if internal_url and not re.search(r"\b(external|public|third party|phishing|untrusted)\b", combined, re.I) else 1.0
    if url_like and re.search(r"\b(get|fetch|open|visit|browse|request|read|retrieve|load|download|click|follow)\b", operation, re.I):
        return 1.0
    return 0.0


def structured_feature_dict(action: ToolAction) -> dict[str, float]:
    args_text = lexicalize(flatten_value(action.arguments))
    operation_name = str(action.tool_name).rsplit(":", 1)[-1].rsplit(".", 1)[-1]
    direct_action_text = _operation_text(action.tool_name, action.action_text)
    action_text = lexicalize(" ".join([action.tool_name, action.action_text, args_text]))
    action_text_lower = action_text.lower()
    history_text = _history_text(action)
    context = " ".join(part for part in (action.context_text or "", history_text) if part)
    combined = " ".join([action_text, context])
    evidence = trusted_evidence_summary(action)
    semantic_hint = tool_semantics_from_raw(action.raw) or classify_tool_semantics(
        action.tool_name,
        action.action_text,
        action.arguments,
    )

    recipient_text = _recipient_text(direct_action_text, action.arguments)
    recipient_is_user = 1.0 if USER_RECIPIENT_RE.search(recipient_text) else 0.0
    recipient_context = " ".join([recipient_text, direct_action_text])
    recipient_is_internal = 1.0 if INTERNAL_RECIPIENT_RE.search(recipient_context) else 0.0
    recipient_is_external = 1.0 if EXTERNAL_RECIPIENT_RE.search(recipient_text) and not recipient_is_user and not recipient_is_internal else 0.0

    confirmation_request = 1.0 if ASK_CONFIRM_RE.search(combined) and (recipient_is_user or "ask" in action_text_lower) else 0.0
    identity_verification_action = (
        1.0
        if re.search(
            r"\b(verify|verified|authenticate|authenticated|identify|identified|find|locate|located|get|search|lookup)\b"
            r".{0,56}\b(identity|customer|user|account|user id)\b"
            r"|\b(ask|request)\b.{0,56}\b(verify|authenticate|identify|identity verification|proof of identity)\b",
            action_text,
            re.I,
        )
        else 0.0
    )
    policy_lookup = 1.0 if POLICY_LOOKUP_RE.search(action_text) or "lookup policy" in action_text else 0.0
    state_read = (
        1.0
        if STATE_READ_RE.search(direct_action_text) or "read state" in direct_action_text or "read current" in direct_action_text
        else 0.0
    )
    user_intent_request = 1.0 if USER_INTENT_REQUEST_ACTION_RE.search(action_text) and (recipient_is_user or "ask" in action_text_lower) else 0.0
    redaction = 1.0 if REDACT_RE.search(action_text) else 0.0
    human_escalation = 1.0 if HUMAN_ESCALATION_RE.search(action_text) else 0.0
    safe_response = 1.0 if operation_name == "draft_safe_response" or SAFE_RESPONSE_ACTION_RE.search(action_text) else 0.0
    safe_repair = (
        1.0
        if any((confirmation_request, user_intent_request, policy_lookup, state_read, redaction, human_escalation, safe_response))
        else 0.0
    )

    raw_read = 1.0 if READ_RE.search(direct_action_text) else 0.0
    identifier_lookup_action = bool(IDENTIFIER_LOOKUP_OPERATION_RE.fullmatch(operation_name))
    computational_action = bool(
        semantic_hint.pure_computation
        or COMPUTATIONAL_ACTION_RE.search(direct_action_text)
        or ANALYTIC_CHANGE_RE.search(direct_action_text)
    )
    computational_read_only = bool(semantic_hint.pure_computation) or (
        computational_action and not bool(SIDE_EFFECT_RE.search(direct_action_text))
    )
    market_data_read = bool(MARKET_DATA_READ_ACTION_RE.search(direct_action_text))
    data_call_read = bool(DATA_CALL_READ_ACTION_RE.search(direct_action_text))
    read_only_signal = bool(READ_ONLY_ACTION_RE.search(direct_action_text) or market_data_read or data_call_read)
    read_only_action = identifier_lookup_action or computational_read_only or market_data_read or data_call_read or (
        semantic_hint.read_only
        or
        read_only_signal
        and not bool(STRONG_MUTATION_RE.search(direct_action_text))
    )
    raw_write = 0.0 if read_only_action else (1.0 if WRITE_RE.search(direct_action_text) else 0.0)
    is_read = 1.0 if raw_read or read_only_action or policy_lookup or state_read else 0.0
    is_write = 0.0 if policy_lookup or state_read or redaction else raw_write
    side_effect = (
        0.0
        if safe_repair or read_only_action
        else (1.0 if semantic_hint.side_effect or SIDE_EFFECT_RE.search(direct_action_text) else is_write)
    )
    irreversible = 0.0 if safe_repair or read_only_action else (1.0 if IRREVERSIBLE_RE.search(direct_action_text) else 0.0)
    financial = 1.0 if FINANCIAL_RE.search(combined) else 0.0
    financial_action = 1.0 if financial and side_effect else 0.0
    privacy_from_action = bool(PRIVACY_RE.search(action_text))
    privacy_from_context = bool(PRIVACY_RE.search(context)) and not bool(NEGATED_PRIVACY_CONTEXT_RE.search(context))
    privacy = 1.0 if privacy_from_action or privacy_from_context else 0.0
    redacted_content = bool(REDACTED_CONTENT_RE.search(" ".join([action_text, args_text, context])))
    target_risk = 1.0 if TARGET_RE.search(args_text) or TARGET_RE.search(action.tool_name) else 0.0
    amount_risk = max(_numeric_amount_score(action.arguments), 1.0 if FINANCIAL_RE.search(args_text) else 0.0)
    arg_sensitivity = 1.0 if SENSITIVE_VALUE_RE.search(args_text) or privacy else 0.0
    private_disclosure = 1.0 if privacy and side_effect and (recipient_is_external or "external" in combined) and not redacted_content else 0.0
    private_access = 1.0 if privacy and is_read and not redaction and not policy_lookup else 0.0

    read_count = int(action.raw.get("read_count_before_this_write", 0) or 0)
    if not read_count:
        read_count = sum(1 for item in action.history if READ_RE.search(lexicalize(flatten_value(item))))
    write_count = sum(1 for item in action.history if WRITE_RE.search(lexicalize(flatten_value(item))))
    same_tool_count = sum(1 for item in action.history if action.tool_name and action.tool_name in flatten_value(item))
    target = _target_key(action.arguments)
    has_state_evidence = bool(read_count or evidence.state_read_seen)
    existing_record_write = (
        1.0
        if is_write and (EXISTING_RECORD_ACTION_RE.search(direct_action_text) or STATE_RE.search(action_text))
        else 0.0
    )
    state_dependency_gap = 1.0 if existing_record_write and not has_state_evidence else 0.0
    confirmation_seen = bool(evidence.confirmation_seen)
    authorization_seen = bool(evidence.authorization_seen or evidence.manager_approval_seen)
    private_access_authorized = bool(authorization_seen or evidence.identity_verified_seen)
    user_intent_action = 1.0 if INTENT_GATED_ACTION_RE.search(action_text) or side_effect else 0.0
    external_web_access = _is_external_web_access(
        operation_name=operation_name,
        direct_action_text=direct_action_text,
        args_text=args_text,
        policy_lookup=policy_lookup,
        state_read=state_read,
        safe_repair=safe_repair,
    )

    values = {
        "tool_is_write": is_write,
        "tool_is_read": is_read,
        "irreversibility": irreversible,
        "financial_risk": financial,
        "privacy_risk": privacy,
        "external_side_effect": side_effect,
        "confirmation_missing": 1.0 if (side_effect or irreversible) and not confirmation_seen and not safe_repair else 0.0,
        "authorization_missing": 1.0
        if (
            (financial_action or private_disclosure) and not authorization_seen
            or private_access and not private_access_authorized
        )
        and not safe_repair
        else 0.0,
        "read_before_write_gap": 1.0 if existing_record_write and not has_state_evidence and not safe_repair else 0.0,
        "policy_evidence_gap": 1.0 if side_effect and not evidence.policy_seen else 0.0,
        "state_dependency_gap": state_dependency_gap,
        "argument_sensitivity": arg_sensitivity,
        "recipient_or_target_risk": target_risk,
        "amount_or_quantity_risk": amount_risk,
        "history_conflict": 1.0 if evidence.conflict_seen else 0.0,
        "previous_tool_count": min(1.0, len(action.history) / 10.0),
        "write_count": min(1.0, write_count / 5.0),
        "same_target_modified_before": 1.0 if _history_target_seen(action, target) else 0.0,
        "loop_or_retry_count": min(1.0, same_tool_count / 3.0),
        "is_clarification_action": 1.0 if safe_repair else 0.0,
        "is_user_confirmation_request": confirmation_request,
        "is_policy_lookup": policy_lookup,
        "is_state_read": state_read,
        "is_identity_verification_action": identity_verification_action,
        "is_user_intent_request_action": user_intent_request,
        "is_redaction_action": redaction,
        "is_human_escalation": human_escalation,
        "recipient_is_user": recipient_is_user,
        "recipient_is_external": recipient_is_external,
        "is_private_data_disclosure": private_disclosure,
        "is_private_data_access": private_access,
        "is_external_web_access": external_web_access,
        "is_existing_record_write": existing_record_write,
        "irreversible_without_confirmation": 1.0 if irreversible and not confirmation_seen and not safe_repair else 0.0,
        "side_effect_without_confirmation": 1.0 if side_effect and not confirmation_seen and not safe_repair else 0.0,
        "privacy_disclosure_without_auth": 1.0 if private_disclosure and not authorization_seen and not safe_repair else 0.0,
        "existing_record_write_without_read": 1.0 if existing_record_write and not has_state_evidence and not safe_repair else 0.0,
        "financial_action_without_auth": 1.0 if financial_action and not authorization_seen and not safe_repair else 0.0,
        "private_data_access_without_auth": 1.0 if private_access and not private_access_authorized and not safe_repair else 0.0,
        "external_web_access_without_user_intent": 1.0
        if external_web_access and not evidence.user_intent_seen and not safe_repair
        else 0.0,
        "user_intent_missing": 1.0 if user_intent_action and not evidence.user_intent_seen and not safe_repair else 0.0,
        "instruction_in_untrusted_context": 1.0 if evidence.injection_seen else 0.0,
        "policy_override_attempt": 1.0 if evidence.injection_seen else 0.0,
        "evidence_from_untrusted_source": 1.0 if evidence.untrusted_evidence_seen else 0.0,
        "trusted_action_family_mismatch": 1.0 if bool(action.raw.get("trusted_action_family_mismatch")) else 0.0,
        "trusted_confirmation_seen": 1.0 if evidence.confirmation_seen else 0.0,
        "trusted_authorization_seen": 1.0 if evidence.authorization_seen else 0.0,
        "trusted_identity_seen": 1.0 if evidence.identity_verified_seen else 0.0,
        "trusted_source_grounding_seen": 1.0 if evidence.source_grounding_seen else 0.0,
        "trusted_user_intent_seen": 1.0 if evidence.user_intent_seen else 0.0,
        "trusted_state_seen": 1.0 if evidence.state_read_seen else 0.0,
        "trusted_manager_approval_seen": 1.0 if evidence.manager_approval_seen else 0.0,
    }
    return {name: float(np.clip(values[name], 0.0, 1.0)) for name in STRUCTURED_FEATURE_NAMES}


@dataclass
class FeatureSpace:
    encoder: TextEncoder
    structured_names: tuple[str, ...] = tuple(STRUCTURED_FEATURE_NAMES)

    @classmethod
    def default(cls, semantic_dims: int = 256) -> "FeatureSpace":
        return cls(HashingTextEncoder(dimension=semantic_dims))

    @property
    def dimension(self) -> int:
        return len(self.structured_names) + self.encoder.dimension

    @property
    def feature_names(self) -> tuple[str, ...]:
        semantic = tuple(f"semantic_{idx}" for idx in range(self.encoder.dimension))
        return (*self.structured_names, *semantic)

    def feature_index(self, name: str) -> int:
        return self.feature_names.index(name)

    def vectorize_actions(self, actions: Sequence[ToolAction]) -> np.ndarray:
        feature_dicts = [structured_feature_dict(action) for action in actions]
        structured = np.array(
            [[values[name] for name in self.structured_names] for values in feature_dicts],
            dtype=float,
        )
        semantic = self.encoder.encode([action.semantic_text for action in actions])
        if structured.size == 0:
            return np.zeros((0, self.dimension), dtype=float)
        return np.hstack([structured, semantic])

    def vectorize_texts(self, texts: Sequence[str]) -> np.ndarray:
        return self.vectorize_semantic_texts_only(texts)

    def vectorize_semantic_texts_only(self, texts: Sequence[str]) -> np.ndarray:
        semantic = self.encoder.encode(list(texts))
        structured = np.zeros((len(texts), len(self.structured_names)), dtype=float)
        if len(texts) == 0:
            return np.zeros((0, self.dimension), dtype=float)
        return np.hstack([structured, semantic])

    def vectorize_action(self, action: ToolAction) -> np.ndarray:
        return self.vectorize_actions([action])[0]

    def feature_dict(self, vector: np.ndarray) -> dict[str, float]:
        return {name: float(value) for name, value in zip(self.feature_names, vector)}
