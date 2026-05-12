"""Deterministic image analysis for print planning."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from emma_mokuhanga.contracts import ImageAnalysis, PaletteCluster, ReferenceImage
from emma_mokuhanga.image.color import kmeans_oklab, oklab_to_rgb_u8
from emma_mokuhanga.paths import new_id


def _load_rgb(path: Path, max_side: int = 192) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return image


def _edge_density(image: Image.Image) -> float:
    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    arr = np.asarray(edges, dtype=np.float64) / 255.0
    if arr.size == 0:
        return 0.0
    threshold = float(arr.mean() + arr.std())
    return float(np.mean(arr > threshold))


def analyze_reference(reference: ReferenceImage, clusters: int = 8) -> ImageAnalysis:
    image = _load_rgb(reference.stored_path)
    rgb = np.asarray(image, dtype=np.uint8)
    centers, labels = kmeans_oklab(rgb, k=clusters)
    counts = np.bincount(labels, minlength=len(centers)).astype(np.float64)
    coverage = counts / max(1, counts.sum())
    rgb_centers = oklab_to_rgb_u8(centers)

    order = np.argsort(-coverage)
    palette: list[PaletteCluster] = []
    for out_idx, center_idx in enumerate(order):
        lab = centers[center_idx]
        rgb_tuple = tuple(int(value) for value in rgb_centers[center_idx])
        palette.append(
            PaletteCluster(
                cluster_id=f"cluster_{out_idx + 1:02d}",
                rgb=rgb_tuple,  # type: ignore[arg-type]
                oklab=(float(lab[0]), float(lab[1]), float(lab[2])),
                coverage=float(coverage[center_idx]),
            )
        )

    edge_density = _edge_density(image)
    nonzero = coverage[coverage > 0]
    entropy = float(-np.sum(nonzero * np.log2(nonzero))) if len(nonzero) else 0.0
    max_entropy = float(np.log2(max(2, len(coverage))))
    normalized_entropy = entropy / max_entropy if max_entropy else 0.0
    complexity = float(np.clip((0.55 * edge_density) + (0.45 * normalized_entropy), 0.0, 1.0))

    aspect = reference.width / reference.height
    grid_cols = 9 if aspect < 0.9 else 10
    grid_rows = 13 if aspect < 0.9 else 10
    return ImageAnalysis(
        analysis_id=new_id("analysis"),
        image_id=reference.image_id,
        width=reference.width,
        height=reference.height,
        palette=palette,
        edge_density=edge_density,
        color_entropy=entropy,
        complexity_score=complexity,
        suggested_grid=(grid_cols, grid_rows),
        notes=["subject_agnostic_analysis", "sam_optional_not_required"],
    )

