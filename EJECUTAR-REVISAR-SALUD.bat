@echo off
REM ============================================================
REM   VIGIA SECOP - ESTA AL DIA?
REM   Una sola pregunta: lo que esta en internet, es lo que hay
REM   en la base. Solo lectura: no arregla nada, solo dice.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0revisar-salud.ps1"
echo.
pause
