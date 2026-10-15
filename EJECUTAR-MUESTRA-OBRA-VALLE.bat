@echo off
REM ============================================================
REM   MUESTRA: OBRA CIVIL Y EDIFICACIONES EN EL VALLE
REM   Solo lectura. Deja muestra-obra-valle.json
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0muestra-obra-valle.ps1"
echo.
pause
