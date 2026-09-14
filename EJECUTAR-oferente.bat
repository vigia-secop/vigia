@echo off
rem Mide si la bandera de oferente unico se puede construir. Solo lectura.

cd /d "%~dp0"
echo ============================================
echo  2.4 -- se puede medir el oferente unico?
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0oferente.ps1"
echo.
pause
