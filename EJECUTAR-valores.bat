@echo off
REM Busca valores imposibles en la capa de contratos.
REM SOLO LECTURA: no cambia nada en la base.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0valores.ps1"
echo.
pause
