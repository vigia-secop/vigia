@echo off
REM ============================================================
REM   VIGIA SECOP - CADA DIA
REM   Un clic al dia. Trae lo nuevo y publica la pagina.
REM   Tarda alrededor de una hora. Dejalo corriendo.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cada-dia.ps1"
echo.
pause
