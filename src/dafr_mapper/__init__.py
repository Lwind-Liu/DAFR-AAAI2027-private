"""Minimal executable pilot for the unified mapper handoff design.

This pilot deliberately keeps semantic extraction in the existing mapper while
making the execution representation and candidate-independent region explicit.
It is a compatibility layer for measurement, not evidence of a trained encoder.
"""

from .handoff import HandoffMapper, MapperContext, MapperOutput

__all__ = ["HandoffMapper", "MapperContext", "MapperOutput"]
