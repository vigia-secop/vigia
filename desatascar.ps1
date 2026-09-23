# DESATASCAR: soltar la base cuando una consulta muerta esta frenando al resto.
#
# POR QUE EXISTE ESTO. El 2026-09-19 una consulta mia se demoro tanto que hubo
# que cerrar la ventana a la fuerza. Cerrar la ventana mata a `psql`, pero NO
# mata la consulta: PostgreSQL sigue trabajando en ella hasta terminarla,
# porque un SELECT largo no se entera de que el cliente se fue hasta que
# intenta devolverle algo.
#
# Y mientras esa consulta viva, tiene tomada la tabla `contrato` en modo
# lectura. Eso basta para que el paso de migraciones del ciclo -que hace
# `ALTER TABLE contrato ...`- se quede esperando SIN decir nada. Se ve como un
# "0 de 5 : Migraciones" que no avanza. No esta colgado: esta haciendo cola.
#
# LO QUE ESTE SCRIPT NO HACE: no reinicia la base, no borra nada y no mata
# "lo que lleve mucho rato". Mata UNICAMENTE a los procesos que estan
# bloqueando a otro. Si no hay nadie bloqueado, no mata a nadie y lo dice.
# Esa es la diferencia entre una herramienta y una escopeta.

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
    Write-Host ""
    Write-Host "  No encontre psql. Sin el no puedo mirar la base." -ForegroundColor Red
    exit 1
}
$env:PGPASSWORD = "vigia"

function Consultar($sql) {
    & $PSQL -h localhost -U vigia -d vigia -c $sql 2>&1 | Out-Host
}

Write-Host ""
Write-Host "  DESATASCAR LA BASE DE VIGIA" -ForegroundColor White
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

Write-Host "== 1 de 3 : Quien esta trabajando ahora mismo" -ForegroundColor Cyan
Consultar @"
SELECT pid,
       state                                           AS estado,
       coalesce(wait_event_type, '-')                  AS esperando,
       date_trunc('second', now() - query_start)       AS lleva,
       left(regexp_replace(query, '\s+', ' ', 'g'), 50) AS consulta
  FROM pg_stat_activity
 WHERE datname = 'vigia' AND pid <> pg_backend_pid()
 ORDER BY query_start;
"@

Write-Host ""
Write-Host "== 2 de 3 : Quien esta frenando a quien" -ForegroundColor Cyan
Consultar @"
SELECT a.pid                                     AS esperando,
       unnest(pg_blocking_pids(a.pid))           AS lo_frena,
       date_trunc('second', now() - a.query_start) AS lleva_esperando
  FROM pg_stat_activity a
 WHERE a.datname = 'vigia'
   AND cardinality(pg_blocking_pids(a.pid)) > 0;
"@

Write-Host ""
Write-Host "== 3 de 3 : Soltar" -ForegroundColor Cyan
# Solo los que frenan a alguien y llevan mas de dos minutos haciendolo. El
# limite de tiempo esta para no matar a un proceso que apenas tomo la tabla y
# la va a soltar solo dentro de un segundo.
Consultar @"
WITH culpables AS (
  SELECT DISTINCT unnest(pg_blocking_pids(a.pid)) AS pid
    FROM pg_stat_activity a
   WHERE a.datname = 'vigia'
     AND cardinality(pg_blocking_pids(a.pid)) > 0
)
SELECT c.pid,
       date_trunc('second', now() - s.query_start) AS llevaba,
       pg_terminate_backend(c.pid)                 AS soltado
  FROM culpables c
  JOIN pg_stat_activity s USING (pid)
 WHERE s.query_start < now() - interval '2 minutes';
"@

Write-Host ""
Write-Host "  Si la tabla de arriba salio vacia, no habia nada que soltar" -ForegroundColor Gray
Write-Host "  y el atasco es otra cosa." -ForegroundColor Gray
Write-Host ""
Write-Host "  Si solto algo: la ventana del ciclo debe seguir sola en unos" -ForegroundColor Gray
Write-Host "  segundos. No la cierres." -ForegroundColor Gray
Write-Host ""
