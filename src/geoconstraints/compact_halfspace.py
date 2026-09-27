from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import math
import re
from typing import Any, Mapping, Sequence

import numpy as np

from geoconstraints.schemas import (
    ActionEvaluation,
    ConstraintCertificate,
    ConstraintMargin,
    NaturalLanguageConstraint,
    ProjectionCertificate,
    SelectionResult,
    ShieldDecision,
    ToolAction,
    UtilityFn,
)
from geoconstraints.text import flatten_value


class CompactDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ABSTAIN = "ABSTAIN"
    REPAIR_ACTION = "REPAIR_ACTION"


_AMOUNT_KEYS = (
    "amount",
    "refund_amount",
    "transfer_amount",
    "payment_amount",
    "charge_amount",
    "price",
    "total",
    "quantity",
)
_LIMIT_KEYS = (
    "max_amount",
    "amount_limit",
    "refund_limit",
    "paid_amount",
    "available_balance",
    "balance",
    "limit",
)

_WRITE_RE = re.compile(
    r"(?:^|[\s_:.\-/])"
    r"(create|add|insert|update|modify|delete|remove|set|change|exchange|replace|book|reserve|cancel|refund|return|send|share|"
    r"forward|submit|purchase|pay|charge|withdraw|transfer|post|publish|upload|enable|disable|activate|deactivate)"
    r"(?:$|[\s_:.\-/])",
    re.I,
)
_READ_RE = re.compile(
    r"(?:^|[\s_:.\-/])"
    r"(get|read|search|query|list|retrieve|check|show|find|lookup|view|fetch|verify|validate|inspect)"
    r"(?:$|[\s_:.\-/])",
    re.I,
)
_IRREVERSIBLE_RE = re.compile(
    r"(?:^|[\s_:.\-/])(delete|remove|cancel|set|update|modify|change|exchange|replace|book|reserve|refund|return|send|submit|purchase|pay|charge|withdraw|transfer|close|disable|deactivate)(?:$|[\s_:.\-/])",
    re.I,
)
_FINANCIAL_RE = re.compile(
    r"\b(refund|payment|pay|charge|transfer|withdraw|deposit|invoice|credit|debit|card|amount|balance|price)\b",
    re.I,
)
_PRIVATE_RE = re.compile(
    r"\b(private|personal|sensitive|password|token|secret|ssn|phone|email|address|account|credential|contact)\b",
    re.I,
)
_EXTERNAL_RE = re.compile(
    r"\b(external|public|third[- ]party|outside|web|website|url|link|http|https|vendor|other user)\b|@[^\s@]+\.[^\s@]+",
    re.I,
)
_INTERNAL_RE = re.compile(r"\b(internal|corp|company|employee|staff|support team)\b|@[^\s@]+\.(?:internal|corp|local)\b", re.I)
_WEB_ACCESS_RE = re.compile(r"\b(open|fetch|visit|browse|request|download|crawl|click|follow|read)\b.{0,40}\b(url|link|website|webpage|http|https)\b|https?://", re.I)
_REPAIR_RE = re.compile(r"\b(ask|confirm|clarify|request|verify|lookup|read|escalate|human|redact|mask)\b", re.I)
_CONFIRM_RE = re.compile(r"\b(confirm|confirmed|confirmation|approve|approved|yes proceed|go ahead|explicit confirmation)\b", re.I)
_AUTH_RE = re.compile(r"\b(authori[sz]e|authori[sz]ed|authori[sz]ation|permission|permitted|approval|approved|allowed|consent|manager approved)\b", re.I)
_INTENT_RE = re.compile(r"\b(user requested|user asked|requested by user|trusted user intent|user wants|user accepted|please|go ahead)\b", re.I)
_IDENTITY_RE = re.compile(r"\b(identity verified|verified identity|authenticated|kyc|identified customer|verified customer)\b", re.I)
_STATE_RE = re.compile(r"\b(state read|read state|checked status|current status|observed state|lookup result|tool result|current state|state was checked)\b", re.I)
_REDACT_RE = re.compile(r"\b(redacted|masked|anonymi[sz]ed|de[- ]identified|without private|without personal|without sensitive)\b|\[(redacted|masked)\]", re.I)
_NEGATED_CONFIRM_RE = re.compile(r"\b(no|not|without|missing|never|unconfirmed)\b.{0,32}\b(confirm|confirmed|confirmation|approval|approved)\b", re.I)
_NEGATED_AUTH_RE = re.compile(r"\b(no|not|without|missing|never|unauthorized)\b.{0,32}\b(authori[sz]ation|authorized|approval|approved|permission|consent)\b", re.I)
_NEGATED_STATE_RE = re.compile(r"\b(no|not|without|missing|never)\b.{0,32}\b(state|status|policy|current record)\b.{0,32}\b(read|checked|verified|lookup)?\b", re.I)


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_flatten(item)}" for key, item in sorted(value.items()))
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(item) for item in value)
    return str(value)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "confirmed", "approved", "authorized", "verified"}


def _numeric_from(keys: Sequence[str], *mappings: Mapping[str, Any]) -> tuple[float, bool]:
    for mapping in mappings:
        for key in keys:
            if key not in mapping:
                continue
            try:
                return float(mapping[key]), True
            except (TypeError, ValueError):
                continue
    return 0.0, False


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class CompactFeatureSchema:
    names: tuple[str, ...]

    def index(self, name: str) -> int:
        try:
            return self.names.index(name)
        except ValueError as exc:
            raise KeyError(f"Unknown compact feature {name!r}") from exc

    def vector(self, values: Mapping[str, float]) -> np.ndarray:
        return np.array([float(values.get(name, 0.0)) for name in self.names], dtype=float)

    def to_dict(self, vector: np.ndarray) -> dict[str, float]:
        return {name: float(value) for name, value in zip(self.names, vector)}


COMPACT_FEATURE_SCHEMA = CompactFeatureSchema(
    names=(
        "is_write",
        "is_read",
        "is_irreversible",
        "is_financial_action",
        "is_private_disclosure",
        "is_private_access",
        "is_external_access",
        "is_existing_record_write",
        "is_account_action",
        "has_confirmation",
        "has_authorization",
        "has_identity",
        "has_state_read",
        "has_user_intent",
        "is_redacted",
        "is_repair_action",
        "amount_known",
        "limit_known",
        "amount_norm",
        "limit_norm",
    )
)


@dataclass(frozen=True)
class CompactFeatureEncoder:
    schema: CompactFeatureSchema = COMPACT_FEATURE_SCHEMA
    amount_scale: float = 1000.0

    def evidence(self, action: ToolAction) -> Mapping[str, Any]:
        raw_evidence = action.raw.get("evidence", {})
        if isinstance(raw_evidence, Mapping):
            return raw_evidence
        return {}

    def state(self, action: ToolAction) -> Mapping[str, Any]:
        for key in ("state", "observed_state", "current_state", "trusted_state"):
            value = action.raw.get(key)
            if isinstance(value, Mapping):
                return value
        return {}

    def encode_dict(self, action: ToolAction) -> dict[str, float]:
        evidence = self.evidence(action)
        state = self.state(action)
        raw_text = _flatten(action.raw)
        history = _flatten(action.history[-8:])
        direct = f"{action.tool_name} {action.action_text} {_flatten(action.arguments)}".lower()
        text = f"{direct} {action.context_text} {history} {raw_text}".lower()
        evidence_text = f"{_flatten(evidence)} {action.context_text} {history} {raw_text}".lower()
        state_text = _flatten(state).lower()

        is_repair = 1.0 if _REPAIR_RE.search(f"{action.tool_name} {action.action_text}".lower()) else 0.0
        is_read = 1.0 if _READ_RE.search(direct) else 0.0
        is_write = 0.0 if is_read and not _WRITE_RE.search(direct) else 1.0 if _WRITE_RE.search(direct) else 0.0
        is_irreversible = 1.0 if _IRREVERSIBLE_RE.search(direct) else 0.0
        if is_repair:
            is_write = 0.0
            is_irreversible = 0.0

        private_signal = bool(_PRIVATE_RE.search(text))
        external_signal = bool(_EXTERNAL_RE.search(direct)) and not bool(_INTERNAL_RE.search(direct))
        is_external_access = 1.0 if _WEB_ACCESS_RE.search(direct) else 0.0
        is_existing_record_write = (
            1.0
            if is_write and re.search(r"\b(id|order|account|reservation|record|ticket|customer|user|task|status)\b", direct)
            else 0.0
        )
        is_account_action = 1.0 if re.search(r"\b(account|customer|user|identity|reservation|order|profile)\b", direct) else 0.0
        is_financial = 1.0 if is_write and _FINANCIAL_RE.search(text) else 0.0
        is_private_disclosure = 1.0 if is_write and private_signal and external_signal else 0.0
        is_private_access = 1.0 if is_read and private_signal and not is_repair else 0.0

        amount, amount_known = _numeric_from(_AMOUNT_KEYS, action.arguments, state, evidence)
        limit, limit_known = _numeric_from(_LIMIT_KEYS, action.arguments, state, evidence)
        scale = max(float(self.amount_scale), 1e-9)

        has_confirmation = any(
            (
                _truthy(evidence.get("confirmation")),
                _truthy(evidence.get("confirmed")),
                _truthy(evidence.get("user_confirmed")),
                bool(_CONFIRM_RE.search(evidence_text)) and not bool(_NEGATED_CONFIRM_RE.search(evidence_text)),
            )
        )
        has_authorization = any(
            (
                _truthy(evidence.get("authorization")),
                _truthy(evidence.get("authorized")),
                _truthy(evidence.get("approval")),
                _truthy(evidence.get("manager_approval")),
                bool(_AUTH_RE.search(evidence_text)) and not bool(_NEGATED_AUTH_RE.search(evidence_text)),
            )
        )
        has_identity = any(
            (
                _truthy(evidence.get("identity_verified")),
                _truthy(state.get("identity_verified")),
                bool(_IDENTITY_RE.search(f"{evidence_text} {state_text}")),
            )
        )
        has_state_read = any(
            (
                _truthy(evidence.get("state_read")),
                _truthy(evidence.get("checked_state")),
                _truthy(state.get("known")),
                bool(state),
                bool(_STATE_RE.search(f"{evidence_text} {state_text}"))
                and not bool(_NEGATED_STATE_RE.search(f"{evidence_text} {state_text}")),
            )
        )
        has_user_intent = any(
            (
                _truthy(evidence.get("user_intent")),
                _truthy(evidence.get("user_requested")),
                bool(_INTENT_RE.search(evidence_text)),
            )
        )
        is_redacted = any(
            (
                _truthy(evidence.get("redacted")),
                _truthy(action.arguments.get("redacted")),
                bool(_REDACT_RE.search(text)),
            )
        )

        return {
            "is_write": float(is_write),
            "is_read": float(is_read),
            "is_irreversible": float(is_irreversible),
            "is_financial_action": float(is_financial),
            "is_private_disclosure": float(is_private_disclosure),
            "is_private_access": float(is_private_access),
            "is_external_access": float(is_external_access),
            "is_existing_record_write": float(is_existing_record_write),
            "is_account_action": float(is_account_action),
            "has_confirmation": 1.0 if has_confirmation else 0.0,
            "has_authorization": 1.0 if has_authorization else 0.0,
            "has_identity": 1.0 if has_identity else 0.0,
            "has_state_read": 1.0 if has_state_read else 0.0,
            "has_user_intent": 1.0 if has_user_intent else 0.0,
            "is_redacted": 1.0 if is_redacted else 0.0,
            "is_repair_action": float(is_repair),
            "amount_known": 1.0 if amount_known else 0.0,
            "limit_known": 1.0 if limit_known else 0.0,
            "amount_norm": amount / scale if amount_known else 0.0,
            "limit_norm": limit / scale if limit_known else 0.0,
        }

    def encode(self, action: ToolAction) -> np.ndarray:
        return self.schema.vector(self.encode_dict(action))


@dataclass(frozen=True)
class CompactGate:
    weights: Mapping[str, float]
    threshold: float = 0.5
    relation: str = ">="

    def value(self, vector: np.ndarray, schema: CompactFeatureSchema) -> float:
        return float(sum(weight * vector[schema.index(name)] for name, weight in self.weights.items()))

    def active(self, vector: np.ndarray, schema: CompactFeatureSchema) -> bool:
        value = self.value(vector, schema)
        if self.relation == ">=":
            return value >= self.threshold
        if self.relation == ">":
            return value > self.threshold
        if self.relation == "<=":
            return value <= self.threshold
        if self.relation == "<":
            return value < self.threshold
        raise ValueError(f"Unsupported gate relation {self.relation!r}")


@dataclass(frozen=True)
class CompactHalfspaceConstraint:
    id: str
    weights: Mapping[str, float]
    bound: float
    description: str
    repair_hint: str
    severity: float = 1.0
    hard: bool = True
    gates: tuple[CompactGate, ...] = ()
    required_features: tuple[str, ...] = ()
    source: str = "compact_template"

    def normal(self, schema: CompactFeatureSchema) -> np.ndarray:
        out = np.zeros(len(schema.names), dtype=float)
        for name, weight in self.weights.items():
            out[schema.index(name)] = float(weight)
        return out

    def applies(self, vector: np.ndarray, schema: CompactFeatureSchema) -> bool:
        return all(gate.active(vector, schema) for gate in self.gates)

    def value(self, vector: np.ndarray, schema: CompactFeatureSchema) -> float:
        return float(self.normal(schema) @ vector)

    def norm(self, schema: CompactFeatureSchema) -> float:
        value = float(np.linalg.norm(self.normal(schema)))
        return value if value > 1e-12 else 1.0

    def margin(self, vector: np.ndarray, schema: CompactFeatureSchema) -> ConstraintMargin:
        value = self.value(vector, schema)
        slack = float(self.bound - value)
        return ConstraintMargin(
            constraint_id=self.id,
            value=value,
            bound=float(self.bound),
            slack=slack,
            normalized_margin=slack / self.norm(schema),
            description=self.description,
            repair_hint=self.repair_hint,
            severity=float(self.severity),
            soft=not self.hard,
            source=self.source,
        )

    def missing_required_features(self, vector: np.ndarray, schema: CompactFeatureSchema) -> tuple[str, ...]:
        return tuple(name for name in self.required_features if vector[schema.index(name)] < 0.5)


@dataclass(frozen=True)
class CompactCompiledPolicy:
    constraints: tuple[CompactHalfspaceConstraint, ...]
    unsupported_lines: tuple[str, ...] = ()
    compiled_lines: tuple[str, ...] = ()


class CompactTemplatePolicyCompiler:
    CONFIRM_RE = re.compile(r"\b(confirm|confirmation|approval|ask the user|explicit confirmation)\b", re.I)
    STATE_RE = re.compile(r"\b(read|check|lookup|verify|current|status|state)\b.{0,80}\b(before|prior|first)\b|\bbefore\b.{0,80}\b(read|check|lookup|verify)", re.I)
    AUTH_RE = re.compile(r"\b(authori[sz]e|authori[sz]ation|permission|consent|approval|permitted|manager)\b", re.I)
    PRIVACY_RE = _PRIVATE_RE
    FINANCIAL_RE = _FINANCIAL_RE
    EXTERNAL_WEB_RE = re.compile(r"\b(external|untrusted|web|website|url|link|browse|visit|open|fetch)\b", re.I)
    USER_INTENT_RE = re.compile(r"\b(user asks|user asked|user requests|user requested|explicit user|unless the user|if the user)\b", re.I)
    IDENTITY_RE = re.compile(r"\b(identity|authenticate|verified customer|identify the customer|verify the user)\b", re.I)
    NUMERIC_RE = re.compile(r"\b(amount|refund|payment|transfer|charge|quantity|price)\b.{0,80}\b(<=|less than|no more than|not exceed|up to|at most|paid amount|balance|limit|more than)\b", re.I)

    def compile(self, policy_lines: Sequence[NaturalLanguageConstraint | str]) -> CompactCompiledPolicy:
        constraints: list[CompactHalfspaceConstraint] = []
        unsupported: list[str] = []
        compiled: list[str] = []
        for idx, item in enumerate(policy_lines):
            line = item.text if isinstance(item, NaturalLanguageConstraint) else str(item)
            line = " ".join(line.strip().split())
            if not line:
                continue
            line_constraints = self._compile_line(idx, line)
            if line_constraints:
                constraints.extend(line_constraints)
                compiled.append(line)
            else:
                unsupported.append(line)
        return CompactCompiledPolicy(tuple(constraints), tuple(unsupported), tuple(compiled))

    def _compile_line(self, idx: int, line: str) -> tuple[CompactHalfspaceConstraint, ...]:
        out: list[CompactHalfspaceConstraint] = []
        prefix = f"compact_p{idx}"
        if self.CONFIRM_RE.search(line) and re.search(r"\b(irreversible|delete|cancel|transfer|pay|charge|withdraw|submit|purchase|external side-effect|side-effect)\b", line, re.I):
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:irreversible_requires_confirmation",
                    weights={"is_irreversible": 1.0, "has_confirmation": -1.0},
                    bound=0.5,
                    description="Irreversible actions must lie inside the confirmation half-space.",
                    repair_hint="Ask the user to confirm the exact irreversible action before calling the tool.",
                    gates=(CompactGate({"is_irreversible": 1.0}),),
                    source="compact_nl_template:confirmation",
                )
            )
        if self.CONFIRM_RE.search(line) and re.search(r"\b(write|modify|update|send|share|create|book|refund)\b", line, re.I):
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:write_requires_confirmation",
                    weights={"is_write": 1.0, "has_confirmation": -1.0},
                    bound=0.5,
                    description="Side-effecting writes must lie inside the confirmation half-space.",
                    repair_hint="Ask for scoped confirmation before executing this side-effecting tool call.",
                    gates=(CompactGate({"is_write": 1.0}),),
                    source="compact_nl_template:confirmation",
                )
            )
        if self.PRIVACY_RE.search(line) and (self.AUTH_RE.search(line) or re.search(r"\b(redact|mask|de[- ]?identify|without authorization)\b", line, re.I)):
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:private_disclosure_requires_auth_or_redaction",
                    weights={"is_private_disclosure": 1.0, "has_authorization": -1.0, "is_redacted": -1.0},
                    bound=0.5,
                    description="External private-data disclosure must be authorized or redacted.",
                    repair_hint="Obtain authorization, redact the content, or avoid the external disclosure.",
                    gates=(CompactGate({"is_private_disclosure": 1.0}),),
                    source="compact_nl_template:privacy",
                )
            )
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:private_access_requires_authorization",
                    weights={"is_private_access": 1.0, "has_authorization": -1.0, "has_identity": -1.0},
                    bound=0.5,
                    description="Private data access must be authorized or identity-verified.",
                    repair_hint="Verify identity or obtain authorization before reading private data.",
                    gates=(CompactGate({"is_private_access": 1.0}),),
                    source="compact_nl_template:privacy",
                )
            )
        if self.FINANCIAL_RE.search(line) and self.AUTH_RE.search(line):
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:financial_requires_authorization",
                    weights={"is_financial_action": 1.0, "has_authorization": -1.0},
                    bound=0.5,
                    description="Financial tool calls must be authorized.",
                    repair_hint="Obtain trusted authorization or manager approval before the financial action.",
                    gates=(CompactGate({"is_financial_action": 1.0}),),
                    source="compact_nl_template:financial",
                )
            )
        if self.EXTERNAL_WEB_RE.search(line) and self.USER_INTENT_RE.search(line):
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:external_access_requires_user_intent",
                    weights={"is_external_access": 1.0, "has_user_intent": -1.0},
                    bound=0.5,
                    description="External web access must have trusted user intent.",
                    repair_hint="Ask the user to confirm the external link or avoid opening it.",
                    gates=(CompactGate({"is_external_access": 1.0}),),
                    source="compact_nl_template:external_web",
                )
            )
        if self.STATE_RE.search(line):
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:record_write_requires_state_read",
                    weights={"is_existing_record_write": 1.0, "has_state_read": -1.0},
                    bound=0.5,
                    description="Existing-record writes must be preceded by trusted state evidence.",
                    repair_hint="Read or verify the current state before mutating this record.",
                    gates=(CompactGate({"is_existing_record_write": 1.0}),),
                    source="compact_nl_template:state",
                )
            )
        if self.IDENTITY_RE.search(line):
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:account_action_requires_identity",
                    weights={"is_account_action": 1.0, "has_identity": -1.0},
                    bound=0.5,
                    description="Customer/account-specific actions require identity verification.",
                    repair_hint="Verify the user's identity before using account-specific tools.",
                    gates=(CompactGate({"is_account_action": 1.0}),),
                    source="compact_nl_template:identity",
                )
            )
        if self.NUMERIC_RE.search(line):
            out.append(
                CompactHalfspaceConstraint(
                    id=f"{prefix}:amount_within_limit",
                    weights={"amount_norm": 1.0, "limit_norm": -1.0},
                    bound=0.0,
                    description="Action amount must stay inside the observed numeric limit.",
                    repair_hint="Use an amount not exceeding the trusted limit, paid amount, or available balance.",
                    gates=(CompactGate({"amount_known": 1.0}),),
                    required_features=("limit_known",),
                    source="compact_nl_template:numeric_limit",
                )
            )
        return tuple(out)


@dataclass
class CompactHalfspacePolicy:
    constraints: tuple[CompactHalfspaceConstraint, ...]
    encoder: CompactFeatureEncoder = field(default_factory=CompactFeatureEncoder)
    unsupported_lines: tuple[str, ...] = ()
    compiled_lines: tuple[str, ...] = ()
    violation_tolerance: float = 1e-9

    @classmethod
    def from_constraints(
        cls,
        constraints: Sequence[NaturalLanguageConstraint | str],
        *,
        encoder: CompactFeatureEncoder | None = None,
    ) -> "CompactHalfspacePolicy":
        compiled = CompactTemplatePolicyCompiler().compile(constraints)
        return cls(
            compiled.constraints,
            encoder=encoder or CompactFeatureEncoder(),
            unsupported_lines=compiled.unsupported_lines,
            compiled_lines=compiled.compiled_lines,
        )

    @property
    def schema(self) -> CompactFeatureSchema:
        return self.encoder.schema

    def active_constraints(self, vector: np.ndarray) -> tuple[CompactHalfspaceConstraint, ...]:
        return tuple(constraint for constraint in self.constraints if constraint.applies(vector, self.schema))

    def project_features(self, vector: np.ndarray, active_constraints: Sequence[CompactHalfspaceConstraint]) -> np.ndarray:
        projected = vector.astype(float).copy()
        for _ in range(32):
            changed = False
            for constraint in active_constraints:
                if not constraint.hard:
                    continue
                normal = constraint.normal(self.schema)
                violation = float(normal @ projected - constraint.bound)
                if violation <= self.violation_tolerance:
                    continue
                norm_sq = float(normal @ normal)
                if norm_sq <= 1e-12:
                    continue
                projected = projected - (violation / norm_sq) * normal
                changed = True
            if not changed:
                break
        return projected

    def evaluate(self, action: ToolAction, utility: float = 0.0, margin_weight: float = 0.4) -> ActionEvaluation:
        vector = self.encoder.encode(action)
        features = self.schema.to_dict(vector)
        active = self.active_constraints(vector)
        margins = tuple(constraint.margin(vector, self.schema) for constraint in active)
        violated = tuple(m.constraint_id for m in margins if not m.soft and m.slack < -self.violation_tolerance)
        missing: list[str] = []
        for constraint in active:
            for name in constraint.missing_required_features(vector, self.schema):
                missing.append(f"{constraint.id}:{name}")
        missing_evidence = tuple(dict.fromkeys(missing))
        min_margin = min((m.normalized_margin for m in margins), default=1.0)
        projected = self.project_features(vector, active)
        delta = projected - vector
        projection_distance = float(math.sqrt(max(0.0, float(delta @ delta))))
        repair_hints = tuple(dict.fromkeys(m.repair_hint for m in margins if m.slack < 0.0 or m.constraint_id in violated))

        if missing_evidence:
            decision = ShieldDecision.ABSTAIN
        elif violated:
            decision = ShieldDecision.BLOCK
        elif features.get("is_repair_action", 0.0) > 0.5:
            decision = ShieldDecision.REPAIR_ACTION
        else:
            decision = ShieldDecision.ALLOW

        violation_penalty = sum(max(0.0, -m.normalized_margin) * max(m.severity, 0.05) for m in margins)
        missing_penalty = 0.25 * len(missing_evidence)
        score_margin = min_margin if min_margin != float("inf") else 1.0
        score = (
            float(utility)
            + float(margin_weight) * max(score_margin, -1.0)
            - violation_penalty
            - missing_penalty
            - 0.1 * projection_distance
        )
        projection = ProjectionCertificate(
            original_margin=float(min_margin),
            projected_margin=min((constraint.margin(projected, self.schema).normalized_margin for constraint in active), default=1.0),
            distance=projection_distance,
            feasible=not violated and not missing_evidence,
            active_constraints=tuple(dict.fromkeys(m.constraint_id for m in margins)),
            violated_facets=violated,
            projected_features=self.schema.to_dict(projected),
        )
        certificate = ConstraintCertificate(
            decision=decision,
            min_margin=float(min_margin),
            certificate_margin=float(min_margin if not violated and not missing_evidence else min(min_margin, -1.0)),
            active_constraints=tuple(dict.fromkeys(m.constraint_id for m in margins)),
            violated_facets=violated,
            missing_evidence=missing_evidence,
            hard_failures=violated,
            projection=projection,
        )
        return ActionEvaluation(
            action=action,
            feasible=decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION},
            margin=float(min_margin),
            score=float(score),
            utility=float(utility),
            margins=margins,
            feature_values=features,
            decision=decision,
            abstain_reason="missing_required_feature" if missing_evidence else "",
            repair_hints=repair_hints,
            hard_verifier_results=(),
            certificate=certificate,
            projection=projection,
        )

    def select(
        self,
        actions: Sequence[ToolAction],
        utility_fn: UtilityFn | None = None,
        margin_weight: float = 0.4,
    ) -> SelectionResult:
        utility_fn = utility_fn or (lambda action: 0.0)
        action_tuple = tuple(actions)
        order = {id(action): idx for idx, action in enumerate(action_tuple)}
        use_margin_tiebreak = abs(float(margin_weight)) > 1e-12
        evaluations = tuple(self.evaluate(action, utility_fn(action), margin_weight=margin_weight) for action in action_tuple)

        def order_index(evaluation: ActionEvaluation) -> int:
            return order.get(id(evaluation.action), 0)

        def rank_key(evaluation: ActionEvaluation) -> tuple[int, float, float, float, int]:
            decision_rank = {
                ShieldDecision.ALLOW: 3,
                ShieldDecision.REPAIR_ACTION: 2,
                ShieldDecision.ABSTAIN: 1,
                ShieldDecision.BLOCK: 0,
            }[evaluation.decision]
            margin_key = evaluation.margin if use_margin_tiebreak else 0.0
            return (decision_rank, evaluation.score, margin_key, evaluation.utility, -order_index(evaluation))

        ranked = tuple(sorted(evaluations, key=rank_key, reverse=True))
        feasible = tuple(ev for ev in ranked if ev.decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION})
        rejected = tuple(ev for ev in ranked if ev.decision in {ShieldDecision.ABSTAIN, ShieldDecision.BLOCK})
        selected = feasible[0] if feasible else None
        utility_baseline = max(evaluations, key=lambda ev: (ev.utility, -order_index(ev)), default=None)
        selection_certificate = {
            "selected_action_id": selected.action.id if selected else "",
            "selected_decision": selected.decision.value if selected else "",
            "selected_margin": selected.margin if selected else 0.0,
            "selected_certificate_margin": selected.certificate.certificate_margin if selected and selected.certificate else 0.0,
            "selected_projection_distance": selected.projection.distance if selected and selected.projection else 0.0,
            "utility_baseline_action_id": utility_baseline.action.id if utility_baseline else "",
            "utility_baseline_decision": utility_baseline.decision.value if utility_baseline else "",
            "utility_baseline_margin": utility_baseline.margin if utility_baseline else 0.0,
            "utility_baseline_certificate_margin": (
                utility_baseline.certificate.certificate_margin if utility_baseline and utility_baseline.certificate else 0.0
            ),
            "utility_baseline_projection_distance": (
                utility_baseline.projection.distance if utility_baseline and utility_baseline.projection else 0.0
            ),
            "selection_changed_by_constraints": bool(selected and utility_baseline and selected.action.id != utility_baseline.action.id),
            "projection_changed_tool_action": bool(
                selected
                and utility_baseline
                and selected.action.id != utility_baseline.action.id
                and utility_baseline.projection
                and utility_baseline.projection.distance > 1e-9
            ),
            "compiled_policy_lines": self.compiled_lines,
            "unsupported_policy_lines": self.unsupported_lines,
            "active_constraints": tuple(dict.fromkeys(cid for ev in evaluations for cid in (m.constraint_id for m in ev.margins))),
        }
        return SelectionResult(
            selected=selected,
            feasible=feasible,
            rejected=rejected,
            ranked=ranked,
            status="OK" if selected and selected.decision == ShieldDecision.ALLOW else "REPAIR_ACTION" if selected else "NO_ALLOW_ACTION",
            selection_certificate=selection_certificate,
        )

    def repair_candidates(
        self,
        actions: Sequence[ToolAction],
        *,
        base_utility: float = 0.7,
    ) -> tuple[ToolAction, ...]:
        repairs: list[ToolAction] = []
        seen: set[tuple[str, str]] = set()
        for action in actions:
            evaluation = self.evaluate(action, utility=base_utility)
            for margin in evaluation.margins:
                if margin.slack >= 0.0:
                    continue
                repair = self._repair_for(action, margin.constraint_id)
                key = (repair.tool_name, flatten_value(repair.arguments))
                if key in seen:
                    continue
                seen.add(key)
                repairs.append(repair)
        return tuple(repairs)

    def _repair_for(self, action: ToolAction, constraint_id: str) -> ToolAction:
        if "confirmation" in constraint_id:
            return ToolAction(
                id=f"{action.id}:compact_repair_confirm",
                tool_name="send_message",
                action_text="Ask the user to confirm the exact tool action before proceeding.",
                arguments={"to": "user", "target_action": action.tool_name},
            )
        if "state_read" in constraint_id or "record_write" in constraint_id:
            return ToolAction(
                id=f"{action.id}:compact_repair_read_state",
                tool_name="read_state",
                action_text="Read current state before mutating the record.",
                arguments={"id": action.arguments.get("id") or action.arguments.get("order_id") or action.arguments.get("account_id")},
            )
        if "private" in constraint_id:
            args = dict(action.arguments)
            for key in list(args):
                if any(token in str(key).lower() for token in ("phone", "email", "account", "token", "password", "contact")):
                    args[key] = "[REDACTED]"
            args["redacted"] = True
            return ToolAction(
                id=f"{action.id}:compact_repair_redact",
                tool_name="redact_sensitive_info",
                action_text="Redact sensitive fields before continuing.",
                arguments=args,
                raw={"evidence": {"redacted": True}},
            )
        if "authorization" in constraint_id or "financial" in constraint_id:
            return ToolAction(
                id=f"{action.id}:compact_repair_authorize",
                tool_name="transfer_to_human_agent",
                action_text="Request trusted authorization before the sensitive or financial action.",
                arguments={"target_action": action.tool_name},
            )
        if "external_access" in constraint_id:
            return ToolAction(
                id=f"{action.id}:compact_repair_user_intent",
                tool_name="send_message",
                action_text="Ask whether the user wants to open this external link.",
                arguments={"to": "user", "url": action.arguments.get("url") or action.arguments.get("link")},
            )
        if "amount_within_limit" in constraint_id:
            state = _as_mapping(action.raw.get("state"))
            args = dict(action.arguments)
            limit = state.get("paid_amount") or state.get("max_amount") or args.get("paid_amount") or args.get("max_amount")
            if limit is not None:
                for key in _AMOUNT_KEYS:
                    if key in args:
                        args[key] = limit
                        break
                return replace(action, id=f"{action.id}:compact_repair_amount", arguments=args)
            return ToolAction(
                id=f"{action.id}:compact_repair_limit_lookup",
                tool_name="read_state",
                action_text="Read trusted numeric limit before executing amount-sensitive tool call.",
                arguments={"target_action": action.tool_name},
            )
        return ToolAction(
            id=f"{action.id}:compact_repair_human",
            tool_name="transfer_to_human_agent",
            action_text="Escalate unsafe or unsupported action for review.",
            arguments={"target_action": action.tool_name},
        )
