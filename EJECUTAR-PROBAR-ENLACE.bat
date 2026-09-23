@echo off
REM ============================================================
REM   VIGIA SECOP - PROBAR EL ARREGLO DEL ENLACE
REM   Compara la forma vieja con la nueva. No cambia nada.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0probar-enlace.ps1"
echo.
pause
