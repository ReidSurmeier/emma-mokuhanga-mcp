"""Render tool wrapper."""

from __future__ import annotations

from pathlib import Path

from emma_mokuhanga.contracts import PrintPlan, RenderArtifact
from emma_mokuhanga.render.t0 import render_plan_t0
from emma_mokuhanga.render.t1 import render_plan_t1


def render_plan(
    plan: PrintPlan,
    tier: str = "t0",
    session_id: str | None = None,
    home: Path | None = None,
) -> RenderArtifact:
    if tier == "t0":
        return render_plan_t0(plan, session_id=session_id, home=home)
    if tier == "t1":
        return render_plan_t1(plan, session_id=session_id, home=home)
    raise NotImplementedError("only T0 and T1 render tiers are implemented")
