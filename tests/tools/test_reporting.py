from __future__ import annotations

from pathlib import Path

from emma_mokuhanga.reporting import build_report, process_image


def test_process_image_writes_case_report(non_emma_image: Path, tmp_path: Path) -> None:
    case = process_image(non_emma_image, report_dir=tmp_path / "report")
    assert case.page_path.exists()
    assert (case.case_dir / "input_preview.jpg").exists()
    assert (case.case_dir / "t0_composite.png").exists()
    assert (case.case_dir / "t1_composite.png").exists()
    assert (case.case_dir / "plan.json").exists()
    assert len(case.plan.impressions) == 27


def test_build_report_writes_index(test_images_dir: Path, tmp_path: Path) -> None:
    cases = build_report(test_images_dir, tmp_path / "report")
    assert len(cases) >= 3
    assert (tmp_path / "report" / "index.html").exists()

