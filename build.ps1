# Builds dist\PortGuard\ with two executables:
#   PortGuard.exe     - GUI application (no console window)
#   PortGuardCLI.exe  - command line (list, ports, holders, action, monitor)
#
#   .\build.ps1            normal build
#   .\build.ps1 -Clean     rebuild from scratch

param([switch]$Clean)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Clean) {
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
}

python tools\make_icon.py

python -m PyInstaller --noconfirm --clean PortGuard.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$gui = Join-Path $PSScriptRoot "dist\PortGuard\PortGuard.exe"
$cli = Join-Path $PSScriptRoot "dist\PortGuard\PortGuardCLI.exe"
foreach ($exe in @($gui, $cli)) {
    if (-not (Test-Path $exe)) { throw "Missing $exe" }
}

$size = [math]::Round((Get-ChildItem "dist\PortGuard" -Recurse -File |
    Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "Done: dist\PortGuard\ ($size MB)"
Write-Host "  PortGuard.exe    - GUI"
Write-Host "  PortGuardCLI.exe - list, ports, holders, action, monitor"
