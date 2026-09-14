# PUBLICAR EL SITIO. Construye docs/ y lo sube a GitHub Pages.
#
#     .\publicar.ps1               # la semana pasada
#     .\publicar.ps1 -Mensual
#     .\publicar.ps1 -SoloConstruir   # arma docs/ y NO sube nada
#
# LO QUE ESTE SCRIPT NO HACE: no publica en X. Eso lo hace una persona, con el
# hilo de EJECUTAR-BOLETIN.bat delante y despues de leerlo.
#
# LAS TRES COMPROBACIONES ANTES DE SUBIR, y cualquiera de ellas aborta:
#
#   1. Que `.env` este ignorado. Lleva el token de Socrata.
#   2. Que NINGUN archivo que git vaya a subir contenga algo con forma de
#      documento de identidad. `revision.html` lleva cedulas de contratistas
#      personas naturales, y un repositorio publico es internet.
#   3. Que el sitio construido pase la barrera de `vigia/publicacion.py`.
#
# La 2 se comprueba sobre lo que git REALMENTE va a subir, no sobre una lista
# escrita a mano: una lista se queda vieja, `git ls-files` no.

param([switch]$Mensual, [switch]$SoloConstruir, [string]$Desde = "", [string]$Hasta = "")

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "publicar-ultima-corrida.txt") -Force | Out-Null } catch { }

function Mal($m) {
    Write-Host ""
    Write-Host "  ABORTADO: $m" -ForegroundColor Red
    Write-Host "  No se subio nada." -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

if (-not $Desde -or -not $Hasta) {
    $hoy = (Get-Date).Date
    if ($Mensual) {
        $primero = Get-Date -Year $hoy.Year -Month $hoy.Month -Day 1
        $fin = $primero.AddDays(-1); $ini = Get-Date -Year $fin.Year -Month $fin.Month -Day 1
    } else {
        $diasDesdeLunes = ([int]$hoy.DayOfWeek + 6) % 7
        $lunes = $hoy.AddDays(-$diasDesdeLunes)
        $ini = $lunes.AddDays(-7); $fin = $lunes.AddDays(-1)
    }
    $Desde = $ini.ToString("yyyy-MM-dd"); $Hasta = $fin.ToString("yyyy-MM-dd")
}
$periodo = if ($Mensual) { "mes" } else { "semana" }

function Buscar($n) {
    $p = Get-Command $n -ErrorAction SilentlyContinue
    if ($p) { return $p.Source }
    foreach ($r in @("C:\Program Files\PostgreSQL","C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $r)) { continue }
        foreach ($v in (Get-ChildItem $r -Directory -EA SilentlyContinue |
            Sort-Object { if ($_.Name -match '^(\d+)') { [int]$Matches[1] } else { 0 } } -Descending)) {
            $ruta = Join-Path $v.FullName "bin\$n.exe"
            if (Test-Path $ruta) { return $ruta }
        }
    }
    return $null
}
$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; break
    }
}
$PSQL = Buscar "psql"
if (-not $PSQL -or -not $pyExe) { Mal "faltan psql o Python 3.11+" }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

Write-Host ""
Write-Host "  PUBLICAR VIGIA - $periodo del $Desde al $Hasta" -ForegroundColor White
Write-Host ""

# ---- 1. Los datos, de boletin.sql, que no puede traer nombres.
Write-Host "== 1 de 4 : Consultar" -ForegroundColor Cyan
$json = "boletin-$Desde.json"
& $PSQL -h localhost -U vigia -d vigia -tA -v desde="'$Desde'" -v hasta="'$Hasta'" `
    -f "boletin.sql" -o $json 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "fallo la consulta" }

# ---- 2. El sitio. El propio generador aborta si algo no es publicable.
Write-Host ""
Write-Host "== 2 de 4 : Construir docs/" -ForegroundColor Cyan
& $pyExe @pyArgs -m vigia.sitio --json $json --docs docs --periodo $periodo 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "el sitio no paso la barrera de publicacion" }

# ---- 2b. El Panel y la lista de revision, en su version publicable.
#
# Van al sitio porque son lo que de verdad permite control ciudadano: quien
# contrato, cuanto, con quien, y —sobre todo— cuanto queda fuera de lo que se
# puede medir. Se construyen con los mismos datos que las de escritorio y una
# sola diferencia: **el NIT va completo y la cedula de una persona natural va
# enmascarada**. Donde esta el poder esta el NIT.
Write-Host ""
Write-Host "== 2b de 4 : Panel y lista de revision para el sitio" -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -tA -f "panel.sql" -o "panel-publico.json" 2>&1 | Out-Host
& $pyExe @pyArgs -m vigia.panel --json "panel-publico.json" --salida "docs\panel.html" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "no se pudo construir el Panel publico" }
& $PSQL -h localhost -U vigia -d vigia -tA -f "revision.sql" -o "revision-publico.json" 2>&1 | Out-Host
& $pyExe @pyArgs -m vigia.revision --json "revision-publico.json" --salida "docs\revision.html" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "no se pudo construir la lista de revision publica" }

# ---- 2c. LA PORTADA DEL DIA, que es `docs\index.html`.
#
# El boletin semanal se quedo en `semana.html`. La portada es el REGISTRO:
# quien entre un miercoles tiene que ver el miercoles, no la semana pasada.
# Un ano de portadas sin un hueco y sin una cifra desmentida es lo que
# convierte a Vigia en algo que alguien cita.
#
# Se usa el ultimo dia con contratos, no «hoy»: SECOP publica con rezago y una
# portada en blanco por haber corrido a las seis de la manana se lee como que
# el sitio esta roto.
Write-Host ""
Write-Host "== 2c de 4 : La portada del dia" -ForegroundColor Cyan
$ultimo = (& $PSQL -h localhost -U vigia -d vigia -tA -c `
    "SELECT max(fecha_de_firma) FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE" 2>&1).Trim()
if (-not ($ultimo -match '^\d{4}-\d{2}-\d{2}$')) { Mal "no pude averiguar el ultimo dia con contratos" }
Write-Host "   Ultimo dia con contratos: $ultimo" -ForegroundColor DarkGray
& $PSQL -q -h localhost -U vigia -d vigia -tA -v dia="'$ultimo'" -f "portada.sql" -o "portada.json" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "fallo la consulta de la portada" }
& $pyExe @pyArgs -m vigia.portada --json "portada.json" --salida "docs\index.html" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "la portada no se pudo construir (o llevaba un documento sin enmascarar)" }

# La comprobacion que corresponde a estas dos paginas: NO «ninguna cadena de
# digitos» —eso ahogaria todos los NIT, que son justo lo que hay que
# publicar— sino «ningun documento de PERSONA NATURAL escrito entero».
# Se recorre TODA la carpeta, no una lista escrita a mano. La lista anterior
# tenia tres archivos y ya se habia quedado corta: no miraba `semanas\*.html`
# ni `semana.html`. Una lista se queda vieja en silencio; un recorrido no.
$revisor = @'
import sys, pathlib
sys.path.insert(0, ".")
from vigia.documento import persona_sin_enmascarar
malos = []
mirados = 0
for p in sorted(pathlib.Path("docs").rglob("*")):
    if not p.is_file() or p.suffix.lower() not in (".html", ".md", ".txt", ".json", ".csv"):
        continue
    mirados += 1
    hallazgos = persona_sin_enmascarar(p.read_text(encoding="utf-8", errors="replace"))
    if hallazgos:
        malos.append((str(p), hallazgos[:5]))
if malos:
    for f, h in malos:
        print(f"  {f}: documento(s) de persona natural sin enmascarar -> {h}")
    sys.exit(1)
print(f"  OK  {mirados} archivo(s) de docs/ revisados: ninguna cedula sin enmascarar")
'@
$revisor | & $pyExe @pyArgs -
if ($LASTEXITCODE -ne 0) { Mal "hay documentos de personas naturales sin enmascarar en docs/" }

if ($SoloConstruir) {
    Write-Host ""
    Write-Host "  docs/ construido. NO se subio nada (-SoloConstruir)." -ForegroundColor Green
    Write-Host "  Abrelo con docs\index.html para verlo." -ForegroundColor Gray
    try { Stop-Transcript | Out-Null } catch { }
    exit 0
}

# ---- 3. Las comprobaciones, sobre lo que git va a subir DE VERDAD.
Write-Host ""
Write-Host "== 3 de 4 : Comprobar antes de subir" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    foreach ($r in @("C:\Program Files\Git\cmd\git.exe","C:\Program Files (x86)\Git\cmd\git.exe","$env:LOCALAPPDATA\Programs\Git\cmd\git.exe")) {
        if (Test-Path $r) { $env:PATH = (Split-Path $r) + ";" + $env:PATH; break }
    }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Mal "no encuentro git" }

& git check-ignore -q ".env"
if ($LASTEXITCODE -ne 0) { Mal ".env NO esta ignorado por git. Lleva el token de Socrata." }
Write-Host "   OK  .env esta ignorado" -ForegroundColor Green

# ---- LA IDENTIDAD QUE VA PEGADA A CADA COMMIT.
#
# Vigia se publica anonimo, y el punto mas facil por donde se rompe eso no es
# el sitio: es git. CADA commit lleva escrito un nombre y un correo, para
# siempre, y en un repositorio publico cualquiera los lee con un clic. Si ahi
# va el correo personal, el anonimato se acabo antes del primer tuit — y un
# commit no se borra del historial con un `git commit --amend`.
#
# Por eso esto ABORTA en vez de avisar. Un aviso se lee despues.
$nombre = (& git config user.name 2>$null)
$correo = (& git config user.email 2>$null)
Write-Host "   --  cada commit ira firmado como: $nombre <$correo>" -ForegroundColor DarkGray
if (-not $correo) { Mal "git no tiene user.email configurado" }
if ($correo -notmatch 'users\.noreply\.github\.com$') {
    Write-Host ""
    Write-Host "   El correo '$correo' quedaria escrito en cada commit, publico y para siempre." -ForegroundColor Yellow
    Write-Host "   Para publicar anonimo, en GitHub:" -ForegroundColor Yellow
    Write-Host "     Settings -> Emails -> marcar 'Keep my email addresses private'" -ForegroundColor Gray
    Write-Host "   y despues, en esta carpeta:" -ForegroundColor Yellow
    Write-Host "     git config user.name  'Vigia SECOP'" -ForegroundColor Gray
    Write-Host "     git config user.email 'ID+usuario@users.noreply.github.com'" -ForegroundColor Gray
    Write-Host "   (el correo exacto lo da esa misma pagina de GitHub)" -ForegroundColor Gray
    Mal "el correo de git no es anonimo"
}
Write-Host "   OK  el correo de git es de los que no identifican" -ForegroundColor Green

& git add -A docs .gitignore 2>&1 | Out-Null
$archivos = @(& git ls-files) + @(& git diff --cached --name-only)
$archivos = $archivos | Sort-Object -Unique | Where-Object { $_ -and (Test-Path $_) }

$sospechosos = @()
foreach ($f in $archivos) {
    # Solo texto, y solo lo que de verdad se lee. Un .py o un .sql con un NIT
    # en un comentario es documentacion del metodo; una pagina de docs/ con un
    # numero de cedula es un dato personal publicado.
    if ($f -notmatch '\.(html|md|txt|json|csv)$') { continue }
    if ($f -like 'tests/*') { continue }
    if ($f -like 'datos/*') { continue }
    # Y `docs/` NO pasa por esta regla, a proposito.
    #
    # Esta comprobacion —«ninguna cadena de 6 a 12 digitos»— se escribio cuando
    # NADA de lo que se publicaba llevaba un identificador. Hoy el sitio publica
    # el NIT de las empresas a proposito: donde esta el poder esta el NIT, y un
    # NIT son nueve digitos seguidos. Aplicarle esta regla a `docs/` abortaria
    # cada publicacion por hacer justo lo que decidimos hacer.
    #
    # Lo que corresponde a `docs/` es la comprobacion fina de mas arriba:
    # `persona_sin_enmascarar`, que busca el documento de una PERSONA NATURAL
    # escrito entero y deja pasar los NIT. Esa ya corrio sobre toda la carpeta
    # y aborta por su cuenta. Aqui se cuida el resto del repositorio, que es
    # donde un numero largo no tiene por que aparecer.
    if ($f -like 'docs/*' -or $f -like 'docs\*') { continue }
    $texto = Get-Content -Raw -Encoding UTF8 $f -ErrorAction SilentlyContinue
    if (-not $texto) { continue }
    # Se quitan las cifras con separador de miles antes de buscar: son plata.
    $limpio = [regex]::Replace($texto, '\d{1,3}(\.\d{3})+', ' ')
    if ([regex]::IsMatch($limpio, '(?<!\d)\d{6,12}(?!\d)')) {
        $m = [regex]::Match($limpio, '(?<!\d)\d{6,12}(?!\d)')
        $sospechosos += "$f  ->  $($m.Value)"
    }
}
if ($sospechosos.Count -gt 0) {
    Write-Host ""
    foreach ($s in $sospechosos) { Write-Host "   $s" -ForegroundColor Red }
    Mal "$($sospechosos.Count) archivo(s) que git subiria contienen algo con forma de documento de identidad"
}
Write-Host "   OK  ningun archivo publicable trae documentos de identidad" -ForegroundColor Green

# ---- 4. Subir.
Write-Host ""
Write-Host "== 4 de 4 : Subir a GitHub" -ForegroundColor Cyan
$remoto = (& git remote get-url origin 2>$null)
if (-not $remoto) {
    Write-Host ""
    Write-Host "  No hay repositorio remoto configurado." -ForegroundColor Yellow
    Write-Host "  Corre primero EJECUTAR-subir-a-github.bat, que te guia para crearlo." -ForegroundColor Yellow
    Write-Host "  docs/ ya quedo construido y revisado." -ForegroundColor Gray
    try { Stop-Transcript | Out-Null } catch { }
    exit 0
}

& git commit -m "Boletin $periodo $Desde a $Hasta" 2>&1 | Out-Host
& git push 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "fallo el push" }

$usuario = ""
if ($remoto -match 'github\.com[:/]([^/]+)/([^/.]+)') { $usuario = $Matches[1]; $repo = $Matches[2] }
Write-Host ""
Write-Host "  Subido." -ForegroundColor Green
if ($usuario) {
    Write-Host "  El sitio queda en: https://$usuario.github.io/$repo/" -ForegroundColor White
    Write-Host ""
    Write-Host "  SI ES LA PRIMERA VEZ, hay que encenderlo una sola vez:" -ForegroundColor Gray
    Write-Host "  github.com/$usuario/$repo -> Settings -> Pages" -ForegroundColor Gray
    Write-Host "  Source: Deploy from a branch · Branch: main · Folder: /docs · Save" -ForegroundColor Gray
}
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
