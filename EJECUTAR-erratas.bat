@echo off
REM Detecta erratas de tecleo x1000 en los valores. El techo de 1e14 no las ataja.
REM SOLO LECTURA: no cambia nada en la base.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0erratas.ps1"
echo.
pause
