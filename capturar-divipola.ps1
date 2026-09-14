# Captura la tabla DIVIPOLA de municipios y la deja versionada en el repo.
#
#   Doble clic en EJECUTAR-capturar-divipola.bat
#
# POR QUE CAPTURAR Y NO CONSULTAR EN CADA CORRIDA. Misma decision que la tabla
# de esquemas esperados de la 1.3 y la de departamentos de la 1.6: una tabla
# que cambia bajo los pies vuelve incomparable cualquier serie historica. La
# division politico-administrativa cambia -municipios nuevos, nombres que se
# corrigen-. Se captura, se versiona, y cuando cambie se ve en el diff.
#
# NO escribe el archivo si algo no cuadra. Prefiere dejar la tabla anterior
# intacta antes que reemplazarla por una captura a medias.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

# Queda registro para poder diagnosticar sin mirar la pantalla.
try { Start-Transcript -Path (Join-Path $raiz "divipola-ultima-corrida.txt") -Force | Out-Null } catch { }

# PowerShell 5.1 no negocia TLS 1.2 por defecto en algunas maquinas y la
# llamada falla con un error de conexion que no dice por que.
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch { }

$RECURSO = "https://www.datos.gov.co/resource/gdxc-w37w.json"
$DESTINO = Join-Path $raiz "datos\divipola_municipios.csv"
$ESPERADOS = 1122

Write-Host "Capturando DIVIPOLA de municipios desde datos.gov.co" -ForegroundColor White
Write-Host ""

$todos = @()
$offset = 0
$pagina = 1000
while ($true) {
    $url = "$RECURSO`?`$select=cod_mpio,nom_mpio&`$order=cod_mpio&`$limit=$pagina&`$offset=$offset"
    Write-Host "   pagina desde $offset ..." -NoNewline
    try {
        $filas = Invoke-RestMethod -Uri $url -TimeoutSec 120
    } catch {
        Write-Host ""
        Write-Host "   FALLO al consultar la fuente: $_" -ForegroundColor Red
        Write-Host "   No se toco $DESTINO." -ForegroundColor Yellow
        Read-Host "   Enter para cerrar"; exit 1
    }
    $cuantas = @($filas).Count
    Write-Host " $cuantas filas"
    if ($cuantas -eq 0) { break }
    $todos += $filas
    $offset += $pagina
    if ($cuantas -lt $pagina) { break }
}

Write-Host ""
Write-Host "   total: $($todos.Count) municipios" -ForegroundColor Cyan

# --- comprobaciones ANTES de escribir -------------------------------------
$codigos = $todos | ForEach-Object { $_.cod_mpio }
$distintos = ($codigos | Sort-Object -Unique).Count
if ($distintos -ne $todos.Count) {
    Write-Host "   FALLO: $($todos.Count) filas pero $distintos codigos distintos." -ForegroundColor Red
    Read-Host "   Enter para cerrar"; exit 1
}
$malos = $codigos | Where-Object { $_ -notmatch '^\d{5}$' }
if ($malos) {
    Write-Host "   FALLO: hay codigos que no son cinco digitos: $($malos -join ', ')" -ForegroundColor Red
    Read-Host "   Enter para cerrar"; exit 1
}
if ([Math]::Abs($todos.Count - $ESPERADOS) -gt 30) {
    Write-Host "   FALLO: se esperaban ~$ESPERADOS municipios. La captura se trunco o la fuente cambio de forma." -ForegroundColor Red
    Write-Host "   No se toco $DESTINO." -ForegroundColor Yellow
    Read-Host "   Enter para cerrar"; exit 1
}

$nombres = ($todos | ForEach-Object { $_.nom_mpio } | Sort-Object -Unique).Count
$repetidos = $todos.Count - $nombres
Write-Host "   nombres distintos: $nombres" -ForegroundColor Cyan
Write-Host "   nombres compartidos por mas de un municipio: $repetidos" -ForegroundColor Yellow
Write-Host "   (por eso la llave es el par departamento+municipio y no el nombre)" -ForegroundColor DarkGray

# --- escribir --------------------------------------------------------------
$carpeta = Split-Path -Parent $DESTINO
if (-not (Test-Path $carpeta)) { New-Item -ItemType Directory -Path $carpeta -Force | Out-Null }

$lineas = New-Object System.Collections.Generic.List[string]
$lineas.Add("codigo,nombre")
# HAY NOMBRES CON COMA, y uno es Bogota.
#
# La primera version de este script daba por hecho que ningun municipio
# colombiano traia coma en el nombre, y abortaba si encontraba una. Aborto en
# la primera corrida: DIVIPOLA llama al municipio 11001 "BOGOTA, D.C.", con
# coma. La comprobacion hizo su trabajo -paro antes de escribir un CSV roto-
# pero el supuesto era falso. Asi que ahora se cita como manda el CSV en vez
# de suponer que no hace falta.
foreach ($m in ($todos | Sort-Object cod_mpio)) {
    $nombre = $m.nom_mpio
    if ($nombre -match "`r|`n") {
        Write-Host "   FALLO: el nombre '$nombre' trae un salto de linea." -ForegroundColor Red
        Read-Host "   Enter para cerrar"; exit 1
    }
    $citado = '"' + ($nombre -replace '"', '""') + '"'
    $lineas.Add("$($m.cod_mpio),$citado")
}

[IO.File]::WriteAllLines($DESTINO, $lineas, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "   Escrito: $DESTINO" -ForegroundColor Green
Write-Host "   $($todos.Count) municipios. Ahora esta versionado: cuando cambie, se vera en el diff."
Write-Host ""
Read-Host "Enter para cerrar"
