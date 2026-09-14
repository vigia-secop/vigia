@echo off
rem Aplica la correccion del conteo de nombres compartidos (66/67, no 85).
rem La tabla ya esta capturada en datos\divipola_municipios.csv; esto solo
rem corrige el codigo, las pruebas y la nota.

cd /d "%~dp0"
echo ============================================
echo  1.9 -- correccion del conteo
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0aplicar-1-9c.ps1"
echo.
pause
