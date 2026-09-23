@echo off
REM ============================================================
REM   VIGIA SECOP - SOLTAR LA CONSULTA LARGA
REM   Mata las consultas de mas de 20 minutos que quedaron
REM   sueltas al cerrar una ventana. No borra datos.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0soltar-consulta-larga.ps1"
echo.
pause
