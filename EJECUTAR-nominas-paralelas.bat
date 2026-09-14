@echo off
REM Cuenta personas con varios contratos abiertos a la vez (nominas paralelas).
REM SOLO LECTURA: no cambia nada en la base.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0nominas-paralelas.ps1"
echo.
pause
