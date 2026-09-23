@echo off
REM ============================================================
REM   VIGIA SECOP - MEDIR POR QUE LAS CONSULTAS SON LENTAS
REM   No arregla nada: mide y escribe medicion-consultas.txt
REM   Tarda media hora larga. No lo corras junto con otra cosa.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0medir-consultas.ps1"
echo.
pause
