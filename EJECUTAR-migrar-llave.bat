@echo off
rem Lanzador para migrar-llave.ps1
rem
rem NO toca crudo_registro: solo llena una tabla nueva y cuenta.

cd /d "%~dp0"
echo ============================================
echo  Migracion 005 -- llave de negocio
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0migrar-llave.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
pause
