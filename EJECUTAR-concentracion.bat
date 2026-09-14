@echo off
REM Mide si se puede construir la bandera 4.3 (concentracion por proveedor).
REM SOLO LECTURA: no cambia nada en la base.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0concentracion.ps1"
echo.
pause
