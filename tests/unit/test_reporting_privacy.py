from __future__ import annotations

from pathlib import Path

from PIL import Image

from emma_mokuhanga.reporting import process_image


def test_case_json_does_not_expose_absolute_host_paths(tmp_path: Path) -> None:
    source_dir = tmp_path / "private-source-location"
    source_dir.mkdir()
    source = source_dir / "fixture.png"
    Image.new("RGB", (8, 8), (80, 120, 160)).save(source)
    report_dir = tmp_path / "published-report"

    case = process_image(source, report_dir=report_dir)

    for path in case.case_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert str(tmp_path) not in text, f"{path.name} exposes an absolute host path"
