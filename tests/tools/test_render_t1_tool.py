from __future__ import annotations

from pathlib import Path

from emma_mokuhanga.tools.analysis import analyze_reference
from emma_mokuhanga.tools.ingest import ingest_image
from emma_mokuhanga.tools.planning import generate_plan
from emma_mokuhanga.tools.render import render_plan


def test_render_t1_outputs_uncalibrated_warnings(emma_image: Path, tmp_path: Path) -> None:
    reference = ingest_image(emma_image, home=tmp_path)
    analysis = analyze_reference(reference)
    plan = generate_plan(analysis)
    artifact = render_plan(plan, tier="t1", session_id=reference.session_id, home=tmp_path)
    assert artifact.composite_path.exists()
    assert len(artifact.cumulative_paths) == len(plan.impressions)
    assert artifact.tier == "t1"
    assert "t1_uncalibrated_glaze_estimate" in artifact.warnings
    assert "deep_translucent_stack_requires_calibration" in artifact.warnings

