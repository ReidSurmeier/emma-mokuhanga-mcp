from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from emma_mokuhanga.tools.workflow import run_reconstruction_workflow


def test_run_reconstruction_workflow_writes_image_derived_outputs(tmp_path: Path) -> None:
    source = tmp_path / "input.png"
    image = Image.new("RGB", (24, 16), (220, 60, 40))
    for x in range(12, 24):
        for y in range(16):
            image.putpixel((x, y), (40, 80, 190))
    image.save(source)

    manifest = run_reconstruction_workflow(
        source,
        tmp_path / "out",
        plate_count=4,
        max_side=128,
        case_id="case-test",
    )

    case_dir = Path(manifest["case_dir"])
    assert Path(manifest["previews"]["reconstruction"]).exists()
    assert Path(manifest["previews"]["contact_sheet"]).exists()
    assert len(manifest["plates"]) == 4
    assert Path(manifest["plates"][0]["mask_png"]).exists()
    assert Path(manifest["plates"][0]["svg"]).exists()

    saved = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    assert saved["workflow"] == "image_derived_reconstruction_v1"
    assert saved["metrics"]["quantized_similarity"] > 0.0
