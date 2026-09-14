@echo off
REM ============================================================
REM   TRAER LA HISTORIA DESDE EL 1 DE JULIO DE 2026
REM   TARDA UNAS 3 HORAS. Dejalo corriendo y vete.
REM   Se puede volver a correr: no duplica nada.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0historia.ps1" -Desde 2026-07-01
echo.
pause
