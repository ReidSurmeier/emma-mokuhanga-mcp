"""Subject-agnostic first-pass print-plan generation."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np

from emma_mokuhanga.config import BuildDefaults
from emma_mokuhanga.contracts import (
    Block,
    CNCProfile,
    ColorZone,
    ImageAnalysis,
    Impression,
    MaskRole,
    MaskSpec,
    OpacityClass,
    PigmentComponent,
    PigmentProfile,
    PigmentRecipe,
    PlanScore,
    PrintPlan,
)
from emma_mokuhanga.paths import new_id
from emma_mokuhanga.pigments import list_pigments


@dataclass(frozen=True)
class _RoleSlot:
    role: MaskRole
    shape: str
    opacity: OpacityClass | None = None


ROLE_SEQUENCE: tuple[_RoleSlot, ...] = (
    _RoleSlot(MaskRole.BASE_WASH, "full", OpacityClass.TRANSPARENT),
    _RoleSlot(MaskRole.SUPPORT, "band", OpacityClass.TRANSPARENT),
    _RoleSlot(MaskRole.SUPPORT, "band", OpacityClass.SEMI_TRANSPARENT),
    _RoleSlot(MaskRole.BASE_WASH, "ellipse", OpacityClass.TRANSPARENT),
    _RoleSlot(MaskRole.SUPPORT, "rect", OpacityClass.SEMI_TRANSPARENT),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "tile", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "tile", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "tile", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "rect", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "ellipse", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "tile", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "tile", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "rect", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "ellipse", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "tile", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "tile", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "rect", None),
    _RoleSlot(MaskRole.VISIBLE_COLOR, "ellipse", None),
    _RoleSlot(MaskRole.ACCENT, "tile", OpacityClass.SEMI_OPAQUE),
    _RoleSlot(MaskRole.ACCENT, "rect", OpacityClass.SEMI_OPAQUE),
    _RoleSlot(MaskRole.ACCENT, "ellipse", OpacityClass.SEMI_OPAQUE),
    _RoleSlot(MaskRole.SUPPORT, "band", OpacityClass.SEMI_TRANSPARENT),
    _RoleSlot(MaskRole.CORRECTION, "rect", OpacityClass.SEMI_TRANSPARENT),
    _RoleSlot(MaskRole.KEY, "tile", OpacityClass.OPAQUE),
    _RoleSlot(MaskRole.KEY, "rect", OpacityClass.OPAQUE),
    _RoleSlot(MaskRole.CORRECTION, "ellipse", OpacityClass.SEMI_OPAQUE),
    _RoleSlot(MaskRole.KEY, "full", OpacityClass.OPAQUE),
)


def _nearest_pigment(rgb: tuple[int, int, int], pigments: list[PigmentProfile]) -> PigmentProfile:
    target = np.asarray(rgb, dtype=np.float64)
    best = min(
        pigments,
        key=lambda pigment: float(np.linalg.norm(target - np.asarray(pigment.masstone_rgb))),
    )
    return best


def _pigment_for_slot(
    slot: _RoleSlot,
    palette_rgb: tuple[int, int, int],
    pigments: list[PigmentProfile],
    order: int,
) -> PigmentProfile:
    by_id = {pigment.pigment_id: pigment for pigment in pigments}
    if slot.role == MaskRole.BASE_WASH:
        return by_id["ultramarine"] if order % 2 else by_id["yellow_ochre"]
    if slot.role == MaskRole.SUPPORT:
        return by_id[("viridian", "ultramarine", "burnt_sienna")[order % 3]]
    if slot.role == MaskRole.KEY:
        return by_id["sumi"]
    if slot.role == MaskRole.CORRECTION:
        return by_id[("raw_umber", "alizarin", "cad_yellow")[order % 3]]
    if slot.role == MaskRole.ACCENT:
        return by_id[("cad_red", "cad_yellow", "alizarin")[order % 3]]
    return _nearest_pigment(palette_rgb, pigments)


def _bbox_for(
    order: int,
    total: int,
    shape: str,
    grid: tuple[int, int],
) -> tuple[float, float, float, float]:
    if shape == "full":
        return (0.0, 0.0, 1.0, 1.0)
    if shape == "band":
        band = (order % 5) / 5
        if order % 2:
            return (0.0, max(0.0, band - 0.08), 1.0, min(1.0, band + 0.28))
        return (max(0.0, band - 0.08), 0.0, min(1.0, band + 0.28), 1.0)
    if shape == "ellipse":
        phase = order / max(1, total)
        cx = 0.25 + 0.5 * ((order * 0.37) % 1.0)
        cy = 0.25 + 0.5 * ((order * 0.53) % 1.0)
        radius = 0.22 + 0.12 * phase
        return (
            max(0.0, cx - radius),
            max(0.0, cy - radius),
            min(1.0, cx + radius),
            min(1.0, cy + radius),
        )
    if shape == "tile":
        cols, rows = grid
        col = (order * 3) % max(1, cols)
        row = (order * 5) % max(1, rows)
        w = min(0.42, 2.4 / max(1, cols))
        h = min(0.36, 2.8 / max(1, rows))
        left = min(0.92, col / max(1, cols))
        top = min(0.92, row / max(1, rows))
        return (left, top, min(1.0, left + w), min(1.0, top + h))
    offset = (order % 7) / 10
    return (offset, offset / 2, min(1.0, offset + 0.48), min(1.0, offset / 2 + 0.42))


def _recipe_for(
    pigment: PigmentProfile,
    slot: _RoleSlot,
    palette_rgb: tuple[int, int, int],
    order: int,
) -> PigmentRecipe:
    opacity = slot.opacity or pigment.opacity
    load = pigment.default_load
    if slot.role in {MaskRole.BASE_WASH, MaskRole.SUPPORT}:
        load *= 0.62
    if slot.role == MaskRole.KEY:
        load = min(0.9, load * 1.2)
    return PigmentRecipe(
        recipe_id=f"recipe_{order:02d}_{pigment.pigment_id}",
        name=f"{pigment.name} {slot.role.value.replace('_', ' ')}",
        components=[PigmentComponent(pigment_id=pigment.pigment_id, amount=1.0)],
        estimated_rgb=palette_rgb if slot.role == MaskRole.VISIBLE_COLOR else pigment.masstone_rgb,
        opacity=opacity,
        load=load,
        notes="Uncalibrated planning recipe; Mixbox/glaze T1 can refine later.",
    )


def generate_candidate_plan(
    analysis: ImageAnalysis,
    target_block_count: int | None = None,
    cnc_profile: CNCProfile | None = None,
) -> PrintPlan:
    defaults = BuildDefaults()
    target = target_block_count or defaults.target_block_count
    target = max(defaults.min_block_count, min(defaults.max_block_count, target))
    pigments = list_pigments()
    palette = analysis.palette or []
    palette_rgbs = [cluster.rgb for cluster in palette] or [(160, 120, 90)]

    masks: list[MaskSpec] = []
    impressions: list[Impression] = []
    blocks: list[Block] = []

    role_slots = list(ROLE_SEQUENCE)
    if target != len(role_slots):
        if target < len(role_slots):
            role_slots = role_slots[:target]
        else:
            role_slots.extend([ROLE_SEQUENCE[-1]] * (target - len(role_slots)))

    for idx, slot in enumerate(role_slots, start=1):
        palette_rgb = palette_rgbs[(idx - 1) % len(palette_rgbs)]
        pigment = _pigment_for_slot(slot, palette_rgb, pigments, idx)
        zone_count = 2 if idx % 5 == 0 and defaults.allow_multi_zone_blocks else 1
        color_zones: list[ColorZone] = []
        color_zone_ids: list[str] = []
        for zone_idx in range(zone_count):
            mask_id = f"mask_{idx:02d}_{zone_idx + 1}"
            bbox = _bbox_for(idx + zone_idx, target, slot.shape, analysis.suggested_grid)
            confidence = 0.55 + min(0.35, sqrt(max(0.0, analysis.complexity_score)) * 0.25)
            mask = MaskSpec(
                mask_id=mask_id,
                role=slot.role,
                shape=slot.shape,  # type: ignore[arg-type]
                bbox_norm=bbox,
                confidence=confidence,
            )
            masks.append(mask)
            recipe = _recipe_for(pigment, slot, palette_rgb, idx)
            zone_id = f"zone_{idx:02d}_{zone_idx + 1}"
            color_zones.append(
                ColorZone(
                    zone_id=zone_id,
                    mask_id=mask_id,
                    recipe=recipe,
                    role=slot.role,
                    application_notes=f"{slot.role.value}; one-pull block zone.",
                )
            )
            color_zone_ids.append(zone_id)

        impression_id = f"impression_{idx:02d}"
        block_id = f"block_{idx:02d}"
        impressions.append(
            Impression(
                impression_id=impression_id,
                block_id=block_id,
                order=idx,
                role=slot.role,
                color_zones=color_zones,
                notes="Generated by first-pass subject-agnostic Emma-style grammar.",
            )
        )
        blocks.append(
            Block(
                block_id=block_id,
                impression_id=impression_id,
                color_zone_ids=color_zone_ids,
            )
        )

    distance = abs(target - defaults.target_block_count)
    block_fit = max(0.0, 1.0 - (distance / defaults.target_block_count))
    return PrintPlan(
        plan_id=new_id("plan"),
        image_id=analysis.image_id,
        analysis_id=analysis.analysis_id,
        target_block_count=defaults.target_block_count,
        subject_agnostic=True,
        cnc_profile=cnc_profile or CNCProfile(),
        masks=masks,
        impressions=impressions,
        blocks=blocks,
        score=PlanScore(
            visual_similarity=0.0,
            emma_rhythm=0.72,
            block_count_fit=block_fit,
            process_risk=0.42,
            cnc_risk=0.5,
        ),
        warnings=[
            "uncalibrated_plan",
            "masks_are_planning_priors_not_final_cnc_vectors",
        ],
    )
