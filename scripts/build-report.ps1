<#
.SYNOPSIS
  Build a static Allure HTML report from the latest pytest run.

.DESCRIPTION
  Wraps `allure generate ... --clean` into a single command. After it
  finishes, IMPORTANT: the report MUST be opened over HTTP, not file://,
  because Allure loads its widgets via AJAX and browsers block XHR from
  file:// origins (you'll see seven "Loading..." panels forever).

  To view the built report:
      .\scripts\open-report.ps1            # uses `allure open`
  Or share it: zip the entire `reports\allure-html\` folder; the recipient
  can serve it with any static-file server (`python -m http.server` works).

.NOTES
  Requires the Allure CLI on PATH.
    - Windows:  scoop install allure
    - npm:      npm install -g allure-commandline
#>

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not (Test-Path "reports\allure-results")) {
        Write-Host "No allure results found at reports\allure-results." -ForegroundColor Yellow
        Write-Host "Run pytest first, e.g.:  pytest tests/ -v" -ForegroundColor Yellow
        exit 1
    }

    # Preserve history from the previous report so the Trend chart builds up
    # across runs. allure generate reads history/ from the input (allure-results)
    # and writes updated history/ to the output (allure-html).
    $historySource = "reports\allure-html\history"
    $historyDest   = "reports\allure-results\history"
    if (Test-Path $historySource) {
        if (Test-Path $historyDest) { Remove-Item $historyDest -Recurse -Force }
        Copy-Item $historySource $historyDest -Recurse
        Write-Host "  Preserved history from previous report." -ForegroundColor DarkGray
    }

    Write-Host "Generating Allure HTML report..." -ForegroundColor Cyan
    allure generate "reports/allure-results" --clean -o "reports/allure-html"

    Write-Host ""
    Write-Host "HTML report ready at: reports\allure-html\" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: open it via HTTP, not file:// (CORS blocks file:// XHR)." -ForegroundColor Yellow
    Write-Host "  Run:  .\scripts\open-report.ps1" -ForegroundColor Cyan
    Write-Host "  Or:   allure open reports/allure-html" -ForegroundColor Cyan

    # Build the evidence dashboard (single-file HTML with embedded screenshots).
    $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) { $pythonExe = "python" }
    Write-Host ""
    Write-Host "Building evidence dashboard..." -ForegroundColor Cyan
    try {
        & $pythonExe scripts/build-dashboard.py
        Write-Host "  Dashboard ready at: reports\dashboard.html" -ForegroundColor Green
        Write-Host "  Open it: start reports\dashboard.html" -ForegroundColor Cyan
    } catch {
        Write-Host "  Dashboard build failed: $_" -ForegroundColor Yellow
    }
}
finally {
    Pop-Location
}
