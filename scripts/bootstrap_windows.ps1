# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# AIRDESK — Windows development bootstrap.
#   .\scripts\bootstrap_windows.ps1            # create/refresh .venv and verify
#   .\scripts\bootstrap_windows.ps1 -Recreate  # delete .venv first, then install
#   .\scripts\bootstrap_windows.ps1 -SkipDev   # runtime dependencies only
#
# Per-user only: no administrator rights, no global packages, no paid services.

[CmdletBinding()]
param(
    [switch]$Recreate,
    [switch]$SkipDev,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Write-Ok($message)   { Write-Host "  OK  $message" -ForegroundColor Green }
function Write-Warn2($message){ Write-Host "  !!  $message" -ForegroundColor Yellow }
function Fail($message) {
    Write-Host "`nERROR: $message" -ForegroundColor Red
    exit 1
}

Write-Step "AIRDESK Windows bootstrap"
Write-Host "    project: $projectRoot"

# ---------------------------------------------------------------- 1. platform
if ($env:OS -ne "Windows_NT") {
    Fail "This script is for Windows. On Kali Linux run scripts/bootstrap_kali.sh instead."
}
$arch = if ([Environment]::Is64BitOperatingSystem) { "64-bit" } else { "32-bit" }
Write-Ok "Windows detected ($arch)"

# ------------------------------------------------------------------- 2. Python
$venv = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"

function Test-PythonCandidate($exe, $args) {
    try {
        $out = & $exe @args "-c" "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -Last 1).Trim() }
    } catch { }
    return $null
}

function Test-Supported($version) {
    if (-not $version) { return $false }
    $parts = $version.Split(".")
    return ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11 -and [int]$parts[1] -le 12)
}

$venvUsable = $false
if (-not $Recreate -and (Test-Path $venvPython)) {
    $existing = Test-PythonCandidate $venvPython @()
    if (Test-Supported $existing) {
        $venvUsable = $true
        Write-Ok "existing .venv runs Python $existing (will be reused)"
    } else {
        Write-Warn2 "existing .venv runs Python $existing, which is outside 3.11-3.12; it will be rebuilt"
        $Recreate = $true
    }
}

$pythonExe = $null; $pythonArgs = @(); $pythonVersion = $null
if (-not $venvUsable) {
    $candidates = @()
    if ($Python) { $candidates += , @($Python, @()) }
    $candidates += , @("py", @("-3.12"))
    $candidates += , @("py", @("-3.11"))
    $candidates += , @("py", @("-3"))
    $candidates += , @("python", @())
    $candidates += , @("python3", @())

    $found = @()
    foreach ($cand in $candidates) {
        $ver = Test-PythonCandidate $cand[0] $cand[1]
        if (-not $ver) { continue }
        $found += "$($cand[0]) $($cand[1] -join ' ') => $ver"
        if (-not $pythonExe -and (Test-Supported $ver)) {
            $pythonExe = $cand[0]; $pythonArgs = $cand[1]; $pythonVersion = $ver
        }
    }

    if (-not $pythonExe) {
        Write-Host ""
        Write-Host "Python 3.11 or 3.12 (64-bit) is required; found:" -ForegroundColor Red
        if ($found.Count -eq 0) { Write-Host "    (no python.exe / py launcher on PATH)" -ForegroundColor Red }
        else { $found | ForEach-Object { Write-Host "    $_" -ForegroundColor Red } }
        Write-Host "Install 3.12 from https://www.python.org/downloads/windows/ (tick" -ForegroundColor Yellow
        Write-Host "'Add python.exe to PATH'), or point at it directly:" -ForegroundColor Yellow
        Write-Host "    .\scripts\bootstrap_windows.ps1 -Python C:\Python312\python.exe" -ForegroundColor Yellow
        exit 1
    }
    Write-Ok "Python $pythonVersion via '$pythonExe $($pythonArgs -join ' ')'"
}

# ---------------------------------------------------------------------- 3. Git
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) { Write-Ok "git $((& git --version) -replace 'git version ','')" }
else { Write-Warn2 "git not found: source control and updates need it (https://git-scm.com/download/win)" }

# ------------------------------------------------------------- 4. venv + install
if ($Recreate -and (Test-Path $venv)) {
    Write-Step "Removing the existing virtual environment (-Recreate)"
    Remove-Item -Recurse -Force $venv
    $venvUsable = $false
}

if (-not (Test-Path $venvPython)) {
    if (-not $pythonExe) { Fail "No usable Python 3.11/3.12 found. Install one from python.org and retry." }
    Write-Step "Creating .venv with Python $pythonVersion"
    & $pythonExe @pythonArgs "-m" "venv" $venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the virtual environment. Install the Python 'venv' component." }
} elseif (-not $venvUsable) {
    Write-Ok "Reusing the existing .venv"
} else {
    Write-Ok "Reusing the existing .venv"
}
if (-not (Test-Path $venvPython)) { Fail "The virtual environment has no interpreter at $venvPython" }

Write-Step "Upgrading pip inside .venv"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed (check your network or proxy)." }

Write-Step "Installing the pinned runtime dependencies (requirements.txt)"
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "Dependency installation failed. Re-run with -Recreate, then read the pip error above." }

if (-not $SkipDev) {
    Write-Step "Installing test dependencies (requirements-dev.txt)"
    & $venvPython -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { Fail "Development dependency installation failed." }
}

Write-Step "Installing AIRDESK in editable mode (project metadata)"
& $venvPython -m pip install -e . --no-deps
if ($LASTEXITCODE -ne 0) { Fail "Editable install failed; check pyproject.toml." }

# ------------------------------------------------------------------- 5. checks
Write-Step "Validating imports and the bundled models"
$check = @'
import sys
import cv2, mediapipe, numpy, pyautogui, pydantic
from PySide6 import QtWidgets
import gestura
from gestura.vision.models import verify_models
print(f"airdesk {gestura.__version__} | python {sys.version.split()[0]}")
print(f"opencv {cv2.__version__} | mediapipe {mediapipe.__version__} | numpy {numpy.__version__}")
print(f"pyside6 {QtWidgets.__name__} ok | pyautogui {pyautogui.__version__} | pydantic {pydantic.__version__}")
bad = []
for m in verify_models():
    print(f"  model {m.name}: {'ok' if m.usable else m.detail}")
    if not m.usable:
        bad.append(m.name)
sys.exit(1 if bad else 0)
'@
$tmp = Join-Path $env:TEMP "airdesk_bootstrap_check.py"
Set-Content -Path $tmp -Value $check -Encoding UTF8
& $venvPython $tmp
$checkExit = $LASTEXITCODE
Remove-Item $tmp -ErrorAction SilentlyContinue
if ($checkExit -ne 0) {
    Write-Host ""
    Write-Warn2 "A model is missing or no longer matches its pinned checksum."
    Write-Host "    Fix with: .\.venv\Scripts\python.exe scripts\download_models.py" -ForegroundColor Yellow
    Write-Host "    Model source and licence: UPSTREAM.md" -ForegroundColor Yellow
    exit 1
}

Write-Step "Running the platform diagnostics"
& $venvPython main.py --diagnostics

Write-Host ""
Write-Ok "AIRDESK is installed in $venv"
Write-Host "    Launch:  .\scripts\run_airdesk_windows.ps1"
Write-Host "    Tests:   .\.venv\Scripts\python.exe -m pytest"
Write-Host "    Camera:  .\.venv\Scripts\python.exe main.py --camera-diagnostics"
Write-Host "    Full:    .\.venv\Scripts\python.exe main.py --full-diagnostics --probe-camera"
Write-Host "    Docs:    docs/DEVELOPMENT_WINDOWS.md"
