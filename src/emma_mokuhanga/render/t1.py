"""Uncalibrated T1 plausibility renderer.

T1 uses a deliberately simple split:

- premix happens inside a recipe,
- optical-density glazing happens between pulls.

This is not calibrated pigment prediction. It is a process-aware preview tier that can
be replaced by swatch-calibrated T2 later.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from emma_mokuhanga.config import BuildDefaults
from emma_mokuhanga.contracts import (
    MaskRole,
    MaskSpec,
    OpacityClass,
    PigmentRecipe,
    PrintPlan,
    RenderArtifact,
    RenderTier,
)
from emma_mokuhanga.paths import ensure_session
from emma_mokuhanga.render.t0 import _mask_array

OPACITY_STRENGTH = {
    OpacityClass.TRANSPARENT: 0.32,
    OpacityClass.SEMI_TRANSPARENT: 0.48,
    OpacityClass.SEMI_OPAQUE: 0.68,
    OpacityClass.OPAQUE: 0.86,
}

ROLE_LOAD_FACTOR = {
    MaskRole.BASE_WASH: 0.68,
    MaskRole.SUPPORT: 0.76,
    MaskRole.VISIBLE_COLOR: 0.9,
    MaskRole.ACCENT: 1.0,
    MaskRole.KEY: 1.0,
    MaskRole.CORRECTION: 0.86,
}


def premix_recipe_rgb(recipe: PigmentRecipe) -> np.ndarray:
    """Return the current premixed recipe estimate as 0..1 RGB.

    This function is the future Mixbox adapter seam. It currently trusts the recipe's
    uncalibrated `estimated_rgb` so the planner and renderer can be tested independently.
    """

    return np.asarray(recipe.estimated_rgb, dtype=np.float32) / 255.0


def glaze_over(under_rgb: np.ndarray, pigment_rgb: np.ndarray, strength: np.ndarray) -> np.ndarray:
    """Apply an optical-density style glaze over an existing RGB image."""

    under = np.clip(under_rgb, 1e-4, 1.0)
    pigment = np.clip(pigment_rgb, 1e-4, 1.0)
    strength = np.clip(strength, 0.0, 1.0)[..., None]
    return np.exp((1.0 - strength) * np.log(under) + strength * np.log(pigment))


def _layer_strength(
    mask: MaskSpec,
    recipe: PigmentRecipe,
    role: MaskRole,
    height: int,
    width: int,
) -> np.ndarray:
    base = _mask_array(mask, height, width)
    opacity = OPACITY_STRENGTH[recipe.opacity]
    role_factor = ROLE_LOAD_FACTOR[role]
    return base * opacity * role_factor * recipe.load


def render_plan_t1(
    plan: PrintPlan,
    session_id: str | None = None,
    home: Path | None = None,
    width: int = 384,
) -> RenderArtifact:
    aspect = plan.cnc_profile.print_height_mm / plan.cnc_profile.print_width_mm
    height = max(1, int(round(width * aspect)))
    sid, root = ensure_session(session_id=session_id, home=home)
    out_dir = root / "renders" / plan.plan_id / "t1"
    out_dir.mkdir(parents=True, exist_ok=True)

    paper = np.asarray(BuildDefaults().paper_color_rgb, dtype=np.float32) / 255.0
    canvas = np.zeros((height, width, 3), dtype=np.float32)
    canvas[:, :] = paper

    masks_by_id = {mask.mask_id: mask for mask in plan.masks}
    cumulative_paths: list[Path] = []
    translucent_layers = 0
    warnings = ["t1_uncalibrated_glaze_estimate"]

    for impression in sorted(plan.impressions, key=lambda item: item.order):
        for zone in impression.color_zones:
            mask = masks_by_id[zone.mask_id]
            pigment_rgb = premix_recipe_rgb(zone.recipe)
            strength = _layer_strength(mask, zone.recipe, zone.role, height, width)
            if zone.recipe.opacity in {OpacityClass.TRANSPARENT, OpacityClass.SEMI_TRANSPARENT}:
                translucent_layers += 1
            canvas = glaze_over(canvas, pigment_rgb, strength)
        frame = np.clip(np.round(canvas * 255.0), 0, 255).astype(np.uint8)
        frame_path = out_dir / f"{impression.order:03d}_{impression.block_id}.png"
        Image.fromarray(frame, "RGB").save(frame_path)
        cumulative_paths.append(frame_path)

    if translucent_layers >= 8:
        warnings.append("deep_translucent_stack_requires_calibration")

    composite_path = out_dir / "composite.png"
    Image.fromarray(np.clip(np.round(canvas * 255.0), 0, 255).astype(np.uint8), "RGB").save(
        composite_path
    )
    return RenderArtifact(
        plan_id=plan.plan_id,
        tier=RenderTier.T1,
        width=width,
        height=height,
        composite_path=composite_path,
        cumulative_paths=cumulative_paths,
        warnings=warnings,
    )
