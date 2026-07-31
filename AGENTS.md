# Emma Mokuhanga agent guide

This repository owns an experimental MCP and local review workflow for
planning Emma-style mokuhanga print stacks. Preserve the distinction between
diagnostic output and fabrication authority.

Start by reading `PROJECT.md`, then `CONTEXT.md`. Read the accepted decisions
in `docs/adr/` before changing domain language or runtime exposure.

## Boundaries

- Keep this a separate comparative experiment from the Chuck/woodblock MCP.
- Never describe generated masks, recipes, SVGs, or plans as CNC-ready or
  physically validated unless new evidence and an ADR establish that state.
- Keep reference-image corpora and generated reports outside Git.
- Do not embed personal absolute paths, credentials, or private image
  provenance in committed fixtures or documentation.
- The review server is local and unauthenticated. Loopback is the safe default;
  remote binding must be explicit and limited to a specific tailnet address.
- Tests use temporary images. External corpus tests must skip when
  `EMMA_TEST_IMAGES_DIR` is not configured.

## Commands

```bash
uv sync --extra dev
uv run python -m pytest
uv run ruff check .
uv run python -m compileall -q src tests
uv run python -m emma_mokuhanga.mcp_server --smoke
```

## Validation

Run the complete test suite, Ruff, Python compilation, the MCP smoke check,
and a temporary-directory reconstruction scenario before claiming the
workflow works. Check repository history and the proposed tree with a
redacting secret scanner before publishing.

## Agent skills

### Issue tracker

Issues and PRDs live in GitHub Issues for
`ReidSurmeier/emma-mokuhanga-mcp`. See
`docs/agents/issue-tracker.md`.

### Triage labels

Use the five standard Matt Pocock triage roles. See
`docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository with `CONTEXT.md` at the root and
decisions in `docs/adr/`. See `docs/agents/domain.md`.
