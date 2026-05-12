from __future__ import annotations

import numpy as np

from emma_mokuhanga.render.t1 import glaze_over


def test_glaze_dark_layer_does_not_brighten_underlayer() -> None:
    under = np.full((2, 2, 3), 0.8, dtype=np.float32)
    pigment = np.asarray([0.1, 0.1, 0.1], dtype=np.float32)
    strength = np.full((2, 2), 0.5, dtype=np.float32)
    out = glaze_over(under, pigment, strength)
    assert np.all(out <= under)


def test_glaze_strength_is_monotonic() -> None:
    under = np.full((1, 1, 3), 0.9, dtype=np.float32)
    pigment = np.asarray([0.2, 0.3, 0.4], dtype=np.float32)
    weak = glaze_over(under, pigment, np.asarray([[0.2]], dtype=np.float32))
    strong = glaze_over(under, pigment, np.asarray([[0.8]], dtype=np.float32))
    assert np.linalg.norm(strong - pigment) < np.linalg.norm(weak - pigment)

