@echo off
REM   VIGIA SECOP - QUE CIFRAS CAMBIARON DE VERDAD (solo lectura)
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verificar-cifras.ps1"
echo.
pause
