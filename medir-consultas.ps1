# POR QUE LAS CONSULTAS DEL SITIO SE VOLVIERON LENTAS. MEDIR, NO ADIVINAR.
#
# EL HECHO QUE HAY QUE EXPLICAR. El 2026-09-16 la lista de revision se armaba
# en 3 minutos. El 2026-09-20, con un 5 % mas de datos, tardo 17, y la pagina
# de banderas paso de 47 minutos sin terminar. Algo cambio entre esas dos
# fechas y hay solo dos candidatos:
#
#   A. LAS ESTADISTICAS ESTAN VIEJAS. El 19 se normalizaron 100.000 registros
#      nuevos. Si PostgreSQL todavia cree que `contrato` y `proceso` tienen el
#      tamano de antes, elige el plan equivocado para unirlas. Es la causa mas
#      comun de "ayer iba rapido y hoy no" y la mas barata de arreglar.
#
#   B. EL INDICE DE LA MIGRACION 010 ESTORBA. Se creo para buscar UN contrato
#      por su id, y para eso sirve. Pero cinco consultas del sitio recorren
#      los 479.000 documentos JSON ENTEROS: con indice, PostgreSQL los lee
#      saltando por el disco de fila en fila; sin indice los lee de corrido y
#      ordena al final. Para recorrerlo todo, saltar puede ser mucho peor.
#
# Este script decide entre las dos con numeros. Lo unico que cambia en la base
# es `ANALYZE`, que solo recalcula estadisticas: no toca ni un dato, ni un
# indice, ni una tabla, y es tarea de mantenimiento normal.
#
# Tarda: los pasos 3 y 4 corren la consulta entera dos veces. Media hora larga.
# No lo corras junto con el ciclo ni con la publicacion.

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
if (-not $PSQL) {
    Write-Host "  No encontre psql." -ForegroundColor Red
    exit 1
}
$env:PGPASSWORD = "vigia"

$salida = Join-Path $raiz "medicion-consultas.txt"
Set-Content -LiteralPath $salida -Value "MEDICION DE CONSULTAS - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8

function Paso($titulo, $sql) {
    Write-Host ""
    Write-Host "== $titulo" -ForegroundColor Cyan
    Add-Content -LiteralPath $salida -Value ""
    Add-Content -LiteralPath $salida -Value "=============================================================="
    Add-Content -LiteralPath $salida -Value "  $titulo"
    Add-Content -LiteralPath $salida -Value "=============================================================="
    $r = & $PSQL -h localhost -U vigia -d vigia -c $sql 2>&1
    $r | Out-Host
    $r | ForEach-Object { Add-Content -LiteralPath $salida -Value ($_.ToString()) }
}

# El corazon de cinco consultas del sitio: el ultimo registro de cada proceso
# adjudicado. Se mide ESTO porque es lo que se repite en todas.
$consulta = @"
SELECT count(*) FROM (
  SELECT DISTINCT ON (contenido->>'id_del_proceso') contenido
  FROM crudo_registro
  WHERE dataset = 'procesos'
    AND contenido->>'adjudicado' = 'Si'
    AND contenido->>'precio_base' ~ '^[0-9]+(\.[0-9]+)?$'
    AND contenido->>'valor_total_adjudicacion' ~ '^[0-9]+(\.[0-9]+)?$'
    AND (contenido->>'precio_base')::numeric > 0
  ORDER BY contenido->>'id_del_proceso', consultado_en DESC
) u;
"@

Write-Host ""
Write-Host "  POR QUE LAS CONSULTAS SE VOLVIERON LENTAS" -ForegroundColor White
Write-Host "  Todo queda escrito en medicion-consultas.txt" -ForegroundColor DarkGray

Paso "0 de 5 : Con que memoria y que costos trabaja la base" @"
SELECT name, setting, unit FROM pg_settings
 WHERE name IN ('work_mem','shared_buffers','effective_cache_size',
                'random_page_cost','seq_page_cost','max_parallel_workers_per_gather')
 ORDER BY name;
"@

# ESTE PASO ES EL QUE PUEDE CERRAR EL CASO EN UN SEGUNDO. Si `n_mod_since_
# analyze` esta en decenas de miles, PostgreSQL esta planeando a ciegas.
Paso "1 de 5 : Hace cuanto no se miran las estadisticas (CANDIDATO A)" @"
SELECT relname                                    AS tabla,
       n_live_tup                                 AS filas_vivas,
       n_mod_since_analyze                        AS cambios_sin_mirar,
       coalesce(to_char(greatest(last_analyze, last_autoanalyze),
                        'YYYY-MM-DD HH24:MI'), 'NUNCA') AS ultimo_analyze
  FROM pg_stat_user_tables
 WHERE relname IN ('crudo_registro','contrato','proceso','proveedor')
 ORDER BY n_mod_since_analyze DESC;
"@

Write-Host ""
Write-Host "== 2 de 5 : Recalcular estadisticas (ANALYZE)" -ForegroundColor Cyan
Write-Host "   Solo estadisticas. No toca datos, ni indices, ni tablas." -ForegroundColor DarkGray
$r = & $PSQL -h localhost -U vigia -d vigia -c "ANALYZE crudo_registro; ANALYZE contrato; ANALYZE proceso; ANALYZE proveedor;" 2>&1
$r | Out-Host
$r | ForEach-Object { Add-Content -LiteralPath $salida -Value ($_.ToString()) }
Write-Host "   estadisticas al dia." -ForegroundColor Gray

Paso "3 de 5 : Como lo hace con las estadisticas frescas" `
     "EXPLAIN (ANALYZE, BUFFERS, TIMING) $consulta"

Paso "4 de 5 : Prohibiendole usar indice (CANDIDATO B)" `
     "SET enable_indexscan = off; SET enable_bitmapscan = off; SET enable_indexonlyscan = off; EXPLAIN (ANALYZE, BUFFERS, TIMING) $consulta"

Paso "5 de 5 : Tamano de lo que se recorre" @"
SELECT relname,
       pg_size_pretty(pg_relation_size(oid))       AS tabla,
       pg_size_pretty(pg_total_relation_size(oid)) AS con_indices
  FROM pg_class WHERE relname IN ('crudo_registro','contrato','proceso')
 ORDER BY pg_total_relation_size(oid) DESC;
"@

Write-Host ""
Write-Host "  Listo. Todo en medicion-consultas.txt" -ForegroundColor Green
Write-Host ""
Write-Host "  COMO SE LEE:" -ForegroundColor Gray
Write-Host "  - Si en el paso 1 'cambios_sin_mirar' eran decenas de miles," -ForegroundColor Gray
Write-Host "    era el candidato A y el ANALYZE del paso 2 ya lo arreglo." -ForegroundColor Gray
Write-Host "  - Compara el 'Execution Time' del paso 3 contra el del 4." -ForegroundColor Gray
Write-Host "    Si el 4 es MENOR, el indice esta estorbando y hay que" -ForegroundColor Gray
Write-Host "    quitarlo. Si es mayor, el indice esta bien y la causa era A." -ForegroundColor Gray
Write-Host ""
