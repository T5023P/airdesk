# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# AIRDESK — launch from the project's own virtual environment.
#   .\scripts\run_airdesk_windows.ps1
#   .\scripts\run_airdesk_windows.ps1 --test-mode --source 0 --page dashboard
#   .\scripts\run_airdesk_windows.ps1 --full-diagnostics --probe-camera
#
# Never installs anything and never elevates: if setup is incomplete it says so.

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

function Fail($message, $hint) {
    Write-Host "ERROR: $message" -ForegroundColor Red
    if ($hint) { Write-Host "  $hint" -ForegroundColor Yellow }
    exit 1
}

if ($env:OS -ne "Windows_NT") {
    Fail "This launcher is for Windows." "On Kali Linux run ./scripts/run_airdesk_kali.sh"
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Fail "No virtual environment at .venv." "Run .\scripts\bootstrap_windows.ps1 first."
}

& $venvPython -c "import gestura" 2>$null
if ($LASTEXITCODE -ne 0) {
    Fail "AIRDESK is not importable from .venv (dependencies missing?)." `
         "Run .\scripts\bootstrap_windows.ps1 -Recreate"
}

& $venvPython main.py @Arguments
exit $LASTEXITCODE
