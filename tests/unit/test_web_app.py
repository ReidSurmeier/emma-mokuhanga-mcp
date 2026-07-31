from __future__ import annotations

from http import HTTPStatus
from io import BytesIO
from pathlib import Path

import pytest

from emma_mokuhanga import web_app
from emma_mokuhanga.web_app import _extract_upload


def test_extract_upload_from_multipart_body() -> None:
    boundary = "----boundary"
    body = (
        b"------boundary\r\n"
        b'Content-Disposition: form-data; name="image"; filename="test.png"\r\n'
        b"Content-Type: image/png\r\n\r\n"
        b"PNGDATA\r\n"
        b"------boundary--\r\n"
    )
    filename, payload = _extract_upload(body, f"multipart/form-data; boundary={boundary}")
    assert filename == "test.png"
    assert payload == b"PNGDATA"


def test_extract_upload_preserves_valid_trailing_bytes() -> None:
    boundary = "----boundary"
    body = (
        b"------boundary\r\n"
        b'Content-Disposition: form-data; name="image"; filename="test.png"\r\n'
        b"Content-Type: image/png\r\n\r\n"
        b"PNGDATA--\r\n\r\n"
        b"------boundary--\r\n"
    )

    _, payload = _extract_upload(body, f"multipart/form-data; boundary={boundary}")

    assert payload == b"PNGDATA--\r\n"


def test_web_server_binds_to_loopback_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, object] = {}

    class FakeServer:
        def __init__(self, address: tuple[str, int], handler: object) -> None:
            observed["address"] = address
            observed["handler"] = handler

        def serve_forever(self) -> None:
            observed["served"] = True

    monkeypatch.setattr(web_app, "ThreadingHTTPServer", FakeServer)

    assert web_app.main(["--report-dir", str(tmp_path)]) == 0
    assert observed["address"] == ("127.0.0.1", 8787)
    assert observed["served"] is True


def test_upload_over_limit_is_rejected_before_body_is_read(tmp_path: Path) -> None:
    handler_type = web_app.make_handler(tmp_path, max_upload_bytes=8)
    handler = handler_type.__new__(handler_type)
    handler.path = "/upload"
    handler.headers = {
        "Content-Length": "9",
        "Content-Type": "multipart/form-data; boundary=test",
    }
    handler.rfile = BytesIO(b"must-not-read")
    responses: list[tuple[HTTPStatus, str]] = []
    handler.send_error = lambda status, message: responses.append((status, message))

    handler.do_POST()

    assert responses == [(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "upload exceeds 8 bytes")]
    assert handler.rfile.tell() == 0
