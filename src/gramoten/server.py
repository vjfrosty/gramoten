"""A local page for trying the checker by hand: `python -m gramoten serve`.

Standard library only. It serves `playground.html` and answers `POST /check`
with `{text, extra}` → `{ms, issues}`, and `POST /fix` with
`{text, extra}` → `{text}` (every certain fix applied). It listens on 127.0.0.1 by default and is
meant for one person's testing, not for serving others.
"""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ._data import PAGE

DEFAULT_PORT = 8765
#: Longer texts are refused; the checker itself has no limit.
MAX_TEXT = 200_000


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        # Read on every request, so an edited page shows on reload.
        self._send(200, "text/html; charset=utf-8", PAGE.read_bytes())

    def do_POST(self) -> None:
        import gramoten

        if self.path not in ("/check", "/fix"):
            self.send_error(404)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8") or "{}")
            if not isinstance(body, dict):
                raise ValueError("the body must be a JSON object")
            text = body.get("text", "")
            extra = body.get("extra", [])
            if not isinstance(text, str) or not isinstance(extra, list) or not all(isinstance(w, str) for w in extra):
                raise ValueError("text must be a string and extra a list of strings")
        except (ValueError, UnicodeDecodeError) as e:
            self._json(400, {"error": f"Bad request: {e}"})
            return
        if len(text) > MAX_TEXT:
            self._json(413, {"error": f"Text longer than {MAX_TEXT:,} characters"})
            return
        words = frozenset(w.strip().lower() for w in extra if w.strip())
        if self.path == "/fix":
            self._json(200, {"text": gramoten.fix_text(text, words)})
            return
        started = time.perf_counter()
        issues = gramoten.check(text, words)
        ms = (time.perf_counter() - started) * 1000
        self._json(200, {"ms": round(ms, 1), "issues": [i.to_json() for i in issues]})

    def log_message(self, format: str, *args) -> None:  # noqa: A002 (the base class's name)
        pass  # keep the terminal for the start-up line and errors

    def _json(self, status: int, data: dict) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())

    def _send(self, status: int, kind: str, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(port: int = DEFAULT_PORT, host: str = "127.0.0.1", open_browser: bool = False) -> None:
    """Serve the page until interrupted (Ctrl+C)."""
    import gramoten

    gramoten.check("проверка")  # load the word lists before the first request
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    print(f"gramoten playground on {url}  (Ctrl+C stops it)", flush=True)
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
