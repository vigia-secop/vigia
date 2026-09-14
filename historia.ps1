# TRAER HISTORIA HACIA ATRAS. Una sola vez, y tarda horas.
#
#     .\historia.ps1 -Meses 6
#
# POR QUE HACE FALTA. La medicion de concentracion del 2026-09-10 dio, por
# primera vez en el proyecto, la forma de una senal de verdad: exigiendo cinco
# contratos por entidad, la mediana de «cuanto se lleva el mayor proveedor» es
# 29 % y solo el 2,1 % de las entidades pasa del 90 %. Minoria medida, no norma.
#
# PERO LA VENTANA ES DE UN MES, y **la concentracion es un fenomeno de tiempo**.
# Una entidad con seis contratos en agosto, cinco de ellos al mismo proveedor,
# puede ser perfectamente normal vista sobre un ano. Publicar esa lista hoy
# seria senalar a alguien con una foto de 33 dias, que es la misma clase de
# error que mato a las tres banderas anteriores, solo que al reves.
#
# Ademas la primera corrida ya lo grito por su cuenta:
#   «VENTANA CORTA: 5538 registro(s) nuevo(s) con fecha de hecho en el dia mas
#    viejo de la ventana.»
# Cuando el dia mas viejo viene lleno, hay mas atras que no estamos viendo.
#
# COMO LO HACE. Mes a mes hacia atras, cada tramo con sus fechas explicitas.
# NO se toca la marca de agua: el ciclo diario sigue trayendo lo nuevo por su
# lado. Cada tramo es independiente, asi que si uno falla —o si cierras la
# ventana a la mitad— lo que ya entro se queda, y volver a correrlo no duplica
# nada (la capa cruda reconoce los repetidos: en la corrida del 6 de septiembre
# descarto 160.399 duplicados sin despeinarse).
#
# CUANTO TARDA. Un mes de contratos son ~10 minutos y uno de procesos ~14. Seis
# meses son unas 2,5 horas; un ano, unas 5. Dejalo corriendo y vete.

param(
    [int]$Meses = 6,
    [string]$Desde = "",   # p.ej. "2026-07-01": trae hasta esa fecha exacta
    [switch]$SoloContratos,
    [switch]$SoloProcesos
)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$bitacora = Join-Path $raiz "bitacora"
if (-not (Test-Path $bitacora)) { New-Item -ItemType Directory -Path $bitacora -Force | Out-Null }
$sello = Get-Date -Format "yyyy-MM-dd-HHmm"
try { Start-Transcript -Path (Join-Path $bitacora "historia-$sello.txt") -Force | Out-Null } catch { }

$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; break
    }
}
if (-not $pyExe) { Write-Host "FALLO: no hay Python 3.11+" -ForegroundColor Red; exit 1 }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"
$env:VIGIA_DSN = "postgresql://vigia:vigia@localhost:5432/vigia"

$datasets = @()
if (-not $SoloProcesos)  { $datasets += "contratos" }
if (-not $SoloContratos) { $datasets += "procesos" }

$inicio = Get-Date
$hoy = (Get-Date).Date

# Con -Desde se cuenta cuantos meses hay que retroceder para cubrir esa fecha,
# redondeando hacia arriba. Es mas honesto que pedirle al usuario que traduzca
# «desde julio» a un numero de meses y se equivoque por uno.
if ($Desde) {
    try { $objetivo = [datetime]::ParseExact($Desde, "yyyy-MM-dd", $null) }
    catch { Write-Host "FALLO: -Desde debe ser AAAA-MM-DD" -ForegroundColor Red; exit 1 }
    if ($objetivo -ge $hoy) { Write-Host "FALLO: -Desde tiene que ser anterior a hoy" -ForegroundColor Red; exit 1 }
    $Meses = 0
    while ($hoy.AddMonths(-$Meses) -gt $objetivo) { $Meses++ }
    Write-Host "  Para cubrir desde $Desde hacen falta $Meses meses." -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "  TRAER HISTORIA - $Meses meses hacia atras" -ForegroundColor White
Write-Host "  Estimado: $([math]::Round($Meses * $datasets.Count * 12 / 60.0, 1)) horas. No cierres la ventana." -ForegroundColor DarkGray
Write-Host ""

$fallos = 0
foreach ($m in 1..$Meses) {
    # Se cuenta desde el dia 1 de cada mes hacia atras. Los tramos se solapan
    # un dia a proposito: un registro justo en la frontera es mejor traerlo dos
    # veces —la capa cruda lo descarta— que dejarlo en el hueco entre dos
    # tramos, donde no lo echaria de menos nadie.
    $fin = $hoy.AddMonths(-($m - 1))
    $ini = $hoy.AddMonths(-$m)
    $desde = $ini.ToString("yyyy-MM-dd")
    $hasta = $fin.ToString("yyyy-MM-dd")

    foreach ($d in $datasets) {
        Write-Host ""
        Write-Host "== Mes $m de $Meses · $d · $desde a $hasta" -ForegroundColor Cyan
        & $pyExe @pyArgs -m vigia --dataset $d --desde $desde --hasta $hasta 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) {
            $fallos++
            Write-Host "   FALLO este tramo. Se sigue con el siguiente: lo que ya entro se queda." -ForegroundColor Yellow
        }
    }
}

# La normalizacion va UNA SOLA VEZ al final, no por tramo: es la parte cara y
# recalcula todo de todos modos, asi que hacerla doce veces seria tirar horas.
Write-Host ""
Write-Host "== Normalizar (una sola vez, sobre todo lo traido)" -ForegroundColor Cyan
& $pyExe @pyArgs -m vigia.normalizado 2>&1 |
    Where-Object { $_ -notmatch "WARNING portafolio" } | Out-Host

$horas = [math]::Round(((Get-Date) - $inicio).TotalHours, 1)
Write-Host ""
Write-Host "  ----------------------------------------------------------" -ForegroundColor DarkGray
if ($fallos -gt 0) {
    Write-Host "  Termino con $fallos tramo(s) fallido(s), en $horas horas." -ForegroundColor Yellow
    Write-Host "  Vuelve a correrlo cuando quieras: lo que ya entro no se duplica." -ForegroundColor Yellow
} else {
    Write-Host "  Historia completa: $Meses meses, en $horas horas." -ForegroundColor Green
}
Write-Host "  Ahora corre EJECUTAR-DIA.bat para redibujar las paginas," -ForegroundColor Gray
Write-Host "  y EJECUTAR-concentracion.bat para volver a medir con el historico." -ForegroundColor Gray
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
