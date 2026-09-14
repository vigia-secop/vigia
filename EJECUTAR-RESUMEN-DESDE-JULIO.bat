@echo off
REM ============================================================
REM   EL RESUMEN ACUMULADO: 1 de julio a hoy.
REM   Construye docs/ y lo abre. NO sube nada.
REM   Antes hay que haber corrido EJECUTAR-HISTORIA-DESDE-JULIO.bat
REM ============================================================
cd /d "%~dp0"
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"') do set HOY=%%i
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publicar.ps1" -SoloConstruir -Desde 2026-07-01 -Hasta %HOY%
start "" "%~dp0docs\index.html"
echo.
pause
