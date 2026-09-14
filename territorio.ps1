# Aplica la 1.6 y ensena el territorio de TU base.
#
# Corre la migracion 008 y vuelve a normalizar. La normalizacion tarda: sobre
# la base real son ~20 minutos, porque relee la capa cruda entera. No esta
# colgada; hasta que no termina no imprime.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
$REGISTRO = Join-Path $raiz "territorio-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

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
function Mal($m) {
    Write-Host "   FALLO: $m" -ForegroundColor Red
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"; exit 1
}

$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; break
    }
}
if (-not $pyExe) { Mal "No encuentro Python 3.11 o superior." }
$PSQL = Buscar-Herramienta "psql"
if (-not $PSQL) { Mal "No encuentro psql." }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"
$env:VIGIA_DSN = "postgresql://vigia:vigia@localhost:5432/vigia"

Write-Host ""
Write-Host "== 1 de 3 : Migraciones" -ForegroundColor Cyan
$antes = $ErrorActionPreference
$ErrorActionPreference = "Continue"
foreach ($m in (Get-ChildItem "migraciones\*.sql" | Sort-Object Name)) {
    & $PSQL -h localhost -U vigia -d vigia -v ON_ERROR_STOP=1 -f $m.FullName 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { $ErrorActionPreference = $antes; Mal "no aplico $($m.Name)" }
    Write-Host ("   OK  " + $m.Name) -ForegroundColor Green
}
$ErrorActionPreference = $antes

Write-Host ""
Write-Host "== 2 de 3 : Normalizar (paciencia: ~20 min sobre tu base)" -ForegroundColor Cyan
$antes = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $pyExe @pyArgs -m vigia.normalizado 2>&1 | Where-Object { $_ -notmatch "WARNING portafolio" } | Out-Host
$codigo = $LASTEXITCODE
$ErrorActionPreference = $antes
if ($codigo -ne 0) { Mal "la normalizacion fallo" }

Write-Host ""
Write-Host "== 3 de 3 : El territorio de TU base" -ForegroundColor Cyan
$consulta = @"
\pset border 2
\pset numericlocale on

SELECT coalesce(orden, '(sin declarar)') AS orden,
       count(*)                          AS contratos,
       sum(valor)::numeric(20,0)         AS valor
FROM contrato GROUP BY 1 ORDER BY contratos DESC;

SELECT coalesce(departamento_codigo, '--')          AS cod,
       coalesce(departamento_nombre, '(sin codigo)') AS departamento,
       count(*)                                      AS contratos,
       sum(valor)::numeric(20,0)                     AS valor
FROM contrato GROUP BY 1,2 ORDER BY valor DESC NULLS LAST LIMIT 15;

-- La prueba de que el municipio necesita el par (departamento, municipio):
-- un mismo nombre en departamentos distintos son municipios distintos.
SELECT municipio_nombre, count(DISTINCT departamento_codigo) AS en_cuantos_departamentos
FROM contrato
WHERE municipio_nombre IS NOT NULL AND departamento_codigo IS NOT NULL
GROUP BY 1 HAVING count(DISTINCT departamento_codigo) > 1
ORDER BY 2 DESC, 1 LIMIT 15;
"@
$antes = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$consulta | & $PSQL -h localhost -U vigia -d vigia 2>&1 | Out-Host
$ErrorActionPreference = $antes

Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
