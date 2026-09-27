from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .schemas import RuntimeEvidence, ToolAction


_ORDINAL_TOKEN_RE = re.compile(r"\b(?P<number>\d+)(?P<suffix>st|nd|rd|th)\b", re.IGNORECASE)
_ORDINAL_TEMPLATE_RE = re.compile(
    r"(?:\b(?:k|rank|position|place)\b|\{(?:k|rank|position|place)\})\s*-\s*th\b",
    re.IGNORECASE,
)
_TRUSTED_STRUCTURED_VALUE_RE = re.compile(
    r"\b(?:new\s+)?(?P<label>[a-z][a-z0-9_ -]{2,40})\s*:\s*"
    r"(?P<value>[^.\n]+?)(?=\s+\band\b|[.;\n]|$)",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_WEAK_CONTEXT_TERMS = {
    "a",
    "an",
    "and",
    "as",
    "be",
    "being",
    "for",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "user",
    "users",
    "where",
    "with",
}


@dataclass(frozen=True, slots=True)
class FormatProjection:
    action: ToolAction
    changed: bool
    changes: tuple[Mapping[str, str], ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class _OrdinalTemplate:
    left_terms: tuple[str, ...]
    right_terms: tuple[str, ...]


def project_action_format(action: ToolAction, evidence: RuntimeEvidence) -> FormatProjection:
    """Project low-level argument formatting back to explicit trusted templates.

    This is not an attack classifier. It only uses the trusted task text to find
    literal output-format templates, edits top-level string arguments, and then
    returns a normal ToolAction that must still be selected by CLAFR.
    """

    structured_projection = _project_schema_guided_structured_split(action, evidence)
    if structured_projection is not None:
        return structured_projection

    templates = _trusted_ordinal_templates(evidence.trusted_task)
    if not templates:
        return FormatProjection(action=action, changed=False)

    projected_arguments: dict[str, Any] = {}
    changes: list[Mapping[str, str]] = []
    for key, value in dict(action.arguments).items():
        if isinstance(value, str) and _ORDINAL_TOKEN_RE.search(value) and _matches_ordinal_template(value, templates):
            projected_value = _project_ordinal_template(value)
            projected_arguments[key] = projected_value
            if projected_value != value:
                changes.append(
                    {
                        "argument": str(key),
                        "before": value,
                        "after": projected_value,
                        "projection": "trusted_ordinal_template",
                    }
                )
        else:
            projected_arguments[key] = value

    if not changes:
        return FormatProjection(action=action, changed=False)

    projected_action = ToolAction(
        id=action.id,
        tool_name=action.tool_name,
        arguments=projected_arguments,
        rationale=action.rationale,
        utility_hint=action.utility_hint,
    )
    return FormatProjection(
        action=projected_action,
        changed=True,
        changes=tuple(changes),
        reason="trusted_ordinal_template_projection",
    )


def _project_schema_guided_structured_split(action: ToolAction, evidence: RuntimeEvidence) -> FormatProjection | None:
    trusted_values = _trusted_structured_values(evidence.trusted_task)
    if not trusted_values:
        return None
    required_keys = [
        key
        for key in evidence.required_args(action.tool_name)
        if key in action.arguments and isinstance(action.arguments.get(key), str)
    ]
    if len(required_keys) < 2:
        return None
    arguments = dict(action.arguments)
    for first_key, second_key in zip(required_keys, required_keys[1:]):
        first_value = str(arguments.get(first_key, "") or "").strip()
        second_value = str(arguments.get(second_key, "") or "").strip()
        if not first_value:
            continue
        for raw_value, parts in trusted_values:
            leading = parts[0]
            trailing = ", ".join(parts[1:])
            if _normalize_text(first_value) not in {
                _normalize_text(raw_value),
                _normalize_text(" ".join(parts)),
            }:
                continue
            if second_value and _normalize_text(second_value) not in _normalize_text(trailing):
                continue
            projected_arguments = dict(arguments)
            projected_arguments[first_key] = leading
            projected_arguments[second_key] = trailing
            if projected_arguments == arguments:
                continue
            projected_action = ToolAction(
                id=action.id,
                tool_name=action.tool_name,
                arguments=projected_arguments,
                rationale=action.rationale,
                utility_hint=action.utility_hint,
            )
            return FormatProjection(
                action=projected_action,
                changed=True,
                changes=(
                    {
                        "argument": f"{first_key}/{second_key}",
                        "before": f"{first_key}={first_value}; {second_key}={second_value}",
                        "after": f"{first_key}={leading}; {second_key}={trailing}",
                        "projection": "trusted_structured_schema_split",
                    },
                ),
                reason="trusted_structured_schema_split_projection",
            )
    return None


def _trusted_structured_values(trusted_task: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    values: list[tuple[str, tuple[str, ...]]] = []
    for match in _TRUSTED_STRUCTURED_VALUE_RE.finditer(trusted_task or ""):
        raw_value = match.group("value").strip()
        parts = tuple(part.strip() for part in raw_value.split(",") if part.strip())
        if len(parts) >= 2:
            values.append((raw_value, parts))
    return tuple(values)


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _trusted_ordinal_templates(trusted_task: str) -> tuple[_OrdinalTemplate, ...]:
    templates: list[_OrdinalTemplate] = []
    for match in _ORDINAL_TEMPLATE_RE.finditer(trusted_task or ""):
        left = _context_terms((trusted_task or "")[max(0, match.start() - 96) : match.start()])
        right = _context_terms((trusted_task or "")[match.end() : match.end() + 96])
        templates.append(_OrdinalTemplate(left_terms=left[-5:], right_terms=right[:5]))
    return tuple(templates)


def _context_terms(text: str) -> tuple[str, ...]:
    terms = []
    for term in _WORD_RE.findall(text.lower()):
        if len(term) < 3 or term in _WEAK_CONTEXT_TERMS:
            continue
        terms.append(term)
    return tuple(terms)


def _matches_ordinal_template(value: str, templates: tuple[_OrdinalTemplate, ...]) -> bool:
    value_terms = set(_context_terms(value))
    if not value_terms:
        return True
    for template in templates:
        left = set(template.left_terms)
        right = set(template.right_terms)
        if not left and not right:
            return True
        if len(value_terms & right) >= min(2, len(right)):
            return True
        if len(value_terms & left) >= min(2, len(left)):
            return True
    return False


def _project_ordinal_template(value: str) -> str:
    return _ORDINAL_TOKEN_RE.sub(lambda match: f"{match.group('number')}-th", value)
