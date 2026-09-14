@echo off
rem Solo dice que tablas hay y que significa. NO toca nada.

cd /d "%~dp0"
echo ============================================
echo  Estado de la migracion de la llave
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "cd '%~dp0'; $py = if (Get-Command py -EA SilentlyContinue) { 'py' } else { 'python' }; & $py -m vigia.crudo.rellave --dsn 'postgresql://vigia:vigia@localhost:5432/vigia' --estado"

echo.
pause
