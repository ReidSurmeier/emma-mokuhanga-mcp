from __future__ import annotations

from pathlib import Path

from emma_mokuhanga.tools.analysis import analyze_reference
from emma_mokuhanga.tools.ingest import ingest_image


def test_analyze_reference_is_subject_agnostic(non_emma_image: Path, tmp_path: Path) -> None:
    reference = ingest_image(non_emma_image, home=tmp_path)
    analysis = analyze_reference(reference)
    assert analysis.image_id == reference.image_id
    assert len(analysis.palette) == 8
    assert 0.0 <= analysis.edge_density <= 1.0
    assert 0.0 <= analysis.complexity_score <= 1.0
    assert "subject_agnostic_analysis" in analysis.notes

