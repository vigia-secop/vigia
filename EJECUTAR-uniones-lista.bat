@echo off
rem Solo la lista de uniones temporales. No normaliza. Segundos.

cd /d "%~dp0"
echo ============================================
echo  Uniones temporales -- lista corregida
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uniones-lista.ps1"
echo.
pause
