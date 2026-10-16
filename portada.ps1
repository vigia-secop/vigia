# LA PORTADA DEL DIA. Construye docs\index.html y la abre. NO sube nada.
#
#     .\portada.ps1              # el ultimo dia con contratos
#     .\portada.ps1 -Dia 2026-09-10
#
# POR QUE «EL ULTIMO DIA CON CONTRATOS» Y NO «HOY». SECOP publica con rezago:
# a las seis de la manana el dia de hoy puede estar vacio. Una portada en
# blanco no se lee como «todavia no hay datos», se lee como «este sitio esta
# roto», y eso pasaria casi todos los dias.
#
# LO QUE ESTA PAGINA ES. El boletin semanal se quedo en semana.html. La portada
# es el REGISTRO: quien entre un miercoles tiene que ver el miercoles. Un ano
# de portadas sin un hueco y sin una cifra desmentida es lo que convierte a
# Vigia en algo que alguien cita.

param([string]$Dia = "", [switch]$NoAbrir)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "portada-ultima-corrida.txt") -Force | Out-Null } catch { }

function Mal($m) {
    Write-Host ""
    Write-Host "  ABORTADO: $m" -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

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
$PSQL = Buscar "psql"
if (-not $PSQL -or -not $pyExe) { Mal "faltan psql o Python 3.11+" }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

# EL ULTIMO DIA COMPLETO, NO EL ULTIMO DIA CON ALGO.
#
# `max(fecha_de_firma)` parecia obvio y estuvo mal durante meses. El SECOP
# publica con dos a cinco dias de retraso, asi que el dia mas reciente de la
# base casi siempre esta a medio llenar: el 2026-10-15 la portada mostro el
# 13 de octubre con UN contrato de $7,8 millones y un "-100,0 % contra el
# mismo dia de la semana pasada". Nada de eso era falso y todo daba la
# impresion contraria a la verdad, que es la peor clase de error en una
# pagina publica.
#
# Se toma entonces el ultimo dia que ya se parece a un dia: al menos el 60 %
# de los contratos de un dia tipico de las ultimas semanas. El umbral no es
# magico (un dia habil ronda los 3.000 y un dia a medio llenar no pasa de
# unas decenas), y por eso deja fuera tambien sabados y domingos, que no son
# dias de jornada. La pagina lo dice en su propia linea: ver `portada.py`.
if (-not $Dia) {
    $consultaDia = @"
WITH dias AS (
  SELECT fecha_de_firma AS dia, count(*) AS n
  FROM contrato
  WHERE valor_fuera_de_escala IS NOT TRUE
    AND fecha_de_firma > current_date - 60
  GROUP BY 1
),
tipico AS (
  SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY n) AS m
  FROM dias
  WHERE n >= 300
)
SELECT coalesce(
  (SELECT max(dia) FROM dias, tipico WHERE tipico.m IS NOT NULL AND n >= 0.6 * tipico.m),
  (SELECT max(dia) FROM dias)
)
"@
    $Dia = (& $PSQL -h localhost -U vigia -d vigia -tA -c $consultaDia 2>&1).Trim()
}
if ($Dia -notmatch '^\d{4}-\d{2}-\d{2}$') { Mal "no hay un dia valido que dibujar ($Dia)" }

Write-Host ""
Write-Host "  PORTADA DE VIGIA - $Dia" -ForegroundColor White
Write-Host ""

Write-Host "== 1 de 2 : Consultar el dia" -ForegroundColor Cyan
& $PSQL -q -h localhost -U vigia -d vigia -tA -v dia="'$Dia'" -f "portada.sql" -o "portada.json" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "fallo la consulta" }

Write-Host ""
Write-Host "== 2 de 2 : Dibujar docs\index.html" -ForegroundColor Cyan
& $pyExe @pyArgs -m vigia.portada --json "portada.json" --salida "docs\index.html" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "la portada no se pudo construir (o llevaba un documento sin enmascarar)" }

Write-Host ""
Write-Host "  Listo. NO se subio nada." -ForegroundColor Green
Write-Host "  Para publicarla: EJECUTAR-PUBLICAR.bat" -ForegroundColor Gray
if (-not $NoAbrir -and (Test-Path "docs\index.html")) { Start-Process (Resolve-Path "docs\index.html") }
try { Stop-Transcript | Out-Null } catch { }
