# ESTA VIGIA AL DIA? Una sola pregunta, una sola respuesta. SOLO LECTURA.
#
#     Doble clic en EJECUTAR-REVISAR-SALUD.bat
#
# PARA QUE. Antes de mandarle el enlace a alguien (o de mostrarlo en una
# reunion) uno quiere saber una cosa: lo que esta publicado en internet, es
# lo que hay en la base? Hasta hoy eso se averiguaba leyendo tres archivos de
# registro distintos, y por eso nadie lo averiguaba.
#
# EL DIA QUE ESTO HIZO FALTA. Del 6 al 15 de octubre de 2026 el sitio publico
# se quedo quieto. El ciclo diario corria bien todas las mananas, la base se
# llenaba, y la publicacion abortaba por una razon correcta que nadie leyo.
# Diez dias. No fallo nada ruidosamente: fallo en silencio, que es peor.
#
# QUE MIRA, EN ORDEN DE GRAVEDAD:
#   1. La base: hasta que fecha hay contratos.
#   2. El disco: de cuando son las paginas de docs\.
#   3. GitHub: hay commits sin subir.
#   4. El ultimo intento de publicacion: termino o aborto.
#
# NO ARREGLA NADA. Dice que pasa y que hay que correr. Un diagnostico que
# ademas actua es un diagnostico en el que uno deja de confiar.

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

function Bien($m)  { Write-Host "   OK   $m" -ForegroundColor Green }
function Ojo($m)   { Write-Host "   OJO  $m" -ForegroundColor Yellow }
function Mal($m)   { Write-Host "   MAL  $m" -ForegroundColor Red }

Write-Host ""
Write-Host "  VIGIA: ESTA AL DIA?" -ForegroundColor White
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor DarkGray
Write-Host ""

$problemas = @()

# ---- 1. La base
$PSQL = Buscar "psql"
$ultimoDato = $null
if (-not $PSQL) {
    Mal "no encontre psql: no puedo mirar la base."
    $problemas += "psql"
} else {
    $env:PGPASSWORD = "vigia"
    $ultimoDato = (& $PSQL -h localhost -U vigia -d vigia -tA -c `
        "SELECT max(fecha_de_firma) FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE" 2>&1).Trim()
    if ($ultimoDato -match '^\d{4}-\d{2}-\d{2}$') {
        $diasDato = (New-TimeSpan -Start ([datetime]$ultimoDato) -End (Get-Date)).Days
        # El SECOP publica con dos a cinco dias de retraso: hasta cinco es la
        # fuente, no nosotros. Mas de siete ya es que la ingesta no corre.
        if ($diasDato -le 5) { Bien "la base llega al $ultimoDato ($diasDato dia(s); el SECOP publica con retraso)." }
        else {
            # ${} OBLIGATORIO ANTES DE UN DOS PUNTOS. PowerShell lee "$x:" como
            # "la variable x del proveedor x:" (igual que $env:RUTA) y el script
            # ni siquiera arranca: muere al interpretarlo, antes de la primera
            # linea. Paso el 2026-10-16.
            Ojo "la base llega al ${ultimoDato}: $diasDato dias. La ingesta no esta corriendo."
            $problemas += "ingesta"
        }
    } else {
        Mal "no pude leer la base ($ultimoDato)."
        $problemas += "base"
    }
}

# ---- 2. El disco
$indice = Join-Path $raiz "docs\index.html"
if (-not (Test-Path $indice)) {
    Mal "no existe docs\index.html: el sitio nunca se ha construido aqui."
    $problemas += "docs"
} else {
    $construido = (Get-Item $indice).LastWriteTime
    $diasDocs = (New-TimeSpan -Start $construido -End (Get-Date)).Days
    if ($diasDocs -le 1) { Bien "las paginas se construyeron el $($construido.ToString('yyyy-MM-dd HH:mm'))." }
    else {
        Ojo "las paginas son del $($construido.ToString('yyyy-MM-dd')): $diasDocs dias sin rehacerse."
        $problemas += "paginas"
    }
}

# ---- 3. GitHub
if (Get-Command git -ErrorAction SilentlyContinue) {
    $sinSubir = (& git log origin/main..HEAD --oneline 2>$null | Measure-Object).Count
    $sucio    = (& git status --porcelain -- docs 2>$null | Measure-Object).Count
    if ($sinSubir -eq 0 -and $sucio -eq 0) { Bien "no hay nada pendiente de subir a GitHub." }
    else {
        if ($sinSubir -gt 0) { Ojo "hay $sinSubir commit(s) hechos y sin subir." }
        if ($sucio -gt 0)    { Ojo "hay $sucio archivo(s) de docs\ cambiados y sin guardar." }
        $problemas += "github"
    }
} else {
    Ojo "no encontre git: no puedo saber si falta subir algo."
}

# ---- 4. El ultimo intento de publicacion
$registro = Join-Path $raiz "publicar-ultima-corrida.txt"
if (Test-Path $registro) {
    $texto = Get-Content $registro -Raw -Encoding UTF8
    $cuando = (Get-Item $registro).LastWriteTime.ToString('yyyy-MM-dd HH:mm')
    if ($texto -match "ABORTADO") {
        Mal "la ultima publicacion ($cuando) ABORTO. Mira publicar-ultima-corrida.txt."
        $problemas += "abortado"
    } elseif ($texto -match "Subido\.") {
        Bien "la ultima publicacion ($cuando) termino y subio."
    } else {
        Ojo "la ultima publicacion ($cuando) no dice que haya subido."
        $problemas += "publicacion"
    }
} else {
    Ojo "no hay registro de publicacion todavia."
}

Write-Host ""
if ($problemas.Count -eq 0) {
    Write-Host "  VIGIA ESTA AL DIA. El enlace muestra lo que hay en la base." -ForegroundColor Green
    Write-Host "  https://vigia-secop.github.io/vigia/" -ForegroundColor Gray
} else {
    Write-Host "  VIGIA NO ESTA AL DIA." -ForegroundColor Yellow
    Write-Host ""
    if ($problemas -contains "ingesta")   { Write-Host "  -> Corre EJECUTAR-CADA-DIA.bat (trae los datos Y publica)." -ForegroundColor White }
    elseif ($problemas -contains "abortado") { Write-Host "  -> La publicacion se freno sola. Lee el final de publicar-ultima-corrida.txt." -ForegroundColor White }
    elseif ($problemas -contains "paginas" -or $problemas -contains "github") {
        Write-Host "  -> Corre EJECUTAR-MES-EN-CURSO.bat (construye y sube el sitio)." -ForegroundColor White
    }
}
Write-Host ""
