"""Pigment tool wrapper."""

from __future__ import annotations

from emma_mokuhanga.contracts import PigmentProfile
from emma_mokuhanga.pigments import list_pigments as _list_pigments


def list_pigments() -> list[PigmentProfile]:
    return _list_pigments()

