from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping, Sequence

from geoconstraints.policy import SemanticGeoConstraintPolicy
from geoconstraints.schemas import ActionEvaluation, PredicateKind, SelectionResult, ShieldDecision, SourceChannel, ToolAction


TARGET_KEYS = ("target", "id", "record_id", "user_id", "account_id", "order_id", "reservation_id", "reminder_id")


@dataclass(frozen=True)
class AgentCandidateAction:
    id: str
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    action_text: str = ""
    context_text: str = ""
    history: Sequence[Mapping[str, Any] | str] = ()
    raw: Mapping[str, Any] = field(default_factory=dict)
    origin: str = "agent"
    utility: float = 1.0

    def to_tool_action(self) -> ToolAction:
        raw = dict(self.raw)
        raw.setdefault("agent_candidate_origin", self.origin)
        return ToolAction(
            id=self.id,
            tool_name=self.tool_name,
            action_text=self.action_text or f"Tool action {self.tool_name}",
            arguments=dict(self.arguments),
            context_text=self.context_text,
            history=tuple(self.history),
            raw=raw,
        )

    @classmethod
    def from_tool_action(
        cls,
        action: ToolAction,
        *,
        origin: str = "projection",
        utility: float = 0.7,
        raw: Mapping[str, Any] | None = None,
    ) -> "AgentCandidateAction":
        merged_raw = dict(action.raw)
        if raw:
            merged_raw.update(raw)
        return cls(
            id=action.id,
            tool_name=action.tool_name,
            arguments=action.arguments,
            action_text=action.action_text,
            context_text=action.context_text,
            history=action.history,
            raw=merged_raw,
            origin=origin,
            utility=utility,
        )


@dataclass(frozen=True)
class ShieldedToolSelection:
    original_calls: tuple[AgentCandidateAction, ...]
    candidate_calls: tuple[AgentCandidateAction, ...]
    selected_call: AgentCandidateAction | None
    selected_evaluation: ActionEvaluation | None
    selection_result: SelectionResult | None
    decision: ShieldDecision
    selection_certificate: Mapping[str, object] = field(default_factory=dict)
    action_changed_by_constraints: bool = False
    projection_changed_tool_action: bool = False
    utility_baseline_projection_distance: float = 0.0
    selected_certificate_margin: float = 0.0


@dataclass(frozen=True)
class RepairSimulation:
    original_action: ToolAction
    initial_evaluation: ActionEvaluation
    repair_actions: tuple[ToolAction, ...]
    retry_action: ToolAction | None
    retry_evaluation: ActionEvaluation | None
    terminal_evaluation: ActionEvaluation | None
    resolved_safely: bool


def _target(action: ToolAction) -> str:
    for key in TARGET_KEYS:
        if key in action.arguments:
            return str(action.arguments[key])
    return str(action.raw.get("target", "current_action"))


def _event(text: str, channel: SourceChannel, kind: PredicateKind, target: str) -> dict[str, str]:
    return {"text": text, "channel": channel.value, "kind": kind.value, "target": target}


def _coerce_arguments(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        for loader in (json.loads, ast.literal_eval):
            try:
                parsed = loader(stripped)
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue
            if isinstance(parsed, Mapping):
                return dict(parsed)
            return {"value": parsed}
        return {"value": value}
    return {"value": value}


def _mapping_get_any(mapping: Mapping[str, Any], names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return default


def _object_get_any(item: object, names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return default


def agent_candidate_from_python_call(
    source: str,
    *,
    default_id: str = "agent_call",
    context_text: str = "",
    history: Sequence[Mapping[str, Any] | str] = (),
    raw: Mapping[str, Any] | None = None,
    origin: str = "agent",
    utility: float = 1.0,
) -> AgentCandidateAction:
    tree = ast.parse(source.strip())
    if not tree.body or not isinstance(tree.body[0], ast.Expr) or not isinstance(tree.body[0].value, ast.Call):
        raise ValueError("Expected a single Python-style tool call expression.")
    call = tree.body[0].value
    if isinstance(call.func, ast.Name):
        tool_name = call.func.id
    elif isinstance(call.func, ast.Attribute):
        tool_name = call.func.attr
    else:
        raise ValueError("Expected a named Python-style tool call.")
    arguments: dict[str, Any] = {}
    for idx, arg in enumerate(call.args):
        try:
            arguments[f"arg{idx}"] = ast.literal_eval(arg)
        except (ValueError, SyntaxError):
            arguments[f"arg{idx}"] = ast.unparse(arg) if hasattr(ast, "unparse") else str(arg)
    for keyword in call.keywords:
        if keyword.arg is None:
            continue
        try:
            arguments[keyword.arg] = ast.literal_eval(keyword.value)
        except (ValueError, SyntaxError):
            arguments[keyword.arg] = ast.unparse(keyword.value) if hasattr(ast, "unparse") else str(keyword.value)
    return AgentCandidateAction(
        id=default_id,
        tool_name=tool_name,
        arguments=arguments,
        action_text=f"Tool action {tool_name}",
        context_text=context_text,
        history=tuple(history),
        raw=dict(raw or {}),
        origin=origin,
        utility=utility,
    )


def normalize_agent_tool_call(
    tool_call: AgentCandidateAction | Mapping[str, Any] | object,
    *,
    default_id: str = "agent_call",
    context_text: str = "",
    history: Sequence[Mapping[str, Any] | str] = (),
    raw: Mapping[str, Any] | None = None,
    origin: str = "agent",
    utility: float | None = None,
) -> AgentCandidateAction:
    if isinstance(tool_call, AgentCandidateAction):
        base = tool_call
        if utility is None and not context_text and not history and raw is None and origin == base.origin:
            return base
        merged_raw = dict(base.raw)
        if raw:
            merged_raw.update(raw)
        return replace(
            base,
            context_text=context_text or base.context_text,
            history=tuple(history) if history else base.history,
            raw=merged_raw,
            origin=origin,
            utility=base.utility if utility is None else float(utility),
        )
    if isinstance(tool_call, str):
        return agent_candidate_from_python_call(
            tool_call,
            default_id=default_id,
            context_text=context_text,
            history=history,
            raw=raw,
            origin=origin,
            utility=1.0 if utility is None else float(utility),
        )

    call_id = default_id
    tool_name: Any = None
    arguments: Any = None
    action_text = ""
    call_raw = dict(raw or {})

    if isinstance(tool_call, Mapping):
        call_raw.update(dict(tool_call))
        call_id = str(_mapping_get_any(tool_call, ("id", "tool_call_id", "call_id"), default_id))
        function = tool_call.get("function")
        if isinstance(function, Mapping):
            tool_name = _mapping_get_any(function, ("name", "function", "tool", "tool_name"))
            arguments = _mapping_get_any(function, ("arguments", "args", "kwargs", "parameters", "input"))
        elif function is not None and not isinstance(function, str):
            tool_name = _object_get_any(function, ("name", "function", "tool", "tool_name"))
            arguments = _object_get_any(function, ("arguments", "args", "kwargs", "parameters", "input"))
        else:
            tool_name = _mapping_get_any(tool_call, ("tool_name", "tool", "name", "function"))
            arguments = _mapping_get_any(tool_call, ("arguments", "args", "kwargs", "parameters", "input"))
        action_text = str(_mapping_get_any(tool_call, ("action_text", "description", "reasoning"), "") or "")
    else:
        call_id = str(_object_get_any(tool_call, ("id", "tool_call_id", "call_id"), default_id))
        function = _object_get_any(tool_call, ("function",), None)
        if isinstance(function, str):
            tool_name = function
            arguments = _object_get_any(tool_call, ("args", "arguments", "kwargs", "parameters", "input"), None)
        elif function is not None:
            tool_name = _object_get_any(function, ("name", "function", "tool", "tool_name"), None)
            arguments = _object_get_any(function, ("arguments", "args", "kwargs", "parameters", "input"), None)
        else:
            tool_name = _object_get_any(tool_call, ("tool_name", "tool", "name"), None)
            arguments = _object_get_any(tool_call, ("arguments", "args", "kwargs", "parameters", "input"), None)
        action_text = str(_object_get_any(tool_call, ("action_text", "description", "reasoning"), "") or "")
        call_raw.update({"source_type": type(tool_call).__name__})

    if not tool_name:
        raise ValueError(f"Could not normalize tool call {default_id}: missing tool name.")

    return AgentCandidateAction(
        id=call_id,
        tool_name=str(tool_name),
        arguments=_coerce_arguments(arguments),
        action_text=action_text or f"Tool action {tool_name}",
        context_text=context_text,
        history=tuple(history),
        raw=call_raw,
        origin=origin,
        utility=1.0 if utility is None else float(utility),
    )


def _with_evidence(action: ToolAction, events: tuple[Mapping[str, str], ...]) -> ToolAction:
    raw = dict(action.raw)
    previous = raw.get("evidence_events", ())
    if isinstance(previous, Mapping) or isinstance(previous, str):
        previous_events = [previous]
    else:
        previous_events = list(previous)
    raw["evidence_events"] = tuple([*previous_events, *events])
    if any(event.get("kind") == PredicateKind.CONFIRMATION.value for event in events):
        raw["confirmation_scope"] = _target(action)
    return ToolAction(
        id=f"{action.id}:retry",
        tool_name=action.tool_name,
        action_text=action.action_text,
        arguments=action.arguments,
        context_text=action.context_text,
        history=(*action.history, *events),
        raw=raw,
    )


def _redacted_action(action: ToolAction) -> ToolAction:
    redacted_args = {
        key: "[REDACTED]" if any(token in str(key).lower() for token in ("phone", "email", "account", "token", "password", "contact")) else value
        for key, value in action.arguments.items()
    }
    return ToolAction(
        id=f"{action.id}:repair_redact",
        tool_name="redact_sensitive_info",
        action_text="Redact sensitive fields before continuing",
        arguments=redacted_args,
    )


def _human_action(action: ToolAction) -> ToolAction:
    return ToolAction(
        id=f"{action.id}:repair_human",
        tool_name="transfer_to_human_agent",
        action_text="Transfer this case to a human support agent for review",
    )


def _collect_required_fields_action(action: ToolAction, fields: tuple[str, ...]) -> ToolAction:
    readable = ", ".join(field.replace("_", " ") for field in fields)
    return ToolAction(
        id=f"{action.id}:repair_collect_required_fields",
        tool_name="send_message",
        action_text=f"Ask the user to provide required fields: {readable}",
        arguments={"to": "user", "fields": fields},
    )


def _identity_verification_action(action: ToolAction) -> ToolAction:
    return ToolAction(
        id=f"{action.id}:repair_verify_identity",
        tool_name="send_message",
        action_text="Ask the user to verify identity before continuing",
        arguments={"to": "user"},
    )


def _source_grounding_action(action: ToolAction) -> ToolAction:
    return ToolAction(
        id=f"{action.id}:repair_source_grounding",
        tool_name="lookup_policy",
        action_text="Lookup trusted policy or tool evidence before answering",
        arguments={"target": action.arguments.get("topic", action.arguments.get("id", action.id))},
    )


def _user_intent_action(action: ToolAction) -> ToolAction:
    return ToolAction(
        id=f"{action.id}:repair_user_intent",
        tool_name="send_message",
        action_text="Ask the user whether they want or accept this action before continuing",
        arguments={"to": "user"},
    )


def _dedupe_repair_actions(actions: list[ToolAction]) -> tuple[ToolAction, ...]:
    deduped: list[ToolAction] = []
    seen: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
    for action in actions:
        key = (
            action.tool_name,
            action.action_text,
            tuple(sorted((str(item_key), str(item_value)) for item_key, item_value in action.arguments.items())),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return tuple(deduped)


def _is_terminal_repair_action(action: ToolAction) -> bool:
    if ":repair_" in action.id or ":compact_repair_" in action.id:
        return True
    name = action.tool_name.lower()
    text = action.action_text.lower()
    if name in {
        "ask_user_confirmation",
        "inspect_tool_action_risk",
        "draft_safe_response",
        "read_state",
        "lookup_policy",
        "transfer_to_human_agent",
        "redact_sensitive_info",
    }:
        return True
    if name == "send_message" and str(action.arguments.get("to", "")).lower() == "user":
        return any(token in text for token in ("ask", "confirm", "verify", "provide", "authorize", "accept"))
    return False


def simulate_repair(policy: SemanticGeoConstraintPolicy, action: ToolAction) -> RepairSimulation:
    initial = policy.evaluate(action)
    if initial.decision == ShieldDecision.ALLOW or (
        initial.decision == ShieldDecision.REPAIR_ACTION and _is_terminal_repair_action(action)
    ):
        return RepairSimulation(
            original_action=action,
            initial_evaluation=initial,
            repair_actions=(),
            retry_action=None,
            retry_evaluation=None,
            terminal_evaluation=None,
            resolved_safely=initial.decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION},
        )

    features = initial.feature_values
    violated_constraints = {item.constraint_id for item in initial.violations}
    hard_reasons = {item.reason for item in initial.hard_verifier_results if not item.passed}
    target = _target(action)
    evidence_events: list[Mapping[str, str]] = []
    repair_actions: list[ToolAction] = []
    needs_privacy_redaction = any("privacy_disclosure_without_auth" in item for item in violated_constraints)
    needs_read_state = (
        any("existing_record_write_without_read" in item for item in violated_constraints)
        or "read_before_write_missing" in hard_reasons
        or "state_requirement_unknown" in hard_reasons
    )
    needs_confirmation = (
        any("irreversible_without_confirmation" in item for item in violated_constraints)
        or any("side_effect_without_confirmation" in item for item in violated_constraints)
        or "confirmation_missing" in hard_reasons
        or "confirmation_scope_mismatch" in hard_reasons
    )
    needs_financial_authorization = any("financial_action_without_auth" in item for item in violated_constraints)
    needs_private_data_authorization = any("private_data_access_without_auth" in item for item in violated_constraints)
    needs_identity_verification = "identity_verification_missing" in hard_reasons or "identity_verification_unknown" in hard_reasons
    needs_source_grounding = "source_grounding_missing" in hard_reasons or "source_grounding_unknown" in hard_reasons
    needs_user_intent = "user_intent_missing" in hard_reasons or "user_intent_unknown" in hard_reasons
    missing_required_fields = tuple(
        item.constraint_id.rsplit(":", 1)[-1]
        for item in initial.hard_verifier_results
        if not item.passed and item.reason in {"required_argument_missing", "required_argument_unknown"}
    )

    if "forbidden_action" in hard_reasons:
        repair = _human_action(action)
        terminal = policy.evaluate(repair)
        return RepairSimulation(
            original_action=action,
            initial_evaluation=initial,
            repair_actions=(repair,),
            retry_action=None,
            retry_evaluation=None,
            terminal_evaluation=terminal,
            resolved_safely=terminal.decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION},
        )

    if needs_privacy_redaction and features.get("privacy_disclosure_without_auth", 0.0) > 0.5:
        repair = _redacted_action(action)
        terminal = policy.evaluate(repair)
        return RepairSimulation(
            original_action=action,
            initial_evaluation=initial,
            repair_actions=(repair,),
            retry_action=None,
            retry_evaluation=None,
            terminal_evaluation=terminal,
            resolved_safely=terminal.decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION},
        )

    if needs_read_state:
        repair_actions.append(
            ToolAction(
                id=f"{action.id}:repair_read_state",
                tool_name="read_state",
                action_text="Read current state and lookup relevant policy",
                arguments={"id": target},
            )
        )
        evidence_events.append(
            _event(
                f"Read current state and policy for {target}.",
                SourceChannel.TOOL_RESULT,
                PredicateKind.STATE_READ,
                target,
            )
        )

    if needs_confirmation:
        repair_actions.append(
            ToolAction(
                id=f"{action.id}:repair_confirm",
                tool_name="send_message",
                action_text="Ask the user to confirm the exact action before continuing",
                arguments={"to": "user"},
            )
        )
        evidence_events.append(
            _event(
                f"The user confirmed the exact action for {target}.",
                SourceChannel.USER_DIRECTIVE,
                PredicateKind.CONFIRMATION,
                target,
            )
        )

    if "amount_over_limit_without_manager_approval" in hard_reasons:
        repair_actions.append(_human_action(action))
        evidence_events.append(
            _event(
                f"Manager approved this amount for {target}.",
                SourceChannel.POLICY_STORE,
                PredicateKind.MANAGER_APPROVAL,
                target,
            )
        )

    if needs_financial_authorization:
        repair_actions.append(_human_action(action))
        evidence_events.append(
            _event(
                f"Trusted authorization was obtained for the financial action on {target}.",
                SourceChannel.POLICY_STORE,
                PredicateKind.AUTHORIZATION,
                target,
            )
        )

    if needs_private_data_authorization:
        repair_actions.append(
            ToolAction(
                id=f"{action.id}:repair_private_access_auth",
                tool_name="send_message",
                action_text="Ask the user to verify identity and authorize private data access",
                arguments={"to": "user"},
            )
        )
        evidence_events.append(
            _event(
                f"The user verified identity and authorized private data access for {target}.",
                SourceChannel.USER_DIRECTIVE,
                PredicateKind.AUTHORIZATION,
                target,
            )
        )

    if needs_identity_verification:
        repair_actions.append(_identity_verification_action(action))
        evidence_events.append(
            _event(
                f"The user's identity was verified through a trusted channel for {target}.",
                SourceChannel.USER_DIRECTIVE,
                PredicateKind.IDENTITY_VERIFICATION,
                target,
            )
        )

    if needs_source_grounding:
        repair_actions.append(_source_grounding_action(action))
        evidence_events.append(
            _event(
                f"Trusted policy or tool evidence was retrieved for {target}.",
                SourceChannel.POLICY_STORE,
                PredicateKind.SOURCE_GROUNDING,
                target,
            )
        )

    if needs_user_intent:
        repair_actions.append(_user_intent_action(action))
        evidence_events.append(
            _event(
                f"The user requested and accepted this action for {target}.",
                SourceChannel.USER_DIRECTIVE,
                PredicateKind.USER_INTENT,
                target,
            )
        )

    unique_missing_required_fields = tuple(dict.fromkeys(missing_required_fields))
    if unique_missing_required_fields:
        repair_actions.append(_collect_required_fields_action(action, unique_missing_required_fields))
    for field in unique_missing_required_fields:
        evidence_events.append(
            _event(
                f"Collected required field {field.replace('_', ' ')} for {target}.",
                SourceChannel.USER_DIRECTIVE,
                PredicateKind.SCOPE_MATCH,
                target,
            )
        )

    if "amount_unknown" in hard_reasons:
        repair = _human_action(action)
        terminal = policy.evaluate(repair)
        return RepairSimulation(
            original_action=action,
            initial_evaluation=initial,
            repair_actions=(repair,),
            retry_action=None,
            retry_evaluation=None,
            terminal_evaluation=terminal,
            resolved_safely=terminal.decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION},
        )

    if not evidence_events:
        repair = _human_action(action)
        terminal = policy.evaluate(repair)
        return RepairSimulation(
            original_action=action,
            initial_evaluation=initial,
            repair_actions=(repair,),
            retry_action=None,
            retry_evaluation=None,
            terminal_evaluation=terminal,
            resolved_safely=terminal.decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION},
        )

    retry = _with_evidence(action, tuple(evidence_events))
    retry_evaluation = policy.evaluate(retry)
    if retry_evaluation.decision == ShieldDecision.ABSTAIN:
        repair_actions.append(_human_action(action))
        terminal = policy.evaluate(repair_actions[-1])
        return RepairSimulation(
            original_action=action,
            initial_evaluation=initial,
            repair_actions=_dedupe_repair_actions(repair_actions),
            retry_action=retry,
            retry_evaluation=retry_evaluation,
            terminal_evaluation=terminal,
            resolved_safely=terminal.decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION},
        )
    return RepairSimulation(
        original_action=action,
        initial_evaluation=initial,
        repair_actions=_dedupe_repair_actions(repair_actions),
        retry_action=retry,
        retry_evaluation=retry_evaluation,
        terminal_evaluation=None,
        resolved_safely=retry_evaluation.decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION},
    )


def _dedupe_agent_candidates(candidates: Sequence[AgentCandidateAction]) -> tuple[AgentCandidateAction, ...]:
    out: list[AgentCandidateAction] = []
    seen: dict[str, int] = {}
    for candidate in candidates:
        count = seen.get(candidate.id, 0)
        seen[candidate.id] = count + 1
        if count:
            candidate = replace(candidate, id=f"{candidate.id}#{count + 1}")
        out.append(candidate)
    return tuple(out)


def projection_repair_candidates(
    policy: SemanticGeoConstraintPolicy,
    original_calls: Sequence[AgentCandidateAction],
    *,
    base_utility: float = 0.7,
    available_tool_names: Sequence[str] | None = None,
    repair_action_mapper: Callable[[ToolAction], ToolAction | None] | None = None,
) -> tuple[AgentCandidateAction, ...]:
    projected: list[AgentCandidateAction] = []
    seen: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
    available = set(available_tool_names or ())
    for original in original_calls:
        original_action = original.to_tool_action()
        simulation = simulate_repair(policy, original_action)
        projection_distance = (
            simulation.initial_evaluation.projection.distance
            if simulation.initial_evaluation.projection is not None
            else 0.0
        )
        for repair_idx, repair_action in enumerate(simulation.repair_actions):
            if repair_action_mapper is not None:
                mapped = repair_action_mapper(repair_action)
                if mapped is None:
                    continue
                repair_action = mapped
            if available and repair_action.tool_name not in available:
                continue
            key = (
                repair_action.tool_name,
                repair_action.action_text,
                tuple(sorted((str(key), str(value)) for key, value in repair_action.arguments.items())),
            )
            if key in seen:
                continue
            seen.add(key)
            projected.append(
                AgentCandidateAction.from_tool_action(
                    repair_action,
                    origin="projection",
                    utility=max(0.05, base_utility - 0.05 * repair_idx),
                    raw={
                        "projected_from_action_id": original.id,
                        "projection_distance": projection_distance,
                    },
                )
            )
    return tuple(projected)


def select_shielded_tool_action(
    policy: SemanticGeoConstraintPolicy,
    tool_calls: Sequence[AgentCandidateAction | Mapping[str, Any] | object],
    *,
    context_text: str = "",
    history: Sequence[Mapping[str, Any] | str] = (),
    utility_fn: Callable[[AgentCandidateAction], float] | None = None,
    include_projection_candidates: bool = True,
    projection_utility: float = 0.7,
    margin_weight: float = 0.4,
    selection_strategy: str = "linear_score",
    utility_band_epsilon: float = 0.0,
    available_tool_names: Sequence[str] | None = None,
    repair_action_mapper: Callable[[ToolAction], ToolAction | None] | None = None,
) -> ShieldedToolSelection:
    original_calls = tuple(
        call
        if isinstance(call, AgentCandidateAction)
        else normalize_agent_tool_call(
            call,
            default_id=f"agent_call_{idx}",
            context_text=context_text,
            history=history,
            utility=None,
        )
        for idx, call in enumerate(tool_calls)
    )
    if utility_fn is not None:
        original_calls = tuple(replace(call, utility=float(utility_fn(call))) for call in original_calls)
    available = set(available_tool_names or ())
    if available:
        original_calls = tuple(call for call in original_calls if call.tool_name in available)
    original_calls = _dedupe_agent_candidates(original_calls)
    if not original_calls:
        return ShieldedToolSelection(
            original_calls=(),
            candidate_calls=(),
            selected_call=None,
            selected_evaluation=None,
            selection_result=None,
            decision=ShieldDecision.ABSTAIN,
        )

    projection_calls = (
        projection_repair_candidates(
            policy,
            original_calls,
            base_utility=projection_utility,
            available_tool_names=available_tool_names,
            repair_action_mapper=repair_action_mapper,
        )
        if include_projection_candidates
        else ()
    )
    candidate_calls = _dedupe_agent_candidates((*original_calls, *projection_calls))
    call_by_id = {call.id: call for call in candidate_calls}
    utilities = {call.id: float(call.utility) for call in candidate_calls}
    actions = tuple(call.to_tool_action() for call in candidate_calls)
    selection_result = policy.select(
        actions,
        utility_fn=lambda action: utilities.get(action.id, 0.0),
        margin_weight=margin_weight,
        selection_strategy=selection_strategy,
        utility_band_epsilon=utility_band_epsilon,
    )
    selected = selection_result.selected
    selected_call = call_by_id.get(selected.action.id) if selected is not None else None
    certificate = selection_result.selection_certificate
    selected_certificate_margin = float(certificate.get("selected_certificate_margin", 0.0) or 0.0)
    utility_baseline_projection_distance = float(
        certificate.get("utility_baseline_projection_distance", 0.0) or 0.0
    )
    return ShieldedToolSelection(
        original_calls=original_calls,
        candidate_calls=candidate_calls,
        selected_call=selected_call,
        selected_evaluation=selected,
        selection_result=selection_result,
        decision=selected.decision if selected is not None else ShieldDecision.ABSTAIN,
        selection_certificate=certificate,
        action_changed_by_constraints=bool(certificate.get("selection_changed_by_constraints", False)),
        projection_changed_tool_action=bool(certificate.get("projection_changed_tool_action", False)),
        utility_baseline_projection_distance=utility_baseline_projection_distance,
        selected_certificate_margin=selected_certificate_margin,
    )
