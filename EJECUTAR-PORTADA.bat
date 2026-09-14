@echo off
REM Construye la portada del dia (docs\index.html) y la abre. NO sube nada.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0portada.ps1"
echo.
pause
