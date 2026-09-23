# PUBLICAR EL SITIO. Construye docs/ y lo sube a GitHub Pages.
#
#     .\publicar.ps1               # la semana pasada
#     .\publicar.ps1 -Mensual      # el mes pasado, completo
#     .\publicar.ps1 -MesEnCurso   # del 1 de este mes hasta hoy
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

param([switch]$Mensual, [switch]$MesEnCurso, [switch]$SoloConstruir,
      [string]$Desde = "", [string]$Hasta = "")

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

# ---------------------------------------------------------------------------
# GIT ESCRIBE POR EL CANAL DE ERRORES AUNQUE TODO LE SALGA BIEN
# ---------------------------------------------------------------------------
# `git push` manda su parte -"To https://github.com/...", "d8f80c5..f0d11a4
# main -> main"- por stderr, no por stdout. Es asi a proposito: git reserva
# stdout para lo que un programa podria querer leer.
#
# PowerShell no lo sabe. Con `2>&1 | Out-Host` convierte cada linea de stderr
# en un registro de error y la pinta en rojo, con un bloque de
# NativeCommandError, CategoryInfo y RemoteException encima. La subida fue
# perfecta y la pantalla parece un accidente.
#
# Eso no es solo feo. Entrena a no leer el rojo, que es exactamente lo que si
# hay que leer el dia que algo falle de verdad. Una pantalla que grita todos
# los dias no avisa ningun dia.
#
# Lo unico que dice si git fallo es su codigo de salida. Aqui se imprime todo
# lo que git escribe, como texto normal, y se devuelve $LASTEXITCODE.
#
# EL FILTRO QUE APAGA EL INCENDIO FALSO, y lo que costo llegar a el. Probado
# en PowerShell 5.1 -no en el 7, que fue el error del 2026-09-16- con
# `probar-rojo.ps1`, sobre una orden que escribe por stderr y sale con 0:
#
#     2>&1 | Out-Host                           rojo + NativeCommandError
#     lo mismo con ErrorActionPreference bajo   NO IMPRIME NADA
#     capturar en variable con EAP bajo         NO IMPRIME NADA
#     2>&1 | ForEach-Object { Write-Host }      la linea en gris, sin rojo
#     2>&1 | <este filtro>                      la linea en gris, sin rojo
#
# LAS DOS DEL MEDIO SON LA TRAMPA, y ahi cai. El arreglo que puse el 16 era
# capturar con `ErrorActionPreference` bajo. Quito el rojo, si: porque se
# tragaba la linea entera. Desde entonces, y hasta el 2026-09-20, este
# proyecto no mostro NADA de lo que git manda por stderr: ni el
# "To https://github.com/...", ni ninguna advertencia. Funcionaba porque el
# codigo de salida se sigue mirando, pero el dia que git avise algo -un
# rechazo parcial, un aviso de credenciales- no se iba a ver.
#
# Cambiar un incendio falso por un silencio no es arreglar. El filtro de abajo
# imprime todo y no pinta nada de rojo.
filter Sin-Rojo { Write-Host "$_" }

function Correr-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Argumentos)
    # Aqui va sangrado y en gris porque es salida de git dentro de un paso, no
    # del paso mismo. Es la unica diferencia con `Sin-Rojo`.
    & git @Argumentos 2>&1 | ForEach-Object {
        $t = "$_"
        if ($t.Trim()) { Write-Host "   $t" -ForegroundColor Gray }
    }
    return $LASTEXITCODE
}

if (-not $Desde -or -not $Hasta) {
    $hoy = (Get-Date).Date
    if ($MesEnCurso) {
        # DEL 1 DE ESTE MES HASTA HOY. Un mes que todavia no termina se puede
        # publicar, pero no se puede llamar "el mes de septiembre": le faltan
        # dias. La pagina dice el rango exacto, y mas abajo este script recorta
        # el final a la ultima fecha que tenga datos de verdad.
        $ini = Get-Date -Year $hoy.Year -Month $hoy.Month -Day 1
        $fin = $hoy
    } elseif ($Mensual) {
        $primero = Get-Date -Year $hoy.Year -Month $hoy.Month -Day 1
        $fin = $primero.AddDays(-1); $ini = Get-Date -Year $fin.Year -Month $fin.Month -Day 1
    } else {
        $diasDesdeLunes = ([int]$hoy.DayOfWeek + 6) % 7
        $lunes = $hoy.AddDays(-$diasDesdeLunes)
        $ini = $lunes.AddDays(-7); $fin = $lunes.AddDays(-1)
    }
    $Desde = $ini.ToString("yyyy-MM-dd"); $Hasta = $fin.ToString("yyyy-MM-dd")
}
$periodo = if ($Mensual -or $MesEnCurso) { "mes" } else { "semana" }

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

# ---------------------------------------------------------------------------
# LAS MIGRACIONES, TAMBIEN AQUI
# ---------------------------------------------------------------------------
# Las aplicaba solo `ciclo-diario.ps1`. El 2026-09-19 eso costo diez minutos:
# la migracion 010 -los indices sobre los registros crudos- llevaba un dia en
# la carpeta sin aplicarse porque nadie habia corrido el ciclo, y el paso de
# banderas se quedo buscando enlaces en una tabla sin indice.
#
# Un arreglo que depende de que alguien se acuerde de correr OTRO script no es
# un arreglo. Son idempotentes -todas llevan IF NOT EXISTS-, asi que aplicarlas
# aqui no cuesta nada cuando ya estan puestas.
Write-Host ""
Write-Host "== 0 de 4 : Migraciones" -ForegroundColor Cyan
foreach ($m in (Get-ChildItem (Join-Path $raiz "migraciones") -Filter "*.sql" |
                Sort-Object Name)) {
    & $PSQL -h localhost -U vigia -d vigia -q -f $m.FullName 2>&1 |
        Where-Object { $_ -notmatch "^\s*$" } | Sin-Rojo
}
Write-Host "   migraciones al dia." -ForegroundColor Gray

# ---------------------------------------------------------------------------
# NO PUBLICAR ENCIMA DE UN CICLO QUE TODAVIA ESTA CORRIENDO
# ---------------------------------------------------------------------------
# `ciclo-diario.ps1` deja `ciclo-en-curso.lock` mientras trabaja. Publicar en
# ese momento saca una pagina con los datos de ANTES del ciclo, y nadie se
# entera: no falla, sale, y la cifra esta vieja.
#
# Y hay algo peor que lo viejo. La normalizacion escribe procesos, proveedores
# y contratos en TRES transacciones distintas, una por tabla. Cada tabla queda
# entera o no queda -eso si esta bien-, pero no las tres a la vez: quien lea
# en el hueco del medio puede encontrar los procesos de hoy cruzados con los
# contratos de ayer. El detector de erratas hace justo ese cruce, y de ahi
# saca la cifra que la pagina publica como apartada.
#
# El candado se ignora si tiene mas de tres horas: un ciclo al que le cerraron
# la ventana dejaria el archivo tirado, y un candado olvidado que impide
# publicar para siempre es peor que el problema que evita.
$candado = Join-Path $raiz "ciclo-en-curso.lock"
if (Test-Path $candado) {
    $edad = (Get-Date) - (Get-Item $candado).LastWriteTime
    if ($edad.TotalHours -lt 3) {
        $desde = (Get-Content -LiteralPath $candado -ErrorAction SilentlyContinue | Select-Object -First 1)
        Write-Host ""
        Write-Host "  El ciclo diario esta corriendo (arranco $desde)." -ForegroundColor Yellow
        Write-Host "  Publicar ahora saca una pagina con los datos de ANTES del ciclo:" -ForegroundColor Yellow
        Write-Host "  no falla, sale, y esta vieja. Espera a que diga 'Ciclo diario completo'" -ForegroundColor Yellow
        Write-Host "  y vuelve a correr esto." -ForegroundColor Yellow
        Mal "hay un ciclo diario en curso"
    }
    Write-Host "  Habia un candado de hace $([int]$edad.TotalHours) h; lo ignoro: un ciclo viejo lo dejo tirado." -ForegroundColor DarkGray
    Remove-Item -LiteralPath $candado -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# NO PROMETER DIAS QUE NO SE TIENEN
# ---------------------------------------------------------------------------
# Pedir "del 1 al 16" cuando la ingesta llego al 9 produce una pagina que dice
# 16 dias y solo tiene 9. No falla: sale, se lee, y esta mal. Y como los que
# faltan son los ULTIMOS, la pagina muestra una caida al final que no existe.
#
# SECOP publica con rezago, asi que esto va a pasar casi siempre. El final se
# recorta a la ultima fecha con datos dentro de la ventana pedida, y se dice
# en voz alta cuantos dias se recortaron: quien publique tiene que saber que
# la pagina no llega hasta hoy.
$consultaUltimo = "SELECT max(fecha_de_firma) FROM contrato " +
                  "WHERE fecha_de_firma BETWEEN '$Desde' AND '$Hasta'"
$ultimoConDatos = "$(& $PSQL -h localhost -U vigia -d vigia -tAq -c $consultaUltimo)".Trim()
if ($LASTEXITCODE -ne 0) { Mal "no se pudo consultar hasta donde llegan los datos" }
if (-not $ultimoConDatos) { Mal "no hay ni un contrato firmado entre $Desde y $Hasta" }
if ($ultimoConDatos -lt $Hasta) {
    $faltan = ([datetime]$Hasta - [datetime]$ultimoConDatos).Days
    Write-Host ""
    Write-Host "  OJO: pediste hasta $Hasta y los datos llegan al $ultimoConDatos." -ForegroundColor Yellow
    Write-Host "  Son $faltan dia(s) sin ingerir. La pagina se publica hasta $ultimoConDatos," -ForegroundColor Yellow
    Write-Host "  que es lo que se puede sostener. Para traer lo que falta: EJECUTAR-DIA.bat" -ForegroundColor Yellow
    $Hasta = $ultimoConDatos
}

Write-Host ""
Write-Host "  PUBLICAR VIGIA - $periodo del $Desde al $Hasta" -ForegroundColor White
Write-Host ""

# ---- 1. Los datos, de boletin.sql, que no puede traer nombres.
Write-Host "== 1 de 4 : Consultar" -ForegroundColor Cyan
$json = "boletin-$Desde.json"
& $PSQL -h localhost -U vigia -d vigia -tA -v desde="'$Desde'" -v hasta="'$Hasta'" `
    -f "boletin.sql" -o $json 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "fallo la consulta" }

# ---- 2. El sitio. El propio generador aborta si algo no es publicable.
Write-Host ""
Write-Host "== 2 de 4 : Construir docs/" -ForegroundColor Cyan
& $pyExe @pyArgs -m vigia.sitio --json $json --docs docs --periodo $periodo 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "el sitio no paso la barrera de publicacion" }

# ---- 2b. El Panel y la lista de revision, en su version publicable.
#
# Van al sitio porque son lo que de verdad permite control ciudadano: quien
# contrato, cuanto, con quien, y --sobre todo-- cuanto queda fuera de lo que se
# puede medir. Se construyen con los mismos datos que las de escritorio y una
# sola diferencia: **el NIT va completo y la cedula de una persona natural va
# enmascarada**. Donde esta el poder esta el NIT.
Write-Host ""
Write-Host "== 2b de 4 : Panel y lista de revision para el sitio" -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -tA -f "panel.sql" -o "panel-publico.json" 2>&1 | Sin-Rojo
& $pyExe @pyArgs -m vigia.panel --json "panel-publico.json" --salida "docs\panel.html" 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "no se pudo construir el Panel publico" }
& $PSQL -h localhost -U vigia -d vigia -tA -f "revision.sql" -o "revision-publico.json" 2>&1 | Sin-Rojo
& $pyExe @pyArgs -m vigia.revision --json "revision-publico.json" --salida "docs\revision.html" 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "no se pudo construir la lista de revision publica" }

# ---- 2c. LA PORTADA DEL DIA, que es `docs\index.html`.
#
# El boletin semanal se quedo en `semana.html`. La portada es el REGISTRO:
# quien entre un miercoles tiene que ver el miercoles, no la semana pasada.
# Un ano de portadas sin un hueco y sin una cifra desmentida es lo que
# convierte a Vigia en algo que alguien cita.
#
# Se usa el ultimo dia con contratos, no "hoy": SECOP publica con rezago y una
# portada en blanco por haber corrido a las seis de la manana se lee como que
# el sitio esta roto.
Write-Host ""
Write-Host "== 2c de 4 : La portada del dia" -ForegroundColor Cyan
$ultimo = (& $PSQL -h localhost -U vigia -d vigia -tA -c `
    "SELECT max(fecha_de_firma) FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE" 2>&1).Trim()
if (-not ($ultimo -match '^\d{4}-\d{2}-\d{2}$')) { Mal "no pude averiguar el ultimo dia con contratos" }
Write-Host "   Ultimo dia con contratos: $ultimo" -ForegroundColor DarkGray
& $PSQL -q -h localhost -U vigia -d vigia -tA -v dia="'$ultimo'" -f "portada.sql" -o "portada.json" 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "fallo la consulta de la portada" }
& $pyExe @pyArgs -m vigia.portada --json "portada.json" --salida "docs\index.html" 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "la portada no se pudo construir (o llevaba un documento sin enmascarar)" }

# ---- 2d. EL ARCHIVO: dia, semana y mes, en una sola pagina.
#
# Es lo que faltaba entre la portada -que es hoy- y el boletin -que es el
# periodo recien cerrado-: la forma de preguntar "y el martes pasado?" o
# "como fue agosto entero?". Los datos estaban desde el primer dia; el
# recorrido no.
#
# La consulta no lleva fechas: el archivo es TODO lo ingerido, y crece solo.
Write-Host ""
Write-Host "== 2d de 4 : El archivo (dia, semana y mes)" -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -tA -f "archivo.sql" -o "archivo.json" 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "fallo la consulta del archivo" }
& $pyExe @pyArgs -m vigia.archivo --json "archivo.json" --salida "docs\archivo.html" 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "el archivo no se pudo construir (o llevaba un documento sin enmascarar)" }

# La comprobacion que corresponde a estas dos paginas: NO "ninguna cadena de
# digitos" --eso ahogaria todos los NIT, que son justo lo que hay que
# publicar-- sino "ningun documento de PERSONA NATURAL escrito entero".
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

# ---- 2d. QUE LAS PAGINAS DE VERDAD VAYAN A SUBIR.
#
# Esta comprobacion nacio de un fallo silencioso el 2026-09-15: el sitio se
# construyo entero, paso todas las barreras, subio sin un error -- y llego a
# internet SIN el Panel y SIN la lista de revision. Las dos estaban ignoradas
# por `.gitignore`, porque un patron sin barra al principio hace match en
# cualquier carpeta y `panel.html` bloqueaba tambien `docs/panel.html`.
#
# Git no avisa de lo que ignora. Simplemente no lo sube, y el commit se ve
# ---- 2e. LAS BANDERAS. Es la unica pagina del sitio que senala algo, y por
# eso es la unica cuyo generador puede negarse a escribir.
#
# La Regla corre en modo calibracion: si alguien la mueve a un estado en el
# que no deberia estar, `calibrar` levanta y no sale pagina. Y la barrera de
# documentos se aplica igual que al resto -aqui importa mas que en ninguna
# otra, porque es la que nombra entidades una por una.
Write-Host ""
Write-Host "== 2e de 4 : Banderas" -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -tA -f "banderas.sql" -o "banderas.json" 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "fallo la consulta de banderas" }
& $pyExe @pyArgs -m vigia.banderas --json "banderas.json" --salida "docs\banderas.html" 2>&1 | Sin-Rojo
if ($LASTEXITCODE -ne 0) { Mal "las banderas no se pudieron construir (o llevaban un documento sin enmascarar)" }


# perfecto. La unica forma de enterarse es preguntar.
Write-Host ""
Write-Host "== 2f de 4 : Que las paginas si vayan a subir" -ForegroundColor Cyan
$debenSubir = @("docs/index.html", "docs/panel.html", "docs/revision.html",
                "docs/semana.html", "docs/archivo.html",
                "docs/banderas.html")
$mudas = @()
foreach ($pagina in $debenSubir) {
    $enDisco = $pagina -replace '/', '\'
    if (-not (Test-Path (Join-Path $raiz $enDisco))) {
        $mudas += "$pagina (no se construyo)"
        continue
    }
    & git check-ignore -q $pagina 2>$null
    if ($LASTEXITCODE -eq 0) { $mudas += "$pagina (lo ignora .gitignore)" }
}
if ($mudas.Count -gt 0) {
    Write-Host ""
    foreach ($m in $mudas) { Write-Host "   $m" -ForegroundColor Red }
    Write-Host ""
    Write-Host "   Un patron sin barra al principio en .gitignore hace match en" -ForegroundColor Yellow
    Write-Host "   CUALQUIER carpeta: `panel.html` bloquea tambien docs/panel.html." -ForegroundColor Yellow
    Write-Host "   La regla de la raiz se escribe /panel.html, con barra." -ForegroundColor Yellow
    Mal "$($mudas.Count) pagina(s) del sitio no llegarian a internet"
}
Write-Host "   OK  las $($debenSubir.Count) paginas del sitio van a subir" -ForegroundColor Green

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
# va el correo personal, el anonimato se acabo antes del primer tuit -- y un
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

# Los dos archivos de rastro van CON el sitio, no aparte: son la constancia de
# que una persona miro antes de publicar, y esa constancia es la respuesta el
# dia que alguien reclame. Si el sitio sube y el rastro no, el rastro no sirve.
& git add -A docs .gitignore erratas-revisadas.txt numeros-revisados.txt 2>&1 | Out-Null

# El remoto, en minusculas. GitHub redirige de `Vigia-secop` a `vigia-secop`,
# pero lo avisa en rojo en cada push y ese rojo ensena a ignorar los rojos.
$actual = (& git remote get-url origin 2>$null)
if ($actual -and $actual -cmatch 'Vigia-secop') {
    & git remote set-url origin ($actual -creplace 'Vigia-secop', 'vigia-secop')
    Write-Host "   --  remoto corregido a minusculas" -ForegroundColor DarkGray
}
$archivos = @(& git ls-files) + @(& git diff --cached --name-only)
$archivos = $archivos | Sort-Object -Unique | Where-Object { $_ -and (Test-Path $_) }

# Los numeros que una persona ya miro y decidio que no son el documento de
# nadie. Mismo formato tonto a proposito que erratas-revisadas.txt: se puede
# editar a mano, en cualquier parte y sin herramientas.
$yaRevisados = @()
if (Test-Path (Join-Path $raiz "numeros-revisados.txt")) {
    foreach ($l in (Get-Content -Encoding UTF8 (Join-Path $raiz "numeros-revisados.txt"))) {
        $l = $l.Trim()
        if (-not $l -or $l.StartsWith("#")) { continue }
        $yaRevisados += ($l -split '\s+')[0]
    }
}

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
    # Esta comprobacion --"ninguna cadena de 6 a 12 digitos"-- se escribio cuando
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
    # Y los dos registros de lo ya revisado NO se escanean, por una razon que
    # la corrida del 2026-09-14 dejo a la vista: `numeros-revisados.txt`
    # contiene, POR DEFINICION, los numeros que alguien ya miro. Escanearlo es
    # hacer que se dispare a si mismo, para siempre, cada vez que se anota algo.
    # Lo mismo con las erratas, que van identificadas por id de contrato.
    if ($f -eq 'numeros-revisados.txt' -or $f -eq 'erratas-revisadas.txt') { continue }
    # SE VA LINEA POR LINEA, y no de un tiron sobre el archivo entero. Cuando
    # esto aborta, quien lo lee necesita VER el renglon: la primera vez que
    # salto --el 2026-09-14-- marco nueve archivos y los nueve eran falsos
    # positivos, pero el mensaje solo decia "archivo -> 10772032" y averiguar
    # que ese numero era la cola de un `CO1.REQ.10772032` costo un rato.
    $numero = 0
    foreach ($linea in (Get-Content -Encoding UTF8 $f -ErrorAction SilentlyContinue)) {
        $numero++
        if (-not $linea) { continue }
        $limpio = $linea

        # LO QUE SE QUITA ANTES DE BUSCAR, Y POR QUE CADA COSA.
        #
        # Esto NO es bajarle la exigencia a la regla: es ensenarle a reconocer
        # lo que ya sabemos que no es el documento de una persona. La regla de
        # fondo sigue intacta -- si queda un numero largo suelto, aborta.

        # 1. Cifras con separador de miles. Son plata.
        $limpio = [regex]::Replace($limpio, '\d{1,3}(\.\d{3})+', ' ')
        # 2. Identificadores del SECOP: CO1.REQ.*, CO1.PCCNTR.*, CO1.BDOS.*
        #    Son la referencia publica de un proceso o un contrato. Publicarlos
        #    es justo lo que permite que alguien compruebe.
        $limpio = [regex]::Replace($limpio, 'CO1\.[A-Za-z]+\.\d+', ' ')
        # 3. El correo noreply de GitHub, que empieza por el id de la cuenta.
        $limpio = [regex]::Replace($limpio, '\d+\+[\w.\-]+@users\.noreply\.github\.com', ' ')
        # 4. Un solo digito repetido. `000000000`, `11111111`. Ningun documento
        #    real de Colombia lo es -- es la misma regla que ya aplica
        #    `canonizar_documento` en la capa normalizada.
        $limpio = [regex]::Replace($limpio, '(?<!\d)(\d)\1{5,11}(?!\d)', ' ')
        # 5. Un numero precedido de la palabra NIT. El NIT identifica a una
        #    empresa y se publica a proposito.
        $limpio = [regex]::Replace($limpio, '(?i)NIT[^0-9]{0,12}\d{6,12}', ' ')

        $m = [regex]::Match($limpio, '(?<!\d)\d{6,12}(?!\d)')
        if (-not $m.Success) { continue }

        # Lo que sobreviva a los filtros lo tiene que haber mirado una persona.
        # Igual que con las erratas: no hay umbral que inventarse, hay un
        # "alguien lo miro?".
        $marca = "$($f):$($m.Value)"
        if ($yaRevisados -contains $marca) { continue }
        $recorte = $linea.Trim()
        if ($recorte.Length -gt 96) { $recorte = $recorte.Substring(0, 96) + "..." }
        $sospechosos += @{ marca = $marca; f = $f; n = $numero;
                           valor = $m.Value; linea = $recorte }
    }
}
if ($sospechosos.Count -gt 0) {
    Write-Host ""
    foreach ($s in $sospechosos) {
        Write-Host "   $($s.f) : linea $($s.n)  ->  $($s.valor)" -ForegroundColor Red
        Write-Host "       $($s.linea)" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "   Si YA lo miraste y no es el documento de una persona --un" -ForegroundColor Yellow
    Write-Host "   identificador, un ejemplo inventado, una referencia-- anotalo" -ForegroundColor Yellow
    Write-Host "   en numeros-revisados.txt, una linea por caso, con este formato:" -ForegroundColor Yellow
    Write-Host ""
    foreach ($s in $sospechosos) {
        Write-Host "       $($s.marca)   # que es, en tus palabras" -ForegroundColor Gray
    }
    Write-Host ""
    Mal "$($sospechosos.Count) numero(s) con forma de documento que nadie ha revisado"
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

Correr-Git commit -m "Boletin $periodo $Desde a $Hasta" | Out-Null
$codigoPush = Correr-Git push
if ($codigoPush -ne 0) { Mal "fallo el push (git salio con codigo $codigoPush)" }

$usuario = ""
if ($remoto -match 'github\.com[:/]([^/]+)/([^/.]+)') { $usuario = $Matches[1]; $repo = $Matches[2] }
Write-Host ""
Write-Host "  Subido." -ForegroundColor Green
if ($usuario) {
    Write-Host "  El sitio queda en: https://$usuario.github.io/$repo/" -ForegroundColor White
    Write-Host ""
    Write-Host "  SI ES LA PRIMERA VEZ, hay que encenderlo una sola vez:" -ForegroundColor Gray
    Write-Host "  github.com/$usuario/$repo -> Settings -> Pages" -ForegroundColor Gray
    Write-Host "  Source: Deploy from a branch - Branch: main - Folder: /docs - Save" -ForegroundColor Gray
}
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
