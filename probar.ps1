# Probar Vigia SECOP de punta a punta, en Windows.
#
#   Clic derecho sobre este archivo -> "Ejecutar con PowerShell"
#   o, desde una terminal en esta carpeta:
#       powershell -ExecutionPolicy Bypass -File .\probar.ps1
#
# Cada paso dice si paso o fallo, y por que. Si algo falla, el script se
# detiene ahi: copia el mensaje y pidelo revisar.
#
# La base de datos se busca en dos sitios, en este orden:
#   1. PostgreSQL instalado en Windows (el camino normal)
#   2. Docker, si esta corriendo (opcional; exige virtualizacion por hardware)
# Sin ninguno de los dos el script sigue igual y salta lo que necesita base.

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

# Todo lo que salga por pantalla queda tambien en un archivo. Sin esto, un error
# que cierre la ventana no deja absolutamente nada que leer: el diagnostico se
# pierde justo cuando hace falta. Paso el 2026-09-03, dos veces.
$REGISTRO = Join-Path $raiz "probar-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

# Red de seguridad. Cualquier error no previsto -en PowerShell, un comando
# nativo que escribe en stderr basta en algunas versiones- termina el script de
# golpe, y con "Ejecutar con PowerShell" eso cierra la ventana al instante y sin
# mensaje. Este trap lo intercepta, lo muestra, dice en que linea fue y espera.
trap {
    Write-Host ""
    Write-Host "   ERROR NO PREVISTO -- esto es un fallo del script, no tuyo:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    Write-Host "   linea $($_.InvocationInfo.ScriptLineNumber): $($_.InvocationInfo.Line.Trim())" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    Write-Host "   Manda ese archivo y se arregla." -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

$DSN_VIGIA   = "postgresql://vigia:vigia@localhost:5432/vigia"
$DSN_PRUEBAS = "postgresql://vigia:vigia@localhost:5432/vigia_pruebas"

function Paso($numero, $titulo) {
    Write-Host ""
    Write-Host "== PASO $numero : $titulo" -ForegroundColor Cyan
}
function Bien($mensaje) { Write-Host "   OK  $mensaje" -ForegroundColor Green }
function Aviso($mensaje) { Write-Host "   --  $mensaje" -ForegroundColor Yellow }
function Saltado($mensaje) { Write-Host "   --  SALTADO: $mensaje" -ForegroundColor DarkGray }
function Mal($mensaje) {
    Write-Host ""
    Write-Host "   FALLO: $mensaje" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Copia el mensaje de arriba y pidelo revisar." -ForegroundColor Yellow
    Write-Host "   Tambien quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

# Un comando NATIVO que escribe en stderr termina el script cuando
# ErrorActionPreference vale Stop, aunque se redirija su salida. Pasado el
# 2026-09-03: la comprobacion «¿ya existe el rol vigia?» -cuyo fallo es normal
# y esperado la primera vez- tumbaba la corrida entera en el PASO 3.
#
# Estos dos envoltorios convierten cualquier fallo en un CODIGO DE SALIDA, que
# es lo unico que le interesa a quien llama. `Callado` descarta la salida (para
# sondeos); `Visible` la muestra (para migraciones, donde el error de SQL es
# justo lo que hay que leer). `Out-Host` imprime sin devolver nada, para que el
# valor de retorno de la funcion sea el codigo y no el codigo mas la salida.
function Callado {
    param([string]$exe, [string[]]$argumentos = @())
    try {
        & $exe @argumentos *> $null
        if ($null -eq $LASTEXITCODE) { return 0 }
        return $LASTEXITCODE
    } catch { return 1 }
}
function Visible {
    param([string]$exe, [string[]]$argumentos = @())
    try {
        & $exe @argumentos | Out-Host
        if ($null -eq $LASTEXITCODE) { return 0 }
        return $LASTEXITCODE
    } catch {
        Write-Host "   $_" -ForegroundColor Red
        return 1
    }
}

Write-Host "Vigia SECOP - prueba de punta a punta" -ForegroundColor White
Write-Host "Carpeta: $raiz"

# ---------------------------------------------------------------- PASO 1
Paso 1 "Herramientas instaladas"

$pyExe = $null
$pyArgs = @()
$candidatos = @(
    @{ exe = "py";      args = @("-3") },
    @{ exe = "python";  args = @() },
    @{ exe = "python3"; args = @() }
)
foreach ($c in $candidatos) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $version = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($version -match "Python (\d+)\.(\d+)") {
        if ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
            $pyExe = $c.exe
            $pyArgs = $c.args
            Bien ($version.Trim() + "  (" + $c.exe + " " + ($c.args -join " ") + ")")
            break
        }
    }
}
if (-not $pyExe) {
    Mal "No encuentro Python 3.11 o superior. Instalalo desde python.org (marcando 'Add to PATH') y vuelve a correr esto."
}

# La base de datos es OPCIONAL. Sin ella corren todas las pruebas menos las de
# integracion, que quedan saltadas, y se hace igual la consulta real al SECOP.
#
# AQUI NO VA NINGUN NUMERO DE PRUEBAS. Decia "187 de 219" desde julio y el
# 2026-09-22 ya eran 667 y 59 saltadas: un numero escrito a mano en un mensaje
# envejece sin que nada falle, y lo que se lee en pantalla deja de ser cierto.
# pytest ya imprime el conteo justo encima.
#
# Se prefiere PostgreSQL nativo sobre Docker a proposito: Docker Desktop en
# Windows exige virtualizacion por hardware (VT-x / SVM) habilitada en la BIOS,
# y este proyecto no tiene por que exigirte eso para correr sus pruebas.
$modoBase = "ninguno"

# El instalador de EnterpriseDB NO agrega su carpeta `bin` al PATH. Buscar solo
# con Get-Command da "no hay base de datos" en una maquina donde PostgreSQL
# esta perfectamente instalado y corriendo: pasado el 2026-09-03. Asi que se
# busca tambien donde el instalador lo deja siempre.
function Buscar-Herramienta($nombre) {
    $enPath = Get-Command $nombre -ErrorAction SilentlyContinue
    if ($enPath) { return $enPath.Source }
    foreach ($raizPg in @("C:\Program Files\PostgreSQL", "C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $raizPg)) { continue }
        # Descendente por version MAYOR: si hay varias instaladas, gana la mas
        # nueva. Se ordena por el numero inicial y no por el nombre completo,
        # porque "9.6" ordenado como texto queda despues de "17".
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
$PGISREADY = Buscar-Herramienta "pg_isready"

if ($PSQL -and $PGISREADY) {
    # pg_isready no pide contrasena: sirve para saber si hay motor escuchando
    # sin tener que autenticarse todavia.
    if ((Callado $PGISREADY @("-h","localhost","-p","5432")) -eq 0) {
        $modoBase = "nativo"
        Bien "PostgreSQL nativo escuchando en localhost:5432"
        Write-Host "       ($PSQL)" -ForegroundColor DarkGray
    } else {
        Aviso "psql esta instalado pero no hay motor escuchando en localhost:5432."
        Aviso "Abre 'Servicios' de Windows y arranca el servicio postgresql-x64-NN."
    }
} elseif ($PSQL -or $PGISREADY) {
    Aviso "Encontre parte de PostgreSQL pero no las dos herramientas que necesito."
    Aviso "Reinstala marcando 'Command Line Tools'."
}

if ($modoBase -eq "ninguno" -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    # try/catch propio: `docker info` con el motor muerto escribe en stderr y
    # sale con codigo != 0, y eso no puede tumbar la comprobacion entera.
    if ((Callado "docker" @("info")) -eq 0) {
        $modoBase = "docker"
        Bien "Docker responde"
    } else {
        Aviso "Docker esta instalado pero su motor no arranca. Sigo sin el."
        Aviso "Si dice 'Virtualization support not detected', le falta VT-x/SVM en la BIOS."
        Aviso "No pelees con eso: PostgreSQL nativo no lo necesita."
    }
}

if ($modoBase -eq "ninguno") {
    Aviso "Sin base de datos. Sigo igual y salto lo que la necesita."
    Aviso "Se salta lo que necesita base; el resto de las pruebas corre igual."
    Aviso "Para cerrar el circulo: instala PostgreSQL desde postgresql.org/download/windows"
}

$hayBase = ($modoBase -ne "ninguno")

# Ejecutar SQL da igual por donde venga la base: estas dos funciones son la
# unica parte del script que sabe la diferencia. Las dos DEVUELVEN el codigo de
# salida; quien llama lo compara, en vez de mirar $LASTEXITCODE.
function SqlTexto($base, $sentencia) {
    if ($modoBase -eq "nativo") {
        return (Visible $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d",$base,"-q","-v","ON_ERROR_STOP=1","-c",$sentencia))
    }
    return (Visible "docker" @("compose","exec","-T","-e","PGOPTIONS=-c client_min_messages=warning","postgres","psql","-U","vigia","-d",$base,"-q","-v","ON_ERROR_STOP=1","-c",$sentencia))
}
function SqlArchivo($base, $nombreMigracion) {
    if ($modoBase -eq "nativo") {
        return (Visible $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d",$base,"-q","-v","ON_ERROR_STOP=1","-f",(Join-Path $raiz "migraciones\$nombreMigracion")))
    }
    return (Visible "docker" @("compose","exec","-T","-e","PGOPTIONS=-c client_min_messages=warning","postgres","psql","-U","vigia","-d",$base,"-q","-v","ON_ERROR_STOP=1","-f","/docker-entrypoint-initdb.d/$nombreMigracion"))
}

# ---------------------------------------------------------------- PASO 2
Paso 2 "Configuracion (.env)"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Bien "Cree .env a partir de .env.example"
} else {
    Bien ".env ya existia, no lo toco"
}

# Cargarlo, no solo crearlo. Hasta el 2026-09-03 este script comprobaba que
# el .env existiera y nunca lo leia: el token de Socrata estaba puesto y no
# se usaba, y una corrida limpia se atribuyo al token cuando en realidad fue
# la fuente recuperandose sola. Un archivo de configuracion que el programa
# no lee es peor que no tenerlo, porque parece que si.
Get-Content ".env" | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
    $nombreVar, $valorVar = $_ -split '=', 2
    Set-Item -Path ("Env:" + $nombreVar.Trim()) -Value $valorVar.Trim()
}
if ($env:VIGIA_TOKEN_SOCRATA) {
    Bien "token de Socrata cargado ($($env:VIGIA_TOKEN_SOCRATA.Length) caracteres)"
    Aviso "cargado no es lo mismo que valido: si la fuente lo rechaza, el paso 8 lo desactiva solo."
} else {
    Aviso "sin token de Socrata: la cuota es por IP y se agota a mitad de un Ciclo."
}

# ---------------------------------------------------------------- PASO 3
Paso 3 "Preparar PostgreSQL"
if (-not $hayBase) {
    Saltado "no hay motor de base de datos"
} elseif ($modoBase -eq "docker") {
    if ((Visible "docker" @("compose","up","-d","postgres")) -ne 0) { Mal "docker compose no pudo levantar Postgres (mira el mensaje de arriba)." }

    Write-Host "   esperando a que la base acepte conexiones..."
    $listo = $false
    foreach ($intento in 1..60) {
        if ((Callado "docker" @("compose","exec","-T","postgres","pg_isready","-U","vigia","-d","vigia")) -eq 0) { $listo = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $listo) { Mal "Postgres no acepto conexiones en 2 minutos. Revisa: docker compose logs postgres" }
    Bien "PostgreSQL arriba"
} else {
    # En una instalacion nativa no existe el rol `vigia` ni sus bases: hay que
    # crearlos una sola vez, y eso pide el superusuario `postgres`.
    #
    # Todo psql lleva -w: sin eso, un psql que no encuentra contrasena se queda
    # esperando que alguien la teclee y el script se cuelga sin decir nada.
    #
    # PGPASSWORD queda en `vigia` de aqui en adelante, que es la clave del rol de
    # la aplicacion y la misma que va en el DSN. Solo durante la creacion se
    # cambia por la del superusuario, y se devuelve enseguida.
    $env:PGPASSWORD = "vigia"
    # Silencia los NOTICE de psql. Reaplicar una migracion imprime «already
    # exists» en rojo: no es un error -las migraciones son IF NOT EXISTS a
    # proposito- pero lo parece, y un aviso que parece fallo entrena a la gente
    # a ignorar los fallos de verdad.
    $env:PGOPTIONS = "-c client_min_messages=warning"
    if ((Callado $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d","vigia","-q","-c","SELECT 1")) -eq 0) {
        Bien "el rol vigia y la base vigia ya existian"
    } else {
        Write-Host ""
        Write-Host "   Primera vez: hay que crear el rol 'vigia' y sus dos bases." -ForegroundColor Yellow
        Write-Host "   Escribe la contrasena del superusuario 'postgres', la que pusiste al instalar." -ForegroundColor Yellow
        $segura = Read-Host "   Contrasena de postgres" -AsSecureString
        $env:PGPASSWORD = [System.Net.NetworkCredential]::new("", $segura).Password

        if ((Callado $PSQL @("-w","-h","localhost","-p","5432","-U","postgres","-d","postgres","-q","-c","SELECT 1")) -ne 0) {
            $env:PGPASSWORD = "vigia"
            Mal "No pude entrar como 'postgres'. Contrasena incorrecta, o el motor no acepta conexiones por contrasena."
        }

        # CREATE ROLE/DATABASE no tienen IF NOT EXISTS, asi que se toleran los
        # errores de 'ya existe': el estado final es el mismo.
        foreach ($sentencia in @(
            "CREATE ROLE vigia LOGIN PASSWORD 'vigia';",
            "CREATE DATABASE vigia OWNER vigia;",
            "CREATE DATABASE vigia_pruebas OWNER vigia;"
        )) {
            Callado $PSQL @("-w","-h","localhost","-p","5432","-U","postgres","-d","postgres","-q","-c",$sentencia) | Out-Null
        }

        # Se vuelve al rol de la aplicacion para comprobar que de verdad entra.
        # Crear el rol y que luego no pueda conectarse es un fallo silencioso
        # clasico: lo delata pg_hba.conf, no el CREATE ROLE.
        $env:PGPASSWORD = "vigia"
        if ((Callado $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d","vigia","-q","-c","SELECT 1")) -ne 0) { Mal "Cree el rol y las bases pero 'vigia' todavia no puede entrar. Revisa pg_hba.conf." }
        Bien "rol vigia y bases vigia / vigia_pruebas creados"
    }
}

# ---------------------------------------------------------------- PASO 4
Paso 4 "Aplicar migraciones"
if (-not $hayBase) {
    Saltado "sin base de datos no hay nada que migrar"
} else {
    # Aplicarlas siempre es seguro: todas usan CREATE TABLE IF NOT EXISTS.
    # Docker solo las corre al CREAR el volumen, asi que no basta con confiar en el.
    $migraciones = Get-ChildItem (Join-Path $raiz "migraciones") -Filter "*.sql" | Sort-Object Name
    if ($migraciones.Count -eq 0) { Mal "No encontre migraciones en la carpeta migraciones\." }

    foreach ($m in $migraciones) {
        if ((SqlArchivo "vigia" $m.Name) -ne 0) { Mal ("La migracion " + $m.Name + " fallo.") }
        Bien $m.Name
    }

    Write-Host "   preparando la base de pruebas (las pruebas de integracion BORRAN filas)..."
    if ($modoBase -eq "docker") {
        Callado "docker" @("compose","exec","-T","postgres","psql","-U","vigia","-d","postgres","-q","-c","CREATE DATABASE vigia_pruebas OWNER vigia;") | Out-Null
    }
    foreach ($m in $migraciones) {
        if ((SqlArchivo "vigia_pruebas" $m.Name) -ne 0) { Mal ("La migracion " + $m.Name + " fallo en la base de pruebas.") }
    }
    Bien "base vigia_pruebas lista"
}

# ---------------------------------------------------------------- PASO 5
Paso 5 "Instalar el paquete"
& $pyExe @pyArgs -m pip install --quiet --upgrade pip
& $pyExe @pyArgs -m pip install --quiet -e ".[dev]"
if ($LASTEXITCODE -ne 0) { Mal "pip no pudo instalar las dependencias." }
Bien "vigia instalado con sus dependencias"

# ---------------------------------------------------------------- PASO 6
Paso 6 "Pruebas sin base de datos"
Remove-Item Env:VIGIA_DSN_PRUEBAS -ErrorAction SilentlyContinue
& $pyExe @pyArgs -m pytest -q
if ($LASTEXITCODE -ne 0) { Mal "La suite de pruebas fallo." }
Bien "la suite paso (el conteo va en la linea de pytest, aqui arriba)"

# ---------------------------------------------------------------- PASO 7
Paso 7 "Pruebas contra PostgreSQL real"
if (-not $hayBase) {
    Saltado "las 31 pruebas de integracion necesitan una base"
} else {
    $env:VIGIA_DSN_PRUEBAS = $DSN_PRUEBAS
    & $pyExe @pyArgs -m pytest -q -m postgres
    if ($LASTEXITCODE -ne 0) { Mal "Las pruebas de integracion fallaron." }
    Bien "idempotencia y durabilidad verificadas contra el motor real"
}

# ---------------------------------------------------------------- PASO 8
Paso 8 "Consulta real al SECOP (sin escribir nada)"
$hasta = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
$desde = (Get-Date).AddDays(-8).ToString("yyyy-MM-dd")
Write-Host "   rango: $desde a $hasta"
& $pyExe @pyArgs -m vigia --dataset contratos --desde $desde --hasta $hasta --dry-run

# El token de Socrata es OPCIONAL: sin el la API funciona igual, solo que con
# cuota compartida por IP. Un token vencido o mal copiado devuelve 403 y tumba
# la corrida entera -- una credencial opcional que rompe mas de lo que ayuda.
# Asi que si falla CON token, se reintenta UNA vez SIN token y se dice cual de
# las dos cosas era. Paso el 2026-09-03: "403 Invalid app_token specified".
if ($LASTEXITCODE -ne 0 -and $env:VIGIA_TOKEN_SOCRATA) {
    Write-Host ""
    Write-Host "   Fallo CON token. Reintento sin el, para saber si el token es el problema." -ForegroundColor Yellow
    $tokenGuardado = $env:VIGIA_TOKEN_SOCRATA
    Remove-Item Env:VIGIA_TOKEN_SOCRATA -ErrorAction SilentlyContinue
    & $pyExe @pyArgs -m vigia --dataset contratos --desde $desde --hasta $hasta --dry-run
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "   CONFIRMADO: sin token funciona, con token no. Tu token esta vencido o mal copiado." -ForegroundColor Yellow
        Write-Host "   Sigo el resto de la corrida SIN token; no hace falta para nada de esto." -ForegroundColor Yellow
        Write-Host "   Para arreglarlo cuando quieras: datos.gov.co -> tu perfil -> Developer Settings," -ForegroundColor Yellow
        Write-Host "   generas uno nuevo, lo pegas en .env en VIGIA_TOKEN_SOCRATA y le quitas el '#'." -ForegroundColor Yellow
    } else {
        # No era el token: devuelvo el entorno como estaba para no mentir sobre
        # el estado en el que corrio el resto.
        $env:VIGIA_TOKEN_SOCRATA = $tokenGuardado
    }
}
if ($LASTEXITCODE -ne 0) {
    Mal "La consulta al SECOP fallo. Si dice 503 o 429, es la cuota de la API: espera unos minutos y reintenta."
}
Bien "la API del SECOP responde y el Ciclo la recorre"
Aviso "Si dice vistos=0, es correcto: el SECOP publica con dias de retraso."

# ---------------------------------------------------------------- PASO 9
Paso 9 "Ingesta de verdad"
if (-not $hayBase) {
    Saltado "sin base de datos no hay donde guardar"
} else {
    Write-Host ""
    Write-Host "   Todo lo anterior paso. Lo siguiente SI escribe en tu base de datos." -ForegroundColor Yellow
    $respuesta = Read-Host "   Escribe SI para ingerir de verdad (cualquier otra cosa lo salta)"
    if ($respuesta -ne "SI") {
        Write-Host ""
        Write-Host "   Saltado. Cuando quieras:" -ForegroundColor Yellow
        Write-Host "      python -m vigia --dataset contratos --desde $desde --hasta $hasta"
    } else {
        $env:VIGIA_DSN = $DSN_VIGIA
        & $pyExe @pyArgs -m vigia --dataset contratos --desde $desde --hasta $hasta
        if ($LASTEXITCODE -ne 0) { Mal "La ingesta fallo." }
        Bien "datos del SECOP en tu base"

        Write-Host ""
        Write-Host "   Lo que quedo guardado:" -ForegroundColor Cyan
        SqlTexto "vigia" "SELECT dataset, count(*) AS filas_crudas FROM crudo_registro GROUP BY dataset;" | Out-Null
        SqlTexto "vigia" "SELECT dataset, fecha_hecho AS marca, actualizada_en FROM ingesta_marca;" | Out-Null
        SqlTexto "vigia" "SELECT estado, desde, hasta, vistos, insertados, duplicados, en_borde_de_ventana FROM ciclo ORDER BY id DESC LIMIT 5;" | Out-Null

        Write-Host ""
        Write-Host "   Prueba la idempotencia: corre exactamente lo mismo otra vez." -ForegroundColor Cyan
        Write-Host "   Deberia decir insertados=0 y contarlo todo como duplicados." -ForegroundColor Cyan
    }
}

# ---------------------------------------------------------------- PASO 10
Paso 10 "Normalizar y cruzar Contratos con Procesos"
if (-not $hayBase) {
    Saltado "sin base de datos no hay crudo que normalizar"
} else {
    # No sale a la red: lee lo ya ingerido. Se puede correr las veces que sea,
    # porque cada fila se reescribe entera desde el crudo que la origino.
    & $pyExe @pyArgs -m vigia.normalizado --dsn $DSN_VIGIA
    if ($LASTEXITCODE -ne 0) { Mal "La normalizacion fallo." }
    Bien "capa normalizada al dia"
    Aviso "Si casi todo sale huerfano, falta ingerir 'procesos'. Es lo esperado hasta hacerlo."
}

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue

Write-Host ""
if ($hayBase) {
    Write-Host "== TODO PASO ==" -ForegroundColor Green
    Write-Host "   (base de datos: $modoBase)"
} else {
    Write-Host "== LO QUE SE PUDO PROBAR, PASO ==" -ForegroundColor Green
    Write-Host ""
    Write-Host "Quedo SIN verificar, por falta de base de datos:" -ForegroundColor Yellow
    Write-Host "  - las 31 pruebas contra PostgreSQL real (idempotencia, durabilidad y cruce)"
    Write-Host "  - la ingesta de verdad"
    Write-Host ""
    Write-Host "Instala PostgreSQL para Windows y vuelve a correr esto:" -ForegroundColor Yellow
    Write-Host "   https://www.postgresql.org/download/windows/"
}
Write-Host ""
Write-Host "De aqui en adelante el Ciclo se acuerda solo de donde iba:" -ForegroundColor White
Write-Host "   python -m vigia --dataset contratos"
Write-Host ""
Write-Host "Antes de seguir construyendo, guarda esto en git:" -ForegroundColor White
Write-Host "   git init"
Write-Host "   git add ."
Write-Host '   git commit -m "Epica 1: historias 1.1, 1.2 y 1.3"'
Write-Host ""
Write-Host "Todo lo anterior quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
