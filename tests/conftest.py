from __future__ import annotations

import os
from pathlib import Path

import pytest


def _default_corpus() -> Path:
    return Path("/mnt/c/Users/reidsurmeier2/Books/printmaking/test images\uf028")


@pytest.fixture(scope="session")
def test_images_dir() -> Path:
    path = Path(os.environ.get("EMMA_TEST_IMAGES_DIR", _default_corpus()))
    if not path.exists():
        matches = list(Path("/mnt/c/Users/reidsurmeier2/Books/printmaking").glob("test images*"))
        if matches:
            path = matches[0]
    if not path.exists():
        pytest.skip(f"external test image corpus not found: {path}")
    return path


@pytest.fixture(scope="session")
def image_files(test_images_dir: Path) -> list[Path]:
    files = sorted(
        path
        for path in test_images_dir.iterdir()
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    )
    if not files:
        pytest.skip(f"no image fixtures found in {test_images_dir}")
    return files


@pytest.fixture(scope="session")
def emma_image(image_files: list[Path]) -> Path:
    for path in image_files:
        if "emma" in path.name.lower():
            return path
    return image_files[0]


@pytest.fixture(scope="session")
def frankenthaler_image(image_files: list[Path]) -> Path:
    for path in image_files:
        if "frankenthaler" in path.name.lower():
            return path
    return image_files[min(1, len(image_files) - 1)]


@pytest.fixture(scope="session")
def non_emma_image(image_files: list[Path]) -> Path:
    for path in image_files:
        name = path.name.lower()
        if "emma" not in name and "frankenthaler" not in name:
            return path
    return image_files[-1]

