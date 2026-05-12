from __future__ import annotations

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

