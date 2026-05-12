from __future__ import annotations

from emma_mokuhanga.config import A1Profile, BuildDefaults, get_config


def test_locked_defaults() -> None:
    defaults = BuildDefaults()
    assert defaults.subject_agnostic is True
    assert defaults.allow_multi_zone_blocks is True
    assert defaults.target_block_count == 27
    assert defaults.min_block_count == 24
    assert defaults.max_block_count == 32


def test_a1_profile_defaults() -> None:
    profile = A1Profile()
    assert profile.print_width_mm == 594.0
    assert profile.print_height_mm == 841.0
    assert profile.stock_width_mm > profile.print_width_mm
    assert profile.stock_height_mm > profile.print_height_mm
    assert profile.image_width_mm < profile.print_width_mm


def test_config_loads_corpus_path() -> None:
    config = get_config()
    assert "printmaking" in str(config.test_images_dir)

