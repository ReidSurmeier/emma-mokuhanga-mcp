from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from emma_mokuhanga.experiments.overprint_stack import HarnessConfig, run_experiment


def _gradient_image(path: Path) -> None:
    width, height = 48, 64
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)
    red = np.tile(x, (height, 1))
    green = np.tile(y[:, None], (1, width))
    blue = np.full((height, width), 96, dtype=np.uint8)
    Image.fromarray(np.stack([red, green, blue], axis=2), "RGB").save(path)


def _load_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_overprint_stack_experiment_writes_logs_and_previews(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    out_dir = tmp_path / "experiment"
    _gradient_image(image_path)

    summary = run_experiment(
        HarnessConfig(
            input_path=image_path,
            out_dir=out_dir,
            variants=3,
            seed=123,
            width=48,
            contact_sheet_cols=2,
            contact_sheet_rows=2,
        )
    )

    jsonl_path = out_dir / "experiments.jsonl"
    records = _load_records(jsonl_path)
    assert len(records) == 3
    assert Path(summary["jsonl_path"]) == jsonl_path
    assert Path(summary["contact_sheets"][0]).exists()
    assert Path(summary["best_variant"]["preview_path"]).exists()

    metric_keys = {
        "rgb_rmse",
        "rgb_mae",
        "low_frequency_rmse",
        "island_penalty",
        "plate_count",
        "average_mask_coverage",
        "mask_overlap_mean",
        "reuse_overlap_mean",
    }
    assert metric_keys.issubset(records[0]["metrics"])
    assert records[0]["reference_image_targets"]
    assert records[0]["metrics"]["plate_count"] >= 24


def test_overprint_stack_experiment_seed_is_deterministic(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    _gradient_image(image_path)

    run_experiment(
        HarnessConfig(
            input_path=image_path,
            out_dir=tmp_path / "run_a",
            variants=2,
            seed=99,
            width=48,
        )
    )
    run_experiment(
        HarnessConfig(
            input_path=image_path,
            out_dir=tmp_path / "run_b",
            variants=2,
            seed=99,
            width=48,
        )
    )

    records_a = _load_records(tmp_path / "run_a" / "experiments.jsonl")
    records_b = _load_records(tmp_path / "run_b" / "experiments.jsonl")

    comparable_a = [
        {"params": record["params"], "metrics": record["metrics"]} for record in records_a
    ]
    comparable_b = [
        {"params": record["params"], "metrics": record["metrics"]} for record in records_b
    ]
    assert comparable_a == comparable_b
