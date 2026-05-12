# Emma Mokuhanga MCP

Chat-first planning tools for Emma-style mokuhanga woodblock print stacks.

The system takes one high-quality image and produces plausible print plans:

- subject-agnostic,
- A1 default,
- near-27 one-pull blocks,
- multiple brushed color zones per pull,
- pigment-aware layer order,
- CNC/VCarve-oriented validation and export.

This repo treats `/home/reidsurmeier/src/woodblock-reidsurmeier-wtf` as evidence and salvage
material, not as the implementation base.

## Corpus

Use the shared printmaking fixtures through an environment variable:

```bash
export EMMA_TEST_IMAGES_DIR='/mnt/c/Users/reidsurmeier2/Books/printmaking/test images'
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run python -m emma_mokuhanga.mcp_server --smoke
```

## Tailscale Web Report

Generate the shared test-image report:

```bash
uv run python -m emma_mokuhanga.reporting \
  --input-dir "$EMMA_TEST_IMAGES_DIR" \
  --out reports/test-images
```

Serve the report and upload interface over Tailscale:

```bash
uv run python -m emma_mokuhanga.web_app \
  --host 0.0.0.0 \
  --port 8787 \
  --report-dir reports/test-images
```

Open `http://<tailscale-ip>:8787/`.
