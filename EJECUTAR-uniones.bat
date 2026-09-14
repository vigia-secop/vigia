@echo off
rem Lanzador para uniones.ps1
rem
rem Aplica la migracion 007, vuelve a normalizar y te ensena las uniones
rem temporales y consorcios de TU base: cuantos son y cuanta plata mueven.

cd /d "%~dp0"
echo ============================================
echo  Uniones temporales y consorcios
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uniones.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
pause
