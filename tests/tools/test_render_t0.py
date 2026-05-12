from __future__ import annotations

from pathlib import Path

from PIL import Image

from emma_mokuhanga.tools.analysis import analyze_reference
from emma_mokuhanga.tools.ingest import ingest_image
from emma_mokuhanga.tools.planning import generate_plan
from emma_mokuhanga.tools.render import render_plan


def test_render_t0_outputs_cumulative_previews(non_emma_image: Path, tmp_path: Path) -> None:
    reference = ingest_image(non_emma_image, home=tmp_path)
    analysis = analyze_reference(reference)
    plan = generate_plan(analysis)
    artifact = render_plan(plan, tier="t0", session_id=reference.session_id, home=tmp_path)
    assert artifact.composite_path.exists()
    assert len(artifact.cumulative_paths) == len(plan.impressions)
    assert all(path.exists() for path in artifact.cumulative_paths)
    with Image.open(artifact.composite_path) as image:
        assert image.size == (artifact.width, artifact.height)

