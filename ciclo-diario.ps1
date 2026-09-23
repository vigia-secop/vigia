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

# EL FILTRO QUE APAGA EL INCENDIO FALSO.
#
# Python escribe su registro por el canal de errores -asi funciona `logging`,
# no es un fallo- y PowerShell pinta de rojo todo lo que sale por ahi y encima
# le encaja un bloque `NativeCommandError`. El 2026-09-19 la ingesta termino
# perfecta y la pantalla parecia un incendio: cada linea roja era un HTTP 200.
#
# En el portatil se aguanta porque hay alguien que ya sabe. En el servidor el
# ciclo corre solo a las 5:40 y deja un registro que nadie lee entero: un
# registro que SIEMPRE parece roto no avisa el dia que se rompe de verdad.
#
# LAS FORMAS QUE NO SIRVEN, PROBADAS EN POWERSHELL 5.1 EL 2026-09-20 -no en el
# 7, que fue mi error del 16-. Con `probar-rojo.ps1`, sobre una orden que
# escribe por stderr y termina con codigo 0:
#
#     2>&1 | Out-Host   (lo que habia)        rojo + NativeCommandError
#     lo mismo con ErrorActionPreference bajo   NO IMPRIME NADA
#     capturar en variable con EAP bajo         NO IMPRIME NADA
#     2>&1 | ForEach-Object { Write-Host }      la linea en gris, sin rojo
#     2>&1 | <este filtro>                      la linea en gris, sin rojo
#
# Ojo con las dos del medio: bajar `ErrorActionPreference` no quita el rojo,
# se traga la linea. Eso es peor que el rojo, porque el rojo al menos se ve.
filter Sin-Rojo { Write-Host "$_" }

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

# ---------------------------------------------------------------------------
# EL CANDADO: MIENTRAS ESTO CORRE, LA BASE NO ESTA QUIETA
# ---------------------------------------------------------------------------
# El 2026-09-16 se publico el sitio mientras este ciclo estaba normalizando.
# La pagina salio con los datos de ayer sin que nadie se enterara: decia que
# septiembre llegaba al dia 9 cuando los del 13 ya estaban bajados, todavia
# sin normalizar. Y la normalizacion escribe procesos, proveedores y contratos
# en tres transacciones separadas, asi que quien lea en el medio puede cruzar
# tablas de momentos distintos.
#
# Ese es el peor tipo de error: no falla, no avisa, y la cifra se lee mal.
# Asi que el ciclo deja constancia de que esta trabajando, y `publicar.ps1`
# mira este archivo antes de empezar.
$candado = Join-Path $raiz "ciclo-en-curso.lock"
Set-Content -LiteralPath $candado -Value (Get-Date -Format "yyyy-MM-dd HH:mm:ss") -Encoding ASCII

Write-Host "Ciclo diario de Vigia - $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor White

# LAS MIGRACIONES VAN PRIMERO Y EN CADA CICLO. Todas son idempotentes
# (`IF NOT EXISTS`), asi que reaplicarlas no cuesta nada; y sin esto, una
# columna nueva -como `valor_fuera_de_escala` de la 009- existiria en el codigo
# y no en la base del usuario, y las consultas fallarian en silencio el dia que
# se actualiza el repositorio y no la base.
Paso "0 de 5 : Migraciones"
if ($PSQL) {
    foreach ($m in (Get-ChildItem (Join-Path $raiz "migraciones") -Filter "*.sql" |
                    Sort-Object Name)) {
        & $PSQL -h localhost -U vigia -d vigia -q -f $m.FullName 2>&1 |
            Where-Object { $_ -notmatch "^\s*$" } | Sin-Rojo
    }
    Write-Host "   migraciones al dia."
}

Paso "1 de 5 : Ingesta de contratos"
& $pyExe @pyArgs -m vigia --dataset contratos 2>&1 | Sin-Rojo
$codigoContratos = $LASTEXITCODE

Paso "2 de 5 : Ingesta de procesos"
& $pyExe @pyArgs -m vigia --dataset procesos 2>&1 | Sin-Rojo
$codigoProcesos = $LASTEXITCODE

# Se normaliza aunque una ingesta haya fallado: lo ya ingerido sigue siendo
# valido, y un Panel de ayer es mejor que ningun Panel. El fallo queda escrito.
Paso "3 de 5 : Normalizar"
& $pyExe @pyArgs -m vigia.normalizado 2>&1 |
    Where-Object { $_ -notmatch "WARNING portafolio" } | Sin-Rojo

Paso "4 de 5 : Panel"
if ($PSQL) {
    & $PSQL -h localhost -U vigia -d vigia -tA -f "panel.sql" -o "panel.json" 2>&1 | Sin-Rojo
    & $pyExe @pyArgs -m vigia.panel 2>&1 | Sin-Rojo
}

# La lista de revision va DESPUES del Panel y no antes: el Panel dice sobre que
# parte del universo se esta calculando, y esta lista solo se lee bien sabiendo
# eso. Es la misma razon por la que el bloque de cobertura va primero adentro
# del Panel.
Paso "5 de 5 : Lista de revision"
if ($PSQL) {
    & $PSQL -h localhost -U vigia -d vigia -tA -f "revision.sql" -o "revision.json" 2>&1 | Sin-Rojo
    & $pyExe @pyArgs -m vigia.revision 2>&1 | Sin-Rojo
}

Remove-Item -LiteralPath $candado -Force -ErrorAction SilentlyContinue

Write-Host ""
if ($codigoContratos -ne 0 -or $codigoProcesos -ne 0) {
    Write-Host "TERMINO CON FALLOS DE INGESTA (contratos=$codigoContratos procesos=$codigoProcesos)" -ForegroundColor Yellow
    Write-Host "El Panel se regenero con lo que ya habia en la base." -ForegroundColor Yellow
} else {
    Write-Host "Ciclo diario completo." -ForegroundColor Green
}
try { Stop-Transcript | Out-Null } catch { }
