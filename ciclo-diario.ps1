# Ciclo diario de Vigia. Lo corre el Programador de tareas de Windows.
#
# Ingiere lo nuevo, normaliza y vuelve a dibujar el Panel. No pregunta nada y
# no abre ventanas: esta pensado para correr solo.
#
# La ingesta NO lleva fechas a proposito: el Ciclo arranca desde la marca de
# agua del dataset menos la ventana de solapamiento. Poner fechas fijas aqui
# haria que un dia sin correr dejara un hueco para siempre.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$sello = Get-Date -Format "yyyy-MM-dd"
$bitacora = Join-Path $raiz "bitacora"
if (-not (Test-Path $bitacora)) { New-Item -ItemType Directory -Path $bitacora -Force | Out-Null }
$registro = Join-Path $bitacora "ciclo-$sello.txt"
try { Start-Transcript -Path $registro -Append | Out-Null } catch { }

function Paso($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }
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
if (-not $pyExe) { Write-Host "FALLO: no hay Python 3.11+" -ForegroundColor Red; exit 1 }
$PSQL = Buscar "psql"
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"
$env:VIGIA_DSN = "postgresql://vigia:vigia@localhost:5432/vigia"

Write-Host "Ciclo diario de Vigia - $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor White

# LAS MIGRACIONES VAN PRIMERO Y EN CADA CICLO. Todas son idempotentes
# (`IF NOT EXISTS`), asi que reaplicarlas no cuesta nada; y sin esto, una
# columna nueva —como `valor_fuera_de_escala` de la 009— existiria en el codigo
# y no en la base del usuario, y las consultas fallarian en silencio el dia que
# se actualiza el repositorio y no la base.
Paso "0 de 5 : Migraciones"
if ($PSQL) {
    foreach ($m in (Get-ChildItem (Join-Path $raiz "migraciones") -Filter "*.sql" |
                    Sort-Object Name)) {
        & $PSQL -h localhost -U vigia -d vigia -q -f $m.FullName 2>&1 |
            Where-Object { $_ -notmatch "^\s*$" } | Out-Host
    }
    Write-Host "   migraciones al dia."
}

Paso "1 de 5 : Ingesta de contratos"
& $pyExe @pyArgs -m vigia --dataset contratos 2>&1 | Out-Host
$codigoContratos = $LASTEXITCODE

Paso "2 de 5 : Ingesta de procesos"
& $pyExe @pyArgs -m vigia --dataset procesos 2>&1 | Out-Host
$codigoProcesos = $LASTEXITCODE

# Se normaliza aunque una ingesta haya fallado: lo ya ingerido sigue siendo
# valido, y un Panel de ayer es mejor que ningun Panel. El fallo queda escrito.
Paso "3 de 5 : Normalizar"
& $pyExe @pyArgs -m vigia.normalizado 2>&1 |
    Where-Object { $_ -notmatch "WARNING portafolio" } | Out-Host

Paso "4 de 5 : Panel"
if ($PSQL) {
    & $PSQL -h localhost -U vigia -d vigia -tA -f "panel.sql" -o "panel.json" 2>&1 | Out-Host
    & $pyExe @pyArgs -m vigia.panel 2>&1 | Out-Host
}

# La lista de revision va DESPUES del Panel y no antes: el Panel dice sobre que
# parte del universo se esta calculando, y esta lista solo se lee bien sabiendo
# eso. Es la misma razon por la que el bloque de cobertura va primero adentro
# del Panel.
Paso "5 de 5 : Lista de revision"
if ($PSQL) {
    & $PSQL -h localhost -U vigia -d vigia -tA -f "revision.sql" -o "revision.json" 2>&1 | Out-Host
    & $pyExe @pyArgs -m vigia.revision 2>&1 | Out-Host
}

Write-Host ""
if ($codigoContratos -ne 0 -or $codigoProcesos -ne 0) {
    Write-Host "TERMINO CON FALLOS DE INGESTA (contratos=$codigoContratos procesos=$codigoProcesos)" -ForegroundColor Yellow
    Write-Host "El Panel se regenero con lo que ya habia en la base." -ForegroundColor Yellow
} else {
    Write-Host "Ciclo diario completo." -ForegroundColor Green
}
try { Stop-Transcript | Out-Null } catch { }
