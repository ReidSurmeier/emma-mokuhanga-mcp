# Contributing

Use a focused branch or Orca worktree and preserve the experimental safety
boundaries in `CONTEXT.md` and `docs/adr/`.

For behavior changes:

1. Add a failing test that demonstrates the missing behavior or incorrect
   boundary.
2. Make the smallest change that passes it.
3. Refactor with the full suite green.
4. Update `PROJECT.md`, `CONTEXT.md`, or an ADR when capability or terminology
   changes.

Before opening a pull request, run:

```bash
uv sync --extra dev
uv run python -m pytest
uv run ruff check .
uv run python -m compileall -q src tests
uv run python -m emma_mokuhanga.mcp_server --smoke
```

Use synthetic temporary images in automated tests. Do not commit corpus
images, generated reports, machine-specific paths, credentials, or claims of
physical validation without evidence.
