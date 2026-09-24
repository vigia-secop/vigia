@echo off
REM   VIGIA SECOP - POR QUE HOY SOLO ENTRARON 17 CONTRATOS (solo lectura)
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0por-que-17.ps1"
echo.
pause
