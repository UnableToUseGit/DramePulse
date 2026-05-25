from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
from pathlib import Path
from typing import Sequence


class RangeRequestHandler(SimpleHTTPRequestHandler):
    def send_head(self):  # type: ignore[override]
        path = Path(self.translate_path(self.path))
        if path.is_dir():
            return super().send_head()
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        file_size = path.stat().st_size
        range_header = self.headers.get("Range")
        if not range_header:
            return super().send_head()

        byte_range = self._parse_single_range(range_header, file_size)
        if byte_range is None:
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            return None

        start, end = byte_range
        content_length = end - start + 1
        content_type = self.guess_type(str(path))
        handle = path.open("rb")
        handle.seek(start)

        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Last-Modified", self.date_time_string(path.stat().st_mtime))
        self.end_headers()
        self.range = (start, end)
        return handle

    def copyfile(self, source, outputfile):  # type: ignore[override]
        byte_range = getattr(self, "range", None)
        if byte_range is None:
            return super().copyfile(source, outputfile)

        start, end = byte_range
        remaining = end - start + 1
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self.range = None

    @staticmethod
    def _parse_single_range(value: str, file_size: int) -> tuple[int, int] | None:
        if not value.startswith("bytes="):
            return None
        range_value = value.removeprefix("bytes=").split(",", 1)[0].strip()
        if "-" not in range_value:
            return None
        start_text, end_text = range_value.split("-", 1)
        try:
            if start_text == "":
                suffix_length = int(end_text)
                if suffix_length <= 0:
                    return None
                start = max(0, file_size - suffix_length)
                end = file_size - 1
            else:
                start = int(start_text)
                end = int(end_text) if end_text else file_size - 1
        except ValueError:
            return None
        if start < 0 or end < start or start >= file_size:
            return None
        return start, min(end, file_size - 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the annotation tool with HTTP Range support for MP4 seeking.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--directory", type=Path, default=Path("."))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    handler = lambda *handler_args, **kwargs: RangeRequestHandler(  # noqa: E731
        *handler_args,
        directory=str(args.directory),
        **kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving annotation tool on http://{args.host}:{args.port}/apps/annotation-tool/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
