@echo off
rem Build PortGuard distribution (bypasses script execution policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
pause
