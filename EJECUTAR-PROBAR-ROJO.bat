@echo off
REM ============================================================
REM   VIGIA SECOP - QUE FORMA NO PINTA DE ROJO
REM   Prueba cinco maneras de imprimir la salida de Python.
REM   No toca nada: solo escribe en pantalla.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0probar-rojo.ps1"
echo.
pause
