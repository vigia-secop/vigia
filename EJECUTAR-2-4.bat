@echo off
rem Historia 2.4: bandera de oferente unico. Instala y corre las pruebas.
rem No toca la base de datos.

cd /d "%~dp0"
echo ============================================
echo  2.4 -- bandera de oferente unico
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0aplicar-2-4.ps1"
echo.
pause
