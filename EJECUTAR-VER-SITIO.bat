@echo off
REM Construye docs/ y NO sube nada. Para verlo antes de publicarlo.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publicar.ps1" -SoloConstruir
start "" "%~dp0docs\index.html"
echo.
pause
