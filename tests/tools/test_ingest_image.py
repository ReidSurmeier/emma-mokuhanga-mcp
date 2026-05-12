from __future__ import annotations

from pathlib import Path

import pytest

from emma_mokuhanga.tools.ingest import ingest_image


@pytest.mark.parametrize("fixture_name", ["emma", "frankenthaler", "non_emma"])
def test_ingest_external_fixture(
    fixture_name: str,
    emma_image: Path,
    frankenthaler_image: Path,
    non_emma_image: Path,
    tmp_path: Path,
) -> None:
    fixture = {
        "emma": emma_image,
        "frankenthaler": frankenthaler_image,
        "non_emma": non_emma_image,
    }[fixture_name]
    reference = ingest_image(fixture, home=tmp_path)
    assert reference.width > 0
    assert reference.height > 0
    assert reference.stored_path.exists()
    assert reference.preview_path.exists()
    assert len(reference.sha256) == 64


def test_ingest_rejects_non_image(tmp_path: Path) -> None:
    text = tmp_path / "not-image.txt"
    text.write_text("not an image", encoding="utf-8")
    with pytest.raises(ValueError, match="not a readable image"):
        ingest_image(text, home=tmp_path)

