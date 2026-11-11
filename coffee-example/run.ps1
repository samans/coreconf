<#
.SYNOPSIS
    One-command launcher for the CORECONF coffee-maker fleet web console on
    native Windows (PowerShell) — no WSL, no Docker.

.DESCRIPTION
    Mirrors run.sh / run.bat: creates a local virtual environment (first run
    only), installs the two dependencies, and starts the web console. Needs
    Python 3.10+ on PATH (py launcher or python.exe).

    The web console is launched with Start-Process so this script can report
    the child's PID and, on Ctrl+C, stop it cleanly with taskkill. Get-Process
    is used to confirm the child is alive before and after.

.PARAMETER Port
    Web UI port. Overrides $env:WEBUI_PORT. Default 8080.

.PARAMETER BindHost
    Web UI bind address. Overrides $env:WEBUI_HOST. Default 127.0.0.1.

.EXAMPLE
    .\run.ps1
    .\run.ps1 -Port 9000
    $env:WEBUI_PORT = "9000"; .\run.ps1

.NOTES
    If PowerShell blocks this script ("running scripts is disabled"), launch it
    for one session with:
        powershell -ExecutionPolicy Bypass -File .\run.ps1
    or use the run.cmd wrapper, which does that for you.
#>
[CmdletBinding()]
param(
    [int]$Port = $(if ($env:WEBUI_PORT) { [int]$env:WEBUI_PORT } else { 8080 }),
    [string]$BindHost = $(if ($env:WEBUI_HOST) { $env:WEBUI_HOST } else { "127.0.0.1" })
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# --- locate a Python interpreter -----------------------------------------
# Prefer the 'py' launcher (ships with python.org installers); fall back to
# python.exe on PATH. We ask for 3.10+ explicitly where we can.
function Resolve-Python {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        # 'py -3' picks the newest installed Python 3.
        return @{ Exe = $pyLauncher.Source; Args = @("-3") }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @{ Exe = $python.Source; Args = @() }
    }
    return $null
}

$py = Resolve-Python
if ($null -eq $py) {
    Write-Error "error: Python not found. Install Python 3.10+ (python.org) and retry."
    exit 1
}

# --- create the virtual environment (first run only) ----------------------
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[run] creating virtual environment (.venv)..."
    & $py.Exe @($py.Args + @("-m", "venv", ".venv"))
    if ($LASTEXITCODE -ne 0) {
        Write-Error "error: failed to create virtual environment."
        exit 1
    }
}

# Enforce the verified minimum runtime (both deps require Python >= 3.10).
$verOk = & $venvPython -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) {
    $ver = & $venvPython -c "import sys; print('%d.%d' % sys.version_info[:2])"
    Write-Error "error: Python 3.10+ required (aiocoap and cbor2 need >=3.10); .venv has $ver. Delete .venv and re-run with a newer Python."
    exit 1
}

# --- install dependencies (first run only) --------------------------------
& $venvPython -c "import aiocoap, cbor2" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[run] installing dependencies..."
    & $venvPython -m pip install --quiet --upgrade pip
    & $venvPython -m pip install --quiet -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "error: dependency install failed."
        exit 1
    }
}

# --- start the web console ------------------------------------------------
$env:WEBUI_HOST = $BindHost
$env:WEBUI_PORT = "$Port"

Write-Host "[run] starting web console on http://$BindHost`:$Port"
Write-Host "[run] press Ctrl+C to stop."

# Start-Process returns a process object we can track and stop. The console
# shares this window's stdout/stderr so logs appear inline.
$consoleScript = Join-Path $PSScriptRoot "webui\web_console.py"
$proc = Start-Process -FilePath $venvPython `
    -ArgumentList @($consoleScript) `
    -WorkingDirectory $PSScriptRoot `
    -NoNewWindow -PassThru

try {
    # Wait for the child, but keep this script responsive to Ctrl+C so we can
    # stop the console cleanly via taskkill.
    while (-not $proc.HasExited) {
        Start-Sleep -Milliseconds 300
        # Get-Process confirms the PID is still alive (defensive; HasExited
        # already covers the normal case).
        if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
            break
        }
    }
}
finally {
    if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
        Write-Host "`n[run] stopping web console (pid $($proc.Id))..."
        # /T also stops the child server.py the console may have spawned.
        taskkill /PID $proc.Id /T /F | Out-Null
    }
}
