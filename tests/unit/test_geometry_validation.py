from __future__ import annotations

from emma_mokuhanga.tools.geometry import validate_svg_paths


def _codes(paths: list[str]) -> set[str]:
    return {issue.code for issue in validate_svg_paths(paths).issues}


def test_valid_closed_path_passes() -> None:
    report = validate_svg_paths(["M 0 0 L 10 0 L 10 10 L 0 10 Z"])
    assert report.ok is True
    assert report.path_count == 1


def test_open_path_rejected() -> None:
    assert "open_path" in _codes(["M 0 0 L 10 0 L 10 10"])


def test_duplicate_path_rejected() -> None:
    path = "M 0 0 L 10 0 L 10 10 L 0 10 Z"
    assert "duplicate_path" in _codes([path, path])


def test_zero_length_segment_rejected() -> None:
    assert "zero_length_segment" in _codes(["M 0 0 L 0 0 L 10 0 Z"])


def test_self_intersection_rejected() -> None:
    assert "self_intersection" in _codes(["M 0 0 L 10 10 L 0 10 L 10 0 Z"])


def test_unsupported_command_rejected_for_initial_gate() -> None:
    assert "unsupported_path_command" in _codes(["M 0 0 C 1 1 2 2 3 3 Z"])

