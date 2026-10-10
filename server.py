#!/usr/bin/env python3
"""Minimal local HTTP server exposing the BIL interpreter as a webhook.

Gives the browser userscript (userscript/bil-helper.user.js) — or curl, or an
n8n HTTP Request node — something to POST to without standing up n8n itself.
Uses only the standard library; httpx is a client, not a server, so it has no
role here.

CORS reflects whatever Origin a request sends (the userscript runs on
whatever page you're browsing, so there's no fixed allow-list), but every
POST /bil must also carry a matching X-BIL-Token header — that's the actual
gate, since CORS headers alone can't stop a page from making the request in
the first place.

Run:
    python3 server.py
    # BIL webhook server listening on http://127.0.0.1:8787/bil
    # Auth token (set via the userscript's 'Set BIL token' menu command): <token>

Then:
    curl -X POST http://127.0.0.1:8787/bil \\
        -H 'Content-Type: application/json' \\
        -H 'X-BIL-Token: <token>' \\
        -d '{"input_type": "english", "input_text": "Fix the code."}'
"""

from __future__ import annotations

import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict

from bil_v07_interpreter import n8n_handle

HOST = "127.0.0.1"
PORT = 8787
AUTH_TOKEN = os.environ.get("BIL_AUTH_TOKEN") or secrets.token_urlsafe(32)


class BILRequestHandler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        # Reflect the request's own Origin rather than a "*" wildcard: the
        # userscript needs to call in from whatever page is open, but the
        # X-BIL-Token check below is the actual gate, not this header.
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-BIL-Token")

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

        if not secrets.compare_digest(self.headers.get("X-BIL-Token", ""), AUTH_TOKEN):
            self._json(401, {"ok": False, "error": "missing or invalid X-BIL-Token"})
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
    print(f"Auth token (set via the userscript's 'Set BIL token' menu command): {AUTH_TOKEN}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
