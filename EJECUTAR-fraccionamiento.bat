@echo off
REM Mide si se puede construir la bandera 4.6 (fraccionamiento).
REM SOLO LECTURA: no cambia nada en la base.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fraccionamiento.ps1"
echo.
pause
