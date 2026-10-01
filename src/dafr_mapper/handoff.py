from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from clafr.policy_ir import ConstraintIR
from clafr.policy_mapper import parse_mapper_response


@dataclass(frozen=True, slots=True)
class MapperContext:
    """Trusted context used to construct a region, independent of a candidate call."""

    tool_name: str
    fields: tuple[str, ...]
    effect_class: str | None
    field_descriptions: Mapping[str, str]
    policy: str

    def canonical(self) -> str:
        return json.dumps({
            "tool_name": self.tool_name,
            "fields": list(self.fields),
            "effect_class": self.effect_class,
            "field_descriptions": dict(sorted(self.field_descriptions.items())),
            "policy": self.policy,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class MapperOutput:
    ir: ConstraintIR
    action_point: tuple[float, ...]
    region_fingerprint: str
    candidate_independent: bool = True


class HandoffMapper:
    """Executable pilot of the handoff interface.

    The deterministic hash embedding is only a stable interface probe. It is
    intentionally not called a learned encoder; replacing it with a trained
    encoder does not change the checker or evaluation contract.
    """

    def encode_context(self, context: MapperContext, dimensions: int = 32) -> tuple[float, ...]:
        digest = hashlib.sha256(context.canonical().encode("utf-8")).digest()
        values = []
        for i in range(dimensions):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2.0 - 1.0)
        return tuple(values)

    def region(self, context: MapperContext) -> tuple[str, tuple[float, ...]]:
        point = self.encode_context(context)
        return hashlib.sha256(context.canonical().encode("utf-8")).hexdigest(), point

    def map_response(self, response: str, context: MapperContext) -> MapperOutput:
        ir = parse_mapper_response(
            response,
            context.tool_name,
            context.fields,
            field_descriptions=context.field_descriptions,
            effect_class=context.effect_class,
        )
        fingerprint, point = self.region(context)
        return MapperOutput(ir=ir, action_point=point, region_fingerprint=fingerprint)

    @staticmethod
    def check_region_membership(output: MapperOutput, *, margin: float = 0.0) -> bool:
        """Finite pilot check: a valid mapped IR is inside the executable region.

        The actual DAFR constraints remain the authoritative runtime checker;
        this method only verifies the handoff object is structurally complete.
        """
        return bool(output.candidate_independent and output.ir.tool_name and len(output.action_point) > 0 and margin >= 0.0)
