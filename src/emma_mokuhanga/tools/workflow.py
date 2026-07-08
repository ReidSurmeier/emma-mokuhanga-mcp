"""End-to-end image-derived workflows for chat/share operation."""

from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from emma_mokuhanga.config import BuildDefaults
from emma_mokuhanga.image.analysis import analyze_reference
from emma_mokuhanga.image.color import oklab_to_rgb_u8, rgb_u8_to_oklab
from emma_mokuhanga.tools.ingest import ingest_image


def _resize_rgb(path: Path, max_side: int) -> Image.Image:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return image


def _sample_pixels(rgb: np.ndarray, sample_max_side: int = 384) -> np.ndarray:
    image = Image.fromarray(rgb, "RGB")
    image.thumbnail((sample_max_side, sample_max_side), Image.Resampling.BOX)
    return np.asarray(image, dtype=np.uint8).reshape(-1, 3)


def _initial_centers(sample_rgb: np.ndarray, plate_count: int) -> np.ndarray:
    lab = rgb_u8_to_oklab(sample_rgb)
    luminance_order = np.argsort(lab[:, 0])
    quantiles = np.linspace(0, len(luminance_order) - 1, plate_count, dtype=np.int64)
    centers = lab[luminance_order[quantiles]].copy()
    labels = np.zeros(len(lab), dtype=np.int64)
    for _ in range(10):
        distances = np.linalg.norm(lab[:, None, :] - centers[None, :, :], axis=2)
        labels = np.argmin(distances, axis=1)
        for idx in range(len(centers)):
            members = lab[labels == idx]
            if len(members):
                centers[idx] = members.mean(axis=0)
    return centers


def _assign_labels_chunked(
    lab: np.ndarray,
    centers: np.ndarray,
    chunk_size: int = 65_536,
) -> np.ndarray:
    labels = np.empty(len(lab), dtype=np.int64)
    for start in range(0, len(lab), chunk_size):
        block = lab[start : start + chunk_size]
        distances = np.linalg.norm(block[:, None, :] - centers[None, :, :], axis=2)
        labels[start : start + len(block)] = np.argmin(distances, axis=1)
    return labels


def _cluster_image(rgb: np.ndarray, plate_count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    flat_rgb = rgb.reshape(-1, 3)
    sample = _sample_pixels(rgb)
    centers = _initial_centers(sample, plate_count)
    full_lab = rgb_u8_to_oklab(flat_rgb)
    labels = _assign_labels_chunked(full_lab, centers)

    for idx in range(len(centers)):
        members = full_lab[labels == idx]
        if len(members):
            centers[idx] = members.mean(axis=0)
    labels = _assign_labels_chunked(full_lab, centers)

    counts = np.bincount(labels, minlength=len(centers))
    order = np.argsort(-counts)
    remap = np.zeros(len(centers), dtype=np.int64)
    for new_idx, old_idx in enumerate(order):
        remap[old_idx] = new_idx
    ordered_centers = centers[order]
    ordered_counts = counts[order]
    ordered_labels = remap[labels]
    return ordered_centers, ordered_labels, ordered_counts


def _mask_to_svg_path(mask: np.ndarray) -> str:
    parts: list[str] = []
    for y, row in enumerate(mask):
        padded = np.pad(row.astype(np.int8), (1, 1), constant_values=0)
        changes = np.flatnonzero(np.diff(padded))
        for start, end in zip(changes[0::2], changes[1::2], strict=True):
            parts.append(f"M{start} {y}L{end} {y}L{end} {y + 1}L{start} {y + 1}Z")
    return "".join(parts)


def _write_plate_svg(path: Path, mask: np.ndarray, color: tuple[int, int, int]) -> None:
    height, width = mask.shape
    fill = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
    d = _mask_to_svg_path(mask)
    kento_size = max(8, round(min(width, height) * 0.018))
    kento_offset = max(12, round(min(width, height) * 0.03))
    registration = (
        f'<path id="kento-left" fill="none" stroke="#000" stroke-width="1" '
        f'd="M{kento_offset} {height - kento_offset}'
        f'L{kento_offset + kento_size} {height - kento_offset}'
        f'L{kento_offset + kento_size} {height - kento_offset + kento_size}"/>'
        f'<path id="kento-right" fill="none" stroke="#000" stroke-width="1" '
        f'd="M{width - kento_offset - kento_size} {height - kento_offset}'
        f'L{width - kento_offset} {height - kento_offset}'
        f'L{width - kento_offset} {height - kento_offset + kento_size}"/>'
    )
    plate_path = f'<path id="image-derived-mask" fill="{fill}" d="{d}"/>' if d else ""
    path.write_text(
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                (
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                    f'height="{height}" viewBox="0 0 {width} {height}">'
                ),
                '<g id="registration">',
                registration,
                "</g>",
                '<g id="plate">',
                plate_path,
                "</g>",
                "</svg>",
            ]
        ),
        encoding="utf-8",
    )


def _write_contact_sheet(plate_images: list[Path], out_path: Path, thumb_size: int = 160) -> None:
    if not plate_images:
        return
    cols = min(6, len(plate_images))
    rows = math.ceil(len(plate_images) / cols)
    sheet = Image.new("RGB", (cols * thumb_size, rows * (thumb_size + 24)), (248, 245, 236))
    draw = ImageDraw.Draw(sheet)
    for idx, plate_path in enumerate(plate_images):
        with Image.open(plate_path) as opened:
            tile = opened.convert("RGBA")
            tile.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
            background = Image.new("RGBA", (thumb_size, thumb_size), (248, 245, 236, 255))
            offset = ((thumb_size - tile.width) // 2, (thumb_size - tile.height) // 2)
            background.alpha_composite(tile, offset)
        x = (idx % cols) * thumb_size
        y = (idx // cols) * (thumb_size + 24)
        sheet.paste(background.convert("RGB"), (x, y))
        draw.text((x + 6, y + thumb_size + 4), f"plate {idx + 1:02d}", fill=(20, 20, 20))
    sheet.save(out_path)


def _json_path(path: Path) -> str:
    return str(path.resolve())


def run_reconstruction_workflow(
    input_path: str | Path,
    output_dir: str | Path,
    plate_count: int = 27,
    max_side: int = 1024,
    case_id: str | None = None,
) -> dict[str, Any]:
    """Generate image-derived reconstruction plates for one input image.

    This is the truthful baseline workflow: plates are disjoint color-cluster masks, and
    their opaque composite reconstructs the input as a quantized image. It is not the
    final overprint optimizer.
    """

    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(source)
    plate_count = max(2, min(64, int(plate_count)))
    max_side = max(128, min(2048, int(max_side)))

    safe_stem = "".join(char if char.isalnum() or char in "-_" else "-" for char in source.stem)
    run_id = case_id or f"{safe_stem}-{time.strftime('%Y%m%d-%H%M%S')}"
    case_dir = Path(output_dir) / run_id
    source_dir = case_dir / "source"
    plates_dir = case_dir / "plates"
    masks_dir = case_dir / "masks"
    cumulative_dir = case_dir / "cumulative"
    preview_dir = case_dir / "preview"
    for directory in (source_dir, plates_dir, masks_dir, cumulative_dir, preview_dir):
        directory.mkdir(parents=True, exist_ok=True)

    copied_source = source_dir / source.name
    shutil.copy2(source, copied_source)

    reference = ingest_image(source)
    analysis = analyze_reference(reference, clusters=min(12, plate_count))

    image = _resize_rgb(source, max_side=max_side)
    rgb = np.asarray(image, dtype=np.uint8)
    height, width = rgb.shape[:2]
    centers, labels, counts = _cluster_image(rgb, plate_count=plate_count)
    center_rgbs = oklab_to_rgb_u8(centers)
    labels_2d = labels.reshape(height, width)
    reconstruction = center_rgbs[labels].reshape(height, width, 3).astype(np.uint8)

    paper = np.zeros_like(reconstruction)
    paper[:, :] = np.asarray(BuildDefaults().paper_color_rgb, dtype=np.uint8)
    cumulative = paper.copy()
    cumulative_paths: list[Path] = []
    plate_paths: list[Path] = []
    mask_paths: list[Path] = []
    svg_paths: list[Path] = []
    plates: list[dict[str, Any]] = []
    total = int(counts.sum())

    for idx, (color_arr, count) in enumerate(zip(center_rgbs, counts, strict=True), start=1):
        mask = labels_2d == (idx - 1)
        color = tuple(int(value) for value in color_arr)
        alpha = np.where(mask, 255, 0).astype(np.uint8)

        mask_path = masks_dir / f"plate_{idx:02d}_mask.png"
        Image.fromarray(alpha, "L").save(mask_path)
        mask_paths.append(mask_path)

        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[..., :3] = np.asarray(color, dtype=np.uint8)
        rgba[..., 3] = alpha
        plate_path = plates_dir / f"plate_{idx:02d}_ink.png"
        Image.fromarray(rgba, "RGBA").save(plate_path)
        plate_paths.append(plate_path)

        svg_path = plates_dir / f"plate_{idx:02d}.svg"
        _write_plate_svg(svg_path, mask, color)
        svg_paths.append(svg_path)

        cumulative[mask] = np.asarray(color, dtype=np.uint8)
        cumulative_path = cumulative_dir / f"{idx:03d}_plate_{idx:02d}.png"
        Image.fromarray(cumulative, "RGB").save(cumulative_path)
        cumulative_paths.append(cumulative_path)

        plates.append(
            {
                "plate": idx,
                "rgb": color,
                "coverage": float(count / max(1, total)),
                "mask_png": _json_path(mask_path),
                "ink_png": _json_path(plate_path),
                "svg": _json_path(svg_path),
            }
        )

    input_preview = preview_dir / "input_resized.png"
    reconstruction_path = preview_dir / "reconstruction.png"
    diff_path = preview_dir / "difference.png"
    contact_sheet = preview_dir / "plate_contact_sheet.png"
    Image.fromarray(rgb, "RGB").save(input_preview)
    Image.fromarray(reconstruction, "RGB").save(reconstruction_path)
    diff = np.abs(rgb.astype(np.int16) - reconstruction.astype(np.int16)).astype(np.uint8)
    Image.fromarray(diff, "RGB").save(diff_path)
    _write_contact_sheet(plate_paths, contact_sheet)

    error = rgb.astype(np.float32) - reconstruction.astype(np.float32)
    rmse = float(np.sqrt(np.mean(error**2)))
    mae = float(np.mean(np.abs(rgb.astype(np.float32) - reconstruction.astype(np.float32))))
    manifest = {
        "workflow": "image_derived_reconstruction_v1",
        "case_id": run_id,
        "case_dir": _json_path(case_dir),
        "source": _json_path(source),
        "copied_source": _json_path(copied_source),
        "input_size": {"width": width, "height": height},
        "plate_count": len(plates),
        "metrics": {
            "rmse_rgb": rmse,
            "mae_rgb": mae,
            "quantized_similarity": max(0.0, 1.0 - (rmse / 255.0)),
        },
        "mcp_ingest": {
            "image_id": reference.image_id,
            "session_id": reference.session_id,
            "analysis_id": analysis.analysis_id,
            "edge_density": analysis.edge_density,
            "complexity_score": analysis.complexity_score,
        },
        "previews": {
            "input_resized": _json_path(input_preview),
            "reconstruction": _json_path(reconstruction_path),
            "difference": _json_path(diff_path),
            "contact_sheet": _json_path(contact_sheet),
        },
        "plates": plates,
        "warnings": [
            "reconstruction_baseline_not_final_overprint_optimizer",
            "svg_masks_are_exact_raster_run_vectors_not_cnc_final_toolpaths",
            "pigment_mixing_not_calibrated_in_this_run",
        ],
    }

    manifest_path = case_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    readme = case_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                f"# {run_id}",
                "",
                (
                    "This run is image-derived reconstruction output, "
                    "not the old geometric placeholder plan."
                ),
                "",
                f"- Source: `{source}`",
                f"- Plates: {len(plates)}",
                f"- Quantized similarity: {manifest['metrics']['quantized_similarity']:.4f}",
                f"- RGB RMSE: {rmse:.2f}",
                "",
                "Open `preview/reconstruction.png` beside `preview/input_resized.png` first.",
                (
                    "Use `plates/*.svg` only as diagnostic vector masks; "
                    "CNC-ready contour strategy is next."
                ),
            ]
        ),
        encoding="utf-8",
    )
    return manifest
