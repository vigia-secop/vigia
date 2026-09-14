@echo off
REM Censa que campos de SECOP llegan poblados. Decide cuales de las seis
REM banderas que faltan se pueden construir. SOLO LECTURA.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0campos.ps1"
echo.
pause
