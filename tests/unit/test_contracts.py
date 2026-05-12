from __future__ import annotations

import pytest
from pydantic import ValidationError

from emma_mokuhanga.contracts import (
    Block,
    ColorZone,
    Impression,
    MaskRole,
    MaskSpec,
    OpacityClass,
    PigmentComponent,
    PigmentRecipe,
    PrintPlan,
)


def _recipe() -> PigmentRecipe:
    return PigmentRecipe(
        recipe_id="recipe_test",
        name="Test wash",
        components=[PigmentComponent(pigment_id="ultramarine", amount=1.0)],
        estimated_rgb=(40, 80, 160),
        opacity=OpacityClass.TRANSPARENT,
        load=0.4,
    )


def _zone(zone_id: str, mask_id: str) -> ColorZone:
    return ColorZone(
        zone_id=zone_id,
        mask_id=mask_id,
        recipe=_recipe(),
        role=MaskRole.SUPPORT,
    )


def test_multi_zone_one_pull_plan_is_valid() -> None:
    zones = [_zone("zone_1", "mask_1"), _zone("zone_2", "mask_2")]
    plan = PrintPlan(
        plan_id="plan_test",
        image_id="image_test",
        analysis_id="analysis_test",
        masks=[
            MaskSpec(
                mask_id="mask_1",
                role=MaskRole.SUPPORT,
                shape="rect",
                bbox_norm=(0, 0, 0.5, 1),
            ),
            MaskSpec(
                mask_id="mask_2",
                role=MaskRole.SUPPORT,
                shape="rect",
                bbox_norm=(0.5, 0, 1, 1),
            ),
        ],
        impressions=[
            Impression(
                impression_id="impression_1",
                block_id="block_1",
                order=1,
                role=MaskRole.SUPPORT,
                color_zones=zones,
            )
        ],
        blocks=[
            Block(
                block_id="block_1",
                impression_id="impression_1",
                color_zone_ids=["zone_1", "zone_2"],
            )
        ],
    )
    assert len(plan.blocks) == len(plan.impressions) == 1
    assert len(plan.impressions[0].color_zones) == 2


def test_duplicate_block_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="block_id values must be unique"):
        PrintPlan(
            plan_id="plan_test",
            image_id="image_test",
            analysis_id="analysis_test",
            masks=[
                MaskSpec(
                    mask_id="mask_1",
                    role=MaskRole.SUPPORT,
                    shape="rect",
                    bbox_norm=(0, 0, 1, 1),
                ),
                MaskSpec(
                    mask_id="mask_2",
                    role=MaskRole.SUPPORT,
                    shape="rect",
                    bbox_norm=(0, 0, 1, 1),
                ),
            ],
            impressions=[
                Impression(
                    impression_id="impression_1",
                    block_id="block_1",
                    order=1,
                    role=MaskRole.SUPPORT,
                    color_zones=[_zone("zone_1", "mask_1")],
                ),
                Impression(
                    impression_id="impression_2",
                    block_id="block_1",
                    order=2,
                    role=MaskRole.SUPPORT,
                    color_zones=[_zone("zone_2", "mask_2")],
                ),
            ],
            blocks=[
                Block(block_id="block_1", impression_id="impression_1", color_zone_ids=["zone_1"]),
                Block(block_id="block_1", impression_id="impression_2", color_zone_ids=["zone_2"]),
            ],
        )
