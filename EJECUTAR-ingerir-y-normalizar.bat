@echo off
rem Lanzador para ingerir-y-normalizar.ps1
rem
rem Doble clic aqui. Esta ventana NO se cierra sola.
rem
rem NO pregunta nada antes de trabajar: correr esto ES la confirmacion de que
rem quieres escribir en la base de datos. La unica pausa esta al final.

cd /d "%~dp0"
echo ============================================
echo  Ingesta real y normalizacion
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ingerir-y-normalizar.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
echo Si arriba no salio nada, algo esta bloqueando los scripts
echo (antivirus o directiva de Windows). Copia lo que veas y mandalo.
echo.
pause
