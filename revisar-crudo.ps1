# Diagnostico de SOLO LECTURA sobre la capa cruda. No escribe nada.
#
# POR QUE EXISTE
# El 2026-09-03 el tercer Ciclo sobre EXACTAMENTE el mismo rango de fechas
# inserto 25 749 filas y conto CERO duplicados, cuando 24 685 de esos contratos
# ya estaban ingeridos. La segunda corrida, minutos despues de la primera,
# si los habia contado todos como duplicados.
#
# O bien la fuente cambio el contenido de esos contratos en las horas de por
# medio, o el hash que los identifica depende de algo que cambia solo. Las dos
# cosas importan y se distinguen mirando QUE campo cambio.

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "revisar-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

trap {
    Write-Host ""
    Write-Host "   ERROR NO PREVISTO:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    Write-Host "   linea $($_.InvocationInfo.ScriptLineNumber)" -ForegroundColor DarkGray
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

$PSQL = Buscar-Herramienta "psql"
if (-not $PSQL) {
    Write-Host "No encuentro psql." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "Enter para cerrar"
    exit 1
}

$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

function Consulta($titulo, $sql) {
    Write-Host ""
    Write-Host "== $titulo" -ForegroundColor Cyan
    & $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d","vigia","-q","-v","ON_ERROR_STOP=1","-c",$sql) | Out-Host
}

Write-Host "Vigia SECOP - diagnostico de la capa cruda (solo lectura)" -ForegroundColor White

Consulta "Cuantas VERSIONES guarda cada contrato" @"
SELECT versiones, count(*) AS cuantos_contratos
FROM (
    SELECT id_fila_fuente, count(DISTINCT hash_contenido) AS versiones
    FROM crudo_registro WHERE dataset = 'contratos' GROUP BY 1
) t
GROUP BY versiones ORDER BY versiones;
"@

Consulta "Cuando se trajo cada tanda" @"
SELECT date_trunc('minute', consultado_en) AS tanda, count(*) AS filas
FROM crudo_registro WHERE dataset = 'contratos'
GROUP BY 1 ORDER BY 1;
"@

# La pregunta que decide todo: de un contrato que tiene dos versiones, QUE
# campo cambio entre la primera y la segunda. Si es un campo de la plataforma
# (`:updated_at` y companeros) el dato no cambio y el hash esta mirando ruido.
# Si es un campo del contrato, la fuente si lo modifico y guardar las dos
# versiones es exactamente lo que debe pasar.
Consulta "QUE cambio entre la version vieja y la nueva de un mismo contrato" @"
WITH elegido AS (
    SELECT id_fila_fuente
    FROM crudo_registro WHERE dataset = 'contratos'
    GROUP BY 1 HAVING count(DISTINCT hash_contenido) > 1
    LIMIT 1
),
vieja AS (
    SELECT c.contenido FROM crudo_registro c JOIN elegido e USING (id_fila_fuente)
    WHERE c.dataset = 'contratos' ORDER BY c.consultado_en ASC LIMIT 1
),
nueva AS (
    SELECT c.contenido FROM crudo_registro c JOIN elegido e USING (id_fila_fuente)
    WHERE c.dataset = 'contratos' ORDER BY c.consultado_en DESC LIMIT 1
)
SELECT campo,
       left(coalesce(vieja.contenido ->> campo, '(ausente)'), 40) AS antes,
       left(coalesce(nueva.contenido ->> campo, '(ausente)'), 40) AS ahora
FROM vieja, nueva,
     LATERAL jsonb_object_keys(vieja.contenido || nueva.contenido) AS campo
WHERE vieja.contenido ->> campo IS DISTINCT FROM nueva.contenido ->> campo
ORDER BY campo;
"@

Consulta "Tamano de la capa cruda" @"
SELECT pg_size_pretty(pg_total_relation_size('crudo_registro')) AS ocupa,
       count(*) AS filas,
       count(DISTINCT id_fila_fuente) AS contratos_distintos
FROM crudo_registro WHERE dataset = 'contratos';
"@

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
