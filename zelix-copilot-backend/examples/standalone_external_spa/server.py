"""Standalone HTTP Server for External Single Page Application (Port 8080).

Demonstrates that an external client running on a completely separate origin/port
can connect over open HTTP / AG-UI / JSON-RPC protocols to the Alamia Copilot Backend.
"""

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent


class SPAHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)


def run(port: int = 8080) -> None:
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, SPAHTTPRequestHandler)
    print("=" * 70)
    print("External Standalone SPA Web Server running at:")
    print(f"--> http://localhost:{port}")
    print("Connecting to Alamia Copilot Backend at http://localhost:8000")
    print("=" * 70)
    print("Press Ctrl+C to stop the server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    run(port)
