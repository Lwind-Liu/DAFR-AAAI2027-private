from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence


class ShieldDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ABSTAIN = "ABSTAIN"
    REPAIR_ACTION = "REPAIR_ACTION"


class CompileStatus(str, Enum):
    COMPILED = "COMPILED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICT = "CONFLICT"


class SourceChannel(str, Enum):
    SYSTEM_POLICY = "SYSTEM_POLICY"
    DEVELOPER_POLICY = "DEVELOPER_POLICY"
    POLICY_STORE = "POLICY_STORE"
    USER_DIRECTIVE = "USER_DIRECTIVE"
    AGENT_MEMORY = "AGENT_MEMORY"
    TOOL_RESULT = "TOOL_RESULT"
    RETRIEVED_DOC = "RETRIEVED_DOC"
    WEBPAGE = "WEBPAGE"
    EMAIL = "EMAIL"
    UNTRUSTED_TEXT = "UNTRUSTED_TEXT"


class TrustLevel(str, Enum):
    TRUSTED = "TRUSTED"
    STATE_TRUSTED = "STATE_TRUSTED"
    UNTRUSTED = "UNTRUSTED"


class PredicateKind(str, Enum):
    CONFIRMATION = "CONFIRMATION"
    AUTHORIZATION = "AUTHORIZATION"
    IDENTITY_VERIFICATION = "IDENTITY_VERIFICATION"
    MANAGER_APPROVAL = "MANAGER_APPROVAL"
    POLICY_LOOKUP = "POLICY_LOOKUP"
    STATE_READ = "STATE_READ"
    NUMERIC_LIMIT = "NUMERIC_LIMIT"
    SCOPE_MATCH = "SCOPE_MATCH"
    TEMPORAL_ORDER = "TEMPORAL_ORDER"
    SOURCE_GROUNDING = "SOURCE_GROUNDING"
    USER_INTENT = "USER_INTENT"
    PROMPT_INJECTION = "PROMPT_INJECTION"


@dataclass(frozen=True)
class NaturalLanguageConstraint:
    id: str
    text: str
    priority: float = 1.0
    positive_examples: tuple[str, ...] = ()
    negative_examples: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceEvent:
    text: str
    channel: SourceChannel = SourceChannel.USER_DIRECTIVE
    trust: TrustLevel | None = None
    kind: PredicateKind | None = None
    target: str | None = None
    actor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyPredicate:
    kind: PredicateKind
    required: bool = True
    target: str | None = None
    value: float | str | None = None
    source_channels: tuple[SourceChannel, ...] = ()


@dataclass(frozen=True)
class PolicyRule:
    id: str
    text: str
    predicates: tuple[PolicyPredicate, ...] = ()
    severity: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TriggerSpec:
    action_types: tuple[str, ...] = ()
    requires_side_effect: bool = False
    requires_write: bool = False
    privacy_disclosure: bool = False
    private_data_access: bool = False
    financial_action: bool = False
    external_web_access: bool = False
    existing_record_write: bool = False
    irreversible: bool = False
    scope_terms: tuple[str, ...] = ()
    broad_scope: bool = False


@dataclass(frozen=True)
class EvidenceSpec:
    confirmation_required: bool = False
    authorization_required: bool = False
    redaction_required: bool = False
    external_disclosure_forbidden: bool = False
    identity_required: bool = False
    source_grounding_required: bool = False
    user_intent_required: bool = False
    policy_required: bool = False
    state_read_required: bool = False
    manager_approval_required: bool = False
    required_arguments: tuple[str, ...] = ()
    confirmation_scope: str | None = None


@dataclass(frozen=True)
class NumericLimit:
    argument: str = "amount"
    operator: str = "<="
    value: float | None = None
    approval_evidence: str = "manager"


@dataclass(frozen=True)
class CountLimit:
    item: str
    max_count: int
    argument: str | None = None


@dataclass(frozen=True)
class StateRequirement:
    field: str
    operator: str = "checked"
    values: tuple[str, ...] = ()
    evidence_required: bool = True


@dataclass(frozen=True)
class ForbiddenAction:
    verb: str
    object_terms: tuple[str, ...] = ()
    condition_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemporalSpec:
    require_read_before_write: bool = False
    require_confirmation_before_action: bool = False


@dataclass(frozen=True)
class ConstraintClause:
    id: str
    text: str
    trigger: TriggerSpec = field(default_factory=TriggerSpec)
    required_evidence: EvidenceSpec = field(default_factory=EvidenceSpec)
    forbidden_effects: tuple[str, ...] = ()
    forbidden_actions: tuple[ForbiddenAction, ...] = ()
    numeric_limit: NumericLimit | None = None
    count_limits: tuple[CountLimit, ...] = ()
    state_requirements: tuple[StateRequirement, ...] = ()
    temporal_order: TemporalSpec = field(default_factory=TemporalSpec)
    exceptions: tuple[str, ...] = ()
    severity: float = 1.0
    verifier_required: bool = False
    parse_confidence: float = 1.0
    unsupported_reasons: tuple[str, ...] = ()
    source_constraint: NaturalLanguageConstraint | None = None


@dataclass(frozen=True)
class GeoConstraint:
    id: str
    scope: tuple[str, ...] = ()
    trigger: TriggerSpec = field(default_factory=TriggerSpec)
    requirement: tuple[str, ...] = ()
    evidence: EvidenceSpec = field(default_factory=EvidenceSpec)
    exceptions: tuple[str, ...] = ()
    projection_ops: tuple[str, ...] = ()
    metric: str = "min_signed_margin"
    severity: float = 1.0


@dataclass(frozen=True)
class ConstraintCompileCertificate:
    constraint_id: str
    status: CompileStatus
    parse_confidence: float
    unsupported_reasons: tuple[str, ...] = ()
    normal_form: GeoConstraint | None = None
    halfspace_ids: tuple[str, ...] = ()
    verifier_required: bool = False
    abstain_reason: str = ""

    @property
    def should_abstain(self) -> bool:
        return self.status in {CompileStatus.AMBIGUOUS, CompileStatus.UNSUPPORTED, CompileStatus.CONFLICT}


@dataclass(frozen=True)
class CompiledConstraint:
    clause: ConstraintClause
    halfspaces: tuple[Any, ...]
    normal_form: GeoConstraint | None = None
    compile_certificate: ConstraintCompileCertificate | None = None


@dataclass(frozen=True)
class ToolAction:
    id: str
    tool_name: str
    action_text: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    context_text: str = ""
    history: Sequence[Mapping[str, Any] | str] = ()
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def semantic_text(self) -> str:
        arg_text = " ".join(f"{key}={value}" for key, value in sorted(self.arguments.items()))
        history_text = " ".join(str(item) for item in self.history[-6:])
        return " ".join(
            part
            for part in (
                self.tool_name,
                self.action_text,
                arg_text,
                self.context_text[-1600:],
                history_text[-1600:],
            )
            if part
        )


@dataclass(frozen=True)
class ConstraintMargin:
    constraint_id: str
    value: float
    bound: float
    slack: float
    normalized_margin: float
    description: str
    repair_hint: str
    severity: float = 1.0
    soft: bool = False
    source: str = "compiled"


@dataclass(frozen=True)
class HardVerifierResult:
    constraint_id: str
    passed: bool
    severity: float
    reason: str
    repair_hint: str


@dataclass(frozen=True)
class ProjectionCertificate:
    original_margin: float
    projected_margin: float
    distance: float
    feasible: bool
    active_constraints: tuple[str, ...] = ()
    violated_facets: tuple[str, ...] = ()
    projected_features: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstraintCertificate:
    decision: ShieldDecision
    min_margin: float
    certificate_margin: float
    active_constraints: tuple[str, ...] = ()
    violated_facets: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    hard_failures: tuple[str, ...] = ()
    projection: ProjectionCertificate | None = None
    uncertainty: float = 0.0


@dataclass(frozen=True)
class ActionEvaluation:
    action: ToolAction
    feasible: bool
    margin: float
    score: float
    utility: float
    margins: tuple[ConstraintMargin, ...]
    feature_values: Mapping[str, float]
    decision: ShieldDecision = ShieldDecision.ALLOW
    abstain_reason: str = ""
    repair_hints: tuple[str, ...] = ()
    hard_verifier_results: tuple[HardVerifierResult, ...] = ()
    certificate: ConstraintCertificate | None = None
    projection: ProjectionCertificate | None = None

    @property
    def violations(self) -> tuple[ConstraintMargin, ...]:
        return tuple(item for item in self.margins if item.slack < 0.0)


@dataclass(frozen=True)
class SelectionResult:
    selected: ActionEvaluation | None
    feasible: tuple[ActionEvaluation, ...]
    rejected: tuple[ActionEvaluation, ...]
    ranked: tuple[ActionEvaluation, ...]
    status: str
    selection_certificate: Mapping[str, object] = field(default_factory=dict)


UtilityFn = Callable[[ToolAction], float]
