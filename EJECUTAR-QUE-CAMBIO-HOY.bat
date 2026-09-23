@echo off
REM   VIGIA SECOP - QUE CAMBIO EN LA FUENTE HOY (solo lectura)
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0que-cambio-hoy.ps1"
echo.
pause
