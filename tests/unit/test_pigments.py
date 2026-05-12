from __future__ import annotations

from emma_mokuhanga.contracts import OpacityClass
from emma_mokuhanga.pigments import list_pigments, pigment_by_id, recipe_from_pigment


def test_starter_pigments_include_key_materials() -> None:
    pigments = pigment_by_id()
    assert "cad_red" in pigments
    assert "ultramarine" in pigments
    assert "sumi" in pigments
    assert pigments["sumi"].opacity == OpacityClass.OPAQUE


def test_recipe_from_pigment_is_explicit_uncalibrated_recipe() -> None:
    pigment = list_pigments()[0]
    recipe = recipe_from_pigment(pigment)
    assert recipe.components[0].pigment_id == pigment.pigment_id
    assert recipe.estimated_rgb == pigment.masstone_rgb
    assert "Uncalibrated" in recipe.notes

