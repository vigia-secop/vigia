@echo off
REM ============================================================
REM   VIGIA SECOP - CUANTOS DIAS TARDA EL SECOP EN PUBLICAR
REM   Mide el retraso con la fecha de la fuente, no con la nuestra.
REM   Solo lectura. No lo corras junto con el ciclo.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0medir-retraso.ps1"
echo.
pause
