# EL DIA DE VIGIA. Un solo clic: EJECUTAR-DIA.bat
#
# Hace el ciclo diario completo, y ademas SE DA CUENTA de si falta el resumen
# de la semana pasada o el del mes pasado, y lo saca.
#
# POR QUE ESTO NO SE PROGRAMA POR CALENDARIO
# ------------------------------------------
# Las tareas programadas asumen que el equipo esta encendido el lunes a las
# 07:30. Si no lo esta, el resumen de esa semana no se saca NUNCA: el disparador
# paso y no vuelve. Aqui la pregunta no es «que dia es hoy» sino
#
#     ¿existe ya el resumen de la ultima semana COMPLETA?
#
# Si no existe, se saca, sea martes o sea jueves. Lo mismo con el mes. El
# resultado es que el ciclo se puede saltar dias sin perder nada, y que correrlo
# dos veces el mismo dia no reescribe ni duplica nada.
#
# Se le puede pasar -Rehacer para forzar los resumenes aunque ya existan.

param([switch]$Rehacer, [switch]$SinAbrir)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$inicio = Get-Date
Write-Host ""
Write-Host "  VIGIA SECOP - el dia" -ForegroundColor White
Write-Host "  $($inicio.ToString('dddd d \d\e MMMM \d\e yyyy, HH:mm'))" -ForegroundColor DarkGray
Write-Host ""

# ---------------------------------------------------------------- el ciclo
# Se invoca como hijo y NO se abre transcripcion aqui: `ciclo-diario.ps1` abre
# la suya. Anidar Start-Transcript en PowerShell 5.1 hace que el Stop-Transcript
# del hijo cierre la del padre, y el registro del dia quedaria cortado a la
# mitad sin que nadie se entere.
& (Join-Path $raiz "ciclo-diario.ps1")
$cicloFallo = ($LASTEXITCODE -ne 0)

# ------------------------------------------------------- que resumen falta
# `DayOfWeek` cuenta el domingo como 0, asi que se corrige para que la semana
# empiece en lunes, que es como se cuenta aqui.
$hoy = (Get-Date).Date
$diasDesdeLunes = ([int]$hoy.DayOfWeek + 6) % 7
$lunesDeEsta = $hoy.AddDays(-$diasDesdeLunes)
$semDesde = $lunesDeEsta.AddDays(-7)
$semHasta = $lunesDeEsta.AddDays(-1)

$primeroDeEste = Get-Date -Year $hoy.Year -Month $hoy.Month -Day 1
$mesHasta = $primeroDeEste.AddDays(-1).Date
$mesDesde = (Get-Date -Year $mesHasta.Year -Month $mesHasta.Month -Day 1).Date

function Resumen($desde, $hasta, $titulo, $mensual) {
    $sello = $desde.ToString("yyyy-MM-dd")
    $archivo = if ($mensual) { "resumen-mensual-$sello.html" } else { "resumen-semanal-$sello.html" }
    $ruta = Join-Path $raiz $archivo
    if ((Test-Path $ruta) -and -not $Rehacer) {
        Write-Host "   $titulo de $sello : ya estaba hecho." -ForegroundColor DarkGray
        return $ruta
    }
    Write-Host ""
    Write-Host "== $titulo : $sello a $($hasta.ToString('yyyy-MM-dd'))" -ForegroundColor Cyan
    # El `| Out-Host` no es cosmetico: sin el, todo lo que el hijo escriba se
    # sumaria al valor de retorno de esta funcion y `$ruta` dejaria de ser una
    # ruta para volverse un arreglo con media pantalla adentro.
    & (Join-Path $raiz "resumen-periodo.ps1") `
        -Desde $sello -Hasta $hasta.ToString("yyyy-MM-dd") `
        -Titulo $titulo -Salida $archivo 2>&1 | Out-Host
    if (Test-Path $ruta) { return $ruta }
    return $null
}

Write-Host ""
Write-Host "== Resumenes" -ForegroundColor Cyan

# Se mira hacia atras y no solo la ultima semana: si el equipo estuvo apagado
# quince dias, la semana del medio tambien falta, y preguntar solo por la mas
# reciente la perderia igual que la perdia el Programador de tareas. Se paran en
# 4 semanas y 2 meses porque mas atras que eso ya no es «me salte unos dias»,
# es un reproceso, y un reproceso se pide a mano y a sabiendas.
$rutaSemanal = $null
foreach ($atras in 0..3) {
    $d = $semDesde.AddDays(-7 * $atras)
    $h = $semHasta.AddDays(-7 * $atras)
    $r = Resumen $d $h "Resumen semanal" $false
    if ($atras -eq 0) { $rutaSemanal = $r }
}

$rutaMensual = $null
foreach ($atras in 0..1) {
    # `mesDesde` siempre es dia 1, asi que AddMonths no tiene el problema de
    # los dias 29-31 cayendo en un mes que no los tiene.
    $d = $mesDesde.AddMonths(-$atras)
    $h = $mesDesde.AddMonths(-$atras + 1).AddDays(-1)
    $r = Resumen $d $h "Resumen mensual" $true
    if ($atras -eq 0) { $rutaMensual = $r }
}

# ------------------------------------------------------------------ boletin
# El boletin se arma solo, pero NO se publica solo y no va a hacerlo. Se deja
# escrito al lado de los resumenes para leerlo antes de soltarlo al mundo: es
# lo unico de este proyecto que, una vez fuera, no se puede retirar.
$rutaBoletin = Join-Path $raiz "boletin-semana-$($semDesde.ToString('yyyy-MM-dd')).txt"
if ((-not (Test-Path $rutaBoletin)) -or $Rehacer) {
    Write-Host ""
    Write-Host "== Boletin de la semana" -ForegroundColor Cyan
    & (Join-Path $raiz "boletin.ps1") `
        -Desde $semDesde.ToString("yyyy-MM-dd") -Hasta $semHasta.ToString("yyyy-MM-dd") 2>&1 | Out-Host
}

# ------------------------------------------------------------------ cierre
$minutos = [math]::Round(((Get-Date) - $inicio).TotalMinutes, 1)
Write-Host ""
Write-Host "  ----------------------------------------------------------" -ForegroundColor DarkGray
if ($cicloFallo) {
    Write-Host "  El dia termino CON FALLOS. Mira bitacora\ciclo-$($hoy.ToString('yyyy-MM-dd')).txt" -ForegroundColor Yellow
    Write-Host "  Las paginas se regeneraron con lo que ya habia en la base." -ForegroundColor Yellow
} else {
    Write-Host "  El dia esta hecho. $minutos minutos." -ForegroundColor Green
}
Write-Host ""
Write-Host "  panel.html      lo que se contrato y cuanto se ve" -ForegroundColor Gray
Write-Host "  revision.html   que mirar primero, y por que" -ForegroundColor Gray
if ($rutaSemanal) { Write-Host "  $(Split-Path -Leaf $rutaSemanal)" -ForegroundColor Gray }
if ($rutaMensual) { Write-Host "  $(Split-Path -Leaf $rutaMensual)" -ForegroundColor Gray }
Write-Host ""

if (-not $SinAbrir) {
    foreach ($p in @("panel.html", "revision.html")) {
        $r = Join-Path $raiz $p
        if (Test-Path $r) { Start-Process $r }
    }
}
