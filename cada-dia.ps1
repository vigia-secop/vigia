# LO QUE SE CORRE CADA DIA. Un solo clic: trae lo nuevo y publica.
#
#     1. dia.ps1        ingesta, normalizacion, panel, lista de revision,
#                       resumenes y boletin de la semana.
#     2. publicar.ps1   construye el sitio y lo sube a GitHub Pages.
#
# POR QUE UNO DETRAS DEL OTRO Y NO LOS DOS A MANO. Publicar antes de que el
# ciclo termine saca la pagina con los datos de ayer (paso el 2026-09-16). El
# candado de `ciclo-en-curso.lock` lo impide, pero lo impide abortando: el
# sitio no se actualiza y nadie se entera. Encadenados, el orden no depende
# de acordarse.
#
# QUE MES SE PUBLICA. Del 4 en adelante, el mes en curso. Los tres primeros
# dias del mes, el mes ANTERIOR completo. La razon es el retraso de la fuente:
# el 1 de octubre no hay todavia ni un contrato de octubre en los datos, y
# `publicar.ps1 -MesEnCurso` abortaria con "no hay ni un contrato firmado". En
# cambio septiembre, ese dia, ya esta completo y es lo que vale la pena
# mostrar. El archivo (dia, semana y mes) conserva todo lo anterior igual.
#
# Si el ciclo falla, se publica igual: `publicar.ps1` recorta a la ultima fecha
# con datos y lo dice en pantalla. Una pagina de ayer, avisada, es mejor que
# ninguna pagina.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

Write-Host ""
Write-Host "  VIGIA - CADA DIA" -ForegroundColor White
Write-Host "  Paso 1 de 2: traer lo nuevo. Paso 2 de 2: publicar." -ForegroundColor DarkGray

& (Join-Path $raiz "dia.ps1")

if ((Get-Date).Day -le 3) {
    Write-Host ""
    Write-Host "  Primeros dias del mes: se publica el mes anterior completo." -ForegroundColor Gray
    & (Join-Path $raiz "publicar.ps1") -Mensual
} else {
    & (Join-Path $raiz "publicar.ps1") -MesEnCurso
}
