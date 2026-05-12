"""Initial SVG path geometry validator.

This is a conservative first gate for generated vectors. It intentionally handles a
small path subset used in tests and early exports. More SVG path command support can
be added behind the same report contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from emma_mokuhanga.contracts import GeometryIssue, GeometryValidationReport

TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")
Point = tuple[float, float]


@dataclass(frozen=True)
class ParsedPath:
    points: tuple[Point, ...]
    closed: bool
    unsupported: tuple[str, ...]


def _issue(code: str, message: str, path_index: int | None = None) -> GeometryIssue:
    return GeometryIssue(code=code, message=message, path_index=path_index)


def parse_path(path_data: str) -> ParsedPath:
    tokens = TOKEN_RE.findall(path_data)
    points: list[Point] = []
    unsupported: list[str] = []
    closed = False
    idx = 0
    command = ""
    while idx < len(tokens):
        token = tokens[idx]
        if token.isalpha():
            command = token
            idx += 1
            if command in {"Z", "z"}:
                closed = True
            elif command not in {"M", "m", "L", "l"}:
                unsupported.append(command)
            continue
        if command not in {"M", "m", "L", "l"}:
            idx += 1
            continue
        if idx + 1 >= len(tokens):
            break
        try:
            x = float(tokens[idx])
            y = float(tokens[idx + 1])
        except ValueError:
            idx += 1
            continue
        points.append((x, y))
        idx += 2
    if closed and len(points) > 1 and points[0] != points[-1]:
        points.append(points[0])
    return ParsedPath(points=tuple(points), closed=closed, unsupported=tuple(unsupported))


def _zero_length_segments(points: tuple[Point, ...]) -> bool:
    return any(a == b for a, b in zip(points, points[1:], strict=False))


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def on_segment(p: Point, q: Point, r: Point) -> bool:
        return (
            min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
            and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
        )

    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True
    if o1 == 0 and on_segment(a, c, b):
        return True
    if o2 == 0 and on_segment(a, d, b):
        return True
    if o3 == 0 and on_segment(c, a, d):
        return True
    if o4 == 0 and on_segment(c, b, d):
        return True
    return False


def _self_intersects(points: tuple[Point, ...]) -> bool:
    segments = list(zip(points, points[1:], strict=False))
    for idx, (a, b) in enumerate(segments):
        for other_idx, (c, d) in enumerate(segments):
            if other_idx <= idx + 1:
                continue
            if idx == 0 and other_idx == len(segments) - 1:
                continue
            if _segments_intersect(a, b, c, d):
                return True
    return False


def validate_svg_paths(paths: list[str]) -> GeometryValidationReport:
    issues: list[GeometryIssue] = []
    seen: set[str] = set()
    for idx, path_data in enumerate(paths):
        normalized = " ".join(path_data.split())
        if normalized in seen:
            issues.append(_issue("duplicate_path", "Duplicate vector path.", idx))
        seen.add(normalized)

        parsed = parse_path(path_data)
        if parsed.unsupported:
            issues.append(
                _issue(
                    "unsupported_path_command",
                    f"Unsupported path commands: {', '.join(parsed.unsupported)}.",
                    idx,
                )
            )
        if len(parsed.points) < 2:
            issues.append(_issue("empty_or_short_path", "Path has fewer than two points.", idx))
            continue
        if not parsed.closed:
            issues.append(_issue("open_path", "Path is not explicitly closed.", idx))
        if _zero_length_segments(parsed.points):
            issues.append(
                _issue("zero_length_segment", "Path contains a zero-length segment.", idx)
            )
        if _self_intersects(parsed.points):
            issues.append(_issue("self_intersection", "Path contains a self-intersection.", idx))

    return GeometryValidationReport(ok=not issues, issues=issues, path_count=len(paths))
