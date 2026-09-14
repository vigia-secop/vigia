@echo off
REM ============================================================
REM   VIGIA SECOP - EL DIA
REM   Doble clic aqui. Es lo unico que hay que correr.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0dia.ps1"
echo.
pause
