"""Repository-level contracts for a reproducible Emma experiment checkout."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_entrypoints_and_domain_docs_exist() -> None:
    expected = (
        "AGENTS.md",
        "PROJECT.md",
        "CONTEXT.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "docs/agents/issue-tracker.md",
        "docs/agents/triage-labels.md",
        "docs/agents/domain.md",
        "docs/adr/0001-separate-comparative-experiment.md",
        "docs/adr/0002-experimental-output-boundary.md",
        "docs/adr/0003-local-review-surface.md",
        ".github/workflows/validate.yml",
    )

    missing = [relative for relative in expected if not (ROOT / relative).is_file()]
    assert missing == [], f"missing repository contracts: {missing}"


def test_public_docs_are_machine_neutral_and_state_runtime_boundary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert re.search(r"/home/[^/<\s`]+", readme) is None
    assert re.search(r"/mnt/[a-z]/Users/[^/<\s`]+", readme) is None
    assert "separate experiment" in readme.lower()
    assert "not cnc-ready" in readme.lower()
    assert "not deployed" in readme.lower()


def test_generated_dependencies_are_not_tracked() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    generated = [
        path
        for path in tracked
        if "__pycache__/" in path
        or path.endswith((".pyc", ".pyo"))
        or "node_modules/" in path
    ]
    assert generated == [], f"generated dependencies are tracked: {generated}"


def test_ci_runs_behavior_and_repository_contracts() -> None:
    workflow = ROOT / ".github" / "workflows" / "validate.yml"
    assert workflow.is_file()

    text = workflow.read_text(encoding="utf-8")
    assert "python -m pytest" in text
    assert "ruff check" in text
    assert "python -m compileall" in text
