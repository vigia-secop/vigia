# Captura el esquema del dataset de Procesos del SECOP.
#
#   Clic derecho sobre este archivo -> "Ejecutar con PowerShell"
#
# Es el paso que desbloquea la historia 1.4 (cruzar contratos con procesos).
# Sin este archivo, cualquier ingesta de `procesos` aborta con codigo 2.
#
# Lo que hace: le pregunta a la fuente que campos declara el dataset y los
# escribe en vigia/schema/esperado/procesos.json. NO inventa nada: lo que
# quede ahi es lo que la fuente dijo. Despues hay que MIRARLO -- ese archivo
# es la alarma contra la que se comparan todos los Ciclos futuros, y una
# alarma que nadie revisa es un sello de goma.

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "capturar-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

trap {
    Write-Host ""
    Write-Host "   ERROR NO PREVISTO -- esto es un fallo del script, no tuyo:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    Write-Host "   linea $($_.InvocationInfo.ScriptLineNumber): $($_.InvocationInfo.Line.Trim())" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

function Bien($m)  { Write-Host "   OK  $m" -ForegroundColor Green }
function Aviso($m) { Write-Host "   --  $m" -ForegroundColor Yellow }
function Mal($m) {
    Write-Host ""
    Write-Host "   FALLO: $m" -ForegroundColor Red
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

Write-Host "Capturar el esquema de Procesos" -ForegroundColor White
Write-Host "Carpeta: $raiz"
Write-Host ""

# ---- Python
$pyExe = $null; $pyArgs = @()
foreach ($c in @(
    @{ exe = "py";      args = @("-3") },
    @{ exe = "python";  args = @() },
    @{ exe = "python3"; args = @() }
)) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args
        Bien $v.Trim()
        break
    }
}
if (-not $pyExe) { Mal "No encuentro Python 3.11 o superior." }

# ---- El token del .env, si esta. Sin el, la cuota por IP corta la consulta.
if (Test-Path ".env") {
    Get-Content ".env" | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
        $nombre, $valor = $_ -split '=', 2
        Set-Item -Path ("Env:" + $nombre.Trim()) -Value $valor.Trim()
    }
    if ($env:VIGIA_TOKEN_SOCRATA) {
        Bien "token de Socrata cargado del .env"
    } else {
        Aviso "sin token de Socrata: si sale 503, es la cuota por IP."
    }
} else {
    Aviso "no hay .env; sigo sin token"
}

# ---- Estado previo, para poder decir si es la primera captura
$destino = Join-Path $raiz "vigia\schema\esperado\procesos.json"
$existiaAntes = Test-Path $destino

Write-Host ""
Write-Host "Preguntandole a la fuente que campos declara..." -ForegroundColor Cyan
Write-Host ""

& $pyExe @pyArgs -m vigia.schema --capturar --dataset procesos
$codigo = $LASTEXITCODE

# Un token invalido da 403 y bloquea una consulta que SIN token habria pasado.
# Es absurdo quedarse parado por una credencial opcional, asi que se reintenta
# sin ella. Se dice en voz alta: seguir en silencio con menos cuota de la que
# el usuario cree tener es como se llega a un Ciclo que falla sin explicacion.
if ($codigo -ne 0 -and $env:VIGIA_TOKEN_SOCRATA) {
    Write-Host ""
    Aviso "Fallo con token. El token es OPCIONAL, asi que reintento sin el."
    Aviso "Si esto funciona, tu token esta mal y hay que renovarlo (sin prisa)."
    Write-Host ""
    Remove-Item Env:VIGIA_TOKEN_SOCRATA -ErrorAction SilentlyContinue
    & $pyExe @pyArgs -m vigia.schema --capturar --dataset procesos
    $codigo = $LASTEXITCODE
    if ($codigo -eq 0) {
        Write-Host ""
        Aviso "CONFIRMADO: sin token funciona, con token no. Tu VIGIA_TOKEN_SOCRATA es invalido."
        Aviso "Renuevalo cuando puedas en datos.gov.co > perfil > Developer Settings."
    }
}

if ($codigo -ne 0) {
    Mal "La captura fallo (codigo $codigo). Si dice 503 o 429, es la cuota de la API: espera unos minutos y reintenta."
}

Write-Host ""
if (-not (Test-Path $destino)) { Mal "El comando dijo que si, pero el archivo no aparecio en $destino" }

$campos = (Get-Content $destino -Raw | ConvertFrom-Json).campos
Bien ("procesos.json escrito con " + $campos.Count + " campos")

Write-Host ""
Write-Host "Los campos capturados:" -ForegroundColor Cyan
$campos | ForEach-Object { Write-Host "   $_" -ForegroundColor DarkGray }

Write-Host ""
if (-not $existiaAntes) {
    Write-Host "Era la primera captura de este dataset." -ForegroundColor Yellow
}
Write-Host "MIRA esa lista antes de confiar en ella." -ForegroundColor Yellow
Write-Host "Ese archivo es la alarma contra la que se comparan todos los Ciclos" -ForegroundColor Yellow
Write-Host "futuros. Si un campo desaparece de la fuente, el Ciclo se detiene y lo" -ForegroundColor Yellow
Write-Host "nombra. Una alarma calibrada contra algo que nadie reviso no sirve." -ForegroundColor Yellow
Write-Host ""
Write-Host "Con esto queda desbloqueada la historia 1.4." -ForegroundColor White
Write-Host ""
Write-Host "Todo lo anterior quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
