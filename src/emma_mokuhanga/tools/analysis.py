"""Analysis tool wrapper."""

from __future__ import annotations

from emma_mokuhanga.contracts import ImageAnalysis, ReferenceImage
from emma_mokuhanga.image.analysis import analyze_reference as _analyze_reference


def analyze_reference(reference: ReferenceImage, clusters: int = 8) -> ImageAnalysis:
    return _analyze_reference(reference, clusters=clusters)

