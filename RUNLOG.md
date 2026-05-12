# Run Log

## 2026-05-12 Initial Build

Slice: A/B
Goal: create the foundation for a tested MCP planning core.
Decision:
- Keep the old project read-only as evidence.
- Use `EMMA_TEST_IMAGES_DIR` for the shared corpus.
- Start with contracts, ingest, analysis, first planner, and T0 render before CNC/SAM/T1.

Commands:
- `uv sync --extra dev` -> fixed Hatch package discovery, then installed dependencies.
- `uv run pytest -q` -> `25 passed`.
- `uv run ruff check .` -> passed.
- `uv run python -m emma_mokuhanga.mcp_server --smoke` -> passed.
- `uv run python -c "from emma_mokuhanga.mcp_server import build_mcp_server; print(type(build_mcp_server()).__name__)"` -> `FastMCP`.

Implemented:
- Python package and MCP entrypoint.
- A1 default profile and near-27 subject-agnostic defaults.
- Pydantic contracts for reference images, analyses, pigments, masks, blocks, impressions, plans, renders, and geometry validation.
- Hard invariant that each block maps to exactly one impression.
- Starter raw-pigment profiles.
- Real corpus image ingest.
- Deterministic Oklab palette, edge, entropy, and complexity analysis.
- First-pass subject-agnostic 27-impression planner with multi-zone blocks.
- T0 alpha preview renderer.
- T1 uncalibrated optical-density glaze renderer with premix adapter boundary.
- Initial SVG path geometry validator for open paths, duplicates, zero-length spans, unsupported commands, and self-intersections.

Next:
- Replace placeholder planning masks with image-derived masks.
- Add plan persistence JSON and load-by-id MCP tools.
- Add geometry export prototypes after the validator contract stabilizes.

## 2026-05-12 Tailscale Report Interface

Slice: report/web interface
Goal: expose corpus results and image submission over the machine's Tailscale address.
Implemented:
- Batch HTML report generator for all files in `EMMA_TEST_IMAGES_DIR`.
- Per-image pages with input preview, T0 composite, T1 composite, cumulative pull contact sheets, plan JSON, and analysis JSON.
- Small stdlib HTTP server with `/reports/` static serving and `/upload` image submission.
- CLI entrypoints: `emma-mokuhanga-report` and `emma-mokuhanga-web`.
