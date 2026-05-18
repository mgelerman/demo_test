<#
.SYNOPSIS
  Run the full E2E suite in brief order: login -> e2e purchase flow -> data-driven search.

.DESCRIPTION
  pytest collects test files alphabetically by default, which means the
  login test (test_login.py) would run AFTER test_e2e_purchase_flow.py.
  This wrapper makes the order match the brief's narrative order:

      1. test_login.py                     - authentication
      2. test_e2e_purchase_flow.py         - search + add + assert
      3. test_search_data_driven.py        - data-driven search scenarios

  Each subsequent test still re-authenticates via the ``logged_in_page``
  fixture (so they remain runnable standalone), but the SUITE order keeps
  the Allure timeline reading top-to-bottom in the same order as the
  brief's bullet list.

.NOTES
  Any extra arguments after the standard ones are forwarded verbatim to
  pytest. Useful for ``--headed=true``, ``-k <expr>``, ``--maxfail=1``, etc.

.EXAMPLE
  .\scripts\run-suite.ps1
  .\scripts\run-suite.ps1 -k tshirt --maxfail=1
  .\scripts\run-suite.ps1 --headed=true
#>

[CmdletBinding(PositionalBinding = $false)]
param(
    # Any pytest options (e.g. -k, --headed=true, --maxfail=1) are collected
    # here and forwarded as-is. ``ValueFromRemainingArguments`` makes the
    # PowerShell binder accept arbitrary flags without choking on unknown
    # parameter names, which is what callers naturally type.
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $env:PYTHONUNBUFFERED = "1"

    # ----------------------------------------------------------------------
    # Pre-flight: kill any leftover Chrome / Chromium / Node / pytest python
    # processes from a previous run. pytest-playwright's session teardown can
    # leak headless chrome workers when a run is aborted (Ctrl+C, hung
    # network, OS sleep, etc.) and those zombies hold handles the next
    # session needs - which is exactly how we get the multi-minute teardown
    # hangs. Wiping them up-front guarantees a fresh slate every invocation.
    # ----------------------------------------------------------------------
    Write-Host "Pre-flight: killing stale automation processes..." -ForegroundColor DarkGray
    # Only kill Chrome/Chromium spawned by Playwright (command line contains
    # 'ms-playwright'). This leaves personal Chrome, Teams, Edge untouched.
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^(chrome|chromium)\.exe$' -and
            $_.CommandLine -match 'ms-playwright'
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'pytest' -and $_.ProcessId -ne $PID } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Milliseconds 500

    $orderedTargets = @(
        "tests/test_login.py",
        "tests/test_e2e_purchase_flow.py",
        "tests/test_search_data_driven.py"
    )

    $alluredir = "reports/allure-results"
    Write-Host "Running suite in brief order:" -ForegroundColor Cyan
    foreach ($t in $orderedTargets) { Write-Host "  - $t" -ForegroundColor Cyan }
    Write-Host ""

    $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = "python"  # fall back to PATH
    }

    if ($PytestArgs -and $PytestArgs.Count -gt 0) {
        & $pythonExe -u -m pytest @orderedTargets -v --alluredir=$alluredir @PytestArgs
    } else {
        & $pythonExe -u -m pytest @orderedTargets -v --alluredir=$alluredir
    }
    $rc = $LASTEXITCODE

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    if ($rc -eq 0) {
        Write-Host "  All suite tests PASSED." -ForegroundColor Green
    } else {
        Write-Host "  Suite finished with exit code $rc." -ForegroundColor Yellow
    }
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    # Auto-build the Allure HTML report so it's ready to view immediately.
    if (Test-Path "reports\allure-results") {
        # Preserve history so the Trend chart accumulates across runs.
        $histSrc = "reports\allure-html\history"
        $histDst = "reports\allure-results\history"
        if (Test-Path $histSrc) {
            if (Test-Path $histDst) { Remove-Item $histDst -Recurse -Force }
            Copy-Item $histSrc $histDst -Recurse
        }
        Write-Host "Building Allure HTML report..." -ForegroundColor Cyan
        try {
            allure generate "reports/allure-results" --clean -o "reports/allure-html" 2>&1 | Out-Null
            Write-Host "  Report ready at: reports\allure-html\index.html" -ForegroundColor Green
            Write-Host "  View it:  .\scripts\open-report.ps1" -ForegroundColor Cyan
        } catch {
            Write-Host "  allure generate failed: $_" -ForegroundColor Yellow
        }

        # Build the evidence dashboard (single-file HTML with embedded screenshots).
        Write-Host "Building evidence dashboard..." -ForegroundColor Cyan
        try {
            & $pythonExe scripts/build-dashboard.py
            Write-Host "  Dashboard ready at: reports\dashboard.html" -ForegroundColor Green
        } catch {
            Write-Host "  Dashboard build failed: $_" -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "Press any key to close this window..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit $rc
}
finally {
    Pop-Location
}
