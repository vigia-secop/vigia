@echo off
REM PASO 3 - sube a GitHub por primera vez. Revisa antes y aborta si algo huele mal.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0paso-3-subir.ps1"
