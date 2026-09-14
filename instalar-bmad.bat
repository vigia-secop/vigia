@echo off
chcp 65001 >nul
cd /d "%USERPROFILE%\Desktop\vigia-secop"

echo === VIGIA SECOP - Instalador de BMAD === > instalacion-log.txt
echo Fecha: %date% %time% >> instalacion-log.txt
echo. >> instalacion-log.txt

echo Verificando Node.js...
echo --- Version de Node --- >> instalacion-log.txt
node -v >> instalacion-log.txt 2>&1
if errorlevel 1 (
  echo. >> instalacion-log.txt
  echo RESULTADO: NODE NO ENCONTRADO >> instalacion-log.txt
  echo Descarga Node.js 20.12 o superior desde https://nodejs.org y vuelve a ejecutar este archivo. >> instalacion-log.txt
  echo.
  echo No se encontro Node.js. Revisa instalacion-log.txt
  pause
  exit /b 1
)

echo Instalando BMAD. Esto puede tardar varios minutos...
echo. >> instalacion-log.txt
echo --- Instalacion de BMAD --- >> instalacion-log.txt
call npx -y bmad-method@6.11.0 install --directory "%USERPROFILE%\Desktop\vigia-secop" --modules bmm --tools claude-code --yes --user-name Guillermo --communication-language Spanish --document-output-language Spanish >> instalacion-log.txt 2>&1

echo. >> instalacion-log.txt
echo --- FIN --- >> instalacion-log.txt

echo.
echo Listo. Revisa instalacion-log.txt para ver el resultado.
pause
