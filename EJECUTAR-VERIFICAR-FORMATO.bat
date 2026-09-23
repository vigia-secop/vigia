@echo off
REM   VIGIA SECOP - VERIFICAR SI EL CAMBIO DE HOY FUE SOLO DE FORMATO (solo lectura)
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verificar-formato.ps1"
echo.
pause
