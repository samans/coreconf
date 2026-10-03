#!/usr/bin/env python3
"""
Web console for the CORECONF coffee-maker example.

A dependency-free (stdlib only) HTTP server that serves an HTML user
interface and acts as a bridge between the browser and the CORECONF
example running on this machine.

What it provides:

  * Serves  index.html  (the UI).
  * POST /api/server/start   -> launch server.py as a background process.
  * POST /api/server/stop    -> terminate the running CoAP server.
  * GET  /api/server/status  -> whether the CoAP server is running.
  * GET  /api/server/logs    -> incremental server stdout/stderr (SSE-free poll).
  * POST /api/run            -> run a client command and stream its output.

The "command line" in the UI maps a small set of named commands to the
example's existing Python scripts/snippets so the user can interact with
the running CORECONF datastore and see the raw output.

Run:
    python3 webui/web_console.py
then open http://localhost:8080 in a browser.
"""

import json
import os
import queue
import shlex
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths / configuration
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
EXAMPLE_DIR = HERE.parent               # the coffee-example directory
INDEX_HTML = HERE / "index.html"

# Prefer the project's virtualenv interpreter if present so that aiocoap/cbor2
# are importable; otherwise fall back to the interpreter running this server.
VENV_PY = EXAMPLE_DIR / ".venv" / "bin" / "python3"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable

HTTP_HOST = os.environ.get("WEBUI_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("WEBUI_PORT", "8080"))


# ---------------------------------------------------------------------------
# Command catalogue
# ---------------------------------------------------------------------------
# Each command is a short name mapped to an argv list executed from the
# example directory. Inline "-c" snippets reuse the client helpers in
# client.py so the UI can trigger individual CORECONF operations.

def _client_snippet(body: str) -> list:
    """Build a python -c argv that imports the client helpers and awaits
    the given coroutine body against a fresh client context."""
    code = (
        "import asyncio, logging\n"
        "logging.basicConfig(level=logging.INFO, format='%(message)s')\n"
        "import client\n"
        "async def _main():\n"
        "    ctx = await client.Context.create_client_context()\n"
        f"    {body}\n"
        "    await ctx.shutdown()\n"
        "asyncio.run(_main())\n"
    )
    return [PYTHON, "-c", code]


COMMANDS = {
    "help": None,  # handled client-side
    "get": {
        "desc": "GET /c  -> read the whole datastore",
        "argv": _client_snippet("await client.get_full(ctx)"),
    },
    "fetch": {
        "desc": "FETCH /c -> read just power + state",
        "argv": _client_snippet("await client.fetch_power_state(ctx)"),
    },
    "on": {
        "desc": "iPATCH /c -> turn the coffee maker ON (2 cups, strong)",
        "argv": _client_snippet(
            "await client.turn_on(ctx, cups=2, strength='strong')"),
    },
    "off": {
        "desc": "iPATCH /c -> turn the coffee maker OFF",
        "argv": _client_snippet("await client.turn_off(ctx)"),
    },
    "brew": {
        "desc": "POST /c  -> invoke the brew action",
        "argv": _client_snippet("await client.brew(ctx)"),
    },
    "demo": {
        "desc": "Run the full client.py walk-through",
        "argv": [PYTHON, "client.py"],
    },
    "secure-setup": {
        "desc": "Generate OSCORE security contexts (alice, bob)",
        "argv": [PYTHON, "setup_security.py"],
    },
    "secure-demo": {
        "desc": "Run the secure client (needs secure_server.py running)",
        "argv": [PYTHON, "secure_client.py"],
    },
}


# ---------------------------------------------------------------------------
# Managed CoAP server process
# ---------------------------------------------------------------------------

class ServerManager:
    """Owns the lifecycle of the background CORECONF CoAP server process
    and buffers its combined stdout/stderr for incremental polling."""

    def __init__(self, script="server.py"):
        self.script = script
        self.proc = None
        self.lines = []
        self._lock = threading.Lock()
        self._reader = None

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        with self._lock:
            if self.is_running():
                return False, "already running"
            self.lines = []
            self.proc = subprocess.Popen(
                [PYTHON, "-u", self.script],
                cwd=str(EXAMPLE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._reader = threading.Thread(
                target=self._pump, args=(self.proc,), daemon=True)
            self._reader.start()
            return True, "started"

    def _pump(self, proc):
        for line in proc.stdout:
            with self._lock:
                self.lines.append(line.rstrip("\n"))
                # keep the buffer bounded
                if len(self.lines) > 2000:
                    self.lines = self.lines[-1000:]
        with self._lock:
            self.lines.append("[server process exited]")

    def stop(self):
        with self._lock:
            if not self.is_running():
                return False, "not running"
            proc = self.proc
            proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        return True, "stopped"

    def logs(self, since=0):
        with self._lock:
            total = len(self.lines)
            new = self.lines[since:]
        return total, new


SERVER = ServerManager()
SECURE_SERVER = ServerManager(script="secure_server.py")


# ---------------------------------------------------------------------------
# Command runner (streams output back to the browser via chunked response)
# ---------------------------------------------------------------------------

def run_command_stream(name, handler):
    """Execute a catalogue command, writing its output lines to the HTTP
    response as newline-delimited JSON ("ndjson") chunks."""
    entry = COMMANDS.get(name)
    if not entry:
        handler._write_chunk({"type": "error",
                              "line": f"unknown command: {name}"})
        handler._write_chunk({"type": "end", "code": 1})
        return

    argv = entry["argv"]
    handler._write_chunk({"type": "cmd", "line": "$ " + _display(argv)})

    try:
        proc = subprocess.Popen(
            argv, cwd=str(EXAMPLE_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
    except Exception as exc:  # pragma: no cover - defensive
        handler._write_chunk({"type": "error", "line": str(exc)})
        handler._write_chunk({"type": "end", "code": 1})
        return

    for line in proc.stdout:
        handler._write_chunk({"type": "out", "line": line.rstrip("\n")})
    proc.wait()
    handler._write_chunk({"type": "end", "code": proc.returncode})


def _display(argv):
    """Human-friendly rendering of an argv (collapse big -c snippets)."""
    if len(argv) >= 3 and argv[1] == "-c":
        return f"{Path(argv[0]).name} -c <coreconf snippet>"
    return " ".join(shlex.quote(a) for a in argv)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "CoreconfWebUI/1.0"

    # -- helpers ----------------------------------------------------------
    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _begin_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _write_chunk(self, obj):
        try:
            self.wfile.write((json.dumps(obj) + "\n").encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}

    def log_message(self, fmt, *args):  # quieter logging
        sys.stderr.write("[webui] " + (fmt % args) + "\n")

    # -- routing ----------------------------------------------------------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._serve_file(INDEX_HTML, "text/html; charset=utf-8")
        if self.path.startswith("/api/server/status"):
            return self._send_json({
                "server": SERVER.is_running(),
                "secure_server": SECURE_SERVER.is_running(),
                "python": PYTHON,
            })
        if self.path.startswith("/api/server/logs"):
            return self._server_logs(SERVER)
        if self.path.startswith("/api/secure/logs"):
            return self._server_logs(SECURE_SERVER)
        if self.path.startswith("/api/commands"):
            cat = {k: v["desc"] for k, v in COMMANDS.items() if v}
            return self._send_json({"commands": cat})
        return self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/api/server/start":
            ok, msg = SERVER.start()
            return self._send_json({"ok": ok, "msg": msg,
                                    "running": SERVER.is_running()})
        if self.path == "/api/server/stop":
            ok, msg = SERVER.stop()
            return self._send_json({"ok": ok, "msg": msg,
                                    "running": SERVER.is_running()})
        if self.path == "/api/secure/start":
            ok, msg = SECURE_SERVER.start()
            return self._send_json({"ok": ok, "msg": msg,
                                    "running": SECURE_SERVER.is_running()})
        if self.path == "/api/secure/stop":
            ok, msg = SECURE_SERVER.stop()
            return self._send_json({"ok": ok, "msg": msg,
                                    "running": SECURE_SERVER.is_running()})
        if self.path == "/api/run":
            body = self._read_body()
            name = (body.get("command") or "").strip()
            self._begin_stream()
            run_command_stream(name, self)
            return
        return self._send_json({"error": "not found"}, 404)

    # -- misc -------------------------------------------------------------
    def _serve_file(self, path, content_type):
        try:
            data = Path(path).read_bytes()
        except FileNotFoundError:
            return self._send_json({"error": f"missing {path}"}, 500)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _server_logs(self, mgr):
        try:
            since = int(self.path.split("since=")[-1]) if "since=" in self.path else 0
        except ValueError:
            since = 0
        total, new = mgr.logs(since)
        return self._send_json({"total": total, "lines": new,
                                "running": mgr.is_running()})


def main():
    httpd = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    url = f"http://{HTTP_HOST}:{HTTP_PORT}"
    print(f"CORECONF coffee-maker web console at {url}")
    print(f"Using Python interpreter: {PYTHON}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        SERVER.stop()
        SECURE_SERVER.stop()
        httpd.server_close()


if __name__ == "__main__":
    main()
