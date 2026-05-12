"""Fast T0 preview rendering."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from emma_mokuhanga.config import BuildDefaults
from emma_mokuhanga.contracts import MaskRole, MaskSpec, PrintPlan, RenderArtifact, RenderTier
from emma_mokuhanga.paths import ensure_session

ROLE_ALPHA = {
    MaskRole.BASE_WASH: 0.22,
    MaskRole.SUPPORT: 0.28,
    MaskRole.VISIBLE_COLOR: 0.42,
    MaskRole.ACCENT: 0.56,
    MaskRole.KEY: 0.62,
    MaskRole.CORRECTION: 0.38,
}


def _mask_array(mask: MaskSpec, height: int, width: int) -> np.ndarray:
    left, top, right, bottom = mask.bbox_norm
    x0, x1 = int(left * width), max(int(right * width), int(left * width) + 1)
    y0, y1 = int(top * height), max(int(bottom * height), int(top * height) + 1)
    arr = np.zeros((height, width), dtype=np.float32)
    if mask.shape == "full":
        arr[:, :] = 1.0
    elif mask.shape in {"rect", "band", "tile"}:
        arr[y0:y1, x0:x1] = 1.0
    elif mask.shape == "ellipse":
        yy, xx = np.ogrid[:height, :width]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = max(1.0, (x1 - x0) / 2), max(1.0, (y1 - y0) / 2)
        arr[(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) <= 1.0] = 1.0
    return arr


def _blend(base: np.ndarray, color: tuple[int, int, int], alpha: np.ndarray) -> np.ndarray:
    color_arr = np.asarray(color, dtype=np.float32) / 255.0
    alpha = alpha[..., None]
    return (base * (1.0 - alpha)) + (color_arr * alpha)


def render_plan_t0(
    plan: PrintPlan,
    session_id: str | None = None,
    home: Path | None = None,
    width: int = 384,
) -> RenderArtifact:
    aspect = plan.cnc_profile.print_height_mm / plan.cnc_profile.print_width_mm
    height = max(1, int(round(width * aspect)))
    sid, root = ensure_session(session_id=session_id, home=home)
    out_dir = root / "renders" / plan.plan_id / "t0"
    out_dir.mkdir(parents=True, exist_ok=True)

    paper = np.asarray(BuildDefaults().paper_color_rgb, dtype=np.float32) / 255.0
    canvas = np.zeros((height, width, 3), dtype=np.float32)
    canvas[:, :] = paper

    masks_by_id = {mask.mask_id: mask for mask in plan.masks}
    cumulative_paths: list[Path] = []
    warnings: list[str] = []
    for impression in sorted(plan.impressions, key=lambda item: item.order):
        for zone in impression.color_zones:
            mask = masks_by_id[zone.mask_id]
            role_alpha = ROLE_ALPHA[zone.role]
            alpha = _mask_array(mask, height, width) * role_alpha * zone.recipe.load
            canvas = _blend(canvas, zone.recipe.estimated_rgb, alpha)
        frame = np.clip(np.round(canvas * 255.0), 0, 255).astype(np.uint8)
        frame_path = out_dir / f"{impression.order:03d}_{impression.block_id}.png"
        Image.fromarray(frame, "RGB").save(frame_path)
        cumulative_paths.append(frame_path)

    composite_path = out_dir / "composite.png"
    Image.fromarray(np.clip(np.round(canvas * 255.0), 0, 255).astype(np.uint8), "RGB").save(
        composite_path
    )
    if len(plan.impressions) > 20:
        warnings.append("t0_preview_many_layers_no_physical_color_claim")
    return RenderArtifact(
        plan_id=plan.plan_id,
        tier=RenderTier.T0,
        width=width,
        height=height,
        composite_path=composite_path,
        cumulative_paths=cumulative_paths,
        warnings=warnings,
    )

