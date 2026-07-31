"""HTML report generation for planner outputs."""
# ruff: noqa: E501

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from emma_mokuhanga.config import default_test_images_dir
from emma_mokuhanga.contracts import ImageAnalysis, PrintPlan, ReferenceImage, RenderArtifact
from emma_mokuhanga.tools.analysis import analyze_reference
from emma_mokuhanga.tools.ingest import ingest_image
from emma_mokuhanga.tools.planning import generate_plan
from emma_mokuhanga.tools.render import render_plan

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


@dataclass(frozen=True)
class CaseReport:
    slug: str
    source_name: str
    case_dir: Path
    page_path: Path
    reference: ReferenceImage
    analysis: ImageAnalysis
    plan: PrintPlan
    t0: RenderArtifact
    t1: RenderArtifact


def slugify(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return stem or "image"


def image_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _public_json_value(value: object, report_dir: Path) -> object:
    if isinstance(value, Path):
        resolved = value.resolve()
        try:
            return resolved.relative_to(report_dir.resolve()).as_posix()
        except ValueError:
            return value.name
    if isinstance(value, dict):
        return {
            key: _public_json_value(item, report_dir)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_public_json_value(item, report_dir) for item in value]
    return value


def _write_json(path: Path, value: object, report_dir: Path) -> None:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="python")  # type: ignore[attr-defined]
    else:
        payload = value
    path.write_text(
        json.dumps(_public_json_value(payload, report_dir), indent=2),
        encoding="utf-8",
    )


def _copy(path: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return destination


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _contact_sheet(paths: list[Path], output_path: Path, columns: int = 6) -> None:
    thumbs: list[Image.Image] = []
    labels: list[str] = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((150, 210), Image.Resampling.LANCZOS)
        thumbs.append(image.copy())
        labels.append(path.stem.split("_", 1)[0])
        image.close()

    if not thumbs:
        return
    cell_w, cell_h = 168, 238
    rows = math.ceil(len(thumbs) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (244, 241, 232))
    draw = ImageDraw.Draw(sheet)
    for idx, thumb in enumerate(thumbs):
        col = idx % columns
        row = idx // columns
        x = col * cell_w + (cell_w - thumb.width) // 2
        y = row * cell_h + 20
        sheet.paste(thumb, (x, y))
        draw.text((col * cell_w + 8, row * cell_h + 4), labels[idx], fill=(36, 34, 30))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def process_image(
    image_path: Path,
    report_dir: Path,
    slug_prefix: str = "",
) -> CaseReport:
    report_dir.mkdir(parents=True, exist_ok=True)
    data_home = report_dir / ".data"
    slug = slugify(f"{slug_prefix}-{image_path.name}" if slug_prefix else image_path.name)
    case_dir = report_dir / "cases" / slug
    case_dir.mkdir(parents=True, exist_ok=True)

    reference = ingest_image(image_path, home=data_home)
    analysis = analyze_reference(reference)
    plan = generate_plan(analysis)
    t0 = render_plan(plan, tier="t0", session_id=reference.session_id, home=data_home)
    t1 = render_plan(plan, tier="t1", session_id=reference.session_id, home=data_home)

    input_preview = _copy(reference.preview_path, case_dir / "input_preview.jpg")
    t0_composite = _copy(t0.composite_path, case_dir / "t0_composite.png")
    t1_composite = _copy(t1.composite_path, case_dir / "t1_composite.png")
    t0_contact = case_dir / "t0_contact.png"
    t1_contact = case_dir / "t1_contact.png"
    _contact_sheet(t0.cumulative_paths, t0_contact)
    _contact_sheet(t1.cumulative_paths, t1_contact)

    _write_json(case_dir / "reference.json", reference, report_dir)
    _write_json(case_dir / "analysis.json", analysis, report_dir)
    _write_json(case_dir / "plan.json", plan, report_dir)
    _write_json(case_dir / "render_t0.json", t0, report_dir)
    _write_json(case_dir / "render_t1.json", t1, report_dir)

    page_path = case_dir / "index.html"
    page_path.write_text(
        _case_html(
            report_dir=report_dir,
            source_name=image_path.name,
            reference=reference,
            analysis=analysis,
            plan=plan,
            input_preview=input_preview,
            t0_composite=t0_composite,
            t1_composite=t1_composite,
            t0_contact=t0_contact,
            t1_contact=t1_contact,
            t0=t0,
            t1=t1,
        ),
        encoding="utf-8",
    )
    return CaseReport(
        slug=slug,
        source_name=image_path.name,
        case_dir=case_dir,
        page_path=page_path,
        reference=reference,
        analysis=analysis,
        plan=plan,
        t0=t0,
        t1=t1,
    )


def build_report(input_dir: Path, report_dir: Path) -> list[CaseReport]:
    cases = [
        process_image(path, report_dir=report_dir, slug_prefix=f"{idx:02d}")
        for idx, path in enumerate(image_files(input_dir), start=1)
    ]
    write_index(report_dir, cases)
    return cases


def write_index(report_dir: Path, cases: list[CaseReport]) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(_case_card(report_dir, case) for case in cases)
    path = report_dir / "index.html"
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Emma Mokuhanga Test Corpus</title>
  {_style()}
</head>
<body>
  <main>
    <header>
      <h1>Emma Mokuhanga Test Corpus</h1>
      <p>Subject-agnostic near-27 one-pull block plans. T0 is layout preview. T1 is uncalibrated glaze plausibility.</p>
      <p><a href="/">Upload another image</a></p>
    </header>
    <section class="grid">
      {rows}
    </section>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
    return path


def _case_card(report_dir: Path, case: CaseReport) -> str:
    case_rel = _rel(case.page_path, report_dir)
    preview_rel = _rel(case.case_dir / "input_preview.jpg", report_dir)
    t1_rel = _rel(case.case_dir / "t1_composite.png", report_dir)
    name = html.escape(case.source_name)
    return f"""<article class="card">
  <a href="{case_rel}">
    <img src="{t1_rel}" alt="T1 preview for {name}">
  </a>
  <div class="thumbs">
    <img src="{preview_rel}" alt="Input for {name}">
    <img src="{t1_rel}" alt="T1 composite for {name}">
  </div>
  <h2><a href="{case_rel}">{name}</a></h2>
  <p>{len(case.plan.impressions)} pulls · complexity {case.analysis.complexity_score:.3f}</p>
</article>"""


def _case_html(
    report_dir: Path,
    source_name: str,
    reference: ReferenceImage,
    analysis: ImageAnalysis,
    plan: PrintPlan,
    input_preview: Path,
    t0_composite: Path,
    t1_composite: Path,
    t0_contact: Path,
    t1_contact: Path,
    t0: RenderArtifact,
    t1: RenderArtifact,
) -> str:
    name = html.escape(source_name)
    palette = "\n".join(
        f"""<span class="swatch" title="{cluster.cluster_id} {cluster.coverage:.1%}"
          style="background: rgb({cluster.rgb[0]}, {cluster.rgb[1]}, {cluster.rgb[2]})"></span>"""
        for cluster in analysis.palette
    )
    warnings = sorted(set(plan.warnings + t0.warnings + t1.warnings))
    warning_html = "".join(f"<li>{html.escape(warning)}</li>" for warning in warnings)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name}</title>
  {_style()}
</head>
<body>
  <main>
    <p><a href="../../index.html">Back to corpus</a> · <a href="/">Upload another image</a></p>
    <h1>{name}</h1>
    <section class="meta">
      <p>{reference.width} x {reference.height}px · {len(plan.impressions)} pulls · A1 default · one block per pull</p>
      <p>Edge density {analysis.edge_density:.3f} · entropy {analysis.color_entropy:.3f} · complexity {analysis.complexity_score:.3f}</p>
      <div class="palette">{palette}</div>
    </section>
    <section class="compare">
      <figure><img src="{input_preview.name}" alt="Input"><figcaption>Input</figcaption></figure>
      <figure><img src="{t0_composite.name}" alt="T0"><figcaption>T0 layout preview</figcaption></figure>
      <figure><img src="{t1_composite.name}" alt="T1"><figcaption>T1 glaze plausibility</figcaption></figure>
    </section>
    <section>
      <h2>Cumulative Pulls</h2>
      <figure><img src="{t0_contact.name}" alt="T0 contact"><figcaption>T0 cumulative states</figcaption></figure>
      <figure><img src="{t1_contact.name}" alt="T1 contact"><figcaption>T1 cumulative states</figcaption></figure>
    </section>
    <section>
      <h2>Warnings</h2>
      <ul>{warning_html}</ul>
      <p><a href="plan.json">plan.json</a> · <a href="analysis.json">analysis.json</a> · <a href="render_t1.json">render_t1.json</a></p>
    </section>
  </main>
</body>
</html>
"""


def _style() -> str:
    return """<style>
  :root { color-scheme: light; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  body { margin: 0; background: #f4f1e8; color: #24221e; }
  main { max-width: 1280px; margin: 0 auto; padding: 28px; }
  h1 { font-size: 28px; margin: 0 0 8px; }
  h2 { font-size: 17px; margin: 12px 0 6px; }
  a { color: #184f7a; }
  img { max-width: 100%; height: auto; display: block; border: 1px solid #d8d0bf; background: #fff; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; }
  .card { background: #fffaf0; border: 1px solid #d8d0bf; padding: 12px; }
  .card > a > img { aspect-ratio: 1 / 1.25; object-fit: contain; width: 100%; }
  .thumbs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
  .thumbs img { aspect-ratio: 1 / 1; object-fit: contain; }
  .compare { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; align-items: start; }
  figure { margin: 0 0 18px; }
  figcaption { font-size: 13px; color: #5c5549; margin-top: 6px; }
  .palette { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0 18px; }
  .swatch { width: 34px; height: 34px; border: 1px solid #6d6558; display: inline-block; }
  .meta { background: #fffaf0; border: 1px solid #d8d0bf; padding: 12px; margin: 14px 0; }
  @media (max-width: 860px) { .compare { grid-template-columns: 1fr; } main { padding: 16px; } }
</style>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build HTML reports for mokuhanga plans.")
    parser.add_argument("--input-dir", type=Path, default=default_test_images_dir())
    parser.add_argument("--out", type=Path, default=Path("reports/test-images"))
    args = parser.parse_args(argv)
    cases = build_report(args.input_dir, args.out)
    print(f"wrote {len(cases)} cases to {args.out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
