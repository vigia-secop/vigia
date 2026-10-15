@echo off
REM   VIGIA SECOP - COMO SE LLAMA ESA ENTIDAD EN EL SECOP (solo lectura)
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0buscar-entidad.ps1"
echo.
pause
