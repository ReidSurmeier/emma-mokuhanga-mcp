from __future__ import annotations

from pathlib import Path

from emma_mokuhanga.tools.analysis import analyze_reference
from emma_mokuhanga.tools.ingest import ingest_image
from emma_mokuhanga.tools.planning import generate_plan


def test_generate_plan_near_27_one_pull_blocks(emma_image: Path, tmp_path: Path) -> None:
    reference = ingest_image(emma_image, home=tmp_path)
    analysis = analyze_reference(reference)
    plan = generate_plan(analysis)
    assert len(plan.impressions) == 27
    assert len(plan.blocks) == 27
    assert plan.subject_agnostic is True
    assert len({block.block_id for block in plan.blocks}) == 27
    assert len({block.impression_id for block in plan.blocks}) == 27
    assert any(len(impression.color_zones) > 1 for impression in plan.impressions)
    assert {"uncalibrated_plan", "masks_are_planning_priors_not_final_cnc_vectors"}.issubset(
        set(plan.warnings)
    )


def test_generate_plan_clamps_to_soft_budget(frankenthaler_image: Path, tmp_path: Path) -> None:
    reference = ingest_image(frankenthaler_image, home=tmp_path)
    analysis = analyze_reference(reference)
    plan = generate_plan(analysis, target_block_count=80)
    assert 24 <= len(plan.impressions) <= 32

