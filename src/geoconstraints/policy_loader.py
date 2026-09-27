from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from geoconstraints.schemas import NaturalLanguageConstraint


HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^\s{0,6}[-*]\s+(.+?)\s*$")
ORDERED_BULLET_RE = re.compile(r"^\s{0,6}\d+[.)]\s+(.+?)\s*$")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
MARKDOWN_INLINE_RE = re.compile(r"[*_`]+")
ACTIONABLE_RE = re.compile(
    r"\b("
    r"must|should|shall|required|require|requires|need|needs|have to|has to|"
    r"can only|only|cannot|can't|do not|don't|never|deny|transfer|before|after|"
    r"at most|at least|no more than|without|unless|if and only if|if|"
    r"confirm|confirmation|authenticate|authorize|authorization|permission"
    r")\b",
    re.I,
)
CONTEXT_LEAD_IN_RE = re.compile(
    r"\b(?:if|when|otherwise|following|steps?|to do so|they should|can help)\b",
    re.I,
)
HARD_RULE_RE = re.compile(
    r"\b(?:do\s+not|don't|never|must\s+not|cannot|can't|not\s+allowed|forbidden|deny|"
    r"confirm|confirmation|authorize|authorization|permission)\b",
    re.I,
)
AGENT_OBLIGATION_RE = re.compile(
    r"\b(?:you|agent|assistant)\b.{0,80}\b(?:must|should|shall|required|requires?|need(?:s)?\s+to|"
    r"have\s+to|has\s+to|can\s+only|only\s+if|cannot|can't|do\s+not|don't|never|may\s+not)\b",
    re.I,
)
DESCRIPTIVE_STATE_RE = re.compile(
    r"^\s*(?:if|when)\b.{0,96}\b(?:status|state)\s+(?:is|=)\b.{0,192}\b"
    r"(?:has|have|available|unavailable|listed|taken|paid|closed|open|active|inactive)\b",
    re.I,
)
POST_ACTION_EFFECT_RE = re.compile(
    r"^\s*after\b.{0,120}\b(?:will|would|is|are)\s+(?:be\s+)?(?:updated|set|marked|changed|listed)\b",
    re.I,
)
USER_POST_ACTION_RE = re.compile(
    r"^\s*after\s+you\b.{0,120}\bthe\s+user\s+will\s+have\s+to\b",
    re.I,
)
WORKFLOW_LEAD_IN_RE = re.compile(
    r"\byou\s+can\s+help\b.{0,160}\b(?:to\s+do\s+so|follow\s+these\s+steps|following\s+steps)\b",
    re.I,
)


@dataclass(frozen=True)
class MarkdownPolicyItem:
    id: str
    text: str
    heading_path: tuple[str, ...]
    line_start: int


@dataclass(frozen=True)
class MarkdownPolicyFilterDiagnostic:
    id: str
    text: str
    heading_path: tuple[str, ...]
    line_start: int
    reason: str


def _clean_markdown(text: str) -> str:
    text = MARKDOWN_LINK_RE.sub(r"\1", text)
    text = MARKDOWN_INLINE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:48] or "policy"


def _is_context_lead_in(text: str) -> bool:
    return text.endswith(":") and bool(CONTEXT_LEAD_IN_RE.search(text)) and not bool(HARD_RULE_RE.search(text))


def non_constraint_filter_reason(text: str) -> str:
    if _is_context_lead_in(text):
        return "context_lead_in"
    if USER_POST_ACTION_RE.search(text) and not HARD_RULE_RE.search(text):
        return "user_post_action"
    if WORKFLOW_LEAD_IN_RE.search(text) and re.search(r"\bsteps?\s*:?\s*$", text, re.I) and not HARD_RULE_RE.search(text):
        return "workflow_lead_in"
    if HARD_RULE_RE.search(text) or AGENT_OBLIGATION_RE.search(text):
        return ""
    if DESCRIPTIVE_STATE_RE.search(text):
        return "descriptive_state_definition"
    if POST_ACTION_EFFECT_RE.search(text):
        return "post_action_effect"
    return ""


def _is_non_constraint_context(text: str) -> bool:
    return bool(non_constraint_filter_reason(text))


def iter_markdown_policy_items(
    text: str,
    *,
    source_id: str = "policy",
    actionable_only: bool = True,
    min_chars: int = 16,
) -> tuple[MarkdownPolicyItem, ...]:
    items, _ = _iter_markdown_policy_items_and_filters(
        text,
        source_id=source_id,
        actionable_only=actionable_only,
        min_chars=min_chars,
    )
    return items


def iter_markdown_policy_filter_diagnostics(
    text: str,
    *,
    source_id: str = "policy",
    actionable_only: bool = True,
    min_chars: int = 16,
) -> tuple[MarkdownPolicyFilterDiagnostic, ...]:
    _, diagnostics = _iter_markdown_policy_items_and_filters(
        text,
        source_id=source_id,
        actionable_only=actionable_only,
        min_chars=min_chars,
    )
    return diagnostics


def _iter_markdown_policy_items_and_filters(
    text: str,
    *,
    source_id: str,
    actionable_only: bool,
    min_chars: int,
) -> tuple[tuple[MarkdownPolicyItem, ...], tuple[MarkdownPolicyFilterDiagnostic, ...]]:
    items: list[MarkdownPolicyItem] = []
    diagnostics: list[MarkdownPolicyFilterDiagnostic] = []
    headings: list[str] = []
    current_text: list[str] = []
    current_heading: tuple[str, ...] = ()
    current_line = 0
    current_kind = ""

    def flush() -> None:
        nonlocal current_text, current_heading, current_line, current_kind
        if not current_text:
            return
        raw = " ".join(current_text)
        cleaned = _clean_markdown(raw)
        if len(cleaned) < min_chars:
            current_text = []
            current_heading = ()
            current_line = 0
            current_kind = ""
            return
        filter_reason = non_constraint_filter_reason(cleaned)
        if filter_reason:
            idx = len(diagnostics)
            diagnostics.append(
                MarkdownPolicyFilterDiagnostic(
                    id=f"{_slug(source_id)}_filtered_{idx:03d}",
                    text=cleaned,
                    heading_path=current_heading,
                    line_start=current_line,
                    reason=filter_reason,
                )
            )
        elif not actionable_only or ACTIONABLE_RE.search(cleaned):
            idx = len(items)
            items.append(
                MarkdownPolicyItem(
                    id=f"{_slug(source_id)}_{idx:03d}",
                    text=cleaned,
                    heading_path=current_heading,
                    line_start=current_line,
                )
            )
        current_text = []
        current_heading = ()
        current_line = 0
        current_kind = ""

    for line_no, line in enumerate(text.splitlines(), start=1):
        heading = HEADING_RE.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            headings = headings[: level - 1]
            headings.append(_clean_markdown(heading.group(2)))
            continue

        bullet = BULLET_RE.match(line) or ORDERED_BULLET_RE.match(line)
        if bullet:
            flush()
            current_text = [bullet.group(1)]
            current_heading = tuple(headings)
            current_line = line_no
            current_kind = "bullet"
            continue

        if current_text and line.strip() and current_kind == "bullet" and not line.lstrip().startswith("#"):
            current_text.append(line.strip())
        elif line.strip() and not line.lstrip().startswith("#"):
            if not current_text:
                current_text = [line.strip()]
                current_heading = tuple(headings)
                current_line = line_no
                current_kind = "paragraph"
            else:
                current_text.append(line.strip())
        elif not line.strip():
            flush()

    flush()
    return tuple(items), tuple(diagnostics)


def constraints_from_markdown(
    text: str,
    *,
    source_id: str = "policy",
    priority: float = 1.0,
    actionable_only: bool = True,
) -> tuple[NaturalLanguageConstraint, ...]:
    constraints: list[NaturalLanguageConstraint] = []
    for item in iter_markdown_policy_items(text, source_id=source_id, actionable_only=actionable_only):
        constraints.append(
            NaturalLanguageConstraint(
                id=item.id,
                text=item.text,
                priority=priority,
                metadata={
                    "source_id": source_id,
                    "heading_path": " > ".join(item.heading_path),
                    "line_start": item.line_start,
                },
            )
        )
    return tuple(constraints)


def constraints_from_markdown_file(
    path: str | Path,
    *,
    source_id: str | None = None,
    priority: float = 1.0,
    actionable_only: bool = True,
) -> tuple[NaturalLanguageConstraint, ...]:
    policy_path = Path(path)
    return constraints_from_markdown(
        policy_path.read_text(encoding="utf-8"),
        source_id=source_id or policy_path.stem,
        priority=priority,
        actionable_only=actionable_only,
    )
