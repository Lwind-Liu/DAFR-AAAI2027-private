from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from geoconstraints.schemas import EvidenceEvent, PredicateKind, SourceChannel, ToolAction, TrustLevel
from geoconstraints.scope import normalized_terms
from geoconstraints.text import (
    MISSING_AUTH_RE,
    MISSING_CONFIRM_RE,
    MISSING_IDENTITY_RE,
    MISSING_MANAGER_APPROVAL_RE,
    MISSING_POLICY_RE,
    MISSING_STATE_RE,
    MISSING_USER_INTENT_RE,
    USER_INTENT_RE,
    evidence_flags,
    flatten_value,
    lexicalize,
)


UNTRUSTED_CHANNELS = {
    SourceChannel.RETRIEVED_DOC,
    SourceChannel.WEBPAGE,
    SourceChannel.EMAIL,
    SourceChannel.UNTRUSTED_TEXT,
}
POLICY_CHANNELS = {SourceChannel.SYSTEM_POLICY, SourceChannel.DEVELOPER_POLICY, SourceChannel.POLICY_STORE}
USER_EVIDENCE_CHANNELS = {SourceChannel.USER_DIRECTIVE}
STATE_CHANNELS = {SourceChannel.TOOL_RESULT, SourceChannel.AGENT_MEMORY, SourceChannel.POLICY_STORE}

INJECTION_RE = re.compile(
    r"\b(ignore|override|bypass|disable|forget|do not follow|don't follow|jailbreak|"
    r"system prompt|developer instruction|previous instruction|all constraints|safety policy|"
    r"higher priority|priority than|guardrail|guardrails|safety rule|safety rules|"
    r"policy no longer applies|policy does not apply|rules no longer apply|proceed anyway)\b",
    re.I,
)
DIRECT_USER_REQUEST_RE = re.compile(
    r"\b(please|can you|could you|would you|i want|i need|i would like|"
    r"send|share|email|message|create|add|invite|book|reserve|cancel|delete|remove|"
    r"update|modify|change|submit|purchase|pay|transfer|refund|return|exchange|"
    r"post|publish|forward|upload|download|visit|click|read|get|concatenate|include|leak)\b",
    re.I,
)
PRIVATE_REFERENCE_RE = re.compile(
    r"\b(private|personal|sensitive|confidential|pii|account|phone|email|address|contact|token|password|credential|"
    r"ssn|passport|identity|medical|health|api key|secret)\b",
    re.I,
)
FIRST_PERSON_PRIVATE_RE = re.compile(
    r"\b(?:my|mine|me|myself|our|ours)\b.{0,48}\b"
    r"(?:private|personal|sensitive|confidential|pii|account|phone|email|address|contact|token|password|credential|"
    r"ssn|passport|identity|medical|health|api key|secret)\b"
    r"|\b(?:private|personal|sensitive|confidential|pii|account|phone|email|address|contact|token|password|credential|"
    r"ssn|passport|identity|medical|health|api key|secret)\b.{0,48}\b(?:of\s+)?(?:me|mine|my|our|ours)\b",
    re.I,
)
GENERIC_REQUEST_TERMS = {
    "add",
    "call",
    "cancel",
    "change",
    "create",
    "delete",
    "email",
    "forward",
    "get",
    "invite",
    "message",
    "modify",
    "post",
    "read",
    "remove",
    "send",
    "share",
    "submit",
    "tool",
    "update",
    "write",
}


@dataclass(frozen=True)
class TrustedEvidenceSummary:
    confirmation_seen: bool = False
    authorization_seen: bool = False
    identity_verified_seen: bool = False
    source_grounding_seen: bool = False
    user_intent_seen: bool = False
    manager_approval_seen: bool = False
    policy_seen: bool = False
    state_read_seen: bool = False
    conflict_seen: bool = False
    injection_seen: bool = False
    untrusted_evidence_seen: bool = False
    confirmation_targets: tuple[str, ...] = ()


def normalize_channel(value: Any) -> SourceChannel:
    if isinstance(value, SourceChannel):
        return value
    text = str(value or SourceChannel.USER_DIRECTIVE.value).upper()
    try:
        return SourceChannel(text)
    except ValueError:
        return SourceChannel.UNTRUSTED_TEXT


def channel_trust(channel: SourceChannel) -> TrustLevel:
    if channel in UNTRUSTED_CHANNELS:
        return TrustLevel.UNTRUSTED
    if channel in STATE_CHANNELS:
        return TrustLevel.STATE_TRUSTED
    return TrustLevel.TRUSTED


def parse_evidence_event(value: EvidenceEvent | Mapping[str, Any] | str, default_channel: SourceChannel) -> EvidenceEvent:
    if isinstance(value, EvidenceEvent):
        return value
    if isinstance(value, Mapping):
        channel = normalize_channel(value.get("channel", default_channel))
        trust_value = value.get("trust")
        trust = TrustLevel(str(trust_value).upper()) if trust_value else None
        kind_value = value.get("kind")
        kind = PredicateKind(str(kind_value).upper()) if kind_value else None
        return EvidenceEvent(
            text=str(value.get("text", "")),
            channel=channel,
            trust=trust,
            kind=kind,
            target=str(value["target"]) if value.get("target") is not None else None,
            actor=str(value["actor"]) if value.get("actor") is not None else None,
            metadata=dict(value.get("metadata", {})),
        )
    return EvidenceEvent(text=str(value), channel=default_channel)


def evidence_events(action: ToolAction) -> tuple[EvidenceEvent, ...]:
    raw_events = action.raw.get("evidence_events", action.raw.get("evidence", ()))
    default_channel = normalize_channel(action.raw.get("context_channel", SourceChannel.USER_DIRECTIVE))
    events: list[EvidenceEvent] = []
    if isinstance(raw_events, Iterable) and not isinstance(raw_events, (str, bytes, Mapping)):
        events.extend(parse_evidence_event(item, default_channel) for item in raw_events)
    elif raw_events:
        events.append(parse_evidence_event(raw_events, default_channel))

    # Structured evidence events are authoritative for trust-channel decisions.
    # Context text still contributes to semantic/risk features elsewhere. Only
    # suppress the default USER_DIRECTIVE context event when raw evidence has an
    # untrusted channel; otherwise mixed trace context can turn an untrusted
    # overlay candidate into a falsely trusted action.
    has_untrusted_raw_event = any(channel_trust(event.channel) == TrustLevel.UNTRUSTED for event in events)
    if action.context_text and (not events or not has_untrusted_raw_event):
        events.append(EvidenceEvent(text=action.context_text, channel=default_channel))

    structured_history: list[Mapping[str, Any]] = []
    unstructured_history: list[Mapping[str, Any] | str] = []
    for item in action.history:
        if isinstance(item, Mapping) and ("text" in item or "kind" in item or "channel" in item):
            structured_history.append(item)
        else:
            unstructured_history.append(item)

    for item in structured_history:
        events.append(parse_evidence_event(item, normalize_channel(item.get("channel", SourceChannel.AGENT_MEMORY))))
    for item in unstructured_history[-12:]:
        if isinstance(item, Mapping):
            events.append(parse_evidence_event(item, normalize_channel(item.get("channel", SourceChannel.AGENT_MEMORY))))
        else:
            events.append(EvidenceEvent(text=str(item), channel=SourceChannel.AGENT_MEMORY))

    deduped: list[EvidenceEvent] = []
    seen: set[tuple[str, SourceChannel, PredicateKind | None, str | None]] = set()
    for event in events:
        if not event.text:
            continue
        key = (event.text, event.channel, event.kind, event.target)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return tuple(deduped)


def trusted_evidence_summary(action: ToolAction) -> TrustedEvidenceSummary:
    confirmation = False
    authorization = False
    identity_verified = False
    source_grounding = False
    user_intent = False
    manager = False
    policy = False
    state = False
    conflict = False
    injection = False
    untrusted_evidence = False
    confirmation_targets: list[str] = []
    action_terms = set(
        normalized_terms(
            " ".join(
                (
                    action.tool_name,
                    action.action_text,
                    flatten_value(action.arguments),
                    flatten_value(action.raw.get("target", "")),
                )
            )
        )
    )
    meaningful_action_terms = action_terms - GENERIC_REQUEST_TERMS

    for event in evidence_events(action):
        text = lexicalize(flatten_value(event.text))
        event_terms = set(normalized_terms(text))
        flags = evidence_flags(text)
        trust = event.trust or channel_trust(event.channel)
        missing_evidence_statement = bool(
            MISSING_CONFIRM_RE.search(text)
            or MISSING_AUTH_RE.search(text)
            or MISSING_IDENTITY_RE.search(text)
            or MISSING_MANAGER_APPROVAL_RE.search(text)
            or MISSING_POLICY_RE.search(text)
            or MISSING_STATE_RE.search(text)
            or MISSING_USER_INTENT_RE.search(text)
        )
        is_untrusted = trust == TrustLevel.UNTRUSTED
        has_evidence = any(
            flags[key]
            for key in (
                "confirmation_seen",
                "authorization_seen",
                "identity_verified_seen",
                "manager_approval_seen",
                "policy_seen",
                "state_read_seen",
            )
        )
        imperative_instruction = (
            bool(DIRECT_USER_REQUEST_RE.search(text))
            and not missing_evidence_statement
            and not bool(MISSING_USER_INTENT_RE.search(text))
            and not bool(INJECTION_RE.search(text))
        )
        direct_user_request = (
            event.channel in USER_EVIDENCE_CHANNELS
            and event.kind in (None, PredicateKind.USER_INTENT, PredicateKind.CONFIRMATION, PredicateKind.AUTHORIZATION)
            and imperative_instruction
        )
        private_reference = bool(PRIVATE_REFERENCE_RE.search(text))
        first_person_private_reference = bool(FIRST_PERSON_PRIVATE_RE.search(text))
        direct_user_authorization = direct_user_request and (
            flags["authorization_seen"]
            or event.kind == PredicateKind.AUTHORIZATION
            or not private_reference
            or first_person_private_reference
        )
        direct_request_matches_action = direct_user_request and bool(event_terms.intersection(meaningful_action_terms))
        has_user_intent = (
            event.kind == PredicateKind.USER_INTENT or bool(USER_INTENT_RE.search(text)) or direct_request_matches_action
        ) and not bool(MISSING_USER_INTENT_RE.search(text))
        prompt_injection_event = event.kind == PredicateKind.PROMPT_INJECTION or bool(INJECTION_RE.search(text))
        if is_untrusted and (has_evidence or has_user_intent or imperative_instruction or prompt_injection_event):
            untrusted_evidence = untrusted_evidence or has_evidence or has_user_intent or prompt_injection_event
            injection = injection or bool(imperative_instruction or prompt_injection_event)
            continue

        explicit_confirmation = flags["confirmation_seen"] or event.kind == PredicateKind.CONFIRMATION or direct_request_matches_action
        confirmation = confirmation or (
            explicit_confirmation
            and event.channel in USER_EVIDENCE_CHANNELS
            and event.kind in (None, PredicateKind.CONFIRMATION, PredicateKind.USER_INTENT)
        )
        if explicit_confirmation and event.target:
            confirmation_targets.append(event.target.strip().lower())
        authorization = authorization or (
            (flags["authorization_seen"] or direct_user_authorization)
            and event.channel in USER_EVIDENCE_CHANNELS | POLICY_CHANNELS
            and event.kind in (None, PredicateKind.AUTHORIZATION, PredicateKind.MANAGER_APPROVAL, PredicateKind.USER_INTENT)
        )
        identity_verified = identity_verified or (
            (flags["identity_verified_seen"] or event.kind == PredicateKind.IDENTITY_VERIFICATION)
            and event.channel in USER_EVIDENCE_CHANNELS | POLICY_CHANNELS | {SourceChannel.TOOL_RESULT}
            and event.kind in (None, PredicateKind.IDENTITY_VERIFICATION, PredicateKind.AUTHORIZATION)
        )
        source_grounding = source_grounding or (
            event.channel in USER_EVIDENCE_CHANNELS | POLICY_CHANNELS | {SourceChannel.TOOL_RESULT}
            and event.kind in (PredicateKind.SOURCE_GROUNDING, PredicateKind.POLICY_LOOKUP, PredicateKind.STATE_READ)
        )
        user_intent = user_intent or (
            has_user_intent
            and event.channel in USER_EVIDENCE_CHANNELS
            and event.kind in (None, PredicateKind.USER_INTENT)
        )
        manager = manager or (
            flags["manager_approval_seen"]
            and event.channel in USER_EVIDENCE_CHANNELS | POLICY_CHANNELS
            and event.kind in (None, PredicateKind.MANAGER_APPROVAL)
        )
        policy = policy or (
            (flags["policy_seen"] or event.kind == PredicateKind.POLICY_LOOKUP)
            and event.channel in POLICY_CHANNELS | {SourceChannel.TOOL_RESULT}
            and event.kind in (None, PredicateKind.POLICY_LOOKUP)
        )
        state = state or (
            (flags["state_read_seen"] or event.kind == PredicateKind.STATE_READ)
            and event.channel in STATE_CHANNELS
            and event.kind in (None, PredicateKind.STATE_READ)
        )
        conflict = conflict or flags["conflict_seen"]

    return TrustedEvidenceSummary(
        confirmation_seen=confirmation,
        authorization_seen=authorization,
        identity_verified_seen=identity_verified,
        source_grounding_seen=source_grounding,
        user_intent_seen=user_intent,
        manager_approval_seen=manager,
        policy_seen=policy,
        state_read_seen=state,
        conflict_seen=conflict,
        injection_seen=injection,
        untrusted_evidence_seen=untrusted_evidence,
        confirmation_targets=tuple(dict.fromkeys(confirmation_targets)),
    )
