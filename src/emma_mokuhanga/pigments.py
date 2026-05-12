"""Starter pigment profiles and recipe helpers."""

from __future__ import annotations

from .contracts import RGB, OpacityClass, PigmentComponent, PigmentProfile, PigmentRecipe

STARTER_PIGMENTS: tuple[PigmentProfile, ...] = (
    PigmentProfile(
        pigment_id="cad_red",
        name="Cadmium red",
        family="warm_red",
        masstone_rgb=(190, 39, 31),
        opacity=OpacityClass.SEMI_OPAQUE,
        tint_strength=0.88,
        default_load=0.68,
        notes="Strong warm mineral red; assumed high covering power.",
    ),
    PigmentProfile(
        pigment_id="cad_yellow",
        name="Cadmium yellow",
        family="warm_yellow",
        masstone_rgb=(241, 185, 42),
        opacity=OpacityClass.SEMI_OPAQUE,
        tint_strength=0.82,
        default_load=0.62,
        notes="Opaque warm yellow useful for late warmth and accents.",
    ),
    PigmentProfile(
        pigment_id="yellow_ochre",
        name="Yellow ochre",
        family="earth_yellow",
        masstone_rgb=(185, 132, 57),
        opacity=OpacityClass.SEMI_TRANSPARENT,
        tint_strength=0.56,
        default_load=0.48,
        notes="Earth yellow support for skin and warm structure.",
    ),
    PigmentProfile(
        pigment_id="ultramarine",
        name="Ultramarine blue",
        family="cool_blue",
        masstone_rgb=(45, 66, 156),
        opacity=OpacityClass.TRANSPARENT,
        tint_strength=0.62,
        default_load=0.42,
        notes="Transparent blue underwash and optical support.",
    ),
    PigmentProfile(
        pigment_id="prussian_blue",
        name="Prussian blue",
        family="deep_blue",
        masstone_rgb=(19, 49, 91),
        opacity=OpacityClass.SEMI_TRANSPARENT,
        tint_strength=0.9,
        default_load=0.5,
        notes="High tint strength cool dark.",
    ),
    PigmentProfile(
        pigment_id="viridian",
        name="Viridian",
        family="green",
        masstone_rgb=(40, 128, 101),
        opacity=OpacityClass.TRANSPARENT,
        tint_strength=0.58,
        default_load=0.38,
        notes="Transparent green for cool supports and neutralization.",
    ),
    PigmentProfile(
        pigment_id="alizarin",
        name="Alizarin crimson",
        family="cool_red",
        masstone_rgb=(132, 25, 53),
        opacity=OpacityClass.TRANSPARENT,
        tint_strength=0.75,
        default_load=0.45,
        notes="Transparent red glaze approximation.",
    ),
    PigmentProfile(
        pigment_id="burnt_sienna",
        name="Burnt sienna",
        family="earth_red",
        masstone_rgb=(137, 73, 43),
        opacity=OpacityClass.SEMI_TRANSPARENT,
        tint_strength=0.52,
        default_load=0.46,
        notes="Warm earth for structure and muted chroma.",
    ),
    PigmentProfile(
        pigment_id="raw_umber",
        name="Raw umber",
        family="earth_dark",
        masstone_rgb=(92, 74, 45),
        opacity=OpacityClass.SEMI_TRANSPARENT,
        tint_strength=0.5,
        default_load=0.42,
        notes="Muted dark earth.",
    ),
    PigmentProfile(
        pigment_id="sumi",
        name="Sumi",
        family="black",
        masstone_rgb=(20, 18, 16),
        opacity=OpacityClass.OPAQUE,
        tint_strength=0.96,
        default_load=0.62,
        notes="Late key/detail dark.",
    ),
    PigmentProfile(
        pigment_id="titanium_white",
        name="Titanium white",
        family="white",
        masstone_rgb=(246, 243, 232),
        opacity=OpacityClass.OPAQUE,
        tint_strength=0.35,
        default_load=0.3,
        notes="Opaque lightener for premixed zones, not paper reserve.",
    ),
)


def list_pigments() -> list[PigmentProfile]:
    return list(STARTER_PIGMENTS)


def pigment_by_id() -> dict[str, PigmentProfile]:
    return {pigment.pigment_id: pigment for pigment in STARTER_PIGMENTS}


def recipe_from_pigment(
    pigment: PigmentProfile,
    amount: float = 1.0,
    load: float | None = None,
) -> PigmentRecipe:
    return PigmentRecipe(
        recipe_id=f"recipe_{pigment.pigment_id}",
        name=pigment.name,
        components=[PigmentComponent(pigment_id=pigment.pigment_id, amount=amount)],
        estimated_rgb=pigment.masstone_rgb,
        opacity=pigment.opacity,
        load=pigment.default_load if load is None else load,
        notes="Starter Uncalibrated recipe.",
    )


def average_rgb(values: list[RGB]) -> RGB:
    if not values:
        return (0, 0, 0)
    n = len(values)
    return tuple(int(round(sum(value[i] for value in values) / n)) for i in range(3))  # type: ignore[return-value]
