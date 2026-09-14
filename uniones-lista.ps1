# Solo la lista: no normaliza, no migra. Segundos, no minutos.
#
# POR QUE EXISTE. La primera corrida ordeno mal. La consulta decia
#
#     to_char(valor, 'FM999G999G999G999') AS valor ... ORDER BY valor DESC
#
# y PostgreSQL, en ORDER BY, prefiere el NOMBRE DE SALIDA sobre la columna.
# Asi que ordeno por el texto ya formateado: "998.000.000" quedaba por encima
# de "9.287.018.195" porque el 9 va antes que el 9... como cadena. El ranking
# no era de los mas grandes, era alfabetico.
#
# Aqui el alias se llama distinto y el ORDER BY apunta a la columna numerica.
# Es la misma leccion de siempre: un numero que se ve plausible no esta
# verificado. Este se veia perfectamente plausible.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "uniones-lista-ultima-corrida.txt"
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

$PSQL = Buscar-Herramienta "psql"
if (-not $PSQL) {
    Write-Host "No encuentro psql." -ForegroundColor Red
    Read-Host "Enter para cerrar"; exit 1
}
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

Write-Host ""
Write-Host "Uniones temporales y consorcios sin documento -- las 25 mas grandes" -ForegroundColor Cyan
Write-Host ""

$consulta = @"
\pset border 2
\pset numericlocale on

SELECT count(*)                              AS contratos,
       sum(valor)::numeric(20,0)             AS valor_total,
       count(DISTINCT nit_entidad)           AS entidades
FROM contrato WHERE proveedor_provisional;

SELECT proveedor_nombre                      AS union_temporal,
       left(nombre_entidad, 45)              AS entidad,
       valor::numeric(20,0)                  AS valor_cop,
       estado
FROM contrato
WHERE proveedor_provisional
ORDER BY valor DESC NULLS LAST
LIMIT 25;

-- Cuanto pesan sobre el total, que es la pregunta que importa.
SELECT round(100.0 * sum(valor) FILTER (WHERE proveedor_provisional)
             / nullif(sum(valor), 0), 2)     AS pct_del_valor_total,
       round(100.0 * count(*) FILTER (WHERE proveedor_provisional)
             / nullif(count(*), 0), 2)       AS pct_de_los_contratos
FROM contrato;
"@

$antes = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$consulta | & $PSQL -h localhost -U vigia -d vigia 2>&1 | Out-Host
$ErrorActionPreference = $antes

Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
