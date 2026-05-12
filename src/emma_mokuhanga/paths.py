"""Filesystem persistence helpers."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .config import get_config


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def data_home() -> Path:
    return get_config().home


def session_dir(session_id: str, home: Path | None = None) -> Path:
    root = home or data_home()
    return root / "sessions" / session_id


def ensure_session(session_id: str | None = None, home: Path | None = None) -> tuple[str, Path]:
    sid = session_id or new_id("session")
    path = session_dir(sid, home)
    for child in ("images", "analyses", "plans", "renders", "exports", "calibration"):
        (path / child).mkdir(parents=True, exist_ok=True)
    return sid, path

