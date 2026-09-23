@echo off
REM ============================================================
REM   VIGIA SECOP - DESATASCAR LA BASE
REM   Doble clic aqui cuando un paso se queda quieto sin avanzar.
REM   Solo suelta a quien este frenando a otro. No borra nada.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0desatascar.ps1"
echo.
pause
