@echo off
REM ============================================================
REM   VIGIA SECOP - ERRATAS QUE CAMBIARON
REM   Que cifras publicadas se movieron entre una ingesta y otra.
REM   Solo lectura. Tarda un rato.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0erratas-que-cambiaron.ps1"
echo.
pause
