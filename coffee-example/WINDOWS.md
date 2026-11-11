# Running the Coffee-Maker CORECONF Example on Native Windows 11

This guide covers running the simulator **natively on Windows 11 — no WSL and
no Docker**. Everything runs as ordinary Windows processes under a Python
virtual environment. For the Docker path (which also works on Windows) see
[`DOCKER_SHARING.md`](DOCKER_SHARING.md); for macOS/Linux see
[`README.md`](README.md).

> **TL;DR:** install Python 3.10+, then from a PowerShell or `cmd` prompt in
> this folder run `.\run.ps1` (PowerShell) or `run.cmd` (cmd/double-click).
> It makes a `.venv`, installs the two dependencies, and opens the web console
> on <http://127.0.0.1:8080>.

---

## Prerequisites

### Python 3.10 or newer (required)

The two runtime dependencies both declare **`Requires-Python: >=3.10`**:

| Package  | Min Python | Notes |
|----------|-----------|-------|
| `cbor2`  | 3.10 | Ships a C extension *and* a pure-Python fallback. |
| `aiocoap[oscore]` | 3.10 | Pure-Python; the `[oscore]` extra pulls in `cryptography`. |

These minimums were verified against the published package metadata
(`cbor2` and `aiocoap` 0.4.17 at the time of writing). The older `run.bat` /
`README` text says "3.9+"; on Windows use **3.10+** so the current wheels
install. Python 3.11 or 3.12 is a safe choice.

Install from <https://www.python.org/downloads/windows/> (the installer adds
the `py` launcher). Tick **"Add python.exe to PATH"**, or just rely on `py`.
Verify:

```powershell
py -3 --version        # or:  python --version
```

### Build tools: not required

You do **not** need Visual C++ Build Tools. Every dependency (and its
transitive deps) publishes prebuilt Windows wheels for supported CPython
versions:

- `cbor2` — `win32` / `win_amd64` / `win_arm64` wheels for cp310–cp315, so its
  C accelerator installs without a compiler. (If no wheel matched your Python,
  `cbor2` still falls back to pure Python.)
- `cryptography` (via `aiocoap[oscore]`) — ships `win_amd64` wheels.
- `aiocoap` — pure Python, no compilation.

So on a stock Python 3.10+ install, `pip install -r requirements.txt` pulls
only wheels. A compiler is needed **only** if you deliberately run a Python
version so new that a wheel doesn't exist yet — pick a release with wheels
(3.10–3.13) to avoid that.

### No admin rights needed

The launcher creates a per-project `.venv`; nothing is installed
machine-wide. If PowerShell refuses to run the script (`running scripts is
disabled on this system`), either use `run.cmd` (which bypasses the policy for
that one run) or start the script with:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

---

## Run the web UI

From **PowerShell** in this folder:

```powershell
.\run.ps1                 # start on http://127.0.0.1:8080
.\run.ps1 -Port 9000      # pick a different port
```

From **cmd.exe** (or by double-clicking in Explorer):

```bat
run.cmd
run.cmd -Port 9000
```

Either launcher:

1. locates Python (`py -3`, else `python`),
2. creates `.venv\` on first run and checks it is 3.10+,
3. installs `aiocoap` + `cbor2` on first run,
4. starts `webui\web_console.py` and prints the child PID,
5. on **Ctrl+C**, stops the console with `taskkill /T` (which also stops the
   `server.py` subprocess the console spawns).

Then open <http://127.0.0.1:8080> and click **Start manager + fleet**.

> The Unix launcher `run.sh` is unchanged. `run.ps1` is its native-Windows
> sibling; `run.bat` still works too but `run.ps1`/`run.cmd` are preferred on
> Windows because they track and clean up the child process via
> `Start-Process` / `Get-Process` / `taskkill`.

### Configuration (environment variables)

| Variable         | Default     | Purpose |
|------------------|-------------|---------|
| `WEBUI_HOST`     | `127.0.0.1` | Interface the web UI binds to. `-BindHost` / `-Port` on `run.ps1` set these. |
| `WEBUI_PORT`     | `8080`      | Port the web UI listens on. |
| `COAP_BIND_HOST` | `::`        | Address the CoAP/CORECONF datastore (`server.py` / `secure_server.py`) binds to. |
| `COAP_BIND_PORT` | `5683`      | UDP port for the CoAP datastore. |

**Windows `localhost` / IPv6 note.** `server.py` binds the IPv6 wildcard
`::` by default. On some Windows setups the local clients resolve `localhost`
to IPv4 `127.0.0.1` only and won't reach an IPv6-only socket. If **Start
manager + fleet** connects but operations time out, force IPv4 before
launching:

```powershell
$env:COAP_BIND_HOST = "127.0.0.1"
.\run.ps1
```

(The web console inherits this env var when it spawns `server.py`.)

### Running the pieces by hand

If you'd rather not use the launcher:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# plain CLI demo — two terminals
$env:COAP_BIND_HOST = "127.0.0.1"   # if localhost is IPv4-only
python server.py
python client.py

# OSCORE-secured demo
python setup_security.py
python secure_server.py
python secure_client.py
```

---

## Package it for a WSL-less Windows machine

Two offline-friendly ways to hand this to someone on Windows who has **no**
WSL and no Docker. Pick based on whether the target machine has internet
access to PyPI.

### A) Source zip (target can reach PyPI)

Ship just the project; the launcher downloads the two wheels on first run.

Create the zip **from this folder**, excluding the local venv and caches so it
stays small and reproducible:

```powershell
# From inside coffee-example\  (PowerShell 5+)
$exclude = @('.venv','__pycache__','oscore-contexts','.git')
$items = Get-ChildItem -Force | Where-Object { $exclude -notcontains $_.Name }
Compress-Archive -Path $items -DestinationPath ..\coffee-coreconf-src.zip -Force
```

Recipient:

```powershell
Expand-Archive .\coffee-coreconf-src.zip -DestinationPath .\coffee-coreconf
cd .\coffee-coreconf
.\run.ps1        # creates .venv, pulls wheels from PyPI, starts the UI
```

Requirements on the target: Python 3.10+ and network access to PyPI. No build
tools (wheels only).

### B) Offline vendored-deps bundle (target has no internet)

Pre-download the Windows wheels and ship them with the source, so the target
installs with **no network access at all**. Build the bundle on any machine
with internet (Windows, or Linux/macOS using `pip download`'s cross-platform
flags).

**1. Vendor the wheels** for the target's Python (adjust `--python-version`
and `--platform` to match the target — `win_amd64` + `3.12` shown):

```bash
# Build the wheel cache (run anywhere with internet):
pip download -r requirements.txt \
    --only-binary=:all: \
    --platform win_amd64 \
    --python-version 3.12 \
    --implementation cp \
    --dest vendor-wheels
```

This writes `aiocoap`, `cbor2`, `cryptography`, and their deps as `.whl`
files into `vendor-wheels\`.

**2. Zip the project *including* `vendor-wheels\`:**

```powershell
$exclude = @('.venv','__pycache__','oscore-contexts','.git')
$items = Get-ChildItem -Force | Where-Object { $exclude -notcontains $_.Name }
Compress-Archive -Path $items -DestinationPath ..\coffee-coreconf-offline.zip -Force
```

**3. On the offline target**, create the venv and install from the bundle
with `--no-index` (no PyPI contact):

```powershell
Expand-Archive .\coffee-coreconf-offline.zip -DestinationPath .\coffee-coreconf
cd .\coffee-coreconf
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\vendor-wheels -r requirements.txt
.\.venv\Scripts\python.exe webui\web_console.py
```

Because the venv already has the deps, `run.ps1` will skip its install step
and go straight to launching the console — so after step 3's `pip install`
the recipient can simply run `.\run.ps1` on subsequent starts.

> **Match the interpreter.** Wheels are Python-version- and
> architecture-specific. Vendor for the exact `--python-version` /
> `--platform` the target runs (e.g. `cp311` + `win_amd64`). If unsure, ask
> the recipient for `py -3 --version` and `python -c "import platform;
> print(platform.machine())"` first. For ARM Windows use `--platform
> win_arm64`.

---

## What was verified vs. not

- **Verified on Linux (this repo's dev host):** the code changes behind the
  Windows path — the env-configurable CoAP bind (`COAP_BIND_HOST=127.0.0.1
  python server.py` serving a real GET to `client.py`), the web console
  booting and resolving the venv interpreter, and the cross-platform
  stop logic compiling. Dependency metadata and Windows-wheel availability
  (`cbor2`, `aiocoap`, `cryptography`) were confirmed against PyPI, including a
  successful `pip download` of the `cbor2` `win_amd64` wheel.
- **Not executed here (no Windows host available):** `run.ps1` / `run.cmd`
  end-to-end, `taskkill`-based shutdown, and the IPv4-vs-IPv6 `localhost`
  behaviour on Windows. These are written to standard, documented Windows
  behaviour; validate them on a real Windows 11 machine before relying on
  them in a demo.

---

## Quick troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `running scripts is disabled on this system` | PowerShell execution policy. Use `run.cmd`, or `powershell -ExecutionPolicy Bypass -File .\run.ps1`. |
| `Python not found` | Install Python 3.10+ and tick "Add to PATH", or use the `py` launcher. |
| `.venv has 3.9` (or similar) error | The launcher enforces 3.10+. Delete `.venv\` and re-run with a newer Python (`py -3.12 -m venv .venv`). |
| UI loads, **Start manager + fleet** connects but ops time out | `localhost` is IPv4-only; set `$env:COAP_BIND_HOST = "127.0.0.1"` before launching. |
| `No matching distribution` during offline install | Vendored wheels don't match the target's Python version/arch. Re-run `pip download` with the right `--python-version` / `--platform`. |
| Port 8080 in use | `.\run.ps1 -Port 9000` (or set `$env:WEBUI_PORT`). |
| Firewall prompt on first run | Windows Defender Firewall asking to allow Python to listen. Allow it for private networks (local use only). |
