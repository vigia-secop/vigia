@echo off
REM Revisa una por una las erratas que estan deteniendo la publicacion.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0revisar-erratas.ps1"
echo.
pause
