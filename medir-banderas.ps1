# DONDE SE VAN LOS 47 MINUTOS DE LA PAGINA DE BANDERAS.
#
# LO QUE YA SABEMOS, MEDIDO EL 2026-09-20 (medicion-consultas.txt):
#
#   - El corazon compartido de cinco consultas -sacar el ultimo registro de
#     cada proceso adjudicado- tarda ~20 segundos. VEINTE SEGUNDOS, no
#     minutos. No es el cuello.
#   - El planificador NI SIQUIERA USA el indice de la migracion 010 para eso:
#     elige recorrer la tabla entera en paralelo, y hace bien. Con indice y
#     sin indice sale el mismo plan y el mismo tiempo.
#   - Las estadisticas estan frescas. `work_mem` alcanza de sobra: el orden
#     cabe en 1,9 MB.
#
# Es decir: mis tres sospechas -el indice, las estadisticas, la memoria-
# estaban las tres equivocadas. Lo que queda es lo que nunca mire.
#
# LA SOSPECHA QUE SI QUEDA EN PIE. `banderas.sql` busca, por cada contrato
# que va a publicar, el enlace al SECOP dentro de `crudo_registro`:
#
#     WHERE r.dataset = 'contratos'
#       AND r.contenido->>'id_contrato' = ...
#
# Si el indice `crudo_contrato_id_idx` NO se usa ahi, cada una de esas
# busquedas recorre 1.032 MB de tabla. Son unos 4.000 contratos. Cuatro mil
# por un giga es exactamente la clase de numero que se convierte en 47
# minutos sin que nada parezca roto.
#
# ESTE SCRIPT NO CAMBIA NADA. El paso 1 ni siquiera corre la consulta: solo
# pide el plan, y sale al instante.

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

$salida = Join-Path $raiz "medicion-banderas.txt"
Set-Content -LiteralPath $salida -Value "DONDE SE VAN LOS MINUTOS - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8

function Correr($titulo, $archivoSql) {
    Write-Host ""
    Write-Host "== $titulo" -ForegroundColor Cyan
    Add-Content -LiteralPath $salida -Value ""
    Add-Content -LiteralPath $salida -Value "=============================================================="
    Add-Content -LiteralPath $salida -Value "  $titulo"
    Add-Content -LiteralPath $salida -Value "=============================================================="
    $r = & $PSQL -h localhost -U vigia -d vigia -f $archivoSql 2>&1
    $r | Out-Host
    $r | ForEach-Object { Add-Content -LiteralPath $salida -Value ($_.ToString()) }
}

Write-Host ""
Write-Host "  DONDE SE VAN LOS MINUTOS DE LA PAGINA DE BANDERAS" -ForegroundColor White
Write-Host "  Queda escrito en medicion-banderas.txt" -ForegroundColor DarkGray

# --- 1: el plan entero, sin correrlo -----------------------------------
$tmp1 = Join-Path $env:TEMP "vigia-plan-banderas.sql"
$cuerpo = Get-Content -LiteralPath (Join-Path $raiz "banderas.sql") -Raw -Encoding UTF8
Set-Content -LiteralPath $tmp1 -Value ("EXPLAIN`r`n" + $cuerpo) -Encoding UTF8
Correr "1 de 3 : El plan de banderas.sql (sin correrlo)" $tmp1
Remove-Item -LiteralPath $tmp1 -Force -EA SilentlyContinue

# --- 2: UNA busqueda de enlace, cronometrada ---------------------------
$tmp2 = Join-Path $env:TEMP "vigia-un-enlace.sql"
Set-Content -LiteralPath $tmp2 -Encoding UTF8 -Value @"
EXPLAIN (ANALYZE, BUFFERS)
SELECT r.contenido->'urlproceso'->>'url'
  FROM crudo_registro r
 WHERE r.dataset = 'contratos'
   AND r.contenido->>'id_contrato' = (SELECT id_contrato FROM contrato LIMIT 1)
 ORDER BY r.consultado_en DESC
 LIMIT 1;
"@
Correr "2 de 3 : UNA sola busqueda de enlace" $tmp2
Remove-Item -LiteralPath $tmp2 -Force -EA SilentlyContinue

# --- 3: cuantas de esas busquedas hay ----------------------------------
$tmp3 = Join-Path $env:TEMP "vigia-cuantos.sql"
Set-Content -LiteralPath $tmp3 -Encoding UTF8 -Value @"
SELECT count(*) AS indices_sobre_crudo_registro FROM pg_indexes
 WHERE tablename = 'crudo_registro';
SELECT indexname FROM pg_indexes WHERE tablename = 'crudo_registro' ORDER BY 1;
"@
Correr "3 de 3 : Que indices existen de verdad sobre crudo_registro" $tmp3
Remove-Item -LiteralPath $tmp3 -Force -EA SilentlyContinue

Write-Host ""
Write-Host "  COMO SE LEE:" -ForegroundColor Gray
Write-Host "  - En el paso 1, busca la palabra 'Seq Scan on crudo_registro'" -ForegroundColor Gray
Write-Host "    DENTRO del nido del enlace. Si esta ahi, es eso." -ForegroundColor Gray
Write-Host "  - En el paso 2, mira 'Execution Time'. Si UNA busqueda tarda" -ForegroundColor Gray
Write-Host "    segundos en vez de milisegundos, multiplicalo por 4.000." -ForegroundColor Gray
Write-Host ""
