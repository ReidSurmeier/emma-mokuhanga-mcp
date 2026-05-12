"""Pydantic contracts for Emma-style mokuhanga print planning."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RGB = tuple[int, int, int]


class OpacityClass(StrEnum):
    TRANSPARENT = "transparent"
    SEMI_TRANSPARENT = "semi_transparent"
    SEMI_OPAQUE = "semi_opaque"
    OPAQUE = "opaque"


class MaskRole(StrEnum):
    BASE_WASH = "base_wash"
    SUPPORT = "support"
    VISIBLE_COLOR = "visible_color"
    ACCENT = "accent"
    KEY = "key"
    CORRECTION = "correction"


class RenderTier(StrEnum):
    T0 = "t0"
    T1 = "t1"
    T2 = "t2"


class ReferenceImage(BaseModel):
    image_id: str
    session_id: str
    source_path: Path
    stored_path: Path
    preview_path: Path
    sha256: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    mode: str
    format: str | None = None
    profile_name: str | None = None


class PaletteCluster(BaseModel):
    cluster_id: str
    rgb: RGB
    oklab: tuple[float, float, float]
    coverage: float = Field(ge=0.0, le=1.0)


class ImageAnalysis(BaseModel):
    analysis_id: str
    image_id: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    palette: list[PaletteCluster]
    edge_density: float = Field(ge=0.0, le=1.0)
    color_entropy: float = Field(ge=0.0)
    complexity_score: float = Field(ge=0.0, le=1.0)
    suggested_grid: tuple[int, int]
    notes: list[str] = Field(default_factory=list)


class CNCProfile(BaseModel):
    name: str = "A1 default"
    print_width_mm: float = Field(default=594.0, gt=0)
    print_height_mm: float = Field(default=841.0, gt=0)
    margin_mm: float = Field(default=25.0, ge=0)
    kento_offset_mm: float = Field(default=18.0, ge=0)
    kento_size_mm: float = Field(default=12.0, gt=0)
    stock_width_mm: float = Field(default=1219.2, gt=0)
    stock_height_mm: float = Field(default=2438.4, gt=0)
    bit_diameter_in: float = Field(default=1 / 16, gt=0)


class PigmentProfile(BaseModel):
    pigment_id: str
    name: str
    family: str
    masstone_rgb: RGB
    opacity: OpacityClass
    tint_strength: float = Field(ge=0.0, le=1.0)
    default_load: float = Field(ge=0.0, le=1.0)
    notes: str = ""

    @field_validator("masstone_rgb")
    @classmethod
    def _rgb_in_range(cls, value: RGB) -> RGB:
        if any(channel < 0 or channel > 255 for channel in value):
            raise ValueError("RGB channels must be 0..255")
        return value


class PigmentComponent(BaseModel):
    pigment_id: str
    amount: float = Field(gt=0.0, le=1.0)


class PigmentRecipe(BaseModel):
    recipe_id: str
    name: str
    components: list[PigmentComponent]
    estimated_rgb: RGB
    opacity: OpacityClass
    load: float = Field(ge=0.0, le=1.0)
    notes: str = ""

    @model_validator(mode="after")
    def _has_components(self) -> PigmentRecipe:
        if not self.components:
            raise ValueError("PigmentRecipe requires at least one component")
        return self


class MaskSpec(BaseModel):
    mask_id: str
    role: MaskRole
    shape: Literal["full", "rect", "ellipse", "band", "tile"]
    bbox_norm: tuple[float, float, float, float] = Field(
        description="Normalized left, top, right, bottom coordinates."
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("bbox_norm")
    @classmethod
    def _bbox_valid(
        cls,
        value: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        left, top, right, bottom = value
        if not (0.0 <= left <= right <= 1.0 and 0.0 <= top <= bottom <= 1.0):
            raise ValueError("bbox_norm must be normalized and ordered")
        if left == right or top == bottom:
            raise ValueError("bbox_norm must have non-zero area")
        return value


class ColorZone(BaseModel):
    zone_id: str
    mask_id: str
    recipe: PigmentRecipe
    role: MaskRole
    application_notes: str = ""


class Block(BaseModel):
    block_id: str
    impression_id: str
    color_zone_ids: list[str]
    cnc_status: Literal["not_validated", "valid", "invalid"] = "not_validated"


class Impression(BaseModel):
    impression_id: str
    block_id: str
    order: int = Field(ge=1)
    role: MaskRole
    color_zones: list[ColorZone]
    notes: str = ""

    @model_validator(mode="after")
    def _has_color_zone(self) -> Impression:
        if not self.color_zones:
            raise ValueError("Impression requires at least one color zone")
        return self


class PlanScore(BaseModel):
    visual_similarity: float = Field(ge=0.0, le=1.0)
    emma_rhythm: float = Field(ge=0.0, le=1.0)
    block_count_fit: float = Field(ge=0.0, le=1.0)
    process_risk: float = Field(ge=0.0, le=1.0)
    cnc_risk: float = Field(ge=0.0, le=1.0)


class PrintPlan(BaseModel):
    plan_id: str
    image_id: str
    analysis_id: str
    target_block_count: int = 27
    subject_agnostic: bool = True
    cnc_profile: CNCProfile = Field(default_factory=CNCProfile)
    masks: list[MaskSpec]
    impressions: list[Impression]
    blocks: list[Block]
    score: PlanScore | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_block_impression_invariants(self) -> PrintPlan:
        impression_ids = [impression.impression_id for impression in self.impressions]
        block_ids = [block.block_id for block in self.blocks]
        if len(impression_ids) != len(set(impression_ids)):
            raise ValueError("impression_id values must be unique")
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("block_id values must be unique")
        if len(self.impressions) != len(self.blocks):
            raise ValueError("one block is required for each impression")

        impression_by_id = {impression.impression_id: impression for impression in self.impressions}
        block_by_id = {block.block_id: block for block in self.blocks}
        for impression in self.impressions:
            block = block_by_id.get(impression.block_id)
            if block is None:
                raise ValueError(f"missing block for impression {impression.impression_id}")
            if block.impression_id != impression.impression_id:
                raise ValueError("block.impression_id must match impression.impression_id")
            zone_ids = {zone.zone_id for zone in impression.color_zones}
            if set(block.color_zone_ids) != zone_ids:
                raise ValueError("block color_zone_ids must match impression color zones")

        for block in self.blocks:
            if block.impression_id not in impression_by_id:
                raise ValueError(f"missing impression for block {block.block_id}")

        orders = [impression.order for impression in self.impressions]
        if len(orders) != len(set(orders)):
            raise ValueError("impression order values must be unique")
        return self


class RenderArtifact(BaseModel):
    plan_id: str
    tier: RenderTier
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    composite_path: Path
    cumulative_paths: list[Path]
    warnings: list[str] = Field(default_factory=list)


class GeometryIssue(BaseModel):
    code: str
    message: str
    path_index: int | None = None
    severity: Literal["error", "warning"] = "error"


class GeometryValidationReport(BaseModel):
    ok: bool
    issues: list[GeometryIssue] = Field(default_factory=list)
    path_count: int = Field(ge=0)
