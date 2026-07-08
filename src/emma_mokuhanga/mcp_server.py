"""MCP server entrypoint.

The tool functions are deliberately thin wrappers around tested Python modules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from emma_mokuhanga.config import get_config
from emma_mokuhanga.tools.analysis import analyze_reference
from emma_mokuhanga.tools.geometry import validate_svg_paths
from emma_mokuhanga.tools.ingest import ingest_image
from emma_mokuhanga.tools.pigments import list_pigments
from emma_mokuhanga.tools.planning import generate_plan
from emma_mokuhanga.tools.render import render_plan
from emma_mokuhanga.tools.workflow import run_reconstruction_workflow


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def smoke() -> dict[str, Any]:
    config = get_config()
    pigments = list_pigments()
    return {
        "ok": True,
        "home": str(config.home),
        "test_images_dir": str(config.test_images_dir),
        "pigment_count": len(pigments),
        "target_block_count": config.defaults.target_block_count,
    }


def build_mcp_server() -> Any:
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("emma-mokuhanga")

    @server.tool()
    def list_pigments_tool() -> list[dict[str, Any]]:
        """Return starter uncalibrated pigment assumptions."""

        return _jsonable(list_pigments())

    @server.tool()
    def ingest_image_tool(path: str, session_id: str | None = None) -> dict[str, Any]:
        """Ingest an image from a local path into a planning session."""

        return _jsonable(ingest_image(path, session_id=session_id))

    @server.tool()
    def analyze_reference_tool(reference: dict[str, Any], clusters: int = 8) -> dict[str, Any]:
        """Analyze a previously ingested reference image."""

        from emma_mokuhanga.contracts import ReferenceImage

        return _jsonable(
            analyze_reference(ReferenceImage.model_validate(reference), clusters=clusters)
        )

    @server.tool()
    def generate_plan_tool(
        analysis: dict[str, Any],
        target_block_count: int | None = None,
    ) -> dict[str, Any]:
        """Generate a subject-agnostic near-27 one-pull block plan."""

        from emma_mokuhanga.contracts import ImageAnalysis

        return _jsonable(
            generate_plan(
                ImageAnalysis.model_validate(analysis),
                target_block_count=target_block_count,
            )
        )

    @server.tool()
    def render_plan_tool(
        plan: dict[str, Any],
        tier: str = "t0",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Render a plan preview. T0 is the first implemented tier."""

        from emma_mokuhanga.contracts import PrintPlan

        return _jsonable(
            render_plan(PrintPlan.model_validate(plan), tier=tier, session_id=session_id)
        )

    @server.tool()
    def validate_svg_paths_tool(paths: list[str]) -> dict[str, Any]:
        """Validate basic SVG vector path hazards before CNC export."""

        return _jsonable(validate_svg_paths(paths))

    @server.tool()
    def run_reconstruction_workflow_tool(
        input_path: str,
        output_dir: str,
        plate_count: int = 27,
        max_side: int = 1024,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        """Run the image-derived reconstruction baseline workflow."""

        return _jsonable(
            run_reconstruction_workflow(
                input_path=input_path,
                output_dir=output_dir,
                plate_count=plate_count,
                max_side=max_side,
                case_id=case_id,
            )
        )

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Emma Mokuhanga MCP server.")
    parser.add_argument("--smoke", action="store_true", help="Run a local smoke check and exit.")
    parser.add_argument(
        "--ingest-smoke",
        type=Path,
        help="Ingest/analyze/plan/render one local image and exit.",
    )
    args = parser.parse_args(argv)

    if args.smoke:
        print(json.dumps(smoke(), indent=2))
        return 0

    if args.ingest_smoke:
        reference = ingest_image(args.ingest_smoke)
        analysis = analyze_reference(reference)
        plan = generate_plan(analysis)
        artifact = render_plan(plan, session_id=reference.session_id)
        print(
            json.dumps(
                {
                    "reference": _jsonable(reference),
                    "analysis": _jsonable(analysis),
                    "plan_id": plan.plan_id,
                    "impressions": len(plan.impressions),
                    "render": _jsonable(artifact),
                },
                indent=2,
            )
        )
        return 0

    build_mcp_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
