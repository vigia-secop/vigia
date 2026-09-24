@echo off
REM ============================================================
REM   VIGIA SECOP - SACAR LAS MEDICIONES DEL REPOSITORIO
REM   No borra archivos del disco. Arregla la publicacion.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sacar-mediciones-de-git.ps1"
echo.
pause
