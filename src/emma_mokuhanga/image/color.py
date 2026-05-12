"""Color-space helpers.

Oklab formulas follow Bjorn Ottosson's public Oklab conversion constants.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def srgb_to_linear(rgb: NDArray[np.floating]) -> NDArray[np.floating]:
    rgb = np.asarray(rgb, dtype=np.float64)
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(rgb: NDArray[np.floating]) -> NDArray[np.floating]:
    rgb = np.asarray(rgb, dtype=np.float64)
    rgb = np.clip(rgb, 0.0, 1.0)
    return np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)


def rgb_u8_to_oklab(rgb_u8: NDArray[np.integer] | NDArray[np.floating]) -> NDArray[np.floating]:
    rgb = np.asarray(rgb_u8, dtype=np.float64) / 255.0
    linear = srgb_to_linear(rgb)
    r, g, b = linear[..., 0], linear[..., 1], linear[..., 2]
    lms_l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    lms_m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    lms_s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(lms_l), np.cbrt(lms_m), np.cbrt(lms_s)
    return np.stack(
        [
            0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
        ],
        axis=-1,
    )


def oklab_to_rgb_u8(oklab: NDArray[np.floating]) -> NDArray[np.uint8]:
    lab = np.asarray(oklab, dtype=np.float64)
    l_, m_, s_ = (
        lab[..., 0] + 0.3963377774 * lab[..., 1] + 0.2158037573 * lab[..., 2],
        lab[..., 0] - 0.1055613458 * lab[..., 1] - 0.0638541728 * lab[..., 2],
        lab[..., 0] - 0.0894841775 * lab[..., 1] - 1.2914855480 * lab[..., 2],
    )
    lms_l, lms_m, lms_s = l_**3, m_**3, s_**3
    linear = np.stack(
        [
            +4.0767416621 * lms_l - 3.3077115913 * lms_m + 0.2309699292 * lms_s,
            -1.2684380046 * lms_l + 2.6097574011 * lms_m - 0.3413193965 * lms_s,
            -0.0041960863 * lms_l - 0.7034186147 * lms_m + 1.7076147010 * lms_s,
        ],
        axis=-1,
    )
    srgb = linear_to_srgb(linear)
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


def kmeans_oklab(
    pixels_rgb: NDArray[np.uint8],
    k: int = 8,
    iterations: int = 8,
) -> tuple[NDArray[np.floating], NDArray[np.int64]]:
    flat_rgb = pixels_rgb.reshape(-1, 3)
    lab = rgb_u8_to_oklab(flat_rgb)
    if len(lab) == 0:
        raise ValueError("cannot cluster empty image")
    k = max(1, min(k, len(lab)))

    order = np.argsort(lab[:, 0])
    quantiles = np.linspace(0, len(order) - 1, k, dtype=np.int64)
    centers = lab[order[quantiles]].copy()

    labels = np.zeros(len(lab), dtype=np.int64)
    for _ in range(iterations):
        distances = np.linalg.norm(lab[:, None, :] - centers[None, :, :], axis=2)
        labels = np.argmin(distances, axis=1)
        for idx in range(k):
            members = lab[labels == idx]
            if len(members):
                centers[idx] = members.mean(axis=0)
    return centers, labels
