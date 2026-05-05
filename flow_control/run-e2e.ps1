<#
.SYNOPSIS
  One-click E2E demo runner: clean → run all 5 tests (headed) → build report → open it.

.DESCRIPTION
  Designed for live demos. Runs the full flow in order:
    1. Kill stale browser/test processes
    2. Wipe previous reports (clean slate)
    3. Run the 5-test suite in headed mode (visible browser)
    4. Build the Allure HTML report
    5. Serve the report in the browser

.EXAMPLE
  .\flow_control\run-e2e.ps1                  # headed (default)
  .\flow_control\run-e2e.ps1 -Headless        # headless (CI-style)
#>

[CmdletBinding()]
param(
    [switch]$Headless
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $env:PYTHONUNBUFFERED = "1"

    # ------------------------------------------------- 1. Kill stale AUTOMATION processes only
    Write-Host ""
    Write-Host "=== Step 1/5: Killing stale automation processes ===" -ForegroundColor Magenta
    # Only kill chrome/chromium spawned by Playwright (command line contains 'ms-playwright').
    # This leaves your regular Chrome, Teams, Edge etc. untouched.
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
    Write-Host "  Done." -ForegroundColor Green

    # ------------------------------------------------- 2. Clean reports
    Write-Host ""
    Write-Host "=== Step 2/5: Cleaning previous reports ===" -ForegroundColor Magenta
    $cleanTargets = @(
        "reports",
        "storage_state.json",
        ".auth",
        "auth",
        ".pytest_cache"
    )
    foreach ($t in $cleanTargets) {
        $p = Join-Path $repoRoot $t
        if (Test-Path $p) {
            Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "  Done." -ForegroundColor Green

    # ------------------------------------------------- 3. Run tests
    Write-Host ""
    Write-Host "=== Step 3/5: Running E2E suite (5 tests) ===" -ForegroundColor Magenta

    $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }

    $orderedTargets = @(
        "tests/test_login.py",
        "tests/test_e2e_purchase_flow.py",
        "tests/test_search_data_driven.py"
    )

    Write-Host "  Mode: $(if ($Headless) { 'headless' } else { 'headed (visible browser)' })" -ForegroundColor Cyan
    foreach ($t in $orderedTargets) { Write-Host "  - $t" -ForegroundColor Cyan }
    Write-Host ""

    if ($Headless) {
        & $pythonExe -u -m pytest @orderedTargets -v
    } else {
        & $pythonExe -u -m pytest @orderedTargets -v --headed
    }
    $rc = $LASTEXITCODE

    Write-Host ""
    if ($rc -eq 0) {
        Write-Host "  ALL 5 TESTS PASSED" -ForegroundColor Green
    } else {
        Write-Host "  Suite finished with exit code $rc" -ForegroundColor Yellow
    }

    # ------------------------------------------------- 4. Build Allure report
    Write-Host ""
    Write-Host "=== Step 4/5: Building Allure HTML report ===" -ForegroundColor Magenta
    if (Test-Path "reports\allure-results") {
        try {
            allure generate "reports/allure-results" --clean -o "reports/allure-html" 2>&1 | Out-Null
            Write-Host "  Report built: reports\allure-html\" -ForegroundColor Green
        } catch {
            Write-Host "  allure generate failed: $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  No allure-results found, skipping." -ForegroundColor Yellow
    }

    # ------------------------------------------------- 5. Open report
    Write-Host ""
    Write-Host "=== Step 5/5: Opening Allure report ===" -ForegroundColor Magenta
    if (Test-Path "reports\allure-html\index.html") {
        try {
            Write-Host "  Serving at http://127.0.0.1:5050 ..." -ForegroundColor Cyan
            Write-Host "  Press Ctrl+C to stop the server." -ForegroundColor DarkGray
            Write-Host ""
            allure open "reports/allure-html" --port 5050
        } catch {
            Write-Host "  Could not serve report: $_" -ForegroundColor Yellow
            Write-Host "  Try manually: allure open reports/allure-html" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  No report to open." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Press any key to close..." -ForegroundColor DarkGray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }

    exit $rc
}
finally {
    Pop-Location
}
