from __future__ import annotations

from pathlib import Path

from emma_mokuhanga import config


def test_locked_defaults() -> None:
    defaults = config.BuildDefaults()
    assert defaults.subject_agnostic is True
    assert defaults.allow_multi_zone_blocks is True
    assert defaults.target_block_count == 27
    assert defaults.min_block_count == 24
    assert defaults.max_block_count == 32


def test_a1_profile_defaults() -> None:
    profile = config.A1Profile()
    assert profile.print_width_mm == 594.0
    assert profile.print_height_mm == 841.0
    assert profile.stock_width_mm > profile.print_width_mm
    assert profile.stock_height_mm > profile.print_height_mm
    assert profile.image_width_mm < profile.print_width_mm


def test_default_corpus_path_is_machine_neutral(monkeypatch) -> None:
    monkeypatch.delenv("EMMA_TEST_IMAGES_DIR", raising=False)

    path = config.default_test_images_dir()

    assert path == Path.home() / ".emma-mokuhanga" / "test-images"
    assert path.relative_to(Path.home()) == Path(".emma-mokuhanga/test-images")


def test_config_loads_explicit_corpus_path(monkeypatch, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    monkeypatch.setenv("EMMA_TEST_IMAGES_DIR", str(corpus))

    loaded = config.get_config()

    assert loaded.test_images_dir == corpus
