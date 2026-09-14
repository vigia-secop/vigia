@echo off
rem Quien es el proveedor sin razon social. Solo lectura, segundos.

cd /d "%~dp0"
echo ============================================
echo  Diagnostico -- proveedor sin razon social
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0diagnostico.ps1"
echo.
pause
