@echo off
REM ============================================================
REM   VIGIA SECOP - LIMPIAR EL REPOSITORIO
REM   Saca lo que esta ignorado pero seguia versionado.
REM   No borra nada del disco.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0limpiar-repo.ps1"
echo.
pause
