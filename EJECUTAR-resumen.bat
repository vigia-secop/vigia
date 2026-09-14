@echo off
rem Resumen semanal sobre la ventana que ya esta en tu base.
rem Solo lectura. Abre la pagina al terminar.

cd /d "%~dp0"
echo ============================================
echo  Vigia -- resumen semanal
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0resumen-periodo.ps1" -Desde 2026-08-26 -Hasta 2026-09-02 -Titulo "Resumen semanal" -Salida "resumen-semanal.html"
if exist "%~dp0resumen-semanal.html" start "" "%~dp0resumen-semanal.html"
echo.
pause
