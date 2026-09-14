@echo off
REM ============================================================
REM   TRAER HISTORIA HACIA ATRAS - 6 meses
REM   TARDA UNAS 2,5 HORAS. Dejalo corriendo y vete.
REM   Se puede volver a correr: no duplica nada.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0historia.ps1" -Meses 6
echo.
pause
