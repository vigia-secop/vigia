# PROBAR EL ARREGLO ANTES DE ESCRIBIRLO EN CUATRO ARCHIVOS.
#
# LO QUE YA SE MIDIO (medicion-banderas.txt, 2026-09-20):
#
#   Index Scan using crudo_registro_rellave_dataset_consultado_en_idx
#     Index Cond: (dataset = 'contratos')
#     Filter:     (contenido->>'id_contrato' = ...)
#     Rows Removed by Filter: 174.697
#   Execution Time: 11.124 ms
#
# Once segundos para buscar UN enlace, teniendo el indice correcto a mano y
# sin usarlo. La culpa es del `ORDER BY consultado_en DESC LIMIT 1`: con un
# LIMIT 1 delante, el planificador se convence de que le conviene recorrer el
# indice de FECHA esperando toparse con el contrato pronto. No se topa.
#
# EL ARREGLO QUE SE PRUEBA AQUI: quitarle el LIMIT. Sin LIMIT, el planificador
# no tiene la ilusion de parar temprano y tiene que traer todas las filas de
# ese contrato -que son dos o tres-, asi que usa el indice del ID, que es el
# que sirve. El orden se hace despues, dentro del array:
#
#     (array_agg(url ORDER BY consultado_en DESC))[1]
#
# Es exactamente el mismo resultado: la fila mas reciente, o NULL si no hay.
#
# NO CAMBIA NADA. Corre las dos formas sobre el mismo contrato y las compara.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

function Buscar($n) {
    $p = Get-Command $n -ErrorAction SilentlyContinue
    if ($p) { return $p.Source }
    foreach ($r in @("C:\Program Files\PostgreSQL", "C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $r)) { continue }
        foreach ($v in (Get-ChildItem $r -Directory -EA SilentlyContinue |
            Sort-Object { if ($_.Name -match '^(\d+)') { [int]$Matches[1] } else { 0 } } -Descending)) {
            $ruta = Join-Path $v.FullName "bin\$n.exe"
            if (Test-Path $ruta) { return $ruta }
        }
    }
    return $null
}

$PSQL = Buscar "psql"
if (-not $PSQL) { Write-Host "  No encontre psql." -ForegroundColor Red; exit 1 }
$env:PGPASSWORD = "vigia"
$env:PGCLIENTENCODING = "UTF8"

$salida = Join-Path $raiz "medicion-enlace.txt"
Set-Content -LiteralPath $salida -Value "PROBAR EL ARREGLO DEL ENLACE - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8

function Correr($titulo, $sqlTexto) {
    Write-Host ""
    Write-Host "== $titulo" -ForegroundColor Cyan
    $tmp = Join-Path $env:TEMP "vigia-probar-enlace.sql"
    Set-Content -LiteralPath $tmp -Value $sqlTexto -Encoding UTF8
    Add-Content -LiteralPath $salida -Value ""
    Add-Content -LiteralPath $salida -Value "=============================================================="
    Add-Content -LiteralPath $salida -Value "  $titulo"
    Add-Content -LiteralPath $salida -Value "=============================================================="
    $r = & $PSQL -h localhost -U vigia -d vigia -f $tmp 2>&1
    $r | Out-Host
    $r | ForEach-Object { Add-Content -LiteralPath $salida -Value ($_.ToString()) }
    Remove-Item -LiteralPath $tmp -Force -EA SilentlyContinue
}

Write-Host ""
Write-Host "  PROBAR EL ARREGLO DEL ENLACE" -ForegroundColor White
Write-Host "  Queda escrito en medicion-enlace.txt" -ForegroundColor DarkGray

# Se fija un contrato concreto para que las dos formas busquen LO MISMO.
Correr "0 de 3 : Los dos dan el mismo resultado" @"
WITH uno AS (SELECT id_contrato FROM contrato ORDER BY id_contrato LIMIT 1)
SELECT (SELECT r.contenido->'urlproceso'->>'url'
          FROM crudo_registro r
         WHERE r.dataset = 'contratos'
           AND r.contenido->>'id_contrato' = uno.id_contrato
         ORDER BY r.consultado_en DESC LIMIT 1)            AS forma_vieja,
       (SELECT (array_agg(r.contenido->'urlproceso'->>'url'
                          ORDER BY r.consultado_en DESC))[1]
          FROM crudo_registro r
         WHERE r.dataset = 'contratos'
           AND r.contenido->>'id_contrato' = uno.id_contrato) AS forma_nueva
  FROM uno;
"@

Correr "1 de 3 : La forma VIEJA (ORDER BY ... LIMIT 1)" @"
EXPLAIN (ANALYZE, BUFFERS)
SELECT (SELECT r.contenido->'urlproceso'->>'url'
          FROM crudo_registro r
         WHERE r.dataset = 'contratos'
           AND r.contenido->>'id_contrato' = c.id_contrato
         ORDER BY r.consultado_en DESC LIMIT 1)
  FROM (SELECT id_contrato FROM contrato ORDER BY id_contrato LIMIT 1) c;
"@

Correr "2 de 3 : La forma NUEVA (sin LIMIT, se ordena en el array)" @"
EXPLAIN (ANALYZE, BUFFERS)
SELECT (SELECT (array_agg(r.contenido->'urlproceso'->>'url'
                          ORDER BY r.consultado_en DESC))[1]
          FROM crudo_registro r
         WHERE r.dataset = 'contratos'
           AND r.contenido->>'id_contrato' = c.id_contrato)
  FROM (SELECT id_contrato FROM contrato ORDER BY id_contrato LIMIT 1) c;
"@

Correr "3 de 3 : La forma nueva, cincuenta veces seguidas" @"
EXPLAIN (ANALYZE, BUFFERS)
SELECT (SELECT (array_agg(r.contenido->'urlproceso'->>'url'
                          ORDER BY r.consultado_en DESC))[1]
          FROM crudo_registro r
         WHERE r.dataset = 'contratos'
           AND r.contenido->>'id_contrato' = c.id_contrato)
  FROM (SELECT id_contrato FROM contrato ORDER BY id_contrato LIMIT 50) c;
"@

Write-Host ""
Write-Host "  COMO SE LEE:" -ForegroundColor Gray
Write-Host "  - El paso 0 tiene que dar las DOS columnas iguales. Si no," -ForegroundColor Gray
Write-Host "    el arreglo cambia el resultado y no sirve." -ForegroundColor Gray
Write-Host "  - Compara 'Execution Time' del 1 contra el del 2." -ForegroundColor Gray
Write-Host "  - El paso 3 es la prueba de verdad: cincuenta busquedas." -ForegroundColor Gray
Write-Host "    Con la forma vieja serian nueve minutos." -ForegroundColor Gray
Write-Host ""
