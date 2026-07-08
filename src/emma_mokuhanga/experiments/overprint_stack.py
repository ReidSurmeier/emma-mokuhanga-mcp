"""Offline overprint-stack experiment harness.

This module intentionally stays outside MCP server wiring. It generates many
parameterized print-plan variants, renders compact previews in memory, scores them
against one input image, and writes repeatable logs plus contact sheets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image, ImageDraw

from emma_mokuhanga.config import BuildDefaults
from emma_mokuhanga.contracts import (
    Block,
    CNCProfile,
    ColorZone,
    ImageAnalysis,
    Impression,
    MaskRole,
    PrintPlan,
    ReferenceImage,
)
from emma_mokuhanga.image.analysis import analyze_reference
from emma_mokuhanga.planning.generator import generate_candidate_plan
from emma_mokuhanga.render.t0 import ROLE_ALPHA, _mask_array
from emma_mokuhanga.render.t1 import _layer_strength, glaze_over, premix_recipe_rgb

RenderTierName = Literal["t0", "t1"]
StackOrder = Literal["planner", "role_priority", "reverse"]
ExperimentStrategy = Literal["grammar", "field_stack", "residual_stack"]

REFERENCE_IMAGE_TARGETS = [
    "https://images.squarespace-cdn.com/content/v1/5434ff94e4b01cad832a72ab/"
    "1583879425912-WZ09K6DCQ5TJ5I1DDCYC/Woodblock-print-process.png?format=2500w"
]


@dataclass(frozen=True)
class HarnessConfig:
    input_path: Path
    out_dir: Path
    variants: int = 100
    seed: int = 20260512
    width: int = 256
    tier: RenderTierName = "t1"
    clusters: int = 8
    contact_sheet_cols: int = 5
    contact_sheet_rows: int = 4
    preview_quality: int = 90
    diagnostic_width: int | None = None
    preserve_source_aspect: bool = False
    diagnostic_original_size: bool = False
    strategy: ExperimentStrategy | None = None
    palette_size: int = 12
    include_image_palette: bool = False
    mask_smooth_scale: float = 1.0


@dataclass(frozen=True)
class VariantParams:
    variant_index: int
    variant_seed: int
    strategy: ExperimentStrategy
    target_block_count: int
    global_load_scale: float
    transparent_load_scale: float
    opaque_load_scale: float
    bbox_jitter: float
    bbox_scale: float
    color_jitter: float
    stack_order: StackOrder
    underlayer_strength: float
    residual_strength: float
    mask_quantile: float
    broad_smooth: int
    detail_smooth: int


ROLE_PRIORITY = {
    MaskRole.BASE_WASH: 0,
    MaskRole.SUPPORT: 1,
    MaskRole.VISIBLE_COLOR: 2,
    MaskRole.ACCENT: 3,
    MaskRole.CORRECTION: 4,
    MaskRole.KEY: 5,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_int(seed: int, index: int) -> int:
    digest = hashlib.sha256(f"{seed}:{index}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big", signed=False) & 0x7FFFFFFF


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _reference_for_path(path: Path) -> ReferenceImage:
    digest = _sha256(path)
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
        fmt = image.format
    image_id = f"image_{digest[:12]}"
    return ReferenceImage(
        image_id=image_id,
        session_id="offline_experiment",
        source_path=path,
        stored_path=path,
        preview_path=path,
        sha256=digest,
        width=width,
        height=height,
        mode=mode,
        format=fmt,
        profile_name=None,
    )


def _deterministic_analysis(reference: ReferenceImage, clusters: int) -> ImageAnalysis:
    analysis = analyze_reference(reference, clusters=clusters)
    return analysis.model_copy(
        update={"analysis_id": f"analysis_{reference.sha256[:12]}_{clusters}"}
    )


def _target_array(path: Path, size: tuple[int, int]) -> np.ndarray:
    with Image.open(path) as image:
        rgb = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    return np.asarray(rgb, dtype=np.float32)


def _source_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _render_size(width: int, cnc_profile: CNCProfile | None = None) -> tuple[int, int]:
    profile = cnc_profile or CNCProfile()
    aspect = profile.print_height_mm / profile.print_width_mm
    return width, max(1, int(round(width * aspect)))


def _source_aspect_size(path: Path, width: int) -> tuple[int, int]:
    source_width, source_height = _source_size(path)
    aspect = source_height / source_width
    return width, max(1, int(round(width * aspect)))


def _target_size(config: HarnessConfig, width: int) -> tuple[int, int]:
    if config.preserve_source_aspect:
        return _source_aspect_size(config.input_path, width)
    return _render_size(width)


def _diagnostic_size(config: HarnessConfig, reference: ReferenceImage) -> tuple[int, int]:
    if config.diagnostic_original_size:
        return reference.width, reference.height
    width = config.diagnostic_width or config.width
    return _target_size(config, width)


def _variant_params(
    index: int,
    seed: int,
    strategy_override: ExperimentStrategy | None = None,
) -> VariantParams:
    variant_seed = _stable_int(seed, index)
    rng = np.random.default_rng(variant_seed)
    order: StackOrder = rng.choice(["planner", "role_priority", "reverse"]).item()
    if strategy_override is None:
        strategy: ExperimentStrategy = rng.choice(
            ["grammar", "field_stack", "residual_stack"],
            p=[0.18, 0.36, 0.46],
        ).item()
    else:
        strategy = strategy_override
    return VariantParams(
        variant_index=index,
        variant_seed=variant_seed,
        strategy=strategy,
        target_block_count=int(rng.integers(24, 33)),
        global_load_scale=float(rng.uniform(0.76, 1.24)),
        transparent_load_scale=float(rng.uniform(0.82, 1.28)),
        opaque_load_scale=float(rng.uniform(0.84, 1.18)),
        bbox_jitter=float(rng.uniform(0.0, 0.055)),
        bbox_scale=float(rng.uniform(0.86, 1.16)),
        color_jitter=float(rng.uniform(0.0, 18.0)),
        stack_order=order,
        underlayer_strength=float(rng.uniform(0.16, 0.42)),
        residual_strength=float(rng.uniform(0.20, 0.58)),
        mask_quantile=float(rng.uniform(0.58, 0.86)),
        broad_smooth=int(rng.integers(10, 25)),
        detail_smooth=int(rng.integers(3, 10)),
    )


def _clamp_bbox(
    bbox: tuple[float, float, float, float],
    rng: np.random.Generator,
    jitter: float,
    scale: float,
) -> tuple[float, float, float, float]:
    left, top, right, bottom = bbox
    cx = (left + right) / 2.0 + float(rng.normal(0.0, jitter))
    cy = (top + bottom) / 2.0 + float(rng.normal(0.0, jitter))
    width = max(0.02, (right - left) * scale * float(rng.uniform(0.92, 1.08)))
    height = max(0.02, (bottom - top) * scale * float(rng.uniform(0.92, 1.08)))
    left = min(max(0.0, cx - width / 2.0), 0.98)
    top = min(max(0.0, cy - height / 2.0), 0.98)
    right = max(min(1.0, cx + width / 2.0), left + 0.01)
    bottom = max(min(1.0, cy + height / 2.0), top + 0.01)
    return (left, top, min(1.0, right), min(1.0, bottom))


def _perturb_rgb(
    rgb: tuple[int, int, int],
    rng: np.random.Generator,
    jitter: float,
) -> tuple[int, int, int]:
    arr = np.asarray(rgb, dtype=np.float32)
    arr += rng.normal(0.0, jitter, size=3)
    return tuple(int(value) for value in np.clip(np.round(arr), 0, 255))


def _role_load_scale(role: MaskRole, params: VariantParams) -> float:
    if role in {MaskRole.BASE_WASH, MaskRole.SUPPORT, MaskRole.CORRECTION}:
        return params.transparent_load_scale
    if role in {MaskRole.ACCENT, MaskRole.KEY}:
        return params.opaque_load_scale
    return 1.0


def _ordered_impressions(
    impressions: list[Impression],
    stack_order: StackOrder,
) -> list[Impression]:
    if stack_order == "reverse":
        ordered = list(reversed(impressions))
    elif stack_order == "role_priority":
        ordered = sorted(
            impressions,
            key=lambda impression: (ROLE_PRIORITY[impression.role], impression.order),
        )
    else:
        ordered = list(impressions)
    return [
        impression.model_copy(update={"order": order})
        for order, impression in enumerate(ordered, start=1)
    ]


def _variant_plan(
    analysis: ImageAnalysis,
    params: VariantParams,
    cnc_profile: CNCProfile | None = None,
) -> PrintPlan:
    rng = np.random.default_rng(params.variant_seed)
    plan = generate_candidate_plan(
        analysis,
        target_block_count=params.target_block_count,
        cnc_profile=cnc_profile,
    )
    masks = [
        mask.model_copy(
            update={
                "bbox_norm": _clamp_bbox(
                    mask.bbox_norm,
                    rng,
                    jitter=params.bbox_jitter,
                    scale=params.bbox_scale,
                )
            }
        )
        for mask in plan.masks
    ]

    impressions: list[Impression] = []
    for impression in plan.impressions:
        zones: list[ColorZone] = []
        for zone in impression.color_zones:
            recipe = zone.recipe
            load = recipe.load * params.global_load_scale * _role_load_scale(zone.role, params)
            load *= float(rng.uniform(0.92, 1.08))
            next_recipe = recipe.model_copy(
                update={
                    "recipe_id": f"{recipe.recipe_id}_v{params.variant_index:04d}",
                    "estimated_rgb": _perturb_rgb(recipe.estimated_rgb, rng, params.color_jitter),
                    "load": float(np.clip(load, 0.02, 1.0)),
                }
            )
            zones.append(zone.model_copy(update={"recipe": next_recipe}))
        impressions.append(impression.model_copy(update={"color_zones": zones}))

    impressions = _ordered_impressions(impressions, params.stack_order)
    blocks = [
        Block(
            block_id=block.block_id,
            impression_id=block.impression_id,
            color_zone_ids=block.color_zone_ids,
            cnc_status=block.cnc_status,
        )
        for block in plan.blocks
    ]
    return plan.model_copy(
        update={
            "plan_id": f"overprint_variant_{params.variant_index:04d}",
            "target_block_count": params.target_block_count,
            "masks": masks,
            "impressions": impressions,
            "blocks": blocks,
        }
    )


def render_plan_array(plan: PrintPlan, width: int = 256, tier: RenderTierName = "t1") -> np.ndarray:
    """Render a plan to an RGB uint8 array without filesystem side effects."""

    aspect = plan.cnc_profile.print_height_mm / plan.cnc_profile.print_width_mm
    height = max(1, int(round(width * aspect)))
    paper = np.asarray(BuildDefaults().paper_color_rgb, dtype=np.float32) / 255.0
    canvas = np.zeros((height, width, 3), dtype=np.float32)
    canvas[:, :] = paper
    masks_by_id = {mask.mask_id: mask for mask in plan.masks}

    for impression in sorted(plan.impressions, key=lambda item: item.order):
        for zone in impression.color_zones:
            mask = masks_by_id[zone.mask_id]
            if tier == "t0":
                color = np.asarray(zone.recipe.estimated_rgb, dtype=np.float32) / 255.0
                alpha = _mask_array(mask, height, width) * ROLE_ALPHA[zone.role] * zone.recipe.load
                canvas = (canvas * (1.0 - alpha[..., None])) + (color * alpha[..., None])
            else:
                pigment_rgb = premix_recipe_rgb(zone.recipe)
                strength = _layer_strength(mask, zone.recipe, zone.role, height, width)
                canvas = glaze_over(canvas, pigment_rgb, strength)

    return np.clip(np.round(canvas * 255.0), 0, 255).astype(np.uint8)


def _low_frequency(image: np.ndarray, side: int = 32) -> np.ndarray:
    pil = Image.fromarray(np.clip(np.round(image), 0, 255).astype(np.uint8), "RGB")
    width, height = pil.size
    scale = side / max(width, height)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return np.asarray(pil.resize(size, Image.Resampling.BILINEAR), dtype=np.float32)


def _smooth_field(field: np.ndarray, factor: int) -> np.ndarray:
    factor = max(1, int(factor))
    clipped = np.clip(field, 0.0, 1.0)
    if factor <= 1:
        return clipped.astype(np.float32)
    height, width = clipped.shape
    small = (max(1, width // factor), max(1, height // factor))
    image = Image.fromarray(np.round(clipped * 255.0).astype(np.uint8), "L")
    image = image.resize(small, Image.Resampling.BILINEAR)
    image = image.resize((width, height), Image.Resampling.BILINEAR)
    return np.asarray(image, dtype=np.float32) / 255.0


def _normalize01(field: np.ndarray) -> np.ndarray:
    finite = np.nan_to_num(field.astype(np.float32), copy=False)
    low = float(np.percentile(finite, 1.0))
    high = float(np.percentile(finite, 99.0))
    if high <= low:
        return np.zeros_like(finite, dtype=np.float32)
    return np.clip((finite - low) / (high - low), 0.0, 1.0)


def _soft_quantile_mask(field: np.ndarray, quantile: float, smooth: int) -> np.ndarray:
    smooth_field = _smooth_field(_normalize01(field), smooth)
    active = smooth_field[smooth_field > 0.001]
    if len(active) == 0:
        return np.zeros_like(smooth_field, dtype=np.float32)
    threshold = float(np.quantile(active, np.clip(quantile, 0.05, 0.95)))
    high = max(float(active.max()), threshold + 1e-4)
    mask = np.clip((smooth_field - threshold) / (high - threshold), 0.0, 1.0)
    return _smooth_field(mask, max(1, smooth // 2))


def _target_fields(target: np.ndarray) -> dict[str, np.ndarray]:
    rgb = np.clip(target.astype(np.float32) / 255.0, 0.0, 1.0)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    luma = (0.299 * red) + (0.587 * green) + (0.114 * blue)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    paper = np.asarray(BuildDefaults().paper_color_rgb, dtype=np.float32) / 255.0
    paper_delta = np.linalg.norm(rgb - paper, axis=2)
    subject = _normalize01((0.65 * chroma) + (0.35 * paper_delta) + (0.15 * (1.0 - luma)))
    subject = _smooth_field(subject, 4)

    warm = _normalize01((red - (0.46 * green) - (0.34 * blue)) + (0.16 * chroma)) * subject
    flesh = _normalize01((red + (0.74 * green) - (0.82 * blue)) + (0.12 * luma)) * subject
    red_field = _normalize01((red - green) + (0.55 * (red - blue)) + (0.1 * chroma)) * subject
    pink = _normalize01((red + (0.72 * blue) - (0.92 * green)) + (0.12 * chroma)) * subject
    cool = _normalize01(((green + blue) * 0.55) - (0.72 * red) + (0.12 * chroma)) * subject
    blue_field = _normalize01((blue - (0.48 * red) - (0.18 * green)) + (0.18 * chroma)) * subject
    teal = _normalize01((green + blue - (1.08 * red)) + (0.12 * chroma)) * subject
    dark = _normalize01((1.0 - luma) + (0.35 * chroma)) * subject
    light_support = _normalize01((0.78 * luma) + (0.22 * subject)) * subject
    edge_like = _normalize01(dark - _smooth_field(dark, 12))

    return {
        "subject": subject,
        "light": light_support,
        "warm": warm,
        "flesh": flesh,
        "red": red_field,
        "pink": pink,
        "cool": cool,
        "blue": blue_field,
        "teal": teal,
        "dark": dark,
        "edge": edge_like,
    }


def _image_palette(
    target: np.ndarray,
    count: int,
    rng: np.random.Generator,
    jitter: float,
) -> list[tuple[int, int, int]]:
    if count <= 0:
        return []
    image = Image.fromarray(np.clip(np.round(target), 0, 255).astype(np.uint8), "RGB")
    quantized = image.quantize(colors=min(count, 256), method=Image.Quantize.MEDIANCUT)
    colors = quantized.getcolors(maxcolors=image.width * image.height) or []
    palette = quantized.getpalette() or []
    ranked = sorted(colors, key=lambda item: item[0], reverse=True)
    result: list[tuple[int, int, int]] = []
    for _, palette_index in ranked:
        offset = int(palette_index) * 3
        if offset + 2 >= len(palette):
            continue
        result.append(
            _perturb_rgb(
                (
                    int(palette[offset]),
                    int(palette[offset + 1]),
                    int(palette[offset + 2]),
                ),
                rng,
                jitter * 0.25,
            )
        )
    return result


def _dedupe_colors(colors: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    deduped: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for color in colors:
        key = tuple(int(round(channel / 6.0) * 6) for channel in color)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(color)
    return deduped


def _candidate_colors(
    rng: np.random.Generator,
    jitter: float,
    target: np.ndarray | None = None,
    palette_size: int = 12,
    include_image_palette: bool = False,
) -> list[tuple[int, int, int]]:
    colors = [
        (246, 232, 174),
        (248, 215, 184),
        (238, 166, 151),
        (228, 104, 72),
        (204, 43, 58),
        (235, 128, 198),
        (159, 221, 221),
        (49, 168, 191),
        (28, 93, 171),
        (30, 127, 103),
        (105, 77, 61),
        (38, 38, 46),
    ]
    candidates = [_perturb_rgb(color, rng, jitter) for color in colors]
    if include_image_palette and target is not None:
        candidates.extend(_image_palette(target, max(0, palette_size), rng, jitter))
    return _dedupe_colors(candidates)[: max(1, palette_size + len(colors))]


def _apply_glaze_layer(
    canvas: np.ndarray,
    color: tuple[int, int, int],
    mask: np.ndarray,
    strength: float,
) -> np.ndarray:
    pigment = np.asarray(color, dtype=np.float32) / 255.0
    layer_strength = np.clip(mask, 0.0, 1.0) * float(np.clip(strength, 0.0, 1.0))
    return glaze_over(canvas, pigment, layer_strength)


def _underlayer_specs(
    fields: dict[str, np.ndarray],
    params: VariantParams,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    strength = params.underlayer_strength * params.global_load_scale
    quantile = max(0.34, params.mask_quantile - 0.24)
    broad = params.broad_smooth
    specs = [
        ("cream support", "light", (246, 232, 174), 0.72, broad + 10),
        ("cool support", "cool", (159, 221, 221), 0.82, broad + 6),
        ("flesh field", "flesh", (248, 190, 174), 1.0, broad + 2),
        ("warm modifier", "warm", (238, 138, 98), 0.9, broad),
        ("blue shadow mass", "blue", (47, 126, 190), 0.94, broad - 2),
        ("pink modifier", "pink", (230, 133, 190), 0.78, broad - 1),
        ("dark support", "dark", (72, 61, 67), 0.82, max(4, broad - 5)),
    ]
    layers: list[dict[str, Any]] = []
    for name, field_name, color, strength_scale, smooth in specs:
        mask = _soft_quantile_mask(fields[field_name], quantile, max(2, smooth))
        if float(mask.mean()) < 0.01:
            continue
        layers.append(
            {
                "name": name,
                "color": _perturb_rgb(color, rng, params.color_jitter * 0.45),
                "mask": mask,
                "strength": float(np.clip(strength * strength_scale, 0.04, 0.72)),
            }
        )
    return layers


def _best_residual_layer(
    target01: np.ndarray,
    canvas: np.ndarray,
    fields: dict[str, np.ndarray],
    colors: list[tuple[int, int, int]],
    params: VariantParams,
    rng: np.random.Generator,
    layer_index: int,
) -> dict[str, Any] | None:
    residual = target01 - canvas
    progress = layer_index / max(1, params.target_block_count - 1)
    smooth = round(
        ((1.0 - progress) * params.broad_smooth) + (progress * params.detail_smooth)
    )
    smooth = max(1, smooth)
    quantile = float(
        np.clip(
            params.mask_quantile + (0.13 * progress) + float(rng.normal(0.0, 0.035)),
            0.35,
            0.94,
        )
    )
    strength = float(
        np.clip(
            params.residual_strength * (1.08 - (0.35 * progress)) * params.global_load_scale,
            0.04,
            0.82,
        )
    )
    detail_gate = (
        fields["subject"]
        if progress < 0.72
        else np.maximum(fields["dark"], fields["edge"])
    )
    best: dict[str, Any] | None = None
    base_error = float(np.mean((target01 - canvas) ** 2))

    for color in colors:
        pigment = np.asarray(color, dtype=np.float32) / 255.0
        direction = pigment - canvas
        score = np.maximum(np.sum(residual * direction, axis=2), 0.0) * detail_gate
        mask = _soft_quantile_mask(score, quantile, smooth)
        coverage = float(mask.mean())
        if coverage < 0.004:
            continue
        preview = _apply_glaze_layer(canvas, color, mask, strength)
        error = float(np.mean((target01 - preview) ** 2))
        improvement = base_error - error
        if best is None or improvement > best["improvement"]:
            best = {
                "name": "residual detail" if progress > 0.55 else "residual field",
                "color": color,
                "mask": mask,
                "strength": strength,
                "improvement": improvement,
                "coverage": coverage,
            }
    return best


def render_strategy_array(
    target: np.ndarray,
    params: VariantParams,
    *,
    palette_size: int = 12,
    include_image_palette: bool = False,
    mask_smooth_scale: float = 1.0,
) -> tuple[np.ndarray, dict[str, float], list[dict[str, Any]]]:
    if mask_smooth_scale <= 0:
        raise ValueError("mask_smooth_scale must be > 0")
    params = replace(
        params,
        broad_smooth=max(1, int(round(params.broad_smooth * mask_smooth_scale))),
        detail_smooth=max(1, int(round(params.detail_smooth * mask_smooth_scale))),
    )
    rng = np.random.default_rng(params.variant_seed)
    target01 = np.clip(target.astype(np.float32) / 255.0, 0.0, 1.0)
    paper = np.asarray(BuildDefaults().paper_color_rgb, dtype=np.float32) / 255.0
    canvas = np.zeros_like(target01)
    canvas[:, :] = paper
    fields = _target_fields(target)
    colors = _candidate_colors(
        rng,
        params.color_jitter,
        target=target,
        palette_size=palette_size,
        include_image_palette=include_image_palette,
    )

    layers = _underlayer_specs(fields, params, rng)
    if params.strategy == "field_stack":
        extra_fields = [
            ("red accent", "red", (210, 45, 44), 0.64, params.detail_smooth + 2),
            ("teal accent", "teal", (20, 144, 126), 0.58, params.detail_smooth + 2),
            ("blue accent", "blue", (25, 98, 194), 0.62, params.detail_smooth + 1),
            ("dark key", "dark", (34, 32, 38), 0.72, params.detail_smooth),
            ("edge key", "edge", (24, 25, 32), 0.66, max(1, params.detail_smooth - 2)),
        ]
        for name, field_name, color, strength_scale, smooth in extra_fields:
            mask = _soft_quantile_mask(
                fields[field_name],
                min(0.94, params.mask_quantile + 0.08),
                max(1, smooth),
            )
            layers.append(
                {
                    "name": name,
                    "color": _perturb_rgb(color, rng, params.color_jitter * 0.65),
                    "mask": mask,
                    "strength": float(
                        np.clip(params.residual_strength * strength_scale, 0.04, 0.78)
                    ),
                }
            )

    for layer in layers[: params.target_block_count]:
        canvas = _apply_glaze_layer(canvas, layer["color"], layer["mask"], layer["strength"])

    if params.strategy == "residual_stack":
        while len(layers) < params.target_block_count:
            next_layer = _best_residual_layer(
                target01,
                canvas,
                fields,
                colors,
                params,
                rng,
                len(layers),
            )
            if next_layer is None or next_layer["improvement"] <= 0.0:
                break
            layers.append(next_layer)
            canvas = _apply_glaze_layer(
                canvas,
                next_layer["color"],
                next_layer["mask"],
                next_layer["strength"],
            )

    rendered = np.clip(np.round(canvas * 255.0), 0, 255).astype(np.uint8)
    return rendered, layer_metrics(layers), layers


def _component_count(mask: np.ndarray) -> int:
    active = mask > 0.5
    if not bool(active.any()):
        return 0
    visited = np.zeros(active.shape, dtype=bool)
    components = 0
    height, width = active.shape
    starts = np.argwhere(active)
    for row, col in starts:
        row_i = int(row)
        col_i = int(col)
        if visited[row_i, col_i]:
            continue
        components += 1
        stack = [(row_i, col_i)]
        visited[row_i, col_i] = True
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if (
                    0 <= ny < height
                    and 0 <= nx < width
                    and active[ny, nx]
                    and not visited[ny, nx]
                ):
                    visited[ny, nx] = True
                    stack.append((ny, nx))
    return components


def layer_metrics(layers: list[dict[str, Any]]) -> dict[str, float]:
    if not layers:
        return {
            "island_penalty": 0.0,
            "average_mask_coverage": 0.0,
            "mask_overlap_mean": 0.0,
            "reuse_overlap_mean": 0.0,
            "stack_depth_mean": 0.0,
            "stack_depth_gt2_pct": 0.0,
            "max_stack_depth": 0.0,
            "underprint_hidden_ratio": 0.0,
            "underprint_hidden_pct": 0.0,
            "early_to_late_coverage_ratio": 0.0,
        }

    masks = [np.clip(layer["mask"], 0.0, 1.0).astype(np.float32) for layer in layers]
    binary = [mask > 0.18 for mask in masks]
    coverages = [float(mask.mean()) for mask in masks]
    island_penalty = float(
        np.mean([max(0, _component_count(mask.astype(np.float32)) - 1) for mask in binary])
    )

    pair_overlaps: list[float] = []
    for left_idx, left in enumerate(masks):
        left_area = float(left.sum())
        for right in masks[left_idx + 1 :]:
            denom = max(left_area, float(right.sum()), 1.0)
            pair_overlaps.append(float(np.minimum(left, right).sum() / denom))

    cumulative = np.zeros_like(masks[0], dtype=np.float32)
    reuse: list[float] = []
    for mask in masks:
        area = float(mask.sum())
        if area > 0:
            reuse.append(float(np.minimum(mask, cumulative).sum() / area))
        cumulative = np.maximum(cumulative, mask)

    stack_depth = np.zeros_like(masks[0], dtype=np.float32)
    for mask in binary:
        stack_depth += mask.astype(np.float32)

    hidden_ratios: list[float] = []
    hidden_pcts: list[float] = []
    later = np.zeros_like(masks[0], dtype=bool)
    for mask in reversed(binary):
        area = float(mask.sum())
        if area > 0:
            hidden = float(np.logical_and(mask, later).sum())
            visible = max(1.0, area - hidden)
            hidden_ratios.append(min(hidden / visible, 6.0))
            hidden_pcts.append(hidden / area)
        later = np.logical_or(later, mask)

    split = max(1, len(coverages) // 3)
    early = float(np.mean(coverages[:split], dtype=np.float64))
    late = float(np.mean(coverages[-split:], dtype=np.float64))

    return {
        "island_penalty": island_penalty,
        "average_mask_coverage": float(np.mean(coverages, dtype=np.float64)),
        "mask_overlap_mean": float(np.mean(pair_overlaps, dtype=np.float64))
        if pair_overlaps
        else 0.0,
        "reuse_overlap_mean": float(np.mean(reuse, dtype=np.float64)) if reuse else 0.0,
        "stack_depth_mean": float(np.mean(stack_depth, dtype=np.float64)),
        "stack_depth_gt2_pct": float(np.mean(stack_depth >= 2.0, dtype=np.float64)),
        "max_stack_depth": float(np.max(stack_depth)),
        "underprint_hidden_ratio": float(np.mean(hidden_ratios, dtype=np.float64))
        if hidden_ratios
        else 0.0,
        "underprint_hidden_pct": float(np.mean(hidden_pcts, dtype=np.float64))
        if hidden_pcts
        else 0.0,
        "early_to_late_coverage_ratio": early / max(late, 1e-6),
    }


def mask_metrics(plan: PrintPlan, width: int) -> dict[str, float]:
    aspect = plan.cnc_profile.print_height_mm / plan.cnc_profile.print_width_mm
    height = max(1, int(round(width * aspect)))
    masks = [_mask_array(mask, height, width) for mask in plan.masks]
    if not masks:
        return {
            "island_penalty": 0.0,
            "average_mask_coverage": 0.0,
            "mask_overlap_mean": 0.0,
            "reuse_overlap_mean": 0.0,
            "stack_depth_mean": 0.0,
            "stack_depth_gt2_pct": 0.0,
            "max_stack_depth": 0.0,
            "underprint_hidden_ratio": 0.0,
            "underprint_hidden_pct": 0.0,
            "early_to_late_coverage_ratio": 0.0,
        }

    coverages = [float(mask.mean()) for mask in masks]
    island_penalty = float(
        np.mean([max(0, _component_count(mask) - 1) for mask in masks], dtype=np.float64)
    )

    pair_overlaps: list[float] = []
    for left_idx, left in enumerate(masks):
        left_area = float(left.sum())
        for right in masks[left_idx + 1 :]:
            denom = max(left_area, float(right.sum()), 1.0)
            pair_overlaps.append(float(np.minimum(left, right).sum() / denom))

    mask_by_id = {mask.mask_id: arr for mask, arr in zip(plan.masks, masks, strict=True)}
    cumulative = np.zeros((height, width), dtype=np.float32)
    reuse: list[float] = []
    for impression in sorted(plan.impressions, key=lambda item: item.order):
        current = np.zeros((height, width), dtype=np.float32)
        for zone in impression.color_zones:
            current = np.maximum(current, mask_by_id[zone.mask_id])
        area = float(current.sum())
        if area > 0:
            reuse.append(float(np.minimum(current, cumulative).sum() / area))
        cumulative = np.maximum(cumulative, current)

    binary = [mask > 0.18 for mask in masks]
    stack_depth = np.zeros((height, width), dtype=np.float32)
    for mask in binary:
        stack_depth += mask.astype(np.float32)

    hidden_ratios: list[float] = []
    hidden_pcts: list[float] = []
    later = np.zeros((height, width), dtype=bool)
    for mask in reversed(binary):
        area = float(mask.sum())
        if area > 0:
            hidden = float(np.logical_and(mask, later).sum())
            visible = max(1.0, area - hidden)
            hidden_ratios.append(min(hidden / visible, 6.0))
            hidden_pcts.append(hidden / area)
        later = np.logical_or(later, mask)

    split = max(1, len(coverages) // 3)
    early = float(np.mean(coverages[:split], dtype=np.float64))
    late = float(np.mean(coverages[-split:], dtype=np.float64))

    return {
        "island_penalty": island_penalty,
        "average_mask_coverage": float(np.mean(coverages, dtype=np.float64)),
        "mask_overlap_mean": float(np.mean(pair_overlaps, dtype=np.float64))
        if pair_overlaps
        else 0.0,
        "reuse_overlap_mean": float(np.mean(reuse, dtype=np.float64)) if reuse else 0.0,
        "stack_depth_mean": float(np.mean(stack_depth, dtype=np.float64)),
        "stack_depth_gt2_pct": float(np.mean(stack_depth >= 2.0, dtype=np.float64)),
        "max_stack_depth": float(np.max(stack_depth)),
        "underprint_hidden_ratio": float(np.mean(hidden_ratios, dtype=np.float64))
        if hidden_ratios
        else 0.0,
        "underprint_hidden_pct": float(np.mean(hidden_pcts, dtype=np.float64))
        if hidden_pcts
        else 0.0,
        "early_to_late_coverage_ratio": early / max(late, 1e-6),
    }


def image_metrics(rendered: np.ndarray, target: np.ndarray) -> dict[str, float]:
    diff = rendered.astype(np.float32) - target.astype(np.float32)
    low_rendered = _low_frequency(rendered)
    low_target = _low_frequency(target)
    low_diff = low_rendered - low_target
    return {
        "rgb_rmse": float(np.sqrt(np.mean(diff**2, dtype=np.float64))),
        "rgb_mae": float(np.mean(np.abs(diff), dtype=np.float64)),
        "low_frequency_rmse": float(np.sqrt(np.mean(low_diff**2, dtype=np.float64))),
    }


def _rank_metrics(metrics: dict[str, float]) -> None:
    overlap = metrics.get("reuse_overlap_mean", 0.0)
    stack_gt2 = metrics.get("stack_depth_gt2_pct", 0.0)
    hidden = min(metrics.get("underprint_hidden_ratio", 0.0), 4.0) / 4.0
    early_ratio = min(metrics.get("early_to_late_coverage_ratio", 0.0), 6.0) / 6.0
    island = metrics.get("island_penalty", 0.0)
    coverage = metrics.get("average_mask_coverage", 0.0)
    coverage_penalty = abs(coverage - 0.22) * 30.0
    plate_penalty = abs(metrics.get("plate_count", 0.0) - 27.0) * 0.35

    process_score = (
        (0.26 * overlap)
        + (0.25 * stack_gt2)
        + (0.22 * hidden)
        + (0.17 * early_ratio)
        - (0.10 * min(island / 12.0, 1.0))
    )
    rank_score = (
        metrics["rgb_rmse"]
        + (0.65 * metrics["low_frequency_rmse"])
        + coverage_penalty
        + plate_penalty
        + (0.28 * island)
        - (18.0 * process_score)
    )
    metrics["process_score"] = float(process_score)
    metrics["rank_score"] = float(rank_score)


def _draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: list[str]) -> None:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, fill=(20, 20, 20))
        y += 13


def _contact_sheets(
    records: list[dict[str, Any]],
    out_dir: Path,
    cols: int,
    rows: int,
) -> list[Path]:
    sheet_dir = out_dir / "contact_sheets"
    sheet_dir.mkdir(parents=True, exist_ok=True)
    sorted_records = sorted(records, key=lambda record: record["metrics"]["rank_score"])
    page_size = max(1, cols * rows)
    sheet_paths: list[Path] = []
    thumb_w, thumb_h, label_h = 180, 254, 56
    for page_idx, start in enumerate(range(0, len(sorted_records), page_size), start=1):
        page = sorted_records[start : start + page_size]
        sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
        draw = ImageDraw.Draw(sheet)
        for item_idx, record in enumerate(page):
            row, col = divmod(item_idx, cols)
            x = col * thumb_w
            y = row * (thumb_h + label_h)
            with Image.open(record["preview_path"]) as image:
                preview = image.convert("RGB")
            preview.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(preview, (x + (thumb_w - preview.width) // 2, y))
            metrics = record["metrics"]
            params = record["params"]
            _draw_label(
                draw,
                (x + 4, y + thumb_h + 3),
                [
                    (
                        f"#{params['variant_index']:03d} {params['strategy']} "
                        f"rank {metrics['rank_score']:.1f}"
                    ),
                    f"rmse {metrics['rgb_rmse']:.1f} lf {metrics['low_frequency_rmse']:.1f}",
                    f"mae {metrics['rgb_mae']:.1f} hidden {metrics['underprint_hidden_ratio']:.2f}",
                    f"plates {metrics['plate_count']} cov {metrics['average_mask_coverage']:.2f}",
                    (
                        f"reuse {metrics['reuse_overlap_mean']:.2f} "
                        f"proc {metrics['process_score']:.2f}"
                    ),
                ],
            )
        path = sheet_dir / f"contact_sheet_{page_idx:03d}.jpg"
        sheet.save(path, "JPEG", quality=92)
        sheet_paths.append(path)
    return sheet_paths


def _layer_summaries(layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for order, layer in enumerate(layers, start=1):
        mask = np.clip(layer["mask"], 0.0, 1.0)
        summaries.append(
            {
                "order": order,
                "name": layer["name"],
                "color": list(layer["color"]),
                "strength": float(layer["strength"]),
                "coverage": float(np.mean(mask, dtype=np.float64)),
            }
        )
    return summaries


def _strategy_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        strategy = record["params"]["strategy"]
        counts[strategy] = counts.get(strategy, 0) + 1
    return counts


def _slug(value: str) -> str:
    slug = "".join(char if char.isalnum() else "_" for char in value.lower())
    return "_".join(part for part in slug.split("_") if part)


def _plate_preview(layer: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    paper = np.asarray(BuildDefaults().paper_color_rgb, dtype=np.float32)
    color = np.asarray(layer["color"], dtype=np.float32)
    mask = np.clip(layer["mask"], 0.0, 1.0).astype(np.float32)
    image = (paper * (1.0 - mask[..., None])) + (color * mask[..., None])
    pil = Image.fromarray(np.clip(np.round(image), 0, 255).astype(np.uint8), "RGB")
    return pil.resize(size, Image.Resampling.LANCZOS)


def _save_grid_sheet(
    items: list[Image.Image],
    labels: list[list[str]],
    path: Path,
    *,
    cols: int = 5,
    thumb_size: tuple[int, int] = (180, 254),
    label_h: int = 46,
) -> None:
    rows = max(1, int(np.ceil(len(items) / cols)))
    thumb_w, thumb_h = thumb_size
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(items):
        row, col = divmod(index, cols)
        x = col * thumb_w
        y = row * (thumb_h + label_h)
        preview = item.convert("RGB")
        preview.thumbnail(thumb_size, Image.Resampling.LANCZOS)
        sheet.paste(preview, (x + (thumb_w - preview.width) // 2, y))
        _draw_label(draw, (x + 4, y + thumb_h + 3), labels[index])
    sheet.save(path, "JPEG", quality=92)


def _diagnostic_params(
    params: VariantParams,
    diagnostic_width: int,
    base_width: int,
) -> VariantParams:
    if diagnostic_width <= base_width:
        return params
    scale = diagnostic_width / base_width
    return replace(
        params,
        broad_smooth=max(params.broad_smooth, int(round(params.broad_smooth * scale))),
        detail_smooth=max(
            params.detail_smooth,
            int(round(params.detail_smooth * max(1.0, scale * 0.45))),
        ),
    )


def _save_strategy_diagnostics(
    input_path: Path,
    params_data: dict[str, Any],
    out_dir: Path,
    variant_id: str,
    diagnostic_size: tuple[int, int],
    base_width: int,
    palette_size: int,
    include_image_palette: bool,
    mask_smooth_scale: float,
) -> dict[str, Any]:
    source_params = VariantParams(**params_data)
    diagnostic_width, diagnostic_height = diagnostic_size
    params = _diagnostic_params(source_params, diagnostic_width, base_width)
    if params.strategy == "grammar":
        return {}

    target = _target_array(input_path, diagnostic_size)
    rendered, _, layers = render_strategy_array(
        target,
        params,
        palette_size=palette_size,
        include_image_palette=include_image_palette,
        mask_smooth_scale=mask_smooth_scale,
    )
    diag_dir = out_dir / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    final_path = diag_dir / f"{variant_id}_final.png"
    layer_sheet_path = diag_dir / f"{variant_id}_plates.jpg"
    cumulative_sheet_path = diag_dir / f"{variant_id}_cumulative.jpg"
    plate_dir = diag_dir / f"{variant_id}_plate_pngs"
    mask_dir = diag_dir / f"{variant_id}_mask_pngs"
    cumulative_dir = diag_dir / f"{variant_id}_cumulative_pngs"
    plate_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    cumulative_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rendered, "RGB").save(final_path)

    width, height = target.shape[1], target.shape[0]
    plate_items: list[Image.Image] = []
    plate_labels: list[list[str]] = []
    cumulative_items: list[Image.Image] = []
    cumulative_labels: list[list[str]] = []
    plate_paths: list[str] = []
    mask_paths: list[str] = []
    cumulative_paths: list[str] = []
    paper = np.asarray(BuildDefaults().paper_color_rgb, dtype=np.float32) / 255.0
    canvas = np.zeros((height, width, 3), dtype=np.float32)
    canvas[:, :] = paper

    for order, layer in enumerate(layers, start=1):
        name_slug = _slug(layer["name"])
        plate_path = plate_dir / f"plate_{order:02d}_{name_slug}.png"
        mask_path = mask_dir / f"plate_{order:02d}_{name_slug}_mask.png"
        cumulative_path = cumulative_dir / f"cumulative_{order:02d}_{name_slug}.png"
        plate = _plate_preview(layer, (width, height))
        plate.save(plate_path)
        mask_image = Image.fromarray(
            np.clip(np.round(layer["mask"] * 255.0), 0, 255).astype(np.uint8),
            "L",
        )
        mask_image.save(mask_path)
        plate_paths.append(str(plate_path))
        mask_paths.append(str(mask_path))
        plate_items.append(plate.copy())
        plate_labels.append(
            [
                f"#{order:02d} {layer['name']}",
                f"rgb {tuple(layer['color'])}",
                f"cov {float(np.mean(layer['mask'], dtype=np.float64)):.2f}",
            ]
        )
        canvas = _apply_glaze_layer(canvas, layer["color"], layer["mask"], layer["strength"])
        cumulative = np.clip(np.round(canvas * 255.0), 0, 255).astype(np.uint8)
        cumulative_image = Image.fromarray(cumulative, "RGB")
        cumulative_image.save(cumulative_path)
        cumulative_paths.append(str(cumulative_path))
        cumulative_items.append(cumulative_image)
        cumulative_labels.append(
            [
                f"after #{order:02d}",
                layer["name"],
                f"strength {float(layer['strength']):.2f}",
            ]
        )

    _save_grid_sheet(plate_items, plate_labels, layer_sheet_path)
    _save_grid_sheet(cumulative_items, cumulative_labels, cumulative_sheet_path)
    manifest = {
        "variant_id": variant_id,
        "source_params": asdict(source_params),
        "diagnostic_params": asdict(params),
        "diagnostic_width": diagnostic_width,
        "diagnostic_height": diagnostic_height,
        "palette_size": palette_size,
        "include_image_palette": include_image_palette,
        "mask_smooth_scale": mask_smooth_scale,
        "reconstructed_path": str(final_path),
        "plate_visual_paths": plate_paths,
        "plate_mask_paths": mask_paths,
        "cumulative_paths": cumulative_paths,
    }
    manifest_path = diag_dir / f"{variant_id}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, default=_json_default, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "diagnostic_width": diagnostic_width,
        "diagnostic_height": diagnostic_height,
        "final_path": str(final_path),
        "plate_sheet_path": str(layer_sheet_path),
        "cumulative_sheet_path": str(cumulative_sheet_path),
        "plate_dir": str(plate_dir),
        "mask_dir": str(mask_dir),
        "cumulative_dir": str(cumulative_dir),
        "manifest_path": str(manifest_path),
    }


def run_experiment(config: HarnessConfig) -> dict[str, Any]:
    if config.variants < 1:
        raise ValueError("variants must be >= 1")
    if config.width < 16:
        raise ValueError("width must be >= 16")
    if config.diagnostic_width is not None and config.diagnostic_width < 16:
        raise ValueError("diagnostic_width must be >= 16")
    if config.palette_size < 1:
        raise ValueError("palette_size must be >= 1")
    if config.mask_smooth_scale <= 0:
        raise ValueError("mask_smooth_scale must be > 0")
    if config.strategy == "grammar" and config.preserve_source_aspect:
        raise ValueError("grammar strategy requires the fixed CNC/A1 aspect renderer")
    config.out_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = config.out_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    reference = _reference_for_path(config.input_path)
    analysis = _deterministic_analysis(reference, config.clusters)
    strategy_size = _target_size(config, config.width)
    strategy_target = _target_array(config.input_path, strategy_size)

    jsonl_path = config.out_dir / "experiments.jsonl"
    records: list[dict[str, Any]] = []
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for index in range(config.variants):
            params = _variant_params(index, config.seed, config.strategy)
            layers: list[dict[str, Any]] = []
            if params.strategy == "grammar":
                plan = _variant_plan(analysis, params)
                rendered = render_plan_array(plan, width=config.width, tier=config.tier)
                target = _target_array(config.input_path, (rendered.shape[1], rendered.shape[0]))
                metrics = image_metrics(rendered, target)
                metrics.update(mask_metrics(plan, width=min(config.width, 128)))
                metrics["plate_count"] = len(plan.impressions)
                variant_id = plan.plan_id
            else:
                rendered, process_metrics, layers = render_strategy_array(
                    strategy_target,
                    params,
                    palette_size=config.palette_size,
                    include_image_palette=config.include_image_palette,
                    mask_smooth_scale=config.mask_smooth_scale,
                )
                metrics = image_metrics(rendered, strategy_target)
                metrics.update(process_metrics)
                metrics["plate_count"] = len(layers)
                variant_id = f"{params.strategy}_variant_{index:04d}"
            _rank_metrics(metrics)

            preview_path = preview_dir / f"variant_{index:04d}.jpg"
            Image.fromarray(rendered, "RGB").save(
                preview_path,
                "JPEG",
                quality=config.preview_quality,
            )
            record = {
                "variant_id": variant_id,
                "input_path": str(config.input_path),
                "input_sha256": reference.sha256,
                "reference_image_targets": REFERENCE_IMAGE_TARGETS,
                "render_tier": config.tier,
                "render_width": config.width,
                "preview_path": str(preview_path),
                "params": asdict(params),
                "metrics": metrics,
                "layers": _layer_summaries(layers),
            }
            handle.write(json.dumps(record, default=_json_default, sort_keys=True) + "\n")
            records.append(record)

    sheet_paths = _contact_sheets(
        records,
        config.out_dir,
        cols=config.contact_sheet_cols,
        rows=config.contact_sheet_rows,
    )
    best = min(records, key=lambda record: record["metrics"]["rank_score"])
    best_rgb = min(records, key=lambda record: record["metrics"]["rgb_rmse"])
    diagnostic_size = _diagnostic_size(config, reference)
    diagnostics = _save_strategy_diagnostics(
        config.input_path,
        best["params"],
        config.out_dir,
        best["variant_id"],
        diagnostic_size,
        config.width,
        config.palette_size,
        config.include_image_palette,
        config.mask_smooth_scale,
    )
    best_rgb_diagnostics = _save_strategy_diagnostics(
        config.input_path,
        best_rgb["params"],
        config.out_dir,
        best_rgb["variant_id"],
        diagnostic_size,
        config.width,
        config.palette_size,
        config.include_image_palette,
        config.mask_smooth_scale,
    )
    summary = {
        "input_path": str(config.input_path),
        "input_sha256": reference.sha256,
        "reference_image_targets": REFERENCE_IMAGE_TARGETS,
        "variants": config.variants,
        "seed": config.seed,
        "strategy_counts": _strategy_counts(records),
        "strategy_filter": config.strategy,
        "preserve_source_aspect": config.preserve_source_aspect,
        "diagnostic_original_size": config.diagnostic_original_size,
        "palette_size": config.palette_size,
        "include_image_palette": config.include_image_palette,
        "mask_smooth_scale": config.mask_smooth_scale,
        "render_tier": config.tier,
        "render_width": config.width,
        "render_height": strategy_size[1],
        "jsonl_path": str(jsonl_path),
        "contact_sheets": [str(path) for path in sheet_paths],
        "best_variant": {
            "variant_id": best["variant_id"],
            "preview_path": best["preview_path"],
            "params": best["params"],
            "metrics": best["metrics"],
            "diagnostics": diagnostics,
        },
        "best_rgb_variant": {
            "variant_id": best_rgb["variant_id"],
            "preview_path": best_rgb["preview_path"],
            "params": best_rgb["params"],
            "metrics": best_rgb["metrics"],
            "diagnostics": best_rgb_diagnostics,
        },
    }
    summary_path = config.out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, default=_json_default, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run overprint-stack parameter experiments.")
    parser.add_argument("--input", required=True, type=Path, help="Source image to score against.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Experiment output directory.")
    parser.add_argument("--variants", type=int, default=100, help="Number of variants to run.")
    parser.add_argument("--seed", type=int, default=20260512, help="Deterministic master seed.")
    parser.add_argument("--width", type=int, default=256, help="Preview render width in pixels.")
    parser.add_argument("--tier", choices=["t0", "t1"], default="t1", help="Render tier.")
    parser.add_argument("--clusters", type=int, default=8, help="Palette clusters for analysis.")
    parser.add_argument("--contact-sheet-cols", type=int, default=5)
    parser.add_argument("--contact-sheet-rows", type=int, default=4)
    parser.add_argument(
        "--diagnostic-width",
        type=int,
        default=None,
        help="Optional width for high-resolution selected-variant exports.",
    )
    parser.add_argument(
        "--preserve-source-aspect",
        action="store_true",
        help="Score image-derived strategies without forcing the A1/CNC aspect ratio.",
    )
    parser.add_argument(
        "--diagnostic-original-size",
        action="store_true",
        help="Export selected-variant diagnostics at the source image dimensions.",
    )
    parser.add_argument(
        "--strategy",
        choices=["grammar", "field_stack", "residual_stack"],
        default=None,
        help="Optional strategy override for every variant.",
    )
    parser.add_argument(
        "--palette-size",
        type=int,
        default=12,
        help="Number of source-derived palette colors to add when enabled.",
    )
    parser.add_argument(
        "--include-image-palette",
        action="store_true",
        help="Add quantized source-image colors to the residual candidate palette.",
    )
    parser.add_argument(
        "--mask-smooth-scale",
        type=float,
        default=1.0,
        help="Multiplier for generated mask smoothing; lower values make sharper plates.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    summary = run_experiment(
        HarnessConfig(
            input_path=args.input,
            out_dir=args.out_dir,
            variants=args.variants,
            seed=args.seed,
            width=args.width,
            tier=args.tier,
            clusters=args.clusters,
            contact_sheet_cols=args.contact_sheet_cols,
            contact_sheet_rows=args.contact_sheet_rows,
            diagnostic_width=args.diagnostic_width,
            preserve_source_aspect=args.preserve_source_aspect,
            diagnostic_original_size=args.diagnostic_original_size,
            strategy=args.strategy,
            palette_size=args.palette_size,
            include_image_palette=args.include_image_palette,
            mask_smooth_scale=args.mask_smooth_scale,
        )
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
