# Uniones Temporales y Consorcios: que dejen de quedar volando.
#
#   Doble clic en EJECUTAR-uniones.bat
#
# QUE HACE, EN ORDEN
#   1. Aplica TODAS las migraciones en orden (son idempotentes; no borran nada).
#   2. Vuelve a normalizar, que es lo que reparte las identidades.
#   3. Te ensena, de TU base, cuantas uniones temporales sin documento hay,
#      cuanta plata mueven y cuales son las mas grandes, una por una.
#
# No pregunta nada antes de trabajar: correr este archivo ES el consentimiento.
# La unica pausa esta al final. Es la misma leccion del 2026-09-03, cuando la
# ventana se cerro exactamente en el `Read-Host` que pedia escribir SI.

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "uniones-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

trap {
    Write-Host ""
    Write-Host "   ERROR NO PREVISTO -- esto es un fallo del script, no tuyo:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    Write-Host "   linea $($_.InvocationInfo.ScriptLineNumber): $($_.InvocationInfo.Line.Trim())" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

$DSN_VIGIA = "postgresql://vigia:vigia@localhost:5432/vigia"

function Paso($numero, $titulo) {
    Write-Host ""
    Write-Host "== $numero : $titulo" -ForegroundColor Cyan
}
function Bien($mensaje) { Write-Host "   OK  $mensaje" -ForegroundColor Green }
function Aviso($mensaje) { Write-Host "   --  $mensaje" -ForegroundColor Yellow }
function Mal($mensaje) {
    Write-Host ""
    Write-Host "   FALLO: $mensaje" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    Write-Host "   Manda ese archivo y se arregla." -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

function Buscar-Herramienta($nombre) {
    $enPath = Get-Command $nombre -ErrorAction SilentlyContinue
    if ($enPath) { return $enPath.Source }
    foreach ($raizPg in @("C:\Program Files\PostgreSQL", "C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $raizPg)) { continue }
        $versiones = Get-ChildItem $raizPg -Directory -ErrorAction SilentlyContinue |
            Sort-Object { if ($_.Name -match '^(\d+)') { [int]$Matches[1] } else { 0 } } -Descending
        foreach ($v in $versiones) {
            $ruta = Join-Path $v.FullName "bin\$nombre.exe"
            if (Test-Path $ruta) { return $ruta }
        }
    }
    return $null
}

Write-Host "Vigia SECOP - uniones temporales y consorcios" -ForegroundColor White
Write-Host "Carpeta: $raiz"
Write-Host ""

# ---------------------------------------------------------------- 1 de 4
Paso "1 de 4" "Herramientas"

$pyExe = $null
$pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() }, @{ exe = "python3"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $version = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($version -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; Bien $version.Trim(); break
    }
}
if (-not $pyExe) { Mal "No encuentro Python 3.11 o superior." }

$PSQL = Buscar-Herramienta "psql"
if (-not $PSQL) { Mal "No encuentro psql. Sin el no puedo aplicar las migraciones." }
Bien "psql en $PSQL"

$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"
$env:VIGIA_DSN = $DSN_VIGIA

# ---------------------------------------------------------------- 2 de 4
Paso "2 de 4" "Migraciones"
Write-Host "   Se aplican TODAS en orden, no solo la ultima."
Write-Host ""
Write-Host "   POR QUE TODAS: el 2026-09-04 este script fallo con "no existe la"
Write-Host "   relacion proveedor" porque daba por aplicada la 006, que nunca"
Write-Host "   llego a esta maquina. Aplicar solo la ultima supone un estado que"
Write-Host "   nadie comprobo. Todas son idempotentes (IF NOT EXISTS), asi que"
Write-Host "   volver a pasarlas no cuesta nada y no supone nada." -ForegroundColor DarkGray
Write-Host ""

# Una llamada a un .exe que escribe en stderr, con ErrorActionPreference en
# Stop, se convierte en error de terminacion aunque el comando haya ido bien.
# Es la trampa que ya nos costo una corrida: aqui se baja la guardia solo
# alrededor de psql y se decide por el codigo de salida, que es el que manda.
function Sql($archivo) {
    $antes = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PSQL -h localhost -U vigia -d vigia -v ON_ERROR_STOP=1 -f $archivo 2>&1 | Out-Host
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $antes
    }
}

$migraciones = Get-ChildItem "migraciones\*.sql" | Sort-Object Name
foreach ($m in $migraciones) {
    $codigo = Sql $m.FullName
    if ($codigo -ne 0) { Mal "la migracion $($m.Name) no aplico" }
    Bien $m.Name
}

# ---------------------------------------------------------------- 3 de 4
Paso "3 de 4" "Normalizar -- es lo que reparte las identidades"

$antes = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $pyExe @pyArgs -m vigia.normalizado 2>&1 | Out-Host
$codigoNorm = $LASTEXITCODE
$ErrorActionPreference = $antes
if ($codigoNorm -ne 0) { Mal "la normalizacion fallo" }

# ---------------------------------------------------------------- 4 de 4
Paso "4 de 4" "Lo que hay en TU base"

$consulta = @"
\pset border 2
SELECT count(*) FILTER (WHERE proveedor_provisional)              AS uniones_sin_documento,
       count(*) FILTER (WHERE proveedor_provisional IS FALSE)     AS con_identidad_real,
       count(*) FILTER (WHERE proveedor_tipo IS NULL)             AS sin_identidad_ninguna,
       to_char(coalesce(sum(valor) FILTER (WHERE proveedor_provisional), 0), 'FM999G999G999G999')
                                                                  AS plata_de_las_uniones
FROM contrato;

SELECT proveedor_nombre AS union_temporal,
       nombre_entidad   AS entidad,
       to_char(valor, 'FM999G999G999G999') AS valor,
       estado
FROM contrato
WHERE proveedor_provisional
ORDER BY valor DESC NULLS LAST
LIMIT 20;
"@

$antes = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$consulta | & $PSQL -h localhost -U vigia -d vigia 2>&1 | Out-Host
$ErrorActionPreference = $antes

Write-Host ""
Write-Host "COMO SE LEE ESTO" -ForegroundColor White
Write-Host "  Cada union temporal de arriba tiene identidad PROPIA, una por contrato."
Write-Host "  Eso es a proposito: el nombre lo teclea cada entidad y no es unico en"
Write-Host "  Colombia, asi que agrupar por nombre inventaria concentraciones."
Write-Host "  Se cuentan, se suman y se ven -que era el problema-, pero todavia no se"
Write-Host "  les puede medir concentracion. Eso es la historia 1.8." -ForegroundColor Gray
Write-Host ""

try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
