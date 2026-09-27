from __future__ import annotations

import re
from typing import Any, Mapping


WRITE_RE = re.compile(
    r"\b(create|add|insert|update|modify|delete|remove|send|transfer|pay|purchase|book|reserve|"
    r"order|cancel|withdraw|refund|return|exchange|subscribe|register|apply|submit|post|write|set|change|"
    r"issue|credit|charge|debit|waive|grant|compensate|enable|disable|activate|deactivate|resume|suspend)\b",
    re.I,
)
READ_RE = re.compile(r"\b(get|read|search|query|list|retrieve|check|show|find|lookup|view|fetch|verify)\b", re.I)
EXTERNAL_WEB_ACCESS_RE = re.compile(
    r"\b(?:do\s+not|don't|never|must\s+not|should\s+not|cannot|can't)\b.{0,120}\b"
    r"(?:visit|open|fetch|access|browse|request|get|read|click|follow|download)\b.{0,120}\b"
    r"(?:external|untrusted|unknown|suspicious|phishing)?\s*(?:links?|urls?|websites?|webpages?|web\s+pages?|sites?)\b"
    r"|\b(?:external|untrusted|unknown|suspicious|phishing)\b.{0,80}\b"
    r"(?:links?|urls?|websites?|webpages?|web\s+pages?|sites?)\b.{0,80}\b"
    r"(?:visit|open|fetch|access|browse|request|get|read|click|follow|download)\b"
    r"|\b(?:visit|open|fetch|access|browse|request|get|read|click|follow|download)\b.{0,80}\b"
    r"(?:links?|urls?|websites?|webpages?|web\s+pages?|sites?)\b.{0,80}\b"
    r"(?:unless|until|only\s+if|when|after)\b.{0,80}\b(?:user|customer|requester|client)\b",
    re.I,
)
IRREVERSIBLE_RE = re.compile(
    r"\b(delete|remove|cancel|transfer|pay|withdraw|purchase|submit|send|post|refund|return|exchange|book|reserve|"
    r"charge|debit|issue|credit|waive|grant)\b",
    re.I,
)
FINANCIAL_RE = re.compile(
    r"\b(financial|amount|price|pay|payment|money|transfer|bank|card|invoice|purchase|order|refund|return|exchange|"
    r"balance|budget|credit|charge|debit|fee|waive|compensation|reimburse|reimbursement|voucher|coupon)\b",
    re.I,
)
PRIVACY_RE = re.compile(
    r"\b(email|phone|address|password|credential|token|username|user_id|profile|account|ssn|passport|identity|contact|"
    r"private|personal|sensitive|pii|confidential|medical|health|api key|secret)\b",
    re.I,
)
SIDE_EFFECT_RE = re.compile(
    r"\b(send|sms|call|book|reserve|order|delete|update|transfer|pay|purchase|cancel|submit|post|create|"
    r"refund|return|exchange|issue|credit|charge|debit|waive|grant|compensate|compensation|"
    r"enable|disable|activate|deactivate|resume|suspend)\b",
    re.I,
)
TARGET_RE = re.compile(r"\b(to|recipient|receiver|target|user_id|account_id|email|phone|address|contact|customer)\b", re.I)
STATE_RE = re.compile(r"\b(current|existing|status|available|before|after|already|latest|state|policy|record)\b", re.I)
SENSITIVE_VALUE_RE = re.compile(r"(@|\b\d{3}[- ]?\d{3}[- ]?\d{4}\b|\b\d{4,}\b|password|token|secret|credential)", re.I)

CONFIRM_RE = re.compile(r"\b(confirm|confirmed|confirmation|yes|sure|proceed|go ahead|ok|okay|accept|accepted|agree|agreed|consent|consented)\b", re.I)
CONFIRMATION_POLICY_RE = re.compile(r"\b(confirm|confirmed|confirmation|yes|sure|proceed|go ahead|ok|okay)\b", re.I)
ASK_CONFIRM_RE = re.compile(r"\b(ask|request|clarify|confirm with|double check|question)\b.*\b(confirm|confirmation|approve|approval|proceed)\b", re.I)
AUTH_RE = re.compile(
    r"\b(authori[sz](?:e|es|ed|ing|ation)|authorisation|permission|permit|permits|permitted|approve|approved|approval|"
    r"accept|accepted|agree|agreed|consent|consented|"
    r"allowed|logged in|login|authenticate|authenticated|authentication|verified|verification)\b",
    re.I,
)
MANAGER_APPROVAL_RE = re.compile(r"\b(manager|supervisor|admin)\b.{0,32}\b(approve|approved|approval|authorize|authorized|permission)\b", re.I)
IDENTITY_VERIFICATION_RE = re.compile(
    r"\b(identity|customer|user|account)\b.{0,40}\b(verified|verification|authenticated|identified|matched)\b"
    r"|\b(verified|authenticated|identified|matched)\b.{0,40}\b(identity|customer|user|account)\b",
    re.I,
)
USER_INTENT_RE = re.compile(
    r"\b(?:user|customer|requester|client)\b\s+(?:explicitly\s+)?"
    r"(?:ask(?:ed|s)?|request(?:ed|s)?|want(?:ed|s)?|would like|need(?:ed|s)?|accept(?:ed|s)?|agree(?:d|s)?|complain(?:ed|s)?|asked for)\b"
    r"|\b(?:i|we)\b.{0,32}\b"
    r"(?:ask|request|want|would like|need|accept|agree|complain|asked for|requested)\b"
    r"|\byou\b.{0,32}\b(?:want|wish|would like|need|ask|request|accept|agree|complain)\b",
    re.I,
)
POLICY_RE = re.compile(r"\b(policy|rule|terms|allowed|required|must|cannot|may|eligible|limit|window)\b", re.I)
POLICY_LOOKUP_RE = re.compile(r"\b(check|checked|lookup|look up|read|verify|verified|search|retrieve|get)\b.{0,40}\b(policy|rule|limit|eligib|terms)\b", re.I)
STATE_READ_RE = re.compile(r"\b(read|checked|check|lookup|look up|verified|verify|retrieved|get|fetched)\b.{0,48}\b(current|existing|status|state|record|before|latest)\b", re.I)
REDACT_RE = re.compile(
    r"\b(redact(?:ed|ion)?|mask(?:ed|ing)?|remove sensitive|strip sensitive|anonymi[sz](?:e|ed|ation)|hide private)\b",
    re.I,
)
HUMAN_ESCALATION_RE = re.compile(r"\b(transfer|escalate|handoff|hand off|route)\b.{0,40}\b(human|agent|support|reviewer|manager)\b", re.I)
USER_RECIPIENT_RE = re.compile(r"\b(user|customer|requester|owner|self)\b", re.I)
EXTERNAL_RECIPIENT_RE = re.compile(
    r"(@|\bexternal\b|\bthird[- ]party\b|\bvendor\b|\bpublic\b|\bother user\b"
    r"|\b(?:https?://|www\.)[^\s]+"
    r"|\b[a-z0-9.-]+\.(?:com|org|net|io|ai|co|dev|app)(?:/|\b))",
    re.I,
)
CONFLICT_RE = re.compile(r"\b(not|do not|don't|never|without|wrong|instead|however|but|cancel that|no longer)\b", re.I)
MISSING_CONFIRM_RE = re.compile(
    r"\b(no|without|missing|lacking|lack|not|did not|does not|has not|have not|was not|were not|never)\b"
    r".{0,32}\b(confirmation|confirm|confirmed)\b",
    re.I,
)
MISSING_AUTH_RE = re.compile(
    r"\b(no|without|missing|lacking|lack|not|did not|does not|has not|have not)\b.{0,32}\b"
    r"(authorization|authorisation|permission|permit|permitted|approval|authorize|authorizes|authorized|authorise|authorised|"
    r"allow|allowed|authenticate|authenticated|verify|verified|verification)\b",
    re.I,
)
MISSING_POLICY_RE = re.compile(
    r"\b(no|without|missing|lacking|lack|not|did not|does not|has not|have not|was not|were not|never)\b"
    r".{0,36}\b(policy|rule|terms|limit|eligib)\b.{0,36}\b(check|checked|lookup|looked up|read|verified|verify)?\b",
    re.I,
)
MISSING_STATE_RE = re.compile(
    r"\b(no|without|missing|lacking|lack|not|did not|does not|has not|have not|was not|were not|never)\b"
    r".{0,36}\b(current|existing|status|state|record)\b.{0,36}\b(check|checked|read|lookup|verified|verify)?\b",
    re.I,
)
MISSING_MANAGER_APPROVAL_RE = re.compile(
    r"\b(no|without|missing|lacking|lack|not|did not|does not|has not|have not)\b"
    r".{0,36}\b(manager|supervisor|admin)\b.{0,36}\b(approval|approve|approved|authorization|permission)?\b",
    re.I,
)
MISSING_IDENTITY_RE = re.compile(
    r"\b(no|without|missing|lacking|lack|not|did not|does not|has not|have not|was not|were not|never)\b"
    r".{0,40}\b(identity|customer|user|account)\b.{0,40}\b(verified|verification|authenticated|identified|matched)?\b",
    re.I,
)
MISSING_USER_INTENT_RE = re.compile(
    r"\b(no|without|missing|lacking|lack|not|did not|does not|has not|have not|never)\b"
    r".{0,48}\b(user|customer|requester|client)\b.{0,48}\b(ask|asked|request|requested|want|wanted|accept|accepted|complain|complained)\b"
    r"|\b(proactively|unsolicited)\b.{0,32}\b(offer|compensate|refund|send|purchase|book|apply)\b",
    re.I,
)
LIMIT_RE = re.compile(
    r"\b(?:more than|over|above|exceed(?:ing)?|greater than|larger than|beyond)\s+"
    r"(?:\$|usd\s*)?([0-9]+(?:\.[0-9]+)?)\s*(?:dollars?|usd)?\b",
    re.I,
)
UPPER_BOUND_RE = re.compile(
    r"\b(?:at most|no more than|up to)\s+(?:\$|usd\s*)?([0-9]+(?:\.[0-9]+)?)\s*"
    r"(?:dollars?|usd|gb|gbs|gigabytes?|items?|passengers?|units?)?\b"
    r"|\bmax(?:imum)?\b.{0,96}\b(?:is|=)\s+(?:\$|usd\s*)?([0-9]+(?:\.[0-9]+)?)\s*"
    r"(?:dollars?|usd|gb|gbs|gigabytes?|items?|passengers?|units?)?\b",
    re.I,
)
AMOUNT_RE = re.compile(r"(?:\$|usd\s*)?([0-9]+(?:\.[0-9]+)?)\s*(?:dollars?|usd)?", re.I)


def flatten_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {flatten_value(val)}" for key, val in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(flatten_value(item) for item in value)
    return str(value)


def lexicalize(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(text))
    return text.replace("_", " ").replace("-", " ")


def evidence_flags(context_text: str) -> dict[str, bool]:
    missing_confirm = bool(MISSING_CONFIRM_RE.search(context_text))
    missing_auth = bool(MISSING_AUTH_RE.search(context_text))
    missing_policy = bool(MISSING_POLICY_RE.search(context_text))
    missing_state = bool(MISSING_STATE_RE.search(context_text))
    missing_manager = bool(MISSING_MANAGER_APPROVAL_RE.search(context_text))
    missing_identity = bool(MISSING_IDENTITY_RE.search(context_text))
    return {
        "confirmation_seen": bool(CONFIRM_RE.search(context_text)) and not missing_confirm,
        "authorization_seen": bool(AUTH_RE.search(context_text)) and not missing_auth,
        "identity_verified_seen": bool(IDENTITY_VERIFICATION_RE.search(context_text)) and not missing_identity,
        "manager_approval_seen": bool(MANAGER_APPROVAL_RE.search(context_text)) and not missing_manager,
        "policy_seen": bool(POLICY_LOOKUP_RE.search(context_text) or POLICY_RE.search(context_text)) and not missing_policy,
        "state_read_seen": bool(STATE_READ_RE.search(context_text)) and not missing_state,
        "conflict_seen": bool(CONFLICT_RE.search(context_text)),
    }


def categories_for_constraint(text: str) -> set[str]:
    lowered = text.lower()
    categories: set[str] = set()
    if EXTERNAL_WEB_ACCESS_RE.search(lowered):
        categories.add("external_web_access")
    irreversible_policy = bool(IRREVERSIBLE_RE.search(lowered) or re.search(r"\b(?:irreversible|destructive)\b", lowered))
    user_confirmation_phrase = re.search(r"\b(confirm|confirms|confirmed|confirming|confirmation)\b", lowered)
    user_consent_phrase = (
        re.search(
        r"\b(?:user|customer|client|requester)\b.{0,48}\b(?:approve|approval|consent|proceed|agree)\b",
        lowered,
        )
        or re.search(r"\bconsent\s+from\s+(?:the\s+)?(?:user|customer|client|requester)\b", lowered)
        or re.search(r"\b(?:user|customer|client|requester)\b.{0,32}\b(?:says?|said)\s+yes\b", lowered)
    ) and not re.search(
        r"\bwithout\b.{0,32}\b(?:user|customer|client|requester)\b.{0,32}\bconsent\b|\bwithout\b.{0,32}\bconsent\b",
        lowered,
    )
    if user_confirmation_phrase or user_consent_phrase:
        categories.add("confirmation")
    if re.search(
        r"\b(authori[sz](?:e|es|ed|ing|ation)|authorisation|permission|permit|permitted|"
        r"approve|approved|approval|consent|authenticated|authentication)\b",
        lowered,
    ):
        categories.add("authorization")
    if PRIVACY_RE.search(lowered) or "disclose" in lowered or "expose" in lowered or "leak" in lowered:
        categories.add("privacy")
    if FINANCIAL_RE.search(lowered):
        categories.add("financial")
    state_context = any(
        token in lowered
        for token in (
            "current state",
            "current record",
            "existing state",
            "existing record",
            "record state",
            "status",
            "policy",
        )
    )
    state_object_read = bool(
        re.search(
            r"\b(check|checked|read|reading|lookup|look up|verify|verified|retrieve|get|fetch|find|search|obtain)\b"
            r".{0,56}\b(current|existing|status|state|record|policy|profile|order|reservation|booking|user id|account)\b",
            lowered,
        )
        or re.search(
            r"\b(current|existing|status|state|record|policy|profile|order|reservation|booking|user id|account)\b"
            r".{0,56}\b(check|checked|read|reading|lookup|look up|verify|verified|retrieve|get|fetch|find|search)\b",
            lowered,
        )
        or re.search(r"\bread[-\s]+before[-\s]+(?:write|delete|remove|change|modify|cancel)", lowered)
    )
    if state_context or state_object_read:
        categories.add("state")
    if irreversible_policy:
        categories.add("irreversible")
    if SIDE_EFFECT_RE.search(lowered) or re.search(r"\b(?:execute|perform)\b.{0,48}\b(?:destructive|irreversible)\b", lowered):
        categories.add("side_effect")
    return categories or {"general"}


def extract_numeric_limit(text: str) -> float | None:
    for pattern in (LIMIT_RE, UPPER_BOUND_RE):
        match = pattern.search(text)
        if not match:
            continue
        value = next((group for group in match.groups() if group is not None), None)
        if value is None:
            continue
        try:
            return float(value)
        except ValueError:
            continue
    return None


def extract_amounts(text: str) -> tuple[float, ...]:
    amounts: list[float] = []
    for match in AMOUNT_RE.finditer(text):
        try:
            amounts.append(float(match.group(1)))
        except ValueError:
            continue
    return tuple(amounts)
