# SACAR DEL REPOSITORIO LO QUE YA ESTA IGNORADO. Un solo paso.
#
#     Doble clic en EJECUTAR-LIMPIAR-REPO.bat
#
# EL PROBLEMA QUE RESUELVE. Un archivo que entro a git ANTES de que alguien lo
# pusiera en `.gitignore` sigue versionado para siempre: git ignora lo que no
# conoce, no lo que ya tiene. Asi que se sigue subiendo, y el guardian de
# anonimato de `publicar.ps1` lo sigue revisando.
#
# Paso el 2026-09-24. Las mediciones (`medicion-*.txt`, la salida cruda de un
# EXPLAIN) habian entrado al repositorio el dia anterior. El guardian conto 63
# numeros de 6 a 12 digitos ("shared hit=992294", "rows=274485") y aborto la
# publicacion del sitio, que es exactamente lo que debe hacer cuando no sabe
# si un numero es una cedula. La culpa no era del guardian.
#
# QUE HACE. Busca los archivos que estan en el repositorio y a la vez ignorados
# por `.gitignore`, los saca del repositorio SIN BORRARLOS del disco
# (git rm --cached), y lo sube.
#
# QUE NO HACE. No los borra del historial. Lo que ya se publico en GitHub
# sigue en los commits viejos; esto evita que siga subiendo de aqui en
# adelante. Para borrar el historial hay que reescribirlo, y eso se hace a
# mano y sabiendo lo que se hace.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "limpiar-repo-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

function Correr-Git([string[]]$Argumentos) {
    & git @Argumentos 2>&1 | ForEach-Object {
        $t = "$_"; if ($t.Trim()) { Write-Host "   $t" -ForegroundColor Gray }
    }
    return $LASTEXITCODE
}

Write-Host ""
Write-Host "  LIMPIAR EL REPOSITORIO" -ForegroundColor White
Write-Host "  Saca lo ignorado que quedo versionado. No borra nada del disco." -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path (Join-Path $raiz ".git"))) {
    Write-Host "  Esta carpeta no es un repositorio." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

$sobrantes = @(& git ls-files --cached --ignored --exclude-standard)
$sobrantes = @($sobrantes | Where-Object { $_.Trim() })

if ($sobrantes.Count -eq 0) {
    Write-Host "  No hay nada que sacar: lo ignorado ya esta fuera." -ForegroundColor Green
    Write-Host ""
    try { Stop-Transcript | Out-Null } catch { }
    exit 0
}

Write-Host "  Estos archivos estan en el repositorio y deberian estar fuera:" -ForegroundColor White
foreach ($f in $sobrantes) { Write-Host "     $f" -ForegroundColor Yellow }
Write-Host ""
Write-Host "  Siguen en tu disco. Solo dejan de subirse." -ForegroundColor DarkGray
Write-Host ""

# --cached: lo saca del indice y lo deja en el disco. Sin esa bandera, git rm
# borra el archivo, y estos son los que uno quiere seguir teniendo a la mano.
if ((Correr-Git (@("rm", "--cached", "--quiet", "--") + $sobrantes)) -ne 0) {
    Write-Host "  No pude sacarlos. Mira las lineas de arriba." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Correr-Git @("add", "-A") | Out-Null
$mensaje = "Sacar del repositorio " + $sobrantes.Count + " archivo(s) ignorado(s)"
if ((Correr-Git @("commit", "-m", $mensaje)) -ne 0) {
    Write-Host "  El commit fallo." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Write-Host ""
Write-Host "  Subiendo a GitHub..." -ForegroundColor White
if ((Correr-Git @("push")) -ne 0) {
    Write-Host "  El push fallo. El commit ya quedo en el disco; vuelve a correr" -ForegroundColor Red
    Write-Host "  EJECUTAR-SUBIR-TODO.bat cuando haya internet." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Write-Host ""
Write-Host "  Listo. Ya no se suben mas." -ForegroundColor Green
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
