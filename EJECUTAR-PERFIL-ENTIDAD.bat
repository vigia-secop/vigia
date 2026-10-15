@echo off
REM   VIGIA SECOP - PERFIL DE CONTRATACION DE UNA ENTIDAD (solo lectura)
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0perfil-entidad.ps1"
echo.
pause
