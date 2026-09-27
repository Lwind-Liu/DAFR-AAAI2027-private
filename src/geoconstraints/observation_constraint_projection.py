"""Provenance-typed observation projection for dynamic constraint state.

This module is part of the DSFR state-space definition.  It maps public tool
observations into two coupled views:

* a factual view returned to the agent, where explicit untrusted instruction
  spans cannot act as control text; and
* non-authorizing risk events consumed by the dynamic feasible region.

The projection never selects, rewrites, repairs, or executes an action.  Tool
results can contribute factual or risk evidence, but they cannot create user
intent, confirmation, or authorization.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any


OBSERVATION_CONSTRAINT_PROJECTION_VERSION = (
    "dsfr-provenance-observation-constraint-projection-v1"
)

INFORMATION_BLOCK_RE = re.compile(
    r"<INFORMATION>.*?</INFORMATION>", re.IGNORECASE | re.DOTALL
)
PROMPT_INJECTION_MARKER_RE = re.compile(
    r"<information>|hidden instruction|ignore (?:the )?(?:previous|above|system|developer)|"
    r"before you can solve|do the following first|after you do that|signed,\s*[a-z]|"
    r"override (?:the )?(?:policy|instruction)|bypass (?:the )?(?:policy|instruction)",
    re.IGNORECASE,
)
FOLLOWING_INJECTION_RE = re.compile(
    r"\b(hidden instruction|let me first follow|first handle that|first do that|"
    r"follow that before|important note from|important message from)\b",
    re.IGNORECASE,
)
TRAILING_TOOL_INSTRUCTION_RE = re.compile(
    r"(?:^|(?<=[.!?]))\s*"
    r"(?:"
    r"(?:now|next|then|also|first|before\s+continuing|before\s+proceeding)\b"
    r".{0,160}\b(?:you|assistant|agent)\b"
    r".{0,160}\b(?:need|must|should|have\s+to|(?:is|are)\s+required|"
    r"(?:is|are)\s+instructed|(?:is|are)\s+asked)\b"
    r"|(?:new|next|following|additional|separate)\s+"
    r"(?:request|instruction|task|action|command)\b"
    r"|(?:please\s+)?(?:send|email|forward|post|share|transfer|pay|delete|remove|"
    r"update|modify|change|set|reset|adjust|create|book|reserve|purchase|invite|"
    r"visit|open|submit)\b.{0,160}\b(?:external|account|recipient|password|"
    r"credential|secret|token|private|bank|file|document|calendar|booking|"
    r"reservation|url|http|www|@)\b"
    r").*$",
    re.IGNORECASE | re.DOTALL,
)
UNTRUSTED_CONTROL_LINE_RE = re.compile(
    r"ignore (?:the )?(?:previous|above|system|developer|user)|"
    r"before you can solve|do the following first|after you do that|"
    r"(?:now|next|then|also|first|before\s+continuing|before\s+proceeding)\b"
    r".{0,120}\b(?:you|assistant|agent)\b"
    r".{0,120}\b(?:need|must|should|have\s+to|(?:is|are)\s+required|"
    r"(?:is|are)\s+instructed|(?:is|are)\s+asked)\b|"
    r"(?:new|next|following|additional|separate)\s+"
    r"(?:request|instruction|task|action|command)|"
    r"override (?:the )?(?:policy|instruction)|bypass (?:the )?(?:policy|instruction)|"
    r"\b(?:fill|infer|guess|complete)\b.{0,80}\b(?:without asking|do not ask|don't ask|"
    r"underspecified)\b|"
    r"\bthis is an important message\b|^\s*signed,?\s*$|\bthanks!?\b|\bthank you\b",
    re.IGNORECASE,
)
UNTRUSTED_SIDE_EFFECT_COMMAND_RE = re.compile(
    r"\b(?:send|email|forward|post|share|transfer|pay|delete|remove|update|modify|"
    r"change|set|reset|adjust|create|book|reserve|purchase|invite|visit|open|submit)\b",
    re.IGNORECASE,
)
SECURITY_CRITICAL_OBJECT_RE = re.compile(
    r"\b(?:attacker|external(?:ly)?|outside|iban|account|recipient|receiver|destination|"
    r"transaction|payment|private|secret|password|credential|token|otp|security code|"
    r"message history|transaction history|phone|address|email|bank|passport|ssn|file|"
    r"document|repository|repo|calendar|event|booking|reservation)\b|"
    r"https?://|www\.|[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}",
    re.IGNORECASE,
)

def _is_untrusted_control_line(line: str) -> bool:
    """Return true for non-authorizing commands embedded in an untrusted block.

    The predicate is intentionally expressed over generic action semantics:
    command-like side-effect verbs plus security-critical objects or sinks.
    It must not depend on benchmark-specific account numbers, passwords, or
    task identifiers.
    """

    text = str(line or "").strip()
    if not text:
        return False
    if (
        PROMPT_INJECTION_MARKER_RE.search(text)
        or FOLLOWING_INJECTION_RE.search(text)
        or UNTRUSTED_CONTROL_LINE_RE.search(text)
    ):
        return True
    return bool(
        UNTRUSTED_SIDE_EFFECT_COMMAND_RE.search(text)
        and SECURITY_CRITICAL_OBJECT_RE.search(text)
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _state_hash(
    *,
    raw_sha256: str,
    visible_sha256: str,
    block_sha256s: Sequence[str],
    opaque_aliases: Sequence[str],
) -> str:
    return _stable_hash(
        {
            "schema": OBSERVATION_CONSTRAINT_PROJECTION_VERSION,
            "raw_sha256": raw_sha256,
            "visible_sha256": visible_sha256,
            "untrusted_block_sha256s": list(block_sha256s),
            "opaque_aliases": list(sorted(opaque_aliases)),
            "authority_delta": 0.0,
        }
    )


@dataclass(frozen=True, slots=True)
class ObservationConstraintProjectionArtifact:
    """One deterministic observation-to-constraint-state transition."""

    visible_text: str
    untrusted_blocks: tuple[str, ...]
    changed: bool
    raw_sha256: str
    visible_sha256: str
    constraint_state_sha256: str
    opaque_aliases: tuple[str, ...] = ()

    @property
    def canonical_record(self) -> dict[str, Any]:
        return {
            "schema": OBSERVATION_CONSTRAINT_PROJECTION_VERSION,
            "changed": self.changed,
            "raw_sha256": self.raw_sha256,
            "visible_sha256": self.visible_sha256,
            "constraint_state_sha256": self.constraint_state_sha256,
            "untrusted_block_count": len(self.untrusted_blocks),
            "untrusted_block_sha256s": [
                _sha256_text(item) for item in self.untrusted_blocks
            ],
            "opaque_aliases": list(self.opaque_aliases),
            "authority_delta": 0.0,
            "action_projection_or_repair": False,
        }

    @property
    def constraint_events(self) -> tuple[dict[str, Any], ...]:
        """Risk-only events; the projection cannot mint authorization."""

        return ProvenanceTypedObservationProjector.risk_constraint_events(
            self.untrusted_blocks,
            constraint_state_sha256=self.constraint_state_sha256,
        )


@dataclass(frozen=True, slots=True)
class ProvenanceTypedObservationProjector:
    """Constitutive map from tool observations to DSFR constraint state."""

    @property
    def version(self) -> str:
        return OBSERVATION_CONSTRAINT_PROJECTION_VERSION

    @staticmethod
    def risk_constraint_events(
        blocks: Sequence[str],
        *,
        constraint_state_sha256: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        unique_blocks = tuple(dict.fromkeys(str(item) for item in blocks if item))
        state_sha256 = constraint_state_sha256 or _stable_hash(
            {
                "schema": OBSERVATION_CONSTRAINT_PROJECTION_VERSION,
                "untrusted_block_sha256s": [
                    _sha256_text(item) for item in unique_blocks
                ],
                "authority_delta": 0.0,
            }
        )
        return tuple(
            {
                "text": block,
                "channel": "TOOL_RESULT",
                "kind": "PROMPT_INJECTION",
                "metadata": {
                    "observation_constraint_projection": True,
                    "projection_version": (
                        OBSERVATION_CONSTRAINT_PROJECTION_VERSION
                    ),
                    "can_authorize": False,
                    "constraint_state_sha256": state_sha256,
                },
            }
            for block in unique_blocks
        )

    @staticmethod
    def extract_untrusted_instruction_blocks(text: str) -> tuple[str, ...]:
        blocks = [
            block
            for block in (
                match.group(0) for match in INFORMATION_BLOCK_RE.finditer(text)
            )
            if PROMPT_INJECTION_MARKER_RE.search(block)
            or FOLLOWING_INJECTION_RE.search(block)
        ]
        blocks.extend(match.group(0).strip() for match in TRAILING_TOOL_INSTRUCTION_RE.finditer(text))
        return tuple(dict.fromkeys(block for block in blocks if block))

    @staticmethod
    def sanitize_untrusted_instruction_blocks(text: str) -> tuple[str, bool]:
        changed = False

        def replace_block(match: re.Match[str]) -> str:
            nonlocal changed
            block = match.group(0)
            if PROMPT_INJECTION_MARKER_RE.search(
                block
            ) or FOLLOWING_INJECTION_RE.search(block):
                changed = True
                inner = re.sub(r"</?INFORMATION>", "", block, flags=re.IGNORECASE)
                kept_lines = [
                    line.rstrip()
                    for line in inner.splitlines()
                    if line.strip()
                    and not _is_untrusted_control_line(line)
                ]
                if not kept_lines:
                    return "[removed untrusted block]"
                return "\n".join([*kept_lines, "[removed untrusted instructions]"])
            return block

        projected = INFORMATION_BLOCK_RE.sub(replace_block, text)

        def replace_trailing_instruction(match: re.Match[str]) -> str:
            nonlocal changed
            changed = True
            leading = "\n" if match.group(0).startswith("\n") else " "
            return f"{leading}[removed untrusted instructions]"

        projected = TRAILING_TOOL_INSTRUCTION_RE.sub(
            replace_trailing_instruction,
            projected,
        )
        return projected, changed

    @staticmethod
    def opaque_state_alias(raw_value: str) -> str:
        visible = raw_value.split("<INFORMATION>", 1)[0]
        visible = re.sub(r"[^a-zA-Z0-9_.-]+", "_", visible).strip("_.-")
        visible = visible[:36] or "state"
        return f"{visible}__geo_ref_{_stable_hash(raw_value)[:10]}"

    def bindings_from_tool_result(
        self,
        tool_name: str,
        result: Any,
    ) -> dict[str, str]:
        del tool_name
        if not isinstance(result, (list, tuple, set)):
            return {}
        bindings: dict[str, str] = {}
        for value in result:
            if not isinstance(value, str):
                continue
            if not self.extract_untrusted_instruction_blocks(value):
                continue
            bindings[self.opaque_state_alias(value)] = value
        return bindings

    def project(
        self,
        text: str,
        opaque_bindings: Mapping[str, str],
    ) -> ObservationConstraintProjectionArtifact:
        blocks = self.extract_untrusted_instruction_blocks(text)
        projected = text
        for alias, raw_value in sorted(
            opaque_bindings.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        ):
            projected = projected.replace(raw_value, alias)
        projected, sanitized = self.sanitize_untrusted_instruction_blocks(
            projected
        )
        unique_blocks = tuple(dict.fromkeys(blocks))
        aliases = tuple(
            sorted(
                alias
                for alias, raw_value in opaque_bindings.items()
                if raw_value in text
            )
        )
        raw_sha256 = _sha256_text(text)
        visible_sha256 = _sha256_text(projected)
        return ObservationConstraintProjectionArtifact(
            visible_text=projected,
            untrusted_blocks=unique_blocks,
            changed=bool(blocks or sanitized or projected != text),
            raw_sha256=raw_sha256,
            visible_sha256=visible_sha256,
            constraint_state_sha256=_state_hash(
                raw_sha256=raw_sha256,
                visible_sha256=visible_sha256,
                block_sha256s=tuple(
                    _sha256_text(item) for item in unique_blocks
                ),
                opaque_aliases=aliases,
            ),
            opaque_aliases=aliases,
        )

    @staticmethod
    def project_result_value(
        value: Any,
        opaque_bindings: Mapping[str, str],
    ) -> Any:
        aliases_by_raw = {
            raw_value: alias for alias, raw_value in opaque_bindings.items()
        }
        if isinstance(value, str):
            return aliases_by_raw.get(value, value)
        if isinstance(value, list):
            return [
                ProvenanceTypedObservationProjector.project_result_value(
                    item, opaque_bindings
                )
                for item in value
            ]
        if isinstance(value, tuple):
            return tuple(
                ProvenanceTypedObservationProjector.project_result_value(
                    item, opaque_bindings
                )
                for item in value
            )
        if isinstance(value, dict):
            return {
                ProvenanceTypedObservationProjector.project_result_value(
                    key, opaque_bindings
                ): ProvenanceTypedObservationProjector.project_result_value(
                    item, opaque_bindings
                )
                for key, item in value.items()
            }
        return value

    def resolve_arguments(
        self,
        arguments: Mapping[str, Any],
        opaque_bindings: Mapping[str, str],
    ) -> dict[str, Any]:
        aliases_by_lower = {
            alias.lower(): (alias, raw_value)
            for alias, raw_value in opaque_bindings.items()
        }

        def resolve(value: Any, *, allow_prefix: bool) -> Any:
            if isinstance(value, str):
                normalized = value.strip().strip("'\"")
                exact = aliases_by_lower.get(normalized.lower())
                if exact is not None:
                    return exact[1]
                if allow_prefix and len(normalized) >= 8:
                    matches = [
                        raw
                        for alias, raw in opaque_bindings.items()
                        if alias.lower().startswith(normalized.lower())
                    ]
                    if len(matches) == 1:
                        return matches[0]
                return value
            if isinstance(value, list):
                return [resolve(item, allow_prefix=False) for item in value]
            if isinstance(value, tuple):
                return tuple(
                    resolve(item, allow_prefix=False) for item in value
                )
            if isinstance(value, dict):
                return {
                    key: resolve(item, allow_prefix=False)
                    for key, item in value.items()
                }
            return value

        return {
            key: resolve(
                value,
                allow_prefix=True,
            )
            for key, value in arguments.items()
        }


DEFAULT_OBSERVATION_CONSTRAINT_PROJECTOR = ProvenanceTypedObservationProjector()


__all__ = [
    "DEFAULT_OBSERVATION_CONSTRAINT_PROJECTOR",
    "OBSERVATION_CONSTRAINT_PROJECTION_VERSION",
    "ObservationConstraintProjectionArtifact",
    "ProvenanceTypedObservationProjector",
]
