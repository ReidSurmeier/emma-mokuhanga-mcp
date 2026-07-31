# Emma Mokuhanga Planning Experiment

Emma Mokuhanga is a local, chat-first experiment for planning multi-block
mokuhanga reconstructions from a reference image. It analyzes color and
complexity, proposes an approximately 27-impression stack, renders diagnostic
previews, and can generate image-derived raster masks and SVG diagnostics.

This is a separate experiment from the Chuck/woodblock MCP. The two projects
may be compared through explicit evaluation cases, but neither is the other's
implementation base or successor.

## Current boundary

The implemented paths are:

- image ingest and deterministic reference analysis;
- a heuristic, subject-agnostic 24–32 block planning grammar;
- T0 layout and T1 uncalibrated optical-density previews;
- image-derived quantized reconstruction plates;
- basic SVG path-hazard checks; and
- static reports plus an optional local upload/review surface.

Generated masks and SVGs are diagnostic. They are not CNC-ready toolpaths,
fabrication instructions, calibrated pigment recipes, or verified physical
print plans. The project is not deployed as a service, on GitHub Pages, or on
the Droplet Platform.

See [PROJECT.md](PROJECT.md) for operational status, [CONTEXT.md](CONTEXT.md)
for the domain model, and [docs/adr](docs/adr) for decisions.

## Install and test

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --extra dev
uv run python -m pytest
uv run ruff check .
uv run python -m compileall -q src tests
uv run python -m emma_mokuhanga.mcp_server --smoke
```

The default runtime home is `~/.emma-mokuhanga`. Override it without changing
tracked files:

```bash
export EMMA_HOME=/path/to/runtime-data
```

## Optional reference corpus

Corpus images are external inputs and are not committed. Point the report
builder and corpus tests at a directory:

```bash
export EMMA_TEST_IMAGES_DIR=/path/to/reference-images
uv run python -m emma_mokuhanga.reporting \
  --input-dir "$EMMA_TEST_IMAGES_DIR" \
  --out reports/test-images
```

Tests that require that optional corpus skip when the variable is absent.
Rights and provenance for each reference image remain the operator's
responsibility.

## MCP server

Run the stdio MCP server:

```bash
uv run emma-mokuhanga-mcp
```

The server exposes ingest, analysis, planning, rendering, geometry validation,
and reconstruction-workflow tools. Inputs and outputs are local files under
the configured runtime directories.

## Local review surface

The upload/review server binds to loopback by default and rejects request
bodies larger than 25 MiB:

```bash
uv run emma-mokuhanga-web \
  --report-dir reports/test-images
```

It has no authentication. For deliberate tailnet-only review, bind to the
machine's specific Tailscale address—not `0.0.0.0`—and keep host firewall and
Tailscale policy restrictions in place:

```bash
uv run emma-mokuhanga-web \
  --host <tailscale-ip> \
  --port 8787 \
  --report-dir reports/test-images
```

This manual review surface is not deployed or supervised. Do not expose it to
the public internet.

## License

MIT. See [LICENSE](LICENSE).
