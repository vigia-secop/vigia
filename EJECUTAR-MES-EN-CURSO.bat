@echo off
REM Publica el resumen del mes que va corriendo: del dia 1 hasta hoy.
REM
REM Si la ingesta esta atrasada, el script NO inventa los dias que faltan:
REM recorta el final a la ultima fecha con datos y te lo dice en amarillo.
REM Para traer lo que falte, corre antes EJECUTAR-DIA.bat.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publicar.ps1" -MesEnCurso
echo.
pause
