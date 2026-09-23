# PASO 3 - Subir a GitHub por primera vez.
#
#   Doble clic en EJECUTAR-PASO-3.bat
#
# QUE HACE Y QUE NO. Sube lo que ya esta guardado en el commit del paso 2. NO
# vuelve a construir el sitio y NO necesita la base de datos prendida - eso es
# a proposito: el objetivo de hoy es ver la pagina viva, y meter Postgres en el
# camino es una cosa mas que se puede romper.
#
# Reconstruir el sitio con los datos frescos es despues, con EJECUTAR-PUBLICAR.
#
# LAS TRES COMPROBACIONES ANTES DE SUBIR, y cualquiera aborta:
#
#   1. Que `.env` este ignorado. Lleva el token de Socrata, y esto va a un
#      repositorio PUBLICO.
#   2. Que el correo de git no te identifique. Un commit no se borra del
#      historial.
#   3. Que ninguna pagina de docs/ lleve el documento de una persona natural
#      escrito entero. Un NIT si puede ir: es de una empresa. Una cedula no.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$USUARIO = "Vigia-secop"
$REPO    = "https://github.com/$USUARIO/vigia.git"

try { Start-Transcript -Path (Join-Path $raiz "paso-3-ultima-corrida.txt") -Force | Out-Null } catch { }

function Bien($m)  { Write-Host "   OK  $m" -ForegroundColor Green }
function Aviso($m) { Write-Host "   --  $m" -ForegroundColor Yellow }
function Mal($m) {
    Write-Host ""
    Write-Host "   ABORTADO: $m" -ForegroundColor Red
    Write-Host "   No se subio nada." -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

# ---------------------------------------------------------------------------
# GIT ESCRIBE POR EL CANAL DE ERRORES AUNQUE TODO LE SALGA BIEN
# ---------------------------------------------------------------------------
# `git push` manda su parte por stderr, no por stdout. PowerShell convierte
# cada linea de stderr en un registro de error y la pinta en rojo con un
# bloque de NativeCommandError encima: la subida sale perfecta y la pantalla
# parece un accidente. Lo unico que dice si git fallo es su codigo de salida.
# Aqui se captura todo lo que git escribe, se imprime como texto normal, y se
# devuelve $LASTEXITCODE. El comentario de adentro dice por que se captura.
function Correr-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Argumentos)
    # SE CAPTURA LA SALIDA, NO SE REDIRIGE A UN ARCHIVO.
    #
    # El primer intento fue `& git ... 2>$archivo | ForEach-Object`. Funciona en
    # PowerShell 7 y NO funciona en el 5.1 de Windows, que es el que corre aqui:
    # alli `2>` sobre un programa externo sigue pasando por la maquinaria de
    # errores y el bloque rojo de NativeCommandError sale igual. Se vio el
    # 2026-09-16: la subida salio perfecta y la pantalla mostro
    # "publicar.ps1: 62" con RemoteException encima.
    #
    # Lo que si funciona en las dos: fusionar el canal de errores con el de
    # salida (`2>&1`) y ASIGNAR el resultado. Lo asignado no se muestra, asi
    # que PowerShell no tiene nada que pintar de rojo. Despues se imprime como
    # texto normal.
    #
    # Y por si acaso, mientras corre git se baja $ErrorActionPreference: no se
    # pierde informacion, porque lo unico que decide si git fallo es su codigo
    # de salida, y ese se mira abajo.
    $antes = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $salida = & git @Argumentos 2>&1
        $codigo = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $antes
    }
    foreach ($linea in @($salida)) {
        $texto = "$linea"
        if ($texto.Trim()) { Write-Host "   $texto" -ForegroundColor Gray }
    }
    return $codigo
}


Write-Host ""
Write-Host "  PASO 3 - subir a GitHub" -ForegroundColor White
Write-Host "  $REPO" -ForegroundColor DarkGray
Write-Host ""

# ---- git y python
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    foreach ($r in @("C:\Program Files\Git\cmd\git.exe",
                     "C:\Program Files (x86)\Git\cmd\git.exe",
                     "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe")) {
        if (Test-Path $r) { $env:PATH = (Split-Path $r) + ";" + $env:PATH; break }
    }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Mal "no encuentro git" }

$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; break
    }
}
if (-not $pyExe) { Mal "no hay Python 3.11+ (hace falta para revisar docs/)" }

if (-not (Test-Path (Join-Path $raiz ".git"))) { Mal "no hay repositorio. Corre primero EJECUTAR-PASO-2.bat" }
$hayCommit = (& git log -1 --format="%H" 2>$null)
if (-not $hayCommit) { Mal "el repositorio no tiene ningun commit. Corre primero EJECUTAR-PASO-2.bat" }

Write-Host "== 1 de 4 : .env fuera" -ForegroundColor Cyan
& git check-ignore -q ".env"
if ($LASTEXITCODE -ne 0) { Mal ".env NO esta ignorado por git. Lleva el token de Socrata." }
if ((& git ls-files) -contains ".env") { Mal ".env esta DENTRO del commit. No se sube." }
Bien ".env esta ignorado y fuera del commit"

Write-Host ""
Write-Host "== 2 de 4 : la firma no te identifica" -ForegroundColor Cyan
$autor = (& git log -1 --format="%an <%ae>")
Write-Host "   --  el ultimo commit va firmado como: $autor" -ForegroundColor DarkGray
if ($autor -notmatch 'users\.noreply\.github\.com>$') {
    Mal "la firma '$autor' NO es anonima. Corre EJECUTAR-PASO-2.bat"
}
Bien "la firma es anonima"

Write-Host ""
Write-Host "== 3 de 4 : ninguna cedula en docs/" -ForegroundColor Cyan
$revisor = @'
import sys, pathlib
sys.path.insert(0, ".")
from vigia.documento import persona_sin_enmascarar
malos, mirados = [], 0
carpeta = pathlib.Path("docs")
if not carpeta.exists():
    print("  no hay carpeta docs/ todavia"); sys.exit(0)
for p in sorted(carpeta.rglob("*")):
    if not p.is_file() or p.suffix.lower() not in (".html",".md",".txt",".json",".csv",".svg"):
        continue
    mirados += 1
    h = persona_sin_enmascarar(p.read_text(encoding="utf-8", errors="replace"))
    if h: malos.append((str(p), h[:3]))
if malos:
    for f, h in malos: print(f"  {f}: {h}")
    sys.exit(1)
print(f"  {mirados} archivo(s) de docs/ revisados")
'@
$revisor | & $pyExe @pyArgs -
if ($LASTEXITCODE -ne 0) { Mal "hay documentos de persona natural sin enmascarar en docs/" }
Bien "ninguna cedula sin enmascarar"

Write-Host ""
Write-Host "== 4 de 4 : subir" -ForegroundColor Cyan
& git remote remove origin 2>$null | Out-Null
& git remote add origin $REPO
Write-Host "   La primera vez, git abre el navegador para que entres a GitHub." -ForegroundColor DarkGray
Write-Host "   La contrasena se escribe ALLA, no aqui." -ForegroundColor DarkGray
Write-Host ""

$codigoPush = Correr-Git push -u origin main
if ($codigoPush -ne 0) {
    Write-Host ""
    Write-Host "   El push no funciono. Las dos causas de siempre:" -ForegroundColor Yellow
    Write-Host "   1. El repositorio 'vigia' todavia no existe en GitHub." -ForegroundColor Gray
    Write-Host "      Creala en: https://github.com/new  (nombre: vigia, Public)" -ForegroundColor Gray
    Write-Host "   2. No te autenticaste en la ventana del navegador." -ForegroundColor Gray
    Mal "no se pudo subir"
}

Write-Host ""
Write-Host "  ----------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  SUBIDO." -ForegroundColor Green
Write-Host ""
Write-Host "  Ahora falta encender GitHub Pages, UNA sola vez:" -ForegroundColor White
Write-Host "    https://github.com/$USUARIO/vigia/settings/pages" -ForegroundColor Cyan
Write-Host ""
Write-Host "    Source : Deploy from a branch" -ForegroundColor Gray
Write-Host "    Branch : main        Folder: /docs        y Save" -ForegroundColor Gray
Write-Host ""
Write-Host "  A los 2 o 3 minutos, la pagina vive en:" -ForegroundColor White
Write-Host "    https://$($USUARIO.ToLower()).github.io/vigia/" -ForegroundColor Cyan
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
Read-Host "  Enter para cerrar"
