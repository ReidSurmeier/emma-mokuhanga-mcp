"""Small Tailscale-friendly web interface for reports and image uploads."""
# ruff: noqa: E501

from __future__ import annotations

import argparse
import html
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import time
from urllib.parse import unquote, urlparse

from emma_mokuhanga.reporting import process_image

DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _extract_upload(body: bytes, content_type: str) -> tuple[str, bytes]:
    match = re.search(r"boundary=(.+)", content_type)
    if not match:
        raise ValueError("missing multipart boundary")
    boundary = match.group(1).strip().strip('"').encode()
    for part in body.split(b"--" + boundary):
        if b'name="image"' not in part or b"\r\n\r\n" not in part:
            continue
        headers, payload = part.split(b"\r\n\r\n", 1)
        payload = payload.removesuffix(b"\r\n")
        filename_match = re.search(rb'filename="([^"]*)"', headers)
        filename = filename_match.group(1).decode("utf-8", "replace") if filename_match else "upload.png"
        if not payload:
            raise ValueError("empty upload")
        return filename, payload
    raise ValueError("no image field in upload")


def make_handler(
    report_dir: Path,
    *,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> type[BaseHTTPRequestHandler]:
    if max_upload_bytes < 1:
        raise ValueError("max_upload_bytes must be positive")
    report_dir = report_dir.resolve()
    upload_dir = report_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            print(f"{self.address_string()} - {fmt % args}")

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(_home_html(report_dir))
                return
            if parsed.path.startswith("/reports/"):
                self._serve_file(report_dir / unquote(parsed.path.removeprefix("/reports/")))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/upload":
                self.send_error(HTTPStatus.NOT_FOUND, "not found")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1:
                    self.send_error(HTTPStatus.LENGTH_REQUIRED, "positive Content-Length required")
                    return
                if length > max_upload_bytes:
                    self.send_error(
                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        f"upload exceeds {max_upload_bytes} bytes",
                    )
                    return
                filename, payload = _extract_upload(
                    self.rfile.read(length),
                    self.headers.get("Content-Type", ""),
                )
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).name) or "upload.png"
                upload_path = upload_dir / f"{int(time())}-{safe_name}"
                upload_path.write_bytes(payload)
                case = process_image(upload_path, report_dir=report_dir, slug_prefix="upload")
                location = f"/reports/cases/{case.slug}/index.html"
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", location)
                self.end_headers()
            except Exception as exc:
                self.send_error(HTTPStatus.BAD_REQUEST, html.escape(str(exc)))

        def _serve_file(self, path: Path) -> None:
            resolved = path.resolve()
            if not resolved.is_file() or report_dir not in resolved.parents:
                self.send_error(HTTPStatus.NOT_FOUND, "not found")
                return
            content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
            data = resolved.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, text: str) -> None:
            data = text.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _home_html(report_dir: Path) -> str:
    index_link = "/reports/index.html" if (report_dir / "index.html").exists() else "#"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Emma Mokuhanga Interface</title>
  <style>
    body {{ margin: 0; background: #f4f1e8; color: #24221e; font-family: ui-sans-serif, system-ui, sans-serif; }}
    main {{ max-width: 760px; margin: 0 auto; padding: 28px; }}
    form, .panel {{ background: #fffaf0; border: 1px solid #d8d0bf; padding: 16px; margin: 18px 0; }}
    input, button {{ font: inherit; }}
    button {{ padding: 8px 12px; }}
    a {{ color: #184f7a; }}
  </style>
</head>
<body>
  <main>
    <h1>Emma Mokuhanga Interface</h1>
    <div class="panel">
      <p><a href="{index_link}">Open generated test-image report</a></p>
      <p>Report directory: <code>{html.escape(str(report_dir))}</code></p>
    </div>
    <form method="post" action="/upload" enctype="multipart/form-data">
      <h2>Submit Image</h2>
      <p><input type="file" name="image" accept="image/*" required></p>
      <p><button type="submit">Run Ingest → Analyze → Plan → Render</button></p>
    </form>
  </main>
</body>
</html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the mokuhanga report/upload UI.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address. Use a specific tailnet address for remote review.",
    )
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--report-dir", type=Path, default=Path("reports/test-images"))
    parser.add_argument(
        "--max-upload-mib",
        type=int,
        default=25,
        help="Maximum request body size in MiB.",
    )
    args = parser.parse_args(argv)
    if args.max_upload_mib < 1:
        parser.error("--max-upload-mib must be positive")
    max_upload_bytes = args.max_upload_mib * 1024 * 1024
    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(args.report_dir, max_upload_bytes=max_upload_bytes),
    )
    print(f"serving {args.report_dir} on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
