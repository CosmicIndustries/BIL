#!/usr/bin/env python3
"""Minimal local HTTP server exposing the BIL interpreter as a webhook.

Gives the browser userscript (userscript/bil-helper.user.js) — or curl, or an
n8n HTTP Request node — something to POST to without standing up n8n itself.
Uses only the standard library; httpx is a client, not a server, so it has no
role here.

Run:
    python3 server.py

Then:
    curl -X POST http://127.0.0.1:8787/bil \\
        -H 'Content-Type: application/json' \\
        -d '{"input_type": "english", "input_text": "Fix the code."}'
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict

from bil_v07_interpreter import n8n_handle

HOST = "127.0.0.1"
PORT = 8787


class BILRequestHandler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status: int, body: Dict[str, object]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/bil":
            self._json(404, {"ok": False, "error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid JSON"})
            return

        self._json(200, n8n_handle(payload))

    def log_message(self, format: str, *args) -> None:  # quiet by default
        pass


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), BILRequestHandler)
    print(f"BIL webhook server listening on http://{HOST}:{PORT}/bil")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
