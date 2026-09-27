from __future__ import annotations

import re
from dataclasses import dataclass

from geoconstraints.features import FeatureSpace
from geoconstraints.geometry import HalfSpace, coordinate_halfspace, semantic_boundary
from geoconstraints.scope import extract_scope_terms, has_broad_scope, normalized_terms
from geoconstraints.schemas import (
    CompileStatus,
    CompiledConstraint,
    ConstraintClause,
    ConstraintCompileCertificate,
    CountLimit,
    EvidenceSpec,
    ForbiddenAction,
    GeoConstraint,
    NaturalLanguageConstraint,
    NumericLimit,
    StateRequirement,
    TemporalSpec,
    TriggerSpec,
)
from geoconstraints.text import EXTERNAL_WEB_ACCESS_RE, categories_for_constraint, extract_numeric_limit


FIELD_COLLECTION_RE = re.compile(
    r"\b(obtain|collect|provide|get|ask for|request|need|needs|require|required|requires|"
    r"must have|must include|locate|identify|verify)\b",
    re.I,
)
NEGATED_FIELD_COLLECTION_RE = re.compile(
    r"\b(?:there\s+is\s+)?no\s+need\b|\bnot\s+(?:needed|required|necessary)\b|\bwithout\s+requiring\b",
    re.I,
)
WORKFLOW_REQUIREMENT_RE = re.compile(
    r"\b(must|shall|required|requires|should|only)\b.{0,64}\b(follow|use|complete|go through|comply with)\b"
    r".{0,64}\b(workflow|procedure|process|protocol|steps?)\b"
    r"|\b(special|business|manual)\b.{0,32}\b(workflow|procedure|process|protocol|steps?)\b"
    r"|\bneed(?:s)?\s+to\s+follow\b.{0,64}\bsteps?\b",
    re.I,
)
RUNTIME_PROTOCOL_RE = re.compile(
    r"\b(one|single)\s+tool\s+call\b|\btool\s+call\b.{0,64}\b(simultaneously|at the same time)\b|"
    r"\bnot\s+(?:make up|invent|fabricate)\b.{0,64}\b(information|knowledge|procedure|fact)s?\b",
    re.I,
)
TOOL_CALL_MUTEX_RE = re.compile(
    r"\b(?:one|single|at\s+most\s+one)\s+tool\s+call\b|"
    r"\btool\s+call\b.{0,80}\b(?:simultaneously|at\s+the\s+same\s+time)\b|"
    r"\brespond\b.{0,80}\b(?:same\s+time|simultaneously)\b.{0,80}\btool\s+call\b",
    re.I,
)
HUMAN_ESCALATION_GATE_RE = re.compile(
    r"\b(?:transfer|escalate|handoff|hand\s+off|route)\b.{0,96}\b"
    r"(?:human|agent|support|reviewer|manager)\b.{0,160}\b"
    r"(?:if|when|whenever|unless)\b.{0,160}\b"
    r"(?:cannot|can't|can\s+not|unable\s+to|out\s+of\s+scope|outside\s+(?:the\s+)?scope|"
    r"beyond\s+(?:the\s+)?scope|not\s+within\s+(?:the\s+)?scope|not\s+handled|unsupported)\b"
    r"|\b(?:if|when|whenever|unless)\b.{0,160}\b"
    r"(?:cannot|can't|can\s+not|unable\s+to|out\s+of\s+scope|outside\s+(?:the\s+)?scope|"
    r"beyond\s+(?:the\s+)?scope|not\s+within\s+(?:the\s+)?scope|not\s+handled|unsupported)\b"
    r".{0,160}\b(?:transfer|escalate|handoff|hand\s+off|route)\b.{0,96}\b"
    r"(?:human|agent|support|reviewer|manager)\b",
    re.I,
)
POLICY_DENIAL_GATE_RE = re.compile(
    r"\b(?:deny|decline|refuse|reject)\b.{0,96}\b(?:user\s+)?requests?\b.{0,160}\b"
    r"(?:against|violat(?:e|es|ing)|contrary\s+to|not\s+allowed\s+by|disallowed\s+by)\b.{0,96}\b"
    r"(?:policy|policies|rules?)\b"
    r"|\b(?:requests?|actions?)\b.{0,160}\b"
    r"(?:against|violat(?:e|es|ing)|contrary\s+to|not\s+allowed\s+by|disallowed\s+by)\b.{0,96}\b"
    r"(?:policy|policies|rules?)\b.{0,160}\b(?:deny|decline|refuse|reject)\b",
    re.I,
)
IDENTITY_REQUIREMENT_RE = re.compile(
    r"\b(authenticate|authenticated|authentication)\b.{0,80}\b(user|customer|identity|account)\b"
    r"|\b(user|customer|account)\b.{0,40}\b(authenticate|authenticated|authentication)\b"
    r"|\b(verify|verified|verification|identify|identified|locate|located)\b.{0,40}\b(identity|customer|account)\b"
    r"|\b(verify|verified|verification|identify|identified|locate|located)\b\s+(?:the\s+)?user\b(?!\s+confirmation)"
    r"|\b(identity|customer|account)\b.{0,40}\b(verify|verified|verification|identify|identified|located)\b"
    r"|\buser\b.{0,24}\b(identity|account)\b.{0,40}\b(verify|verified|verification|identify|identified|located)\b",
    re.I,
)
SOURCE_GROUNDING_RE = re.compile(
    r"\bnot\s+(?:provide|make up|invent|fabricate)\b.{0,80}\b(information|knowledge|procedures?|facts?)\b.{0,80}\bnot\s+(?:provided|supplied)\b"
    r"|\bnot\s+(?:provided|supplied)\s+by\b.{0,32}\b(user|tools?)\b"
    r"|\b(?:do\s+not|don't|never|must\s+not|should\s+not)\b.{0,48}\b(?:hallucinate|make up|invent|fabricate)\b"
    r"|\b(?:unsupported|ungrounded|unverified|made[- ]up)\b.{0,48}\b(?:facts?|procedures?|information|claims?|answers?)\b"
    r"|\b(?:confirm(?:s|ed|ing)?|verify|verified|verifying)\b.{0,48}\bfacts?\b"
    r"|\bfacts?\b.{0,48}\b(?:confirm(?:s|ed|ing)?|verify|verified|verifying)\b",
    re.I,
)
USER_CONFIRMATION_REQUIREMENT_RE = re.compile(
    r"\bexplicit\s+(?:user|customer|client|requester)?\s*confirmation\b"
    r"|\b(?:user|customer|client|requester)\b.{0,48}\b(?:confirm|confirmation|confirmed|approve|approval|consent|proceed)\b"
    r"|\b(?:confirm|confirmation|confirmed|approve|approval|consent)\b.{0,48}\b(?:user|customer|client|requester)\b",
    re.I,
)
USER_INTENT_REQUIREMENT_RE = re.compile(
    r"\b(?:unless|until|only\s+if|if|when|after|without)\b.{0,96}\b(?:user|customer|requester|client)\b"
    r"\s+(?:explicitly\s+)?(?:ask(?:ed|s)?|request(?:ed|s)?|want(?:ed|s)?|would like|accept(?:ed|s)?|agree(?:d|s)?|complain(?:ed|s)?)\b"
    r"|\b(?:do\s+not|don't|should\s+not|must\s+not|never|cannot|can't)\b.{0,48}\b(?:proactively|unsolicited)\b"
    r"|\b(?:proactively|unsolicited)\b.{0,48}\b(?:offer|compensate|refund|send|purchase|book|apply)\b"
    r"|\b(?:proactively|unsolicited)\b.{0,48}\b(?:offer|compensation|credit|refund|payment|voucher|coupon)\b",
    re.I,
)
EXCEPTION_DENIAL_RE = re.compile(
    r"\b(?:even\s+if|regardless\s+of|despite|irrespective\s+of)\b.{0,80}\b"
    r"(?:user|customer|client|requester|ask(?:s|ed)?|request(?:s|ed)?|permission|authorization|authorisation|approval|consent)\b",
    re.I,
)
APPROVAL_AUTHORITY_RE = re.compile(r"\b(manager|supervisor|admin|administrator|lead|human reviewer)\b", re.I)
APPROVAL_EVIDENCE_RE = re.compile(r"\b(approval|approve|approved|authorize|authorized|authorization|permission|consent)\b", re.I)
REDACTION_REQUIREMENT_RE = re.compile(
    r"\b(?:unless|until|only\s+if|after|when|without|before)\b.{0,80}\b"
    r"(?:redact(?:ed|ion)?|mask(?:ed|ing)?|anonymi[sz](?:ed|ation)?|de[- ]identif(?:ied|ication)|"
    r"no\s+(?:personal|private|sensitive)\s+(?:data|information|identifiers?)|"
    r"remove(?:d)?\s+(?:personal|private|sensitive))\b"
    r"|\b(?:must|should|needs?\s+to|has\s+to)\b.{0,48}\b"
    r"(?:redact(?:ed|ion)?|mask(?:ed|ing)?|anonymi[sz](?:ed|ation)?|de[- ]identif(?:ied|ication))\b",
    re.I,
)
PRIVACY_BROAD_SCOPE_RE = re.compile(
    r"\b(?:pii|sensitive fields?|private data|personal data|confidential data|customer data|account details?|"
    r"contact data|personal identifiers?)\b"
    r"|\b(?:external recipients?|third[- ]part(?:y|ies)|outside\s+(?:the\s+)?(?:company|organization|organisation))\b",
    re.I,
)
INTERNAL_RECIPIENT_EXCEPTION_RE = re.compile(
    r"\b(?:except|but|unless)\b.{0,80}\b(?:internal|inside|within|employee|staff|support)\b",
    re.I,
)
AUTHORIZATION_EXCEPTION_RE = re.compile(
    r"\bwithout\b.{0,64}\b(?:consent|authorization|authorisation|permission|approval|authorize|authorise|authorized|authorised|approved)\b",
    re.I,
)
AUTHORIZATION_ALLOWANCE_RE = re.compile(
    r"\b(?:unless|if|when|after|with|only\s+with|provided\s+that)\b.{0,96}\b"
    r"(?:consent|authorization|authorisation|permission|approval|authorize|authorise|authorized|authorised|approved|verified)\b",
    re.I,
)
OUTSIDE_ORG_PROHIBITION_RE = re.compile(
    r"\b(?:must|should|may|can)?\s*not\b.{0,80}\b"
    r"(?:email(?:ed)?|send|sent|share|shared|disclose|disclosed|provide|provided)\b.{0,80}\b"
    r"(?:outside|external|third[- ]part(?:y|ies))\b.{0,32}\b(?:company|organization|organisation|recipients?)\b",
    re.I,
)
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
FIELD_PHRASES = {
    "title": "title",
    "user id": "user_id",
    "flight id": "flight_ids",
    "flight ids": "flight_ids",
    "flight": "flight_ids",
    "flights": "flight_ids",
    "reservation id": "reservation_id",
    "order id": "order_id",
    "item id": "item_id",
    "product id": "product_id",
    "account id": "account_id",
    "reason": "reason",
    "trip type": "trip_type",
    "origin": "origin",
    "destination": "destination",
    "first name": "first_name",
    "last name": "last_name",
    "date of birth": "date_of_birth",
    "payment method": "payment_method",
    "refund method": "refund_method",
    "phone number": "phone_number",
    "email address": "email",
    "email": "email",
    "zip code": "zip_code",
    "postal code": "zip_code",
    "device id": "device_id",
    "start date": "start_date",
    "end date": "end_date",
    "transfer date": "transfer_date",
    "suspension start date": "suspension_start_date",
    "last transfer date": "last_transfer_date",
}


def _phrase_in_text(phrase: str, text: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text))


EXPLICIT_STATE_READ_RE = re.compile(
    r"\b(check|checked|read|reading|lookup|look up|verify|verified|retrieve|retrieved|fetch|fetched)\b"
    r".{0,64}\b(current|existing|status|state|record|policy|profile|order|reservation|booking|account|balance)\b"
    r"|\b(status|state|record|policy|profile|order|reservation|booking|account|balance)\b"
    r".{0,64}\b(check|checked|read|reading|lookup|look up|verify|verified|retrieve|retrieved|fetch|fetched)\b"
    r"|\bread[-\s]+before[-\s]+(?:write|delete|remove|change|modify|cancel)",
    re.I,
)
COUNT_LIMIT_RE = re.compile(
    r"\b(?:at most|no more than|up to)\s+"
    r"(?P<count>one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+)\s+"
    r"(?P<item>[a-z][a-z0-9]*(?:[\s_-]+[a-z][a-z0-9]*){0,3})",
    re.I,
)
COUNT_ITEM_STOP_RE = re.compile(r"\b(?:and|or|per|for|in|of|with|from|to|that|which|who|whose|is|are|can|must|should|needs?|has|have|different|original|current|existing)\b", re.I)
FIELD_TAIL_RE = re.compile(
    r"\b(?:ask for|obtain|collect|get|provide|needs?|requires?|required|must have|must include|"
    r"locate|identify|verify)\b(?P<tail>[^.;:]+)",
    re.I,
)
FIELD_SPLIT_RE = re.compile(r"\s*(?:,| and | or |\+|/)\s*", re.I)
FIELD_CANDIDATE_RE = re.compile(
    r"\b(id|date|birth|method|code|name|type|origin|destination|reason|address|email|phone|amount|balance|items?)\b",
    re.I,
)
FIELD_LEADING_CONNECTOR_RE = re.compile(r"^\s*(?:and|or|otherwise|then)\b", re.I)
FIELD_PROCEDURAL_NOISE_RE = re.compile(r"\b(?:using|tools?|workflow|procedure|process|steps?)\b", re.I)
FIELD_STATE_PREDICATE_RE = re.compile(r"^\s*(?:enough|sufficient|adequate)\b", re.I)
BARE_FIELD_REJECT_RE = re.compile(
    r"\b(if|when|after|before|unless|only|should|must|shall|can|cannot|can't|will|would|"
    r"need|needs|obtain|collect|ask|request|provide|get|make|send|inform|respond|follow|"
    r"do|don't|not|never|enable|refund|cancel|change|update|deny|help|confuse|confused)\b",
    re.I,
)
FIELD_REJECT = {
    "action",
    "actions",
    "agent",
    "customer",
    "detail",
    "details",
    "dependencies",
    "dependency",
    "information",
    "missing",
    "parameter",
    "parameters",
    "policy",
    "procedure",
    "request",
    "requests",
    "scope",
    "supplied",
    "this",
    "that",
    "tool",
    "tools",
    "using",
    "user",
    "value",
    "approval",
    "approvals",
    "authorization",
    "authorisation",
    "permission",
    "permissions",
    "consent",
    "trusted",
}
NON_INPUT_FIELD_CONTEXT_RE = re.compile(
    r"\b(?:does|do)\s+not\s+count\b|\binsufficient\b|\bnot\s+(?:email|webpage|web\s+page|retrieved)\b",
    re.I,
)
EXISTING_ENTITY_RE = re.compile(
    r"\bexisting\s+(?P<entity>users?|customers?|clients?|accounts?|orders?|reservations?|records?|tasks?|tickets?|cases?)\b",
    re.I,
)
EXISTING_ENTITY_ARGUMENTS = {
    "user": "user_id",
    "users": "user_id",
    "customer": "customer_id",
    "customers": "customer_id",
    "client": "customer_id",
    "clients": "customer_id",
    "account": "account_id",
    "accounts": "account_id",
    "order": "order_id",
    "orders": "order_id",
    "reservation": "reservation_id",
    "reservations": "reservation_id",
    "record": "record_id",
    "records": "record_id",
    "task": "task_id",
    "tasks": "task_id",
    "ticket": "ticket_id",
    "tickets": "ticket_id",
    "case": "case_id",
    "cases": "case_id",
}
STATE_VALUE_TERMS = (
    "pending",
    "processed",
    "delivered",
    "cancelled",
    "canceled",
    "available",
    "delayed",
    "on time",
    "flying",
    "landed",
    "not flown",
    "flown",
    "used",
    "unused",
    "active",
    "inactive",
    "suspended",
    "overdue",
    "paid",
    "unpaid",
    "open",
    "closed",
    "eligible",
    "ineligible",
    "existing",
    "original",
)
STATE_RULE_RE = re.compile(
    r"\b(can only|only|must already|must have enough|different from|"
    r"cannot|can't|not allowed|not eligible|allowed to|need to|needs to|required to)\b",
    re.I,
)
STATE_OBJECT_RE = re.compile(
    r"\b(status|state|profile|balance|available|availability|eligible|eligibility|different|"
    r"original|existing|pending|delivered|cancelled|canceled|overdue)\b",
    re.I,
)
CONDITIONAL_ENABLE_RE = re.compile(
    r"\bcheck\b.{0,80}\b(?P<field>[a-z][a-z0-9\s_-]{0,40}enabled)\b"
    r".{0,160}\bif\s+it\s+is\s+not\b.{0,80}\benable\s+it\b",
    re.I,
)
TERMINAL_STATE_TRANSFER_RE = re.compile(
    r"\b(?:already\s+(?:been\s+)?|has\s+already\s+been\s+|have\s+already\s+been\s+)(?P<state>flown|used|processed|cancelled|canceled)\b"
    r".{0,160}\b(?:cannot|can't|can\s+not)\s+help\b.{0,160}\b(?:transfer|escalat|handoff|hand\s+off)\b"
    r"|\b(?:transfer|escalat|handoff|hand\s+off)\b.{0,160}\b(?:needed|required)\b.{0,160}\b"
    r"(?:already\s+(?:been\s+)?|has\s+already\s+been\s+|have\s+already\s+been\s+)(?P<state_reverse>flown|used|processed|cancelled|canceled)\b",
    re.I,
)
ALLOWED_VALUE_RE = re.compile(
    r"\b(?P<field>refund(?:\s+method)?|payment\s+method|reason)\b"
    r".{0,64}\b(?:must|should|can\s+only|only)\b\s+(?:either\s+)?"
    r"(?:go\s+to|be|use|choose|be\s+one\s+of|one\s+of)\s+(?P<values>[^.;]+)",
    re.I,
)
ALLOWED_STATUS_VALUE_RE = re.compile(
    r"\b(?:task|order|record|ticket|case|request)?\s*status\b"
    r".{0,48}\b(?:can\s+only|must|should|may)\b\s+(?:only\s+)?"
    r"(?:be|be\s+one\s+of|be\s+either|equal|=)\s+(?P<values>[^.;]+)",
    re.I,
)
ALLOWED_TARGET_TO_RE = re.compile(
    r"\b(?:only|solely|exclusively)\b[^.;]{0,120}?\b(?:to|with)\s+(?P<target>[^.;]+)",
    re.I,
)
ALLOWED_TARGET_MUST_RE = re.compile(
    r"\b(?P<field>destination\s+account|target\s+account|beneficiary\s+account|"
    r"recipient(?:\s+type)?|recipient\s+email|email\s+address)\b"
    r".{0,64}\b(?:must|should|may|can)\b\s+(?:only\s+)?"
    r"(?:be|go\s+to|route\s+to|send\s+to|use)\s+(?P<values>[^.;]+)",
    re.I,
)
ALLOWED_ACTION_ATTRIBUTE_RE = re.compile(
    r"\b(?:only|solely|exclusively)\b[^.;]{0,160}?\b(?:through|via|over|using|to|into)\s+"
    r"(?P<values>encrypted|secure|approved|internal|private|verified)"
    r"(?:\s+(?P<object>channels?|connections?|transport|repositories?|repos?|buckets?|recipients?))\b",
    re.I,
)
DISALLOWED_TARGET_STATUS_RE = re.compile(
    r"\b(?:do\s+not|don't|never|must\s+not|should\s+not|cannot|can't|not\s+allowed\s+to)\b"
    r"(?P<prefix>[^.;]{0,140}?)\b(?:to|with|for|into)\s+"
    r"(?P<status>unverified|unapproved|unauthorized|unauthori[sz]ed|untrusted|unknown|external)\s+"
    r"(?P<target>recipients?|recipient\s+emails?|email\s+address(?:es)?|destination\s+accounts?|"
    r"target\s+accounts?|beneficiary\s+accounts?|beneficiar(?:y|ies)|customers?|users?|third[- ]part(?:y|ies))\b",
    re.I,
)
ALLOWED_TARGET_FIELD_RE = re.compile(
    r"\b(?P<field>recipients?|staff|employees?|recipient\s+emails?|email\s+address(?:es)?|"
    r"emails?|address(?:es)?|destination\s+accounts?|target\s+accounts?|beneficiar(?:y|ies))\s*$",
    re.I,
)
ALLOWED_VALUE_FIELD_MAP = {
    "refund": "refund_method",
    "refund method": "refund_method",
    "payment method": "payment_method",
    "reason": "reason",
}
ALLOWED_TARGET_FIELD_MAP = {
    "address": "recipient_email",
    "addresses": "recipient_email",
    "beneficiary": "destination_account",
    "beneficiaries": "destination_account",
    "beneficiary account": "destination_account",
    "beneficiary accounts": "destination_account",
    "customer": "recipient",
    "customers": "recipient",
    "destination account": "destination_account",
    "destination accounts": "destination_account",
    "email": "recipient_email",
    "email address": "recipient_email",
    "email addresses": "recipient_email",
    "emails": "recipient_email",
    "employee": "recipient",
    "employees": "recipient",
    "recipient": "recipient",
    "recipient email": "recipient_email",
    "recipient emails": "recipient_email",
    "recipient type": "recipient",
    "recipients": "recipient",
    "staff": "recipient",
    "target account": "destination_account",
    "target accounts": "destination_account",
    "third party": "recipient",
    "third parties": "recipient",
    "user": "recipient",
    "users": "recipient",
}
ALLOWED_ATTRIBUTE_FIELD_MAP = {
    "bucket": "repository_visibility",
    "buckets": "repository_visibility",
    "channel": "channel_security",
    "channels": "channel_security",
    "connection": "channel_security",
    "connections": "channel_security",
    "recipient": "recipient",
    "recipients": "recipient",
    "repo": "repository_visibility",
    "repos": "repository_visibility",
    "repository": "repository_visibility",
    "repositories": "repository_visibility",
    "transport": "channel_security",
}
ROLE_PERMISSION_RE = re.compile(
    r"\bonly\s+(?P<roles>[^.;]{1,64}?)\s+"
    r"(?:may|can|should|must|are\s+allowed\s+to|are\s+permitted\s+to|are\s+authorized\s+to|are\s+authorised\s+to)\b",
    re.I,
)
ROLE_PERMISSION_FOR_RE = re.compile(
    r"\b(?:allowed|permitted|authorized|authorised)\s+only\s+(?:for|to|by)\s+(?P<roles>[^.;]+)",
    re.I,
)
ROLE_CONDITION_RE = re.compile(
    r"\bunless\b[^.;]{0,96}\b(?:actor|user|operator|role)\b[^.;]{0,32}?\b(?:is|=|has)\s+"
    r"(?P<roles>[^.;,]+?)(?=\s+(?:and|or)\b|[.;,]|$)",
    re.I,
)
ROLE_RESTRICTED_RE = re.compile(
    r"\b(?:permission|permissions|privilege|privileges|access)\b[^.;]{0,96}\b"
    r"(?:restricted|limited|reserved)\s+to\s+(?P<roles>[^.;]+)",
    re.I,
)
ROLE_PRIVILEGE_REQUIREMENT_RE = re.compile(
    r"\b(?:requires?|needs?|must\s+have|with)\s+(?P<roles>[^.;]{1,64}?)\s+"
    r"(?:privilege|privileges|access)\b",
    re.I,
)
ROLE_PROHIBITION_RE = re.compile(
    r"\b(?P<roles>manager|managers|supervisor|supervisors|admin|admins|administrator|administrators|"
    r"owner|owners|staff|employee|employees|agent|agents|support)(?:\s+user|\s+users)?\s+"
    r"(?:must|should|may|can)?\s*not\b[^.;]{0,96}\b(?:delete|remove|modify|change|cancel|transfer|send|refund|issue)",
    re.I,
)
ROLE_TERM_RE = re.compile(
    r"\b(manager|managers|supervisor|supervisors|admin|admins|administrator|administrators|"
    r"owner|owners|staff|employee|employees|agent|agents|support)\b",
    re.I,
)
ROLE_NORMALIZATION = {
    "administrators": "admin",
    "administrator": "admin",
    "admins": "admin",
    "agents": "agent",
    "employees": "employee",
    "managers": "manager",
    "owners": "owner",
    "supervisors": "supervisor",
}
NUMERIC_DIFFERENCE_RE = re.compile(
    r"\b(?:price|amount|total)\b.{0,64}\b(?:after|new|updated)\b.{0,80}\b"
    r"(?P<direction>lower|less|higher|greater|more)\s+than\b.{0,32}\b(?:original|previous|old)\b.{0,160}\b"
    r"(?P<effect>refund(?:ed)?|reimburse(?:d)?|pay|paid|charge(?:d)?)\b.{0,80}\bdifference\b"
    r"|\b(?:original|previous|old)\b.{0,32}\b(?:price|amount|total)\b.{0,80}\b"
    r"(?P<direction_reverse>exceeds?|higher\s+than|greater\s+than|more\s+than|lower\s+than|less\s+than)\b.{0,80}\b"
    r"(?:new|updated|after)\b.{0,160}\b(?P<effect_reverse>refund(?:ed)?|reimburse(?:d)?|pay|paid|charge(?:d)?)\b.{0,80}\bdifference\b",
    re.I,
)
DISTINCT_ARGUMENT_RE = re.compile(
    r"\b(?:no\s+relations?|no\s+relationship|not\s+be\s+confused|should\s+not\s+be\s+confused|"
    r"must\s+not\s+be\s+confused|do\s+not\s+confuse|don't\s+confuse)\b",
    re.I,
)
UNCHANGED_ARGUMENT_RE = re.compile(
    r"\bwithout\s+changing\b(?P<fields>[^.;]+)",
    re.I,
)
ELIGIBILITY_GATE_RE = re.compile(
    r"(?<!and\s)\b(?:only|can\s+only|should\s+only|must\s+only)\b(?P<action>[^.;]{0,80}?)\b(?:if|when)\b(?P<conditions>[^.;]+)",
    re.I,
)
ELIGIBILITY_CONDITION_RE = re.compile(
    r"\b(member|membership|insurance|fare|cabin|class|tier|plan|eligible|eligibility|business)\b",
    re.I,
)
PROHIBITED_VERB_CANONICAL = {
    "add": "add",
    "added": "add",
    "ask": "ask",
    "book": "book",
    "booked": "book",
    "call": "call",
    "contact": "contact",
    "contacted": "contact",
    "cancel": "cancel",
    "cancelled": "cancel",
    "canceled": "cancel",
    "change": "change",
    "changed": "change",
    "compensate": "compensate",
    "delete": "delete",
    "deleted": "delete",
    "disclose": "disclose",
    "disclosed": "disclose",
    "export": "export",
    "exported": "export",
    "lift": "lift",
    "modify": "modify",
    "modified": "modify",
    "offer": "offer",
    "publish": "publish",
    "published": "publish",
    "remove": "remove",
    "removed": "remove",
    "send": "send",
    "sent": "send",
    "share": "share",
    "shared": "share",
    "transmit": "transmit",
    "transmitted": "transmit",
    "unlock": "unlock",
    "unlocked": "unlock",
    "upload": "upload",
    "uploaded": "upload",
    "use": "use",
    "changed": "change",
}
PROHIBITED_VERB_RE = (
    r"add|added|ask|book|booked|call|contact|contacted|cancel|cancelled|canceled|change|changed|compensate|"
    r"delete|deleted|disclose|disclosed|export|exported|lift|modify|modified|offer|publish|published|"
    r"remove|removed|send|sent|share|shared|transmit|transmitted|unlock|unlocked|upload|uploaded|use"
)
PROHIBITION_EVIDENCE_EXCEPTION_RE = re.compile(
    r"\b(?:unless|until|without|except|before)\b.{0,96}\b"
    r"(confirm|confirmation|confirmed|authorization|authorisation|authorize|authorise|permission|"
    r"approval|approve|approved|manager|supervisor|consent|verified|verification)\b",
    re.I,
)
PROHIBITION_ACTIVE_RE = re.compile(
    rf"\b(?:not\s+allowed|forbidden|prohibited)\s+to\s+(?P<verb>{PROHIBITED_VERB_RE})\b(?P<tail>[^.;]*)"
    rf"|\b(?:must|should)\s+not\s+(?P<verb_modal>{PROHIBITED_VERB_RE})\b(?P<tail_modal>[^.;]*)"
    rf"|\bdo\s+not\s+(?P<verb_do>{PROHIBITED_VERB_RE})\b(?P<tail_do>[^.;]*)"
    rf"|\bnever\s+(?P<verb_never>{PROHIBITED_VERB_RE})\b(?P<tail_never>[^.;]*)"
    rf"|\b(?:cannot|can't)\s+(?P<verb_cannot>{PROHIBITED_VERB_RE})\b(?P<tail_cannot>[^.;]*)",
    re.I,
)
PROHIBITION_PASSIVE_RE = re.compile(
    rf"(?P<subject>\b[a-z][^.;]{{0,96}}?)\s+\b(?:cannot|can't)\s+be\s+"
    rf"(?P<verb>{PROHIBITED_VERB_RE})\b(?P<tail>[^.;]*)",
    re.I,
)
CONDITION_SPLIT_RE = re.compile(r"\b(if|when|unless|after|before|where|whose|with|without)\b", re.I)
OBJECT_TERM_REJECT = {
    "action",
    "after",
    "agent",
    "allow",
    "allowed",
    "cannot",
    "customer",
    "flight",
    "human",
    "line",
    "not",
    "order",
    "policy",
    "record",
    "request",
    "reservation",
    "should",
    "support",
    "tool",
    "user",
}


def _normalize_count_item(text: str) -> str:
    item = COUNT_ITEM_STOP_RE.split(text.strip())[0]
    item = re.sub(r"\b(?:a|an|the|each|per)\b", " ", item, flags=re.I)
    item = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_")
    if item.endswith("ies"):
        item = item[:-3] + "y"
    elif item.endswith("s") and len(item) > 4:
        item = item[:-1]
    return item


def _count_value(text: str) -> int | None:
    lowered = text.lower()
    if lowered in NUMBER_WORDS:
        return NUMBER_WORDS[lowered]
    try:
        return int(lowered)
    except ValueError:
        return None


def _guess_count_argument(item: str) -> str | None:
    if not item:
        return None
    if any(token in item for token in ("card", "certificate", "payment", "paypal")):
        return "payment_methods"
    if "passenger" in item:
        return "passengers"
    if "gift" in item:
        return "payment_methods"
    if "item" in item:
        return "item_ids"
    return None


def _extract_count_limits(text: str) -> tuple[CountLimit, ...]:
    limits: list[CountLimit] = []
    for match in COUNT_LIMIT_RE.finditer(text):
        count = _count_value(match.group("count"))
        item = _normalize_count_item(match.group("item"))
        if count is None or not item:
            continue
        limits.append(CountLimit(item=item, max_count=count, argument=_guess_count_argument(item)))
    return tuple(dict.fromkeys(limits))


def _normalize_required_field_candidate(text: str) -> str | None:
    candidate = re.sub(r"\([^)]*\)", " ", text.lower())
    candidate = re.sub(r"['\"`]", " ", candidate)
    candidate = FIELD_LEADING_CONNECTOR_RE.sub(" ", candidate).strip()
    if not candidate or FIELD_PROCEDURAL_NOISE_RE.search(candidate) or FIELD_STATE_PREDICATE_RE.search(candidate):
        return None
    if re.fullmatch(r"reasons?", candidate):
        return "reason"
    if candidate.startswith("other reason") or re.search(r"\breasons\b", candidate):
        return None
    for phrase, argument in FIELD_PHRASES.items():
        if re.search(rf"\b{re.escape(phrase)}\b", candidate):
            return argument
    candidate = re.sub(r"\b(for|to|from|before|after|when|if|that|which|who|whose|by|with)\b.*$", " ", candidate)
    candidate = re.sub(r"\b(?:the|a|an|their|its|user'?s|customer'?s|customer|agent|then|first|and)\b", " ", candidate)
    candidate = re.sub(r"\b(?:is|are|was|were|be|been|required|provided|available|applicable)\b", " ", candidate)
    candidate = re.sub(r"[^a-z0-9]+", " ", candidate).strip()
    if not candidate:
        return None
    words = candidate.split()
    if len(words) > 5:
        return None
    if candidate in FIELD_REJECT or any(word in FIELD_REJECT for word in words):
        return None
    if not FIELD_CANDIDATE_RE.search(candidate):
        return None
    return "_".join(words)


def _extract_required_arguments(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    required: list[str] = []
    for phrase, argument in FIELD_PHRASES.items():
        phrase_context_reject = False
        for match in re.finditer(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", lowered):
            window = lowered[max(0, match.start() - 80) : min(len(lowered), match.end() + 80)]
            if "approval" in window and NON_INPUT_FIELD_CONTEXT_RE.search(window):
                phrase_context_reject = True
                break
        if _phrase_in_text(phrase, lowered) and not phrase_context_reject:
            required.append(argument)
    for match in re.finditer(r"\b([a-z][a-z0-9]*)\s+id\b", lowered):
        required.append(f"{match.group(1)}_id")
    if FIELD_COLLECTION_RE.search(lowered):
        for match in FIELD_TAIL_RE.finditer(text):
            tail = re.sub(r"\bvia\b", ",", match.group("tail"), flags=re.I)
            for part in FIELD_SPLIT_RE.split(tail):
                normalized = _normalize_required_field_candidate(part)
                if normalized:
                    required.append(normalized)
    return tuple(dict.fromkeys(required))


def _extract_bare_required_arguments(text: str) -> tuple[str, ...]:
    candidate = re.sub(r"\([^)]*\)", " ", text)
    candidate = re.sub(r"['\"`]", " ", candidate)
    candidate = re.sub(r"[^a-zA-Z0-9_/\s-]+", " ", candidate).strip()
    if not candidate:
        return ()
    words = candidate.split()
    if len(words) > 8 or BARE_FIELD_REJECT_RE.search(candidate):
        return ()
    required: list[str] = []
    for part in FIELD_SPLIT_RE.split(candidate):
        normalized = _normalize_required_field_candidate(part)
        if normalized:
            required.append(normalized)
    return tuple(dict.fromkeys(required))


def _extract_existing_entity_required_arguments(text: str) -> tuple[str, ...]:
    fields: list[str] = []
    for match in EXISTING_ENTITY_RE.finditer(text):
        field = EXISTING_ENTITY_ARGUMENTS.get(match.group("entity").lower())
        if field:
            fields.append(field)
    return tuple(dict.fromkeys(fields))


def _normalize_state_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip(" .,:;\"'`"))


def _split_state_values(text: str) -> tuple[str, ...]:
    values: list[str] = []
    lowered = re.sub(r"\([^)]*\)", " ", text.lower())
    lowered = re.split(
        r"\b(?:orders?|reservations?|flights?|items?|accounts?|bills?|records?|tools?|actions?|requests?|"
        r"and you|but|then|because|given|with|without)\b",
        lowered,
        maxsplit=1,
    )[0]
    for term in STATE_VALUE_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            values.append(term)
    if not values:
        for part in re.split(r"\s*(?:,| or | and |/)\s*", lowered):
            value = _normalize_state_value(part)
            if value and len(value.split()) <= 3:
                values.append(value)
    return tuple(dict.fromkeys(values))


def _state_requirement(
    field: str,
    operator: str = "checked",
    values: tuple[str, ...] = (),
    *,
    evidence_required: bool = True,
) -> StateRequirement:
    return StateRequirement(field=field, operator=operator, values=values, evidence_required=evidence_required)


def _normalize_allowed_value(value: str) -> str | None:
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"['\"`]", " ", value)
    value = re.sub(r"\b(customer|user|client|requester)\s+s\b", r"\1", value, flags=re.I)
    value = re.sub(r"\b(?:a|an|the)\b", " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" .,:;").lower()
    return value or None


def _split_allowed_values(text: str) -> tuple[str, ...]:
    text = re.sub(r"\b(?:if|when|unless|where|with|before|after)\b.*$", " ", text, flags=re.I)
    parts = re.split(r"\s*(?:,|\bor\b|\band\b)\s*", text, flags=re.I)
    values = [_normalize_allowed_value(part) for part in parts]
    return tuple(dict.fromkeys(value for value in values if value))


def _split_role_values(text: str) -> tuple[str, ...]:
    roles: list[str] = []
    for match in ROLE_TERM_RE.finditer(text):
        role = match.group(1).lower()
        roles.append(ROLE_NORMALIZATION.get(role, role))
    return tuple(dict.fromkeys(roles))


def _normalize_disallowed_status(text: str) -> str | None:
    value = _normalize_allowed_value(text)
    if value in {"unauthorised", "unauthorized"}:
        return "unauthorized"
    return value


def _extract_role_permission_requirements(text: str) -> tuple[StateRequirement, ...]:
    requirements: list[StateRequirement] = []
    for pattern in (
        ROLE_PERMISSION_RE,
        ROLE_PERMISSION_FOR_RE,
        ROLE_CONDITION_RE,
        ROLE_RESTRICTED_RE,
        ROLE_PRIVILEGE_REQUIREMENT_RE,
    ):
        for match in pattern.finditer(text):
            role_text = match.group("roles")
            if APPROVAL_EVIDENCE_RE.search(role_text) and not ROLE_TERM_RE.search(role_text):
                continue
            roles = _split_role_values(role_text)
            if roles:
                requirements.append(_state_requirement("actor_role", "argument_in", roles))
    for match in ROLE_PROHIBITION_RE.finditer(text):
        if re.search(r"\b(?:cannot|can't|can\s+not|must\s+not|should\s+not)\s+help\b", match.group(0), re.I):
            continue
        roles = _split_role_values(match.group("roles"))
        if roles:
            requirements.append(_state_requirement("actor_role", "not_in", roles))
    return tuple(dict.fromkeys(requirements))


def _extract_allowed_value_requirements(text: str) -> tuple[StateRequirement, ...]:
    requirements: list[StateRequirement] = []
    for match in ALLOWED_VALUE_RE.finditer(text):
        field_text = re.sub(r"\s+", " ", match.group("field").lower()).strip()
        field = ALLOWED_VALUE_FIELD_MAP.get(field_text)
        values = _split_allowed_values(match.group("values"))
        if field and values:
            requirements.append(_state_requirement(field, "argument_in", values))
    for match in ALLOWED_STATUS_VALUE_RE.finditer(text):
        values = _split_allowed_values(match.group("values"))
        if values:
            requirements.append(_state_requirement("status", "argument_in", values, evidence_required=False))
    for match in ALLOWED_TARGET_TO_RE.finditer(text):
        target = re.sub(r"\s+", " ", match.group("target").lower()).strip()
        field_match = ALLOWED_TARGET_FIELD_RE.search(target)
        if not field_match:
            continue
        field_text = re.sub(r"\s+", " ", field_match.group("field").lower()).strip()
        field = ALLOWED_TARGET_FIELD_MAP.get(field_text)
        value_text = target[: field_match.start()].strip(" ,")
        values = _split_allowed_values(value_text)
        if field and values:
            requirements.append(_state_requirement(field, "argument_in", values))
    for match in ALLOWED_TARGET_MUST_RE.finditer(text):
        field_text = re.sub(r"\s+", " ", match.group("field").lower()).strip()
        field = ALLOWED_TARGET_FIELD_MAP.get(field_text)
        values = _split_allowed_values(match.group("values"))
        if field and values:
            requirements.append(_state_requirement(field, "argument_in", values))
    for match in ALLOWED_ACTION_ATTRIBUTE_RE.finditer(text):
        object_text = re.sub(r"\s+", " ", (match.group("object") or "").lower()).strip()
        field = ALLOWED_ATTRIBUTE_FIELD_MAP.get(object_text)
        values = _split_allowed_values(match.group("values"))
        if field and values:
            requirements.append(_state_requirement(field, "argument_in", values))
    return tuple(dict.fromkeys(requirements))


def _extract_disallowed_target_status_requirements(text: str) -> tuple[StateRequirement, ...]:
    requirements: list[StateRequirement] = []
    for match in DISALLOWED_TARGET_STATUS_RE.finditer(text):
        if re.search(r"\b(?:except|but|unless|until|without)\b", text[match.end() : match.end() + 120], re.I):
            continue
        target_text = re.sub(r"\s+", " ", match.group("target").lower()).strip()
        field = ALLOWED_TARGET_FIELD_MAP.get(target_text)
        value = _normalize_disallowed_status(match.group("status"))
        if field and value:
            requirements.append(_state_requirement(field, "not_in", (value,)))
    return tuple(dict.fromkeys(requirements))


def _extract_distinct_argument_requirements(text: str) -> tuple[StateRequirement, ...]:
    if not DISTINCT_ARGUMENT_RE.search(text):
        return ()
    lowered = text.lower()
    fields: list[str] = []
    for phrase, field in FIELD_PHRASES.items():
        if not field.endswith("_id"):
            continue
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            fields.append(field)
    fields = list(dict.fromkeys(fields))
    requirements: list[StateRequirement] = []
    for left_index, left in enumerate(fields):
        for right in fields[left_index + 1 :]:
            requirements.append(_state_requirement(left, "argument_distinct_from", (right,)))
    return tuple(dict.fromkeys(requirements))


def _extract_numeric_difference_requirements(text: str) -> tuple[StateRequirement, ...]:
    requirements: list[StateRequirement] = []
    for match in NUMERIC_DIFFERENCE_RE.finditer(text):
        direct_direction = (match.group("direction") or "").lower()
        reverse_direction = (match.group("direction_reverse") or "").lower()
        direction = direct_direction or reverse_direction
        effect = (match.group("effect") or match.group("effect_reverse") or "").lower()
        if direct_direction and ("lower" in direction or "less" in direction):
            relation = "decrease"
        elif direct_direction and ("higher" in direction or "greater" in direction or "more" in direction):
            relation = "increase"
        elif reverse_direction and ("exceed" in direction or "higher" in direction or "greater" in direction or "more" in direction):
            relation = "decrease"
        elif reverse_direction and ("lower" in direction or "less" in direction):
            relation = "increase"
        else:
            continue
        if effect.startswith(("refund", "reimburse")):
            target_field = "refund_amount"
        elif effect.startswith(("pay", "paid", "charge")):
            target_field = "payment_amount"
        else:
            continue
        requirements.append(_state_requirement(target_field, "numeric_difference", ("original_price", "new_price", relation)))
    return tuple(dict.fromkeys(requirements))


def _normalize_boolean_state_field(text: str) -> str | None:
    value = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    if not value.endswith("enabled"):
        return None
    stem = value[: -len("enabled")].strip()
    if not stem:
        return None
    words = [word for word in stem.split() if word not in FIELD_REJECT]
    if not words or len(words) > 4:
        return None
    return "_".join((*words, "enabled"))


def _extract_conditional_enable_requirements(text: str) -> tuple[StateRequirement, ...]:
    requirements: list[StateRequirement] = []
    for match in CONDITIONAL_ENABLE_RE.finditer(text):
        field = _normalize_boolean_state_field(match.group("field"))
        if field:
            requirements.append(_state_requirement(field, "not_in", ("enabled", "true", "yes")))
    return tuple(dict.fromkeys(requirements))


def _extract_unchanged_argument_requirements(text: str) -> tuple[StateRequirement, ...]:
    requirements: list[StateRequirement] = []
    for match in UNCHANGED_ARGUMENT_RE.finditer(text):
        fields = _extract_required_arguments(f"require {match.group('fields')}")
        for field in fields:
            requirements.append(_state_requirement(field, "argument_unchanged"))
    return tuple(dict.fromkeys(requirements))


def _expand_slash_conditions(text: str) -> str:
    return re.sub(
        r"\b([a-z][a-z0-9-]*)/([a-z][a-z0-9-]*)\s+(member|membership|class|tier|plan|fare)\b",
        r"\1 \3 or \2 \3",
        text,
        flags=re.I,
    )


def _normalize_eligibility_value(text: str) -> tuple[str, ...]:
    candidate = re.sub(r"\([^)]*\)", " ", text.lower())
    candidate = re.sub(r"['\"`]", " ", candidate)
    candidate = re.sub(
        r"\b(?:the|a|an|user|customer|traveler|passenger|client|booking)\b",
        " ",
        candidate,
    )
    candidate = re.sub(
        r"\b(?:is|are|be|being|has|have|had|with|flies|fly|flying|uses|use|using|holds|hold|gets|get)\b",
        " ",
        candidate,
    )
    candidate = re.sub(r"[^a-z0-9]+", " ", candidate).strip()
    if not candidate:
        return ()
    words = [word for word in candidate.split() if word not in FIELD_REJECT]
    if not words or len(words) > 5:
        return ()
    phrase = " ".join(words)
    values = [phrase]
    if words[-1] in {"member", "membership", "class", "tier", "plan", "fare"} and len(words) > 1:
        values.append(" ".join(words[:-1]))
    if "insurance" in words and phrase != "insurance":
        values.append("insurance")
    return tuple(dict.fromkeys(values))


def _extract_eligibility_requirements(text: str) -> tuple[StateRequirement, ...]:
    requirements: list[StateRequirement] = []
    for match in ELIGIBILITY_GATE_RE.finditer(text):
        condition_text = _expand_slash_conditions(match.group("conditions"))
        if not ELIGIBILITY_CONDITION_RE.search(condition_text):
            continue
        values: list[str] = []
        for part in re.split(r"\s*(?:,| or | and/or )\s*", condition_text, flags=re.I):
            values.extend(_normalize_eligibility_value(part))
        if values:
            requirements.append(_state_requirement("eligibility", "eligibility_any_in", tuple(dict.fromkeys(values))))
    return tuple(dict.fromkeys(requirements))


def _extract_runtime_protocol_requirements(text: str) -> tuple[StateRequirement, ...]:
    requirements: list[StateRequirement] = []
    if TOOL_CALL_MUTEX_RE.search(text):
        requirements.append(_state_requirement("runtime_protocol", "tool_call_mutex"))
    if HUMAN_ESCALATION_GATE_RE.search(text):
        requirements.append(_state_requirement("runtime_protocol", "human_escalation_if_unhandled"))
    if POLICY_DENIAL_GATE_RE.search(text):
        requirements.append(_state_requirement("runtime_protocol", "deny_if_policy_violation"))
    return tuple(dict.fromkeys(requirements))


def _canonical_prohibited_verb(verb: str) -> str:
    return PROHIBITED_VERB_CANONICAL.get(verb.lower(), verb.lower())


def _terms(text: str) -> tuple[str, ...]:
    return tuple(term for term in normalized_terms(text) if term not in OBJECT_TERM_REJECT)


def _split_object_and_condition_terms(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    text = re.sub(
        r"\b(?:even\s+if|regardless\s+of|despite|irrespective\s+of)\b[^.;]*",
        " ",
        text,
        flags=re.I,
    )
    match = CONDITION_SPLIT_RE.search(text)
    if not match:
        return _terms(text), ()
    object_text = text[: match.start()]
    condition_text = text[match.start() :]
    return _terms(object_text), _terms(condition_text)


def _prohibition_is_evidence_rule(text: str, numeric_value: float | None) -> bool:
    if numeric_value is not None:
        return True
    return bool(PROHIBITION_EVIDENCE_EXCEPTION_RE.search(text))


def _approval_evidence_type(text: str) -> str:
    if APPROVAL_AUTHORITY_RE.search(text):
        return "manager"
    if APPROVAL_EVIDENCE_RE.search(text):
        return "authorization"
    return ""


def _privacy_broad_scope(text: str) -> bool:
    return bool(PRIVACY_BROAD_SCOPE_RE.search(text))


def _requires_user_confirmation(text: str) -> bool:
    return bool(USER_CONFIRMATION_REQUIREMENT_RE.search(text))


def _external_disclosure_forbidden(text: str) -> bool:
    if INTERNAL_RECIPIENT_EXCEPTION_RE.search(text):
        return True
    if AUTHORIZATION_EXCEPTION_RE.search(text) or AUTHORIZATION_ALLOWANCE_RE.search(text):
        return False
    return bool(OUTSIDE_ORG_PROHIBITION_RE.search(text))


def _extract_forbidden_actions(text: str, numeric_value: float | None) -> tuple[ForbiddenAction, ...]:
    if _prohibition_is_evidence_rule(text, numeric_value):
        return ()

    actions: list[ForbiddenAction] = []
    for match in PROHIBITION_ACTIVE_RE.finditer(text):
        verb = next(
            value
            for value in (
                match.group("verb"),
                match.group("verb_modal"),
                match.group("verb_do"),
                match.group("verb_never"),
                match.group("verb_cannot"),
            )
            if value
        )
        tail = next(
            value
            for value in (
                match.group("tail"),
                match.group("tail_modal"),
                match.group("tail_do"),
                match.group("tail_never"),
                match.group("tail_cannot"),
            )
            if value is not None
        )
        object_terms, condition_terms = _split_object_and_condition_terms(tail)
        actions.append(
            ForbiddenAction(
                verb=_canonical_prohibited_verb(verb),
                object_terms=object_terms,
                condition_terms=condition_terms,
            )
        )

    for match in PROHIBITION_PASSIVE_RE.finditer(text):
        subject = match.group("subject")
        tail = match.group("tail")
        object_terms, leading_condition_terms = _split_object_and_condition_terms(subject)
        tail_object_terms, tail_condition_terms = _split_object_and_condition_terms(tail)
        actions.append(
            ForbiddenAction(
                verb=_canonical_prohibited_verb(match.group("verb")),
                object_terms=tuple(dict.fromkeys((*object_terms, *tail_object_terms))),
                condition_terms=tuple(dict.fromkeys((*leading_condition_terms, *tail_condition_terms))),
            )
        )

    return tuple(dict.fromkeys(item for item in actions if item.verb))


def _extract_state_requirements(text: str) -> tuple[StateRequirement, ...]:
    lowered = text.lower()
    runtime_requirements = _extract_runtime_protocol_requirements(text)
    if runtime_requirements:
        return runtime_requirements
    if RUNTIME_PROTOCOL_RE.search(lowered) or SOURCE_GROUNDING_RE.search(lowered) or WORKFLOW_REQUIREMENT_RE.search(lowered):
        return ()
    requirements: list[StateRequirement] = [
        *_extract_role_permission_requirements(text),
        *_extract_allowed_value_requirements(text),
        *_extract_disallowed_target_status_requirements(text),
        *_extract_distinct_argument_requirements(text),
        *_extract_numeric_difference_requirements(text),
        *_extract_conditional_enable_requirements(text),
        *_extract_unchanged_argument_requirements(text),
        *_extract_eligibility_requirements(text),
    ]

    terminal_requirements: list[StateRequirement] = []
    for match in TERMINAL_STATE_TRANSFER_RE.finditer(text):
        state = (match.group("state") or match.group("state_reverse") or "").lower()
        if state:
            terminal_requirements.append(_state_requirement("status", "not_in", (state,)))
    if terminal_requirements:
        return tuple(dict.fromkeys((*requirements, *terminal_requirements)))

    for match in re.finditer(r"\bonly\b.{0,96}\b(?:if|when)\b.{0,32}\bstatus\s+(?:is|=)\s+(?P<values>[^.;]+)", lowered):
        values = _split_state_values(match.group("values"))
        if values:
            requirements.append(_state_requirement("status", "in", values))

    for match in re.finditer(r"\bonly\s+(?:take\s+)?(?:an?\s+)?action\b.{0,40}\bon\s+(?P<values>[^.;]+)", lowered):
        values = _split_state_values(match.group("values"))
        if values:
            requirements.append(_state_requirement("status", "in", values))

    for match in re.finditer(r"\bonly\b.{0,96}\bstatus\s+(?:is|=)\s+(?P<values>[^.;]+)", lowered):
        values = _split_state_values(match.group("values"))
        if values:
            requirements.append(_state_requirement("status", "in", values))

    for match in re.finditer(r"\bif\b.{0,24}\bstatus\s+(?:is|=)?\s*(?P<values>[^,.;]+).{0,96}\b(?:cannot|can't|not)\b.{0,24}\b(?:book|cancel|modify|change|exchange|return|refund|use|help)", lowered):
        values = _split_state_values(match.group("values"))
        if values:
            requirements.append(_state_requirement("status", "not_in", values))

    if re.search(r"\bnot\s+flown\b|\bnot\s+taken\s+off\b", lowered) and re.search(r"\bonly|must|cannot|can't\b", lowered):
        requirements.append(_state_requirement("status", "in", ("not flown",)))

    if re.search(r"\bmust\s+already\s+be\s+in\b.{0,32}\b(profile|account|record)\b", lowered):
        requirements.append(_state_requirement("profile_membership", "present"))

    if re.search(r"\bmust\s+have\s+enough\s+balance\b|\benough\s+balance\s+to\b", lowered):
        requirements.append(_state_requirement("balance", "sufficient"))

    if re.search(r"\bavailable\b.{0,48}\b(new\s+)?(item|seat|slot|option|resource)\b", lowered):
        requirements.append(_state_requirement("availability", "present"))

    if re.search(r"\bsame\b.{0,64}\b(flight|cabin|product|account|profile|address|method)s?\b", lowered):
        requirements.append(_state_requirement("consistency", "same_as"))

    if re.search(r"\bdifferent\s+from\b.{0,40}\b(original|current|existing|previous)\b", lowered):
        requirements.append(_state_requirement("consistency", "different_from"))

    if re.search(r"\b(one|same)\s+user\b.{0,64}\b(conversation|request|session)\b|\bother\s+user\b", lowered):
        requirements.append(_state_requirement("user_scope", "same_as"))

    if (
        not requirements
        and STATE_RULE_RE.search(lowered)
        and STATE_OBJECT_RE.search(lowered)
        and not EXISTING_ENTITY_RE.search(lowered)
    ):
        requirements.append(_state_requirement("state", "checked"))

    return tuple(dict.fromkeys(requirements))


@dataclass
class ConstraintCompiler:
    feature_space: FeatureSpace

    @classmethod
    def default(cls, semantic_dims: int = 256) -> "ConstraintCompiler":
        return cls(FeatureSpace.default(semantic_dims=semantic_dims))

    def compile(self, constraints: list[NaturalLanguageConstraint]) -> tuple[HalfSpace, ...]:
        compiled: list[HalfSpace] = []
        for item in self.compile_constraints(constraints):
            compiled.extend(item.halfspaces)
        return tuple(compiled)

    def compile_constraints(self, constraints: list[NaturalLanguageConstraint]) -> tuple[CompiledConstraint, ...]:
        compiled: list[CompiledConstraint] = []
        for constraint in constraints:
            clause = self.parse_constraint(constraint)
            halfspaces = tuple(self._compile_one(clause))
            normal_form = self._normal_form(clause, halfspaces)
            compiled.append(
                CompiledConstraint(
                    clause=clause,
                    halfspaces=halfspaces,
                    normal_form=normal_form,
                    compile_certificate=self._compile_certificate(clause, halfspaces, normal_form),
                )
            )
        return tuple(compiled)

    def _normal_form(self, clause: ConstraintClause, halfspaces: tuple[HalfSpace, ...]) -> GeoConstraint:
        requirements: list[str] = []
        requirements.extend(effect for effect in clause.forbidden_effects)
        requirements.extend(f"forbid:{item.verb}:{' '.join(item.object_terms)}".strip(":") for item in clause.forbidden_actions)
        if clause.required_evidence.confirmation_required:
            requirements.append("trusted_confirmation")
        if clause.required_evidence.authorization_required:
            requirements.append("trusted_authorization")
        if clause.required_evidence.identity_required:
            requirements.append("trusted_identity")
        if clause.required_evidence.source_grounding_required:
            requirements.append("trusted_source_grounding")
        if clause.required_evidence.user_intent_required:
            requirements.append("trusted_user_intent")
        if clause.required_evidence.state_read_required:
            requirements.append("trusted_state_read")
        if clause.numeric_limit is not None:
            requirements.append(f"{clause.numeric_limit.argument}{clause.numeric_limit.operator}{clause.numeric_limit.value}")
        requirements.extend(f"count:{limit.item}<={limit.max_count}" for limit in clause.count_limits)
        requirements.extend(f"state:{req.field}:{req.operator}:{'|'.join(req.values)}" for req in clause.state_requirements)
        requirements.extend(item.id for item in halfspaces if not item.soft)

        projection_ops = list(clause.exceptions)
        if clause.required_evidence.identity_required:
            projection_ops.append("verify_identity")
        if clause.required_evidence.source_grounding_required:
            projection_ops.append("lookup_trusted_source")
        if clause.required_evidence.user_intent_required:
            projection_ops.append("ask_user_intent")
        if clause.numeric_limit is not None and clause.numeric_limit.approval_evidence:
            projection_ops.append(f"request_{clause.numeric_limit.approval_evidence}_approval")
        if clause.forbidden_actions:
            projection_ops.append("escalate_to_human")

        return GeoConstraint(
            id=clause.id,
            scope=clause.trigger.scope_terms,
            trigger=clause.trigger,
            requirement=tuple(dict.fromkeys(item for item in requirements if item)),
            evidence=clause.required_evidence,
            exceptions=clause.exceptions,
            projection_ops=tuple(dict.fromkeys(projection_ops)),
            metric="min_signed_margin_over_active_facets",
            severity=clause.severity,
        )

    def _compile_certificate(
        self,
        clause: ConstraintClause,
        halfspaces: tuple[HalfSpace, ...],
        normal_form: GeoConstraint,
    ) -> ConstraintCompileCertificate:
        if "conflicting_policy_terms" in clause.unsupported_reasons:
            status = CompileStatus.CONFLICT
        elif clause.parse_confidence < 0.5:
            status = CompileStatus.UNSUPPORTED
        elif clause.unsupported_reasons:
            status = CompileStatus.AMBIGUOUS
        else:
            status = CompileStatus.COMPILED
        abstain_reason = ""
        if status == CompileStatus.UNSUPPORTED:
            abstain_reason = "unsupported_policy_clause"
        elif status == CompileStatus.AMBIGUOUS:
            abstain_reason = "ambiguous_policy_clause"
        elif status == CompileStatus.CONFLICT:
            abstain_reason = "conflicting_policy_clause"
        return ConstraintCompileCertificate(
            constraint_id=clause.id,
            status=status,
            parse_confidence=clause.parse_confidence,
            unsupported_reasons=clause.unsupported_reasons,
            normal_form=normal_form,
            halfspace_ids=tuple(item.id for item in halfspaces),
            verifier_required=clause.verifier_required,
            abstain_reason=abstain_reason,
        )

    def parse_constraint(self, constraint: NaturalLanguageConstraint) -> ConstraintClause:
        lowered = constraint.text.lower()
        protocol_or_workflow_policy = bool(
            RUNTIME_PROTOCOL_RE.search(lowered)
            or SOURCE_GROUNDING_RE.search(lowered)
            or WORKFLOW_REQUIREMENT_RE.search(lowered)
        )
        categories = categories_for_constraint(constraint.text)
        numeric_value = extract_numeric_limit(constraint.text)
        approval_evidence = _approval_evidence_type(constraint.text)
        forbidden_actions = _extract_forbidden_actions(constraint.text, numeric_value)
        identity_required = bool(IDENTITY_REQUIREMENT_RE.search(constraint.text))
        source_grounding_required = bool(SOURCE_GROUNDING_RE.search(constraint.text))
        external_web_access_policy = "external_web_access" in categories or bool(EXTERNAL_WEB_ACCESS_RE.search(constraint.text))
        user_intent_required = (
            bool(USER_INTENT_REQUIREMENT_RE.search(constraint.text)) or external_web_access_policy
        ) and not bool(
            EXCEPTION_DENIAL_RE.search(constraint.text)
        )
        redaction_required = bool(REDACTION_REQUIREMENT_RE.search(constraint.text))
        external_disclosure_forbidden = "privacy" in categories and _external_disclosure_forbidden(constraint.text)
        count_limits = () if protocol_or_workflow_policy else _extract_count_limits(constraint.text)
        state_requirements = _extract_state_requirements(constraint.text)
        private_access_policy = any(token in lowered for token in ("access", "read", "retrieve", "lookup", "view", "use private", "use personal"))
        explicit_state_read_phrase = bool(EXPLICIT_STATE_READ_RE.search(lowered))
        bare_required_arguments = () if protocol_or_workflow_policy else _extract_bare_required_arguments(constraint.text)
        existing_entity_required_arguments = (
            ()
            if protocol_or_workflow_policy or explicit_state_read_phrase
            else _extract_existing_entity_required_arguments(constraint.text)
        )
        field_collection_policy = (
            bool(bare_required_arguments)
            or bool(existing_entity_required_arguments)
            or (
                bool(FIELD_COLLECTION_RE.search(lowered))
                and not bool(NEGATED_FIELD_COLLECTION_RE.search(lowered))
                and not explicit_state_read_phrase
                and not protocol_or_workflow_policy
                and numeric_value is None
            )
        )
        required_arguments = (
            tuple(
                dict.fromkeys(
                    (
                        *bare_required_arguments,
                        *existing_entity_required_arguments,
                        *_extract_required_arguments(constraint.text),
                    )
                )
            )
            if field_collection_policy
            else ()
        )
        explicit_state_read_required = "state" in categories and explicit_state_read_phrase and not field_collection_policy
        if numeric_value is not None and approval_evidence and "confirm" not in lowered:
            categories.discard("confirmation")
        if source_grounding_required and "confirmation" in categories and not _requires_user_confirmation(constraint.text):
            categories.discard("confirmation")
        trigger = TriggerSpec(
            action_types=tuple(sorted(categories)),
            requires_side_effect="side_effect" in categories,
            requires_write=explicit_state_read_required or bool(state_requirements),
            privacy_disclosure="privacy" in categories,
            private_data_access="privacy" in categories and "authorization" in categories and private_access_policy,
            financial_action="financial" in categories,
            external_web_access=external_web_access_policy,
            existing_record_write=explicit_state_read_required or bool(state_requirements),
            irreversible="irreversible" in categories,
            scope_terms=extract_scope_terms(constraint.text),
            broad_scope=has_broad_scope(constraint.text) or ("privacy" in categories and _privacy_broad_scope(constraint.text)),
        )
        evidence = EvidenceSpec(
            confirmation_required="confirmation" in categories,
            authorization_required="authorization" in categories and numeric_value is None,
            redaction_required=redaction_required,
            external_disclosure_forbidden=external_disclosure_forbidden,
            identity_required=identity_required,
            source_grounding_required=source_grounding_required,
            user_intent_required=user_intent_required,
            policy_required=explicit_state_read_required or bool(state_requirements) or "policy" in lowered,
            state_read_required=explicit_state_read_required,
            manager_approval_required=numeric_value is not None and approval_evidence == "manager",
            required_arguments=required_arguments,
        )
        temporal = TemporalSpec(
            require_read_before_write=explicit_state_read_required,
            require_confirmation_before_action=evidence.confirmation_required,
        )
        forbidden: list[str] = []
        if "privacy" in categories:
            forbidden.extend(["unauthorized_private_disclosure", "unauthorized_private_access"])
        if external_disclosure_forbidden:
            forbidden.append("external_private_disclosure")
        if "confirmation" in categories:
            if "irreversible" in categories:
                forbidden.append("irreversible_without_confirmation")
            elif "side_effect" in categories:
                forbidden.append("side_effect_without_confirmation")
            else:
                forbidden.append("irreversible_without_confirmation")
        if explicit_state_read_required:
            forbidden.append("existing_record_write_without_read")
        if "financial" in categories and numeric_value is None:
            forbidden.append("financial_action_without_auth")
        if user_intent_required:
            forbidden.append("action_without_user_intent")
        if external_web_access_policy:
            forbidden.append("external_web_access_without_user_intent")
        supported_structured = bool(
            numeric_value is not None
            or count_limits
            or state_requirements
            or forbidden_actions
            or identity_required
            or source_grounding_required
            or user_intent_required
            or external_web_access_policy
            or redaction_required
            or external_disclosure_forbidden
            or "confirmation" in categories
            or explicit_state_read_required
            or bool(state_requirements)
            or bool(required_arguments)
            or ("authorization" in categories and ("privacy" in categories or "financial" in categories))
        )
        unsupported_reasons: list[str] = []
        if "general" in categories and not supported_structured:
            unsupported_reasons.append("no_structured_trigger")
        if ("financial" in categories or "privacy" in categories) and not supported_structured:
            unsupported_reasons.append("missing_explicit_evidence_or_limit")
        if forbidden and not supported_structured:
            unsupported_reasons.append("forbidden_effect_without_halfspace")
        if not supported_structured and WORKFLOW_REQUIREMENT_RE.search(lowered):
            unsupported_reasons.append("requires_unmodeled_workflow")
        if not supported_structured and RUNTIME_PROTOCOL_RE.search(lowered):
            unsupported_reasons.append("requires_runtime_protocol_monitor")
        if not supported_structured and SOURCE_GROUNDING_RE.search(lowered):
            unsupported_reasons.append("requires_source_grounding_monitor")
        if not supported_structured and numeric_value is None:
            unsupported_reasons.append("semantic_only_constraint")
        parse_confidence = 0.95 if numeric_value is not None or forbidden_actions else 0.9 if supported_structured else 0.35
        if unsupported_reasons and supported_structured:
            parse_confidence = min(parse_confidence, 0.65)

        return ConstraintClause(
            id=constraint.id,
            text=constraint.text,
            trigger=trigger,
            required_evidence=evidence,
            forbidden_effects=tuple(forbidden),
            forbidden_actions=forbidden_actions,
            numeric_limit=NumericLimit(value=numeric_value, approval_evidence=approval_evidence)
            if numeric_value is not None
            else None,
            count_limits=count_limits,
            state_requirements=state_requirements,
            temporal_order=temporal,
            exceptions=(
                "ask_user_for_confirmation",
                "read_state",
                "lookup_policy",
                "redact_sensitive_info",
            ),
            severity=max(float(constraint.priority), 0.05),
            verifier_required=bool(
                numeric_value is not None
                or count_limits
                or state_requirements
                or forbidden_actions
                or evidence.identity_required
                or evidence.source_grounding_required
                or evidence.user_intent_required
                or evidence.redaction_required
                or evidence.external_disclosure_forbidden
                or evidence.required_arguments
                or evidence.confirmation_required
                or evidence.state_read_required
            ),
            parse_confidence=parse_confidence,
            unsupported_reasons=tuple(dict.fromkeys(unsupported_reasons)),
            source_constraint=constraint,
        )

    def _compile_one(self, clause: ConstraintClause) -> list[HalfSpace]:
        categories = set(clause.trigger.action_types)
        constraint = clause.source_constraint or NaturalLanguageConstraint(id=clause.id, text=clause.text, priority=clause.severity)
        safe_texts, unsafe_texts = self._anchors(constraint, categories)
        safe_vectors = self.feature_space.vectorize_semantic_texts_only(safe_texts)
        unsafe_vectors = self.feature_space.vectorize_semantic_texts_only(unsafe_texts)
        halfspaces: list[HalfSpace] = [
            semantic_boundary(
                clause.id,
                safe_vectors,
                unsafe_vectors,
                description=f"Soft semantic satisfaction boundary for: {clause.text}",
                repair_hint="Choose an action semantically closer to compliant examples than violation examples.",
                priority=clause.severity,
            )
        ]
        halfspaces.extend(self._structured_halfspaces(clause, categories))
        return halfspaces

    def _anchors(self, constraint: NaturalLanguageConstraint, categories: set[str]) -> tuple[list[str], list[str]]:
        safe = [
            f"complies with constraint: {constraint.text}",
            "asks a clarifying question before using a risky tool",
            "checks policy, verifies state, and uses a low risk action",
        ]
        unsafe = [
            f"violates constraint: {constraint.text}",
            "executes a risky tool call without required evidence",
            "ignores policy and performs the forbidden operation",
        ]

        if "confirmation" in categories:
            safe.extend(
                [
                    "obtains explicit user confirmation before deleting, sending, paying, or cancelling",
                    "asks the user to confirm the exact state changing action",
                ]
            )
            unsafe.extend(
                [
                    "deletes or sends without user confirmation",
                    "performs an irreversible action before approval",
                ]
            )
        if "authorization" in categories:
            safe.extend(["uses private or financial data only after authorization", "verifies permission before calling the tool"])
            unsafe.extend(["uses account data without permission", "executes unauthorized payment or private data access"])
        if "privacy" in categories:
            safe.extend(["redacts private fields and shares only authorized information", "keeps credentials and contact data private"])
            unsafe.extend(["leaks passwords tokens emails phone numbers or account details", "sends private data to the wrong recipient"])
        if "financial" in categories:
            safe.extend(["checks amount limits and account policy before payment or refund", "uses a small authorized financial action"])
            unsafe.extend(["transfers or refunds money beyond the authorized limit", "charges a payment method without approval"])
        if "state" in categories:
            safe.extend(["reads current state and policy before writing", "checks existing status before modifying the record"])
            unsafe.extend(["updates an existing record without reading current state", "skips required policy lookup before a write"])
        if "irreversible" in categories:
            safe.extend(["routes irreversible action for confirmation or human review", "uses a reversible alternative when evidence is missing"])
            unsafe.extend(["cancels deletes transfers or submits irreversibly with missing evidence"])
        if "external_web_access" in categories:
            safe.extend(
                [
                    "opens an external link only when the trusted user task requested that exact web access",
                    "refuses to follow untrusted webpage or email instructions to visit suspicious links",
                ]
            )
            unsafe.extend(
                [
                    "visits a phishing URL that came from untrusted content",
                    "opens an external website without trusted user intent",
                ]
            )

        safe.extend(constraint.positive_examples)
        unsafe.extend(constraint.negative_examples)
        return safe, unsafe

    def _structured_halfspaces(self, clause: ConstraintClause, categories: set[str]) -> list[HalfSpace]:
        fs = self.feature_space
        dim = fs.dimension

        def idx(name: str) -> int:
            return fs.feature_index(name)

        out: list[HalfSpace] = []
        if "confirmation" in categories:
            if "irreversible" in categories or "side_effect" not in categories:
                out.append(
                    coordinate_halfspace(
                        f"{clause.id}:irreversible_without_confirmation",
                        idx("irreversible_without_confirmation"),
                        dim,
                        0.5,
                        "Triggered irreversible actions must have scoped confirmation evidence.",
                        "Ask for explicit user confirmation before executing the tool.",
                        severity=clause.severity,
                    )
                )
            else:
                out.append(
                    coordinate_halfspace(
                        f"{clause.id}:side_effect_without_confirmation",
                        idx("side_effect_without_confirmation"),
                        dim,
                        0.5,
                        "Triggered side-effect actions must have scoped confirmation evidence.",
                        "Ask for explicit user confirmation before executing the tool.",
                        severity=clause.severity,
                    )
                )
        if "privacy" in categories and (
            "authorization" in categories
            or clause.required_evidence.redaction_required
            or clause.required_evidence.external_disclosure_forbidden
        ):
            out.append(
                coordinate_halfspace(
                    f"{clause.id}:privacy_disclosure_without_auth",
                    idx("privacy_disclosure_without_auth"),
                    dim,
                    0.5,
                    "Privacy disclosure is blocked when disclosure is triggered and neither authorization nor redaction is present.",
                    "Obtain authorization or redact private fields before disclosure.",
                    severity=clause.severity,
                )
            )
            if clause.trigger.private_data_access:
                out.append(
                    coordinate_halfspace(
                        f"{clause.id}:private_data_access_without_auth",
                        idx("private_data_access_without_auth"),
                        dim,
                        0.5,
                        "Private data access is only blocked when private access is triggered and authorization is missing.",
                        "Obtain authorization or use a non-private lookup.",
                        severity=clause.severity,
                    )
                )
        if "authorization" in categories:
            if "financial" in categories and clause.numeric_limit is None:
                out.append(
                    coordinate_halfspace(
                        f"{clause.id}:financial_action_without_auth",
                        idx("financial_action_without_auth"),
                        dim,
                        0.5,
                        "Financial side effects require authorization evidence when no numeric exception applies.",
                        "Verify authorization before executing the financial action.",
                        severity=clause.severity,
                    )
                )
        if clause.required_evidence.state_read_required:
            out.append(
                coordinate_halfspace(
                    f"{clause.id}:existing_record_write_without_read",
                    idx("existing_record_write_without_read"),
                    dim,
                    0.5,
                    "Existing-record writes should be preceded by current-state or policy lookup.",
                    "Read or verify the current state before writing.",
                    severity=clause.severity,
                )
            )
        if clause.required_evidence.user_intent_required:
            out.append(
                coordinate_halfspace(
                    f"{clause.id}:user_intent_missing",
                    idx("user_intent_missing"),
                    dim,
                    0.5,
                    "Intent-gated actions require trusted evidence that the user requested, accepted, or wanted the action.",
                    "Ask the user whether they want or accept this action before proceeding.",
                    severity=clause.severity,
                    soft=True,
                )
            )
        if "external_web_access" in categories and clause.required_evidence.user_intent_required:
            out.append(
                coordinate_halfspace(
                    f"{clause.id}:external_web_access_without_user_intent",
                    idx("external_web_access_without_user_intent"),
                    dim,
                    0.5,
                    "External web or link access requires trusted evidence that the user requested that web access.",
                    "Ask the user to confirm the external link or route the request to human review.",
                    severity=clause.severity,
                )
            )
        return out
