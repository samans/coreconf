#!/usr/bin/env python3
"""
Web console for the CORECONF coffee-maker *fleet* example.

A dependency-free (stdlib only) HTTP server that serves an HTML user
interface which visualises the CORECONF message passing between the
coffee-maker manager and the fleet datastore, and renders a live dashboard
of every coffee maker under management.

What it provides:

  * Serves  index.html  (the UI).
  * POST /api/server/start   -> launch server.py as a background process.
  * POST /api/server/stop    -> terminate the running CoAP server.
  * GET  /api/server/status  -> whether the CoAP server is running.
  * GET  /api/server/logs    -> incremental server stdout/stderr (poll).
  * GET  /api/fleet          -> current fleet state (decoded JSON) for the
                                dashboard, via a one-shot CORECONF GET.
  * POST /api/op             -> run one CORECONF operation and stream the
                                manager<->fleet message events (ndjson).

Run:
    python3 webui/web_console.py
then open http://localhost:8080 in a browser.
"""

import json
import os
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLE_DIR = HERE.parent
INDEX_HTML = HERE / "index.html"
FLOW_CLIENT = HERE / "flow_client.py"

VENV_PY = EXAMPLE_DIR / ".venv" / "bin" / "python3"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable

HTTP_HOST = os.environ.get("WEBUI_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("WEBUI_PORT", "8080"))

# Manager operations the UI can trigger. Each is a CORECONF exchange with the
# fleet datastore.
OPERATIONS = {
    "get":          "Read the whole fleet (manager + all makers)",
    "power-on":     "Turn a coffee maker ON",
    "power-off":    "Turn a coffee maker OFF",
    "set-cups":     "Set a maker's cups-per-brew",
    "set-strength": "Set a maker's brew strength",
    "brew":         "Brew on a maker (POST the brew action)",
    "refill":       "Add coffee beans + water to a maker (refill action)",
    "add":          "Add a new coffee maker to the fleet",
}

# Which optional parameters each operation accepts (passed to flow_client).
OP_PARAMS = {
    "get":          [],
    "power-on":     ["id"],
    "power-off":    ["id"],
    "set-cups":     ["id", "cups"],
    "set-strength": ["id", "strength"],
    "brew":         ["id"],
    "refill":       ["id"],
    "add":          ["id", "location"],
}


class ServerManager:
    """Owns the lifecycle of the background CoAP server process and buffers
    its combined stdout/stderr for incremental polling."""

    def __init__(self, script="server.py"):
        self.script = script
        self.proc = None
        self.lines = []
        self._lock = threading.Lock()

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
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            threading.Thread(target=self._pump, args=(self.proc,),
                             daemon=True).start()
            return True, "started"

    def _pump(self, proc):
        for line in proc.stdout:
            with self._lock:
                self.lines.append(line.rstrip("\n"))
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
            return len(self.lines), self.lines[since:]


SERVER = ServerManager()


class Handler(BaseHTTPRequestHandler):
    server_version = "CoffeeFleetWebUI/1.0"

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
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return {}

    def log_message(self, fmt, *args):
        sys.stderr.write("[webui] " + (fmt % args) + "\n")

    # -- routing ----------------------------------------------------------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._serve_file(INDEX_HTML, "text/html; charset=utf-8")
        if self.path.startswith("/api/server/status"):
            return self._send_json({"server": SERVER.is_running(),
                                    "python": PYTHON})
        if self.path.startswith("/api/server/logs"):
            try:
                since = int(self.path.split("since=")[-1]) if "since=" in self.path else 0
            except ValueError:
                since = 0
            total, new = SERVER.logs(since)
            return self._send_json({"total": total, "lines": new,
                                    "running": SERVER.is_running()})
        if self.path.startswith("/api/operations"):
            return self._send_json({"operations": OPERATIONS})
        if self.path.startswith("/api/fleet"):
            return self._send_json(self._fleet_snapshot())
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
        if self.path == "/api/op":
            body = self._read_body()
            op = (body.get("op") or "").strip()
            self._begin_stream()
            self._run_op(op, body)
            return
        return self._send_json({"error": "not found"}, 404)

    # -- fleet snapshot ---------------------------------------------------
    def _fleet_snapshot(self):
        """Run a one-shot CORECONF GET via flow_client and return the decoded
        fleet state for the dashboard."""
        if not SERVER.is_running():
            return {"running": False, "makers": []}
        try:
            proc = subprocess.run(
                [PYTHON, str(FLOW_CLIENT), "get"],
                cwd=str(EXAMPLE_DIR), capture_output=True, text=True,
                timeout=10)
        except Exception as exc:  # pragma: no cover
            return {"running": True, "makers": [], "error": str(exc)}
        decoded = None
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("decoded"):
                decoded = ev["decoded"]
        if decoded is None:
            return {"running": True, "makers": []}
        decoded["running"] = True
        return decoded

    # -- op runner --------------------------------------------------------
    def _run_op(self, op, body):
        if op not in OPERATIONS:
            self._write_chunk({"dir": "error", "label": f"unknown op: {op}"})
            self._write_chunk({"dir": "end"})
            return
        if not SERVER.is_running():
            self._write_chunk({"dir": "error",
                               "label": "server is not running — start it first"})
            self._write_chunk({"dir": "end"})
            return

        argv = [PYTHON, str(FLOW_CLIENT), op]
        for param in OP_PARAMS.get(op, []):
            val = body.get(param)
            if val is None or val == "":
                continue
            argv += [f"--{param.replace('_', '-')}", str(val)]

        try:
            proc = subprocess.Popen(
                argv, cwd=str(EXAMPLE_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
        except Exception as exc:  # pragma: no cover
            self._write_chunk({"dir": "error", "label": str(exc)})
            self._write_chunk({"dir": "end"})
            return

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._write_chunk(json.loads(line))
            except json.JSONDecodeError:
                self._write_chunk({"dir": "log", "label": line})
        err = proc.stderr.read()
        proc.wait()
        if proc.returncode != 0 and err:
            self._write_chunk({"dir": "error", "label": err.strip()})
        self._write_chunk({"dir": "end"})

    def _serve_file(self, path, content_type):
        try:
            data = Path(path).read_bytes()
        except FileNotFoundError:
            return self._send_json({"error": f"missing {path}"}, 500)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(data)


def main():
    httpd = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    url = f"http://{HTTP_HOST}:{HTTP_PORT}"
    print(f"CORECONF coffee-maker fleet web console at {url}")
    print(f"Using Python interpreter: {PYTHON}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        SERVER.stop()
        httpd.server_close()


if __name__ == "__main__":
    main()
