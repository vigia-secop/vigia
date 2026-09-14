@echo off
rem Lanzador para revisar-crudo.ps1 -- diagnostico de SOLO LECTURA.
rem No escribe nada en la base de datos.

cd /d "%~dp0"
echo ============================================
echo  Diagnostico de la capa cruda (solo lectura)
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0revisar-crudo.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
pause
