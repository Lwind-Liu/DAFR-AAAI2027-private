from __future__ import annotations

import re
from functools import lru_cache
from typing import Mapping

from geoconstraints.schemas import ConstraintClause, ToolAction
from geoconstraints.text import flatten_value, lexicalize


TOKEN_RE = re.compile(r"[a-z][a-z0-9]*", re.I)
BROAD_SCOPE_RE = re.compile(
    r"\b(any|all|every)\b.{0,80}\b(action|tool call|request|record|database|write|update|change|modify|delete|send|submit)\b"
    r"|\b(anything|everything|consequential actions?|existing records?)\b"
    r"|\birreversible\s+side\s+effects?\b"
    r"|\b(irreversible|destructive|external\s+side[- ]?effect|side[- ]?effect|financial)\s+actions?\b"
    r"|\b(?:external|untrusted|unknown|suspicious|phishing)?\s*(?:links?|urls?|websites?|webpages?|web\s+pages?|sites?)\b"
    r"|\bprivacy\s+disclosures?\b",
    re.I,
)
STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "before",
    "but",
    "by",
    "can",
    "cannot",
    "could",
    "do",
    "does",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "must",
    "need",
    "needs",
    "not",
    "of",
    "on",
    "only",
    "or",
    "provided",
    "perform",
    "should",
    "than",
    "that",
    "the",
    "their",
    "then",
    "this",
    "to",
    "user",
    "agent",
    "policy",
    "tool",
    "call",
    "action",
    "actions",
    "already",
    "card",
    "request",
    "requests",
    "detail",
    "details",
    "flight",
    "gift",
    "method",
    "payment",
    "explicit",
    "confirmation",
    "confirm",
    "confirmed",
    "obtain",
    "provide",
    "collect",
    "first",
    "reason",
    "safety",
    "single",
}
STEM_EXCEPTIONS = {
    "booking": "book",
    "booked": "book",
    "cancellation": "cancel",
    "cancelling": "cancel",
    "canceling": "cancel",
    "cancelled": "cancel",
    "canceled": "cancel",
    "compensation": "compensate",
    "compensating": "compensate",
    "compensated": "compensate",
    "deletion": "delete",
    "deleting": "delete",
    "deleted": "delete",
    "modifying": "modify",
    "modified": "modify",
    "changing": "change",
    "changed": "change",
    "updating": "update",
    "updated": "update",
    "editing": "edit",
    "edited": "edit",
    "submitting": "submit",
    "submitted": "submit",
    "refunded": "refund",
    "returning": "return",
    "returned": "return",
    "exchanged": "exchange",
    "delivered": "deliver",
}
OPERATION_SCOPE_TERMS = {
    "activate",
    "add",
    "book",
    "cancel",
    "change",
    "charge",
    "compensate",
    "create",
    "credit",
    "debit",
    "delete",
    "disable",
    "enable",
    "exchange",
    "grant",
    "issue",
    "modify",
    "pay",
    "purchase",
    "refund",
    "remove",
    "reserve",
    "resume",
    "return",
    "send",
    "submit",
    "suspend",
    "transfer",
    "update",
    "waive",
    "withdraw",
}
EXCLUSIVE_WORKFLOW_SCOPE_TERMS = {
    "book",
    "cancel",
    "change",
    "create",
    "exchange",
    "modify",
    "refund",
    "reserve",
    "return",
    "submit",
}


def _stem(token: str) -> str:
    token = token.lower()
    if token in STEM_EXCEPTIONS:
        return STEM_EXCEPTIONS[token]
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("ing") and len(token) > 5:
        token = token[:-3]
        if len(token) > 3 and token[-1] == token[-2]:
            token = token[:-1]
        return token
    if token.endswith("ed") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def normalized_terms(text: str) -> tuple[str, ...]:
    terms: list[str] = []
    for match in TOKEN_RE.finditer(lexicalize(text)):
        term = _stem(match.group(0))
        if len(term) < 3 or term in STOPWORDS:
            continue
        terms.append(term)
    return tuple(dict.fromkeys(terms))


def _negated_scope_terms(text: str) -> set[str]:
    negated: set[str] = set()
    for match in re.finditer(
        r"\b(?:no|without|not)\b\s+(?P<subject>[a-z][a-z0-9]*(?:\s+[a-z][a-z0-9]*){0,4})\s+"
        r"(?:is\s+|are\s+|was\s+|were\s+)?(?:involved|related|relevant|applicable|mentioned)\b",
        lexicalize(text),
        flags=re.I,
    ):
        negated.update(normalized_terms(match.group("subject")))
    return negated


@lru_cache(maxsize=2048)
def extract_scope_terms(text: str) -> tuple[str, ...]:
    return normalized_terms(text)


@lru_cache(maxsize=8192)
def _cached_normalized_terms(text: str) -> tuple[str, ...]:
    return normalized_terms(text)


def has_broad_scope(text: str) -> bool:
    return bool(BROAD_SCOPE_RE.search(text))


def action_scope_terms(action: ToolAction) -> set[str]:
    text = " ".join(
        (
            action.tool_name,
            action.action_text,
            flatten_value(action.arguments),
            flatten_value(action.raw.get("state", "")),
            flatten_value(action.raw.get("observed_state", "")),
            flatten_value(action.raw.get("current_state", "")),
            action.context_text[-800:],
        )
    )
    terms = set(_cached_normalized_terms(text))
    return terms - _negated_scope_terms(action.context_text[-800:])


def direct_action_scope_terms(action: ToolAction) -> set[str]:
    text = " ".join(
        (
            action.tool_name,
            action.action_text,
            flatten_value(action.arguments),
            flatten_value(action.raw.get("state", "")),
            flatten_value(action.raw.get("observed_state", "")),
            flatten_value(action.raw.get("current_state", "")),
        )
    )
    return set(_cached_normalized_terms(text))


def clause_applies_to_action(
    clause: ConstraintClause,
    action: ToolAction,
    feature_values: Mapping[str, float],
) -> bool:
    return clause_applies_to_terms(
        clause,
        action_scope_terms(action),
        feature_values,
        direct_action_terms=direct_action_scope_terms(action),
    )


def clause_applies_to_terms(
    clause: ConstraintClause,
    action_terms: set[str],
    feature_values: Mapping[str, float],
    *,
    direct_action_terms: set[str] | None = None,
) -> bool:
    terms = set(clause.trigger.scope_terms)
    if not terms:
        return True
    direct_terms = action_terms if direct_action_terms is None else direct_action_terms
    clause_ops = terms.intersection(EXCLUSIVE_WORKFLOW_SCOPE_TERMS)
    action_ops = direct_terms.intersection(EXCLUSIVE_WORKFLOW_SCOPE_TERMS)
    if clause_ops and action_ops:
        return bool(clause_ops.intersection(action_ops))
    if terms.intersection(action_terms):
        return True
    if clause.trigger.broad_scope:
        return any(
            feature_values.get(name, 0.0) > 0.5
            for name in (
                "external_side_effect",
                "irreversibility",
                "privacy_risk",
                "financial_risk",
                "is_external_web_access",
                "is_existing_record_write",
            )
        )
    return False
