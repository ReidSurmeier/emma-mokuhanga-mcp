"""Configuration defaults for the mokuhanga planner."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def default_home() -> Path:
    """Return the runtime home without embedding a host-specific path."""

    return Path(os.environ.get("EMMA_HOME", Path.home() / ".emma-mokuhanga"))


def default_test_images_dir() -> Path:
    """Return the optional corpus path, defaulting inside the runtime home."""

    return Path(
        os.environ.get(
            "EMMA_TEST_IMAGES_DIR",
            default_home() / "test-images",
        )
    )


class BuildDefaults(BaseModel):
    """Defaults that encode locked project decisions."""

    target_block_count: int = 27
    min_block_count: int = 24
    max_block_count: int = 32
    subject_agnostic: bool = True
    allow_multi_zone_blocks: bool = True
    paper_color_rgb: tuple[int, int, int] = (248, 245, 236)


class A1Profile(BaseModel):
    """Default A1 physical profile.

    Margins are conservative placeholders until the final kento layout is chosen.
    """

    name: str = "A1 default"
    print_width_mm: float = 594.0
    print_height_mm: float = 841.0
    margin_mm: float = 25.0
    kento_offset_mm: float = 18.0
    kento_size_mm: float = 12.0
    stock_width_mm: float = 1219.2
    stock_height_mm: float = 2438.4
    bit_diameter_in: float = Field(default=1 / 16, gt=0)

    @property
    def image_width_mm(self) -> float:
        return self.print_width_mm - (2 * self.margin_mm)

    @property
    def image_height_mm(self) -> float:
        return self.print_height_mm - (2 * self.margin_mm)


class AppConfig(BaseModel):
    """Runtime configuration."""

    home: Path = Field(default_factory=default_home)
    test_images_dir: Path = Field(default_factory=default_test_images_dir)
    defaults: BuildDefaults = Field(default_factory=BuildDefaults)
    a1_profile: A1Profile = Field(default_factory=A1Profile)


def get_config() -> AppConfig:
    """Load configuration from environment-backed defaults."""

    return AppConfig()
