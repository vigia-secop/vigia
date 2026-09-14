@echo off
REM Cuenta identidades de proveedor que ya no apunta ningun contrato.
REM SOLO LECTURA: no cambia nada en la base.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fantasmas.ps1"
echo.
pause
