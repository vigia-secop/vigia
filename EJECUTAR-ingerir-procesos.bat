@echo off
rem Lanzador para ingerir-procesos.ps1
rem
rem Trae la otra mitad del cruce y vuelve a normalizar.
rem NO pregunta nada: correr esto ES la confirmacion.
rem Puede tardar varios minutos.

cd /d "%~dp0"
echo ============================================
echo  Ingesta de Procesos y nuevo cruce
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ingerir-procesos.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
pause
