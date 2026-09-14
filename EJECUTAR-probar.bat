@echo off
rem Lanzador para probar.ps1 -- la verificacion de punta a punta.
rem
rem Doble clic aqui. A diferencia de "Ejecutar con PowerShell", esta ventana
rem NO se cierra sola: si PowerShell se niega a correr el script, el motivo
rem queda escrito en pantalla en vez de desaparecer.
rem
rem El script pregunta una sola cosa (en el paso 9): escribe SI para ingerir
rem de verdad. Todo lo demas va solo. Queda copia en probar-ultima-corrida.txt.

cd /d "%~dp0"
echo ============================================
echo  probar.ps1 -- los 10 pasos
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0probar.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
echo Si arriba no salio nada, algo esta bloqueando los scripts
echo (antivirus o directiva de Windows). Copia lo que veas y mandalo.
echo.
pause
