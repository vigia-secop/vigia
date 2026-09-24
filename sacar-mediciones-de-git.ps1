# SACAR LAS MEDICIONES DEL REPOSITORIO. Una sola vez, y queda arreglado.
#
#     Doble clic en EJECUTAR-SACAR-MEDICIONES-DE-GIT.bat
#
# QUE PASO. El 2026-09-22, al subir todo el codigo de golpe, entraron tambien
# las salidas de las mediciones del escritorio: `medicion-*.txt`,
# `calibracion-*.txt`, `erratas-que-cambiaron.txt`. No tenian por que estar en
# el repositorio -son la foto de una corrida en esta maquina- y al dia
# siguiente hicieron abortar la publicacion: el guardian de anonimato mira
# TODO lo que git rastrea y encontro 63 numeros de seis cifras con forma de
# cedula. Ninguno lo era; eran conteos de un plan de PostgreSQL
# ("Buffers: shared hit=992294") y numeros de filas.
#
# QUE HACE ESTE ARCHIVO. Les dice a git que deje de rastrear esos archivos.
# NO los borra del disco: siguen ahi para mirarlos. A partir de aqui el
# `.gitignore` los mantiene fuera.
#
# POR QUE NO ANOTARLOS EN `numeros-revisados.txt`. Porque serian 63 hoy y
# otros tantos manana: cada medicion nueva trae numeros nuevos. Anotarlos
# uno por uno es ensenarse a apagar la alarma en vez de quitar la causa. La
# causa es que esos archivos no son del repositorio.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "sacar-mediciones-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

function Correr-Git([string[]]$Argumentos) {
    & git @Argumentos 2>&1 | ForEach-Object {
        $t = "$_"; if ($t.Trim()) { Write-Host "   $t" -ForegroundColor Gray }
    }
    return $LASTEXITCODE
}

Write-Host ""
Write-Host "  SACAR LAS MEDICIONES DEL REPOSITORIO" -ForegroundColor White
Write-Host "  No se borra nada del disco." -ForegroundColor DarkGray
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  No encontre git." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

# `--cached` es la palabra importante: saca el archivo del indice de git y lo
# deja en la carpeta. Sin ella, `git rm` lo borraria de verdad.
# `--ignore-unmatch` evita que falle por un patron que no encuentra nada.
$patrones = @(
    "medicion-*.txt",
    "calibracion-*.txt",
    "erratas-que-cambiaron.txt",
    "por-que-17.txt",
    "que-cambio-hoy.txt",
    "verificar-formato.txt",
    "verificar-cifras.txt"
)

foreach ($p in $patrones) {
    Correr-Git @("rm", "--cached", "--ignore-unmatch", "-q", "--", $p) | Out-Null
}

Correr-Git @("add", "-A", "--", ".gitignore") | Out-Null

Write-Host "  Lo que queda preparado:" -ForegroundColor White
Correr-Git @("status", "--short") | Out-Null

& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  No habia nada que sacar: el repositorio ya estaba limpio." -ForegroundColor Green
    try { Stop-Transcript | Out-Null } catch { }
    exit 0
}

if ((Correr-Git @("commit", "-m", "Las mediciones del escritorio salen del repositorio")) -ne 0) {
    Write-Host "  El commit fallo. Mira las lineas de arriba." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Write-Host ""
Write-Host "  Subiendo a GitHub..." -ForegroundColor White
if ((Correr-Git @("push")) -ne 0) {
    Write-Host "  El push fallo, pero el commit ya esta guardado en el disco." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Write-Host ""
Write-Host "  Listo. Ahora si se puede publicar: EJECUTAR-MES-EN-CURSO.bat" -ForegroundColor Green
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
