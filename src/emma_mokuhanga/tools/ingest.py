"""Image ingest tool."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from PIL import Image

from emma_mokuhanga.contracts import ReferenceImage
from emma_mokuhanga.paths import ensure_session, new_id


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_image(
    path: str | Path,
    session_id: str | None = None,
    home: Path | None = None,
) -> ReferenceImage:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    sid, root = ensure_session(session_id=session_id, home=home)
    image_id = new_id("image")
    try:
        with Image.open(source) as image:
            width, height = image.size
            mode = image.mode
            fmt = image.format
            profile_name = image.info.get("icc_profile")
            ext = (fmt or source.suffix.lstrip(".") or "png").lower()
            if ext == "jpeg":
                ext = "jpg"
            stored = root / "images" / f"{image_id}.{ext}"
            shutil.copy2(source, stored)

            preview = root / "images" / f"{image_id}_preview.jpg"
            rgb = image.convert("RGB")
            rgb.thumbnail((640, 640), Image.Resampling.LANCZOS)
            rgb.save(preview, "JPEG", quality=88)
    except Exception as exc:
        raise ValueError(f"not a readable image: {source}") from exc

    return ReferenceImage(
        image_id=image_id,
        session_id=sid,
        source_path=source,
        stored_path=stored,
        preview_path=preview,
        sha256=_sha256(stored),
        width=width,
        height=height,
        mode=mode,
        format=fmt,
        profile_name="embedded" if profile_name else None,
    )
