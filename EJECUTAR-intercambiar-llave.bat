@echo off
rem Comprueba el traslado y, SOLO si cuadra, intercambia.
rem La tabla anterior no se borra: queda como crudo_registro_antes_de_005.

cd /d "%~dp0"
echo ============================================
echo  Comprobar e intercambiar la llave
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0intercambiar-llave.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
pause
