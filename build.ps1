# Rebuild RuLens.exe (PyInstaller) and the installer (Inno Setup).
# Run from the project root:  powershell -ExecutionPolicy Bypass -File build.ps1
Set-Location $PSScriptRoot

Write-Host "[1/3] Generating icon..." -ForegroundColor Cyan
.\venv\Scripts\python.exe make_icon.py

Write-Host "[2/3] Building RuLens.exe (PyInstaller)..." -ForegroundColor Cyan
.\venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --name RuLens --icon rulens.ico `
  --add-data "rulens.ico;." --collect-all winrt --collect-all winocr `
  --hidden-import pystray._win32 run_rulens.py

Write-Host "[3/3] Building installer (Inno Setup)..." -ForegroundColor Cyan
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" }
& $iscc installer\rulens.iss

Write-Host "`nDone. Share this file:" -ForegroundColor Green
Write-Host "  installer\out\RuLens-Setup.exe"
