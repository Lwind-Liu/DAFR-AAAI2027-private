from __future__ import annotations

import re
from typing import Sequence

from .schemas import RuntimeEvidence, ToolAction


def _tokens(text: str) -> set[str]:
    return {item for item in re.findall(r"[a-zA-Z0-9_@.+:-]+", text.lower()) if len(item) > 2}


class HardVerifier:
    """A deliberately flat verifier baseline.

    This baseline checks a few binary predicates and then returns the first
    allowed action. It does not use confidence dimensions, directional
    competition, or joint-risk budgets.
    """

    def allowed(self, action: ToolAction, evidence: RuntimeEvidence) -> bool:
        text = action.text.lower()
        untrusted = evidence.untrusted_text
        side_effect = bool(re.search(r"send|post|update|delete|remove|transfer|pay|book|invite|create", action.tool_name, re.I))
        sensitive = bool(re.search(r"secret|password|token|security code|private|confidential|bank|balance", text, re.I))
        action_tokens = _tokens(action.text)
        untrusted_tokens = _tokens(untrusted)
        untrusted_overlap = bool(action_tokens and untrusted_tokens and action_tokens & untrusted_tokens)
        if untrusted_overlap and side_effect and sensitive:
            return False
        if sensitive and side_effect and not evidence.trusted_authorizations:
            return False
        return True

    def select(self, actions: Sequence[ToolAction], evidence: RuntimeEvidence) -> ToolAction | None:
        for action in actions:
            if self.allowed(action, evidence):
                return action
        return None
