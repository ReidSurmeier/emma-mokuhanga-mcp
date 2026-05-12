"""Geometry validation tool wrapper."""

from __future__ import annotations

from emma_mokuhanga.contracts import GeometryValidationReport
from emma_mokuhanga.geometry.validator import validate_svg_paths as _validate_svg_paths


def validate_svg_paths(paths: list[str]) -> GeometryValidationReport:
    return _validate_svg_paths(paths)

