# PASO 2 - Dejar el repositorio firmando ANONIMO.
#
#   Doble clic en EJECUTAR-PASO-2.bat
#
# QUE ARREGLA, Y POR QUE HAY QUE ARREGLARLO. El registro del 3 de septiembre
# dice que los commits de esta carpeta se estan firmando asi:
#
#     firma: Guillermo <yeyosag9@gmail.com>
#
# Ese correo queda grabado en CADA commit, para siempre. En un repositorio
# publico cualquiera lo lee con un clic, y no se borra con `git commit --amend`:
# queda en el historial y en cualquier copia que alguien haya clonado.
#
# Cambiar la configuracion NO arregla los commits que ya existen. Lo limpio es
# empezar el repositorio de cero: se aparta el historial viejo, se configura la
# identidad anonima, y se hace el primer commit otra vez.
#
# SE PIERDE EL HISTORIAL LOCAL DE TUS CAMBIOS. No se pierde NI UN ARCHIVO.
# Y no se pierde nada publicado, porque este repositorio nunca se ha subido.
#
# EL HISTORIAL VIEJO NO SE BORRA: se mueve al Escritorio, a una carpeta que
# dice en el nombre lo que es. Si algun dia lo quieres, ahi esta. Cuando estes
# tranquilo, la borras tu.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$USUARIO = "Vigia-secop"
$NOMBRE  = "Vigia SECOP"
$CORREO  = "329292925+vigia-secop@users.noreply.github.com"
$REPO    = "https://github.com/$USUARIO/vigia.git"

try { Start-Transcript -Path (Join-Path $raiz "paso-2-ultima-corrida.txt") -Force | Out-Null } catch { }

function Bien($m)  { Write-Host "   OK  $m" -ForegroundColor Green }
function Aviso($m) { Write-Host "   --  $m" -ForegroundColor Yellow }
function Mal($m) {
    Write-Host ""
    Write-Host "   ABORTADO: $m" -ForegroundColor Red
    Write-Host "   No se cambio nada." -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

Write-Host ""
Write-Host "  PASO 2 - identidad anonima de git" -ForegroundColor White
Write-Host "  $raiz" -ForegroundColor DarkGray
Write-Host ""

# ---- git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    foreach ($r in @("C:\Program Files\Git\cmd\git.exe",
                     "C:\Program Files (x86)\Git\cmd\git.exe",
                     "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe")) {
        if (Test-Path $r) { $env:PATH = (Split-Path $r) + ";" + $env:PATH; break }
    }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Mal "no encuentro git" }
Bien ((& git --version) -join "")

# ---- Que esta sea de verdad la carpeta del proyecto.
#
# Un `git init` en la carpeta equivocada no rompe nada, pero deja un
# repositorio huerfano donde no va y eso confunde despues. Se comprueban tres
# archivos que solo existen aqui.
foreach ($f in @("portada.sql", "publicar.ps1", "vigia")) {
    if (-not (Test-Path (Join-Path $raiz $f))) { Mal "esta no parece la carpeta de Vigia (falta $f)" }
}
Bien "es la carpeta de Vigia"

# ---- Que .gitignore este y excluya .env. Sin esto, el paso siguiente subiria
#      el token de Socrata a un repositorio publico.
if (-not (Test-Path (Join-Path $raiz ".gitignore"))) { Mal "no hay .gitignore" }
$ignora = Get-Content -Raw (Join-Path $raiz ".gitignore")
if ($ignora -notmatch '(?m)^\.env\s*$') { Mal ".gitignore no excluye .env" }
Bien ".gitignore excluye .env"

# ---- El historial viejo se aparta, no se borra.
Write-Host ""
Write-Host "== 1 de 4 : Apartar el historial viejo" -ForegroundColor Cyan
if (Test-Path (Join-Path $raiz ".git")) {
    $firma = (& git log -1 --format="%an <%ae>" 2>$null)
    if ($firma) { Aviso "los commits viejos estan firmados como: $firma" }

    # Un repositorio SIN commits no tiene historial que apartar: es el que dejo
    # una corrida anterior de este mismo script que no llego a terminar. Se
    # borra y ya, en vez de ir dejando carpetas `vigia-git-viejo-...` en el
    # Escritorio cada vez que se reintenta.
    if (-not $firma) {
        Remove-Item (Join-Path $raiz ".git") -Recurse -Force -ErrorAction SilentlyContinue
        Bien "habia un repositorio a medias sin commits; se descarto"
    }
}
if (Test-Path (Join-Path $raiz ".git")) {
    $sello = Get-Date -Format "yyyy-MM-dd-HHmm"
    $destino = Join-Path (Split-Path $raiz -Parent) "vigia-git-viejo-CON-CORREO-PERSONAL-$sello"
    try {
        Move-Item (Join-Path $raiz ".git") $destino -Force -ErrorAction Stop
        Bien "historial viejo movido a: $destino"
        Aviso "esa carpeta la puedes borrar cuando quieras; no hace falta para nada"
    } catch {
        Mal "no pude mover la carpeta .git. Cierra cualquier programa que la tenga abierta (VS Code, GitHub Desktop) y vuelve a correr esto."
    }
} else {
    Bien "no habia repositorio previo"
}

# ---- Repositorio nuevo.
Write-Host ""
Write-Host "== 2 de 4 : Repositorio nuevo, firmando anonimo" -ForegroundColor Cyan
& git init -q 2>&1 | Out-Host
& git branch -M main 2>&1 | Out-Host

# Sin --global a proposito: cambia SOLO este proyecto y no te toca el resto de
# tu trabajo, donde tu nombre real esta bien.
& git config user.name  $NOMBRE
& git config user.email $CORREO
Bien "firma: $((& git config user.name)) <$((& git config user.email))>"

# ---- El primer commit limpio.
Write-Host ""
Write-Host "== 3 de 4 : Primer commit" -ForegroundColor Cyan
# Las advertencias de «LF will be replaced by CRLF» salen en rojo en PowerShell
# y NO son errores: son git avisando de finales de linea en Windows. Se separan
# de los errores de verdad para que el rojo signifique algo.
$salida = & git add -A 2>&1
$problemas = $salida | Where-Object { "$_" -match '^(error|fatal):' }
if ($problemas) {
    foreach ($p in $problemas) { Write-Host "   $p" -ForegroundColor Red }
    $culpable = ($problemas | Where-Object { "$_" -match 'open\("([^"]+)"\)' } |
                 ForEach-Object { if ("$_" -match 'open\("([^"]+)"\)') { $Matches[1] } } |
                 Select-Object -First 1)
    Write-Host ""
    if ($culpable) {
        Write-Host "   Hay un archivo que no se puede abrir: $culpable" -ForegroundColor Yellow
        Write-Host "   Casi siempre es el antivirus, que lo dejo en cuarentena." -ForegroundColor Gray
        Write-Host "   La salida NO es pelear con el antivirus: es excluir el archivo" -ForegroundColor Gray
        Write-Host "   en .gitignore. Mandame este mensaje y lo agrego." -ForegroundColor Gray
    }
    Mal "git no pudo preparar los archivos"
}
$cuantos = (& git diff --cached --name-only | Measure-Object -Line).Lines
& git commit -q -m "Vigia SECOP - registro publico de contratacion" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "no se pudo hacer el commit" }
Bien "$cuantos archivo(s) en el primer commit"

# ---- LA COMPROBACION QUE IMPORTA. Se lee del commit que acaba de quedar, no
#      de la configuracion: la configuracion dice la intencion, el commit dice
#      lo que de verdad quedo escrito.
$autor = (& git log -1 --format="%an <%ae>")
if ($autor -notmatch 'users\.noreply\.github\.com>$') {
    Mal "el commit quedo firmado como '$autor', que NO es anonimo"
}
Bien "el commit quedo firmado como: $autor"

# ---- Que .env de verdad no este dentro.
$subidos = & git ls-files
if ($subidos -contains ".env") { Mal ".env quedo dentro del commit. NO subas esto." }
Bien ".env no esta en el commit"

# ---- El remoto.
Write-Host ""
Write-Host "== 4 de 4 : Apuntar al repositorio de GitHub" -ForegroundColor Cyan
& git remote remove origin 2>$null | Out-Null
& git remote add origin $REPO
Bien "origin -> $REPO"

Write-Host ""
Write-Host "  ----------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Listo. La carpeta ya firma anonimo." -ForegroundColor Green
Write-Host ""
Write-Host "  TODAVIA NO SE HA SUBIDO NADA." -ForegroundColor Yellow
Write-Host "  Falta crear el repositorio 'vigia' en GitHub, y eso es el paso 3." -ForegroundColor Gray
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
Read-Host "  Enter para cerrar"
