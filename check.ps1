# RuLens quality gate: lint, type-check, tests. Run before committing.
#   powershell -ExecutionPolicy Bypass -File check.ps1
Set-Location $PSScriptRoot
$py = ".\venv\Scripts\python.exe"

Write-Host "[1/3] pyflakes (lint)..." -ForegroundColor Cyan
& $py -m pyflakes rulens
if (-not $?) { Write-Host "pyflakes FAILED" -ForegroundColor Red; exit 1 }

Write-Host "[2/3] mypy (type check)..." -ForegroundColor Cyan
& $py -m mypy rulens
if (-not $?) { Write-Host "mypy FAILED" -ForegroundColor Red; exit 1 }

Write-Host "[3/3] pytest..." -ForegroundColor Cyan
& $py -m pytest -q
if (-not $?) { Write-Host "pytest FAILED" -ForegroundColor Red; exit 1 }

Write-Host "`nAll checks passed." -ForegroundColor Green
