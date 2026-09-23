@echo off
REM ============================================================
REM   VIGIA SECOP - DONDE SE VAN LOS MINUTOS DE BANDERAS
REM   Pide el plan sin correr la consulta. Sale rapido.
REM   No cambia nada en la base.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0medir-banderas.ps1"
echo.
pause
