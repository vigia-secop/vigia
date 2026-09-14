@echo off
rem Diagnostico + corridas diaria, semanal y mensual + resumen de prueba.
rem No necesita permisos de administrador.

cd /d "%~dp0"
echo ============================================
echo  Vigia -- diagnostico y corridas programadas
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar-todo.ps1"
echo.
pause
