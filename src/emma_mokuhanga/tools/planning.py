"""Planning tool wrapper."""

from __future__ import annotations

from emma_mokuhanga.contracts import ImageAnalysis, PrintPlan
from emma_mokuhanga.planning.generator import generate_candidate_plan


def generate_plan(analysis: ImageAnalysis, target_block_count: int | None = None) -> PrintPlan:
    return generate_candidate_plan(analysis, target_block_count=target_block_count)

