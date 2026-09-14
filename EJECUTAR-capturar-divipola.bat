@echo off
rem Captura la tabla DIVIPOLA de municipios desde datos.gov.co.
rem Solo lectura de una API publica. No toca la base de datos.

cd /d "%~dp0"
echo ============================================
echo  Capturar DIVIPOLA de municipios
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0capturar-divipola.ps1"
echo.
pause
