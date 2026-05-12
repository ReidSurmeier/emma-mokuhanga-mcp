from __future__ import annotations

from emma_mokuhanga.mcp_server import smoke


def test_mcp_smoke() -> None:
    result = smoke()
    assert result["ok"] is True
    assert result["pigment_count"] >= 8
    assert result["target_block_count"] == 27

