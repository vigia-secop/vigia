#!/usr/bin/env bash
# INSTALAR VIGÍA EN UN SERVIDOR LIMPIO. Ubuntu 24.04 o Debian 12.
#
#     sudo bash servidor/instalar.sh
#
# QUÉ DEJA MONTADO, y nada más que eso:
#   · PostgreSQL 16, escuchando SOLO en localhost
#   · un usuario `vigia` sin shell de login y sin sudo
#   · el proyecto en /opt/vigia con su propio entorno de Python
#   · un temporizador de systemd que corre el ciclo todos los días
#
# QUÉ NO HACE, A PROPÓSITO:
#   · NO abre ningún puerto al mundo. Este servidor no sirve páginas: las
#     construye y las empuja a GitHub Pages, que es quien las sirve. Un puerto
#     abierto es una superficie de ataque a cambio de nada.
#   · NO guarda ninguna credencial dentro de este archivo. Todas viven en
#     /opt/vigia/.env, que lo escribes tú y que nunca entra a git.
#   · NO publica en X. Eso lo hace una persona, siempre.
#
# ES IDEMPOTENTE. Correrlo dos veces no rompe nada ni duplica nada: comprueba
# antes de crear. Si algo falla a la mitad, se arregla y se vuelve a correr.

set -euo pipefail

RAIZ="/opt/vigia"
USUARIO="vigia"
BASE="vigia"

rojo()  { printf '\033[31m%s\033[0m\n' "$*"; }
verde() { printf '\033[32m%s\033[0m\n' "$*"; }
paso()  { printf '\n\033[36m== %s\033[0m\n' "$*"; }

if [[ $EUID -ne 0 ]]; then
  rojo "Esto necesita root. Corre:  sudo bash servidor/instalar.sh"
  exit 1
fi

# ---------------------------------------------------------------- 1. paquetes
paso "1 de 8 · Paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  postgresql postgresql-client python3 python3-venv python3-pip git ca-certificates tzdata
verde "   paquetes instalados"

# La hora del servidor en Bogotá. No es cosmético: el ciclo decide «qué día es»
# y «qué semana falta», y un servidor en UTC saca el resumen del lunes el
# domingo por la noche.
timedatectl set-timezone America/Bogota 2>/dev/null || true
verde "   zona horaria: $(cat /etc/timezone 2>/dev/null || echo desconocida)"

# ------------------------------------------------------------- 2. el usuario
paso "2 de 8 · Usuario del sistema"
if id -u "$USUARIO" >/dev/null 2>&1; then
  verde "   el usuario $USUARIO ya existía"
else
  # Sin shell de login y sin contraseña: si alguien llega a este servidor, no
  # va a ser entrando por esta cuenta.
  useradd --system --create-home --home-dir "$RAIZ" --shell /usr/sbin/nologin "$USUARIO"
  verde "   creado $USUARIO (sin shell, sin sudo)"
fi

# --------------------------------------------------------------- 3. Postgres
paso "3 de 8 · PostgreSQL"
systemctl enable --now postgresql >/dev/null 2>&1 || true

# La contraseña se genera aquí y se guarda en el .env. No la elige nadie, no se
# escribe en este archivo, y no hace falta recordarla: la base no escucha fuera
# de localhost.
CLAVE_ARCHIVO="$RAIZ/.clave-postgres"
if [[ -f "$CLAVE_ARCHIVO" ]]; then
  CLAVE="$(cat "$CLAVE_ARCHIVO")"
else
  CLAVE="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 32)"
  install -o "$USUARIO" -g "$USUARIO" -m 600 /dev/null "$CLAVE_ARCHIVO"
  printf '%s' "$CLAVE" > "$CLAVE_ARCHIVO"
fi

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$BASE'" | grep -q 1; then
  sudo -u postgres psql -qc "ALTER ROLE $BASE WITH PASSWORD '$CLAVE';" >/dev/null
  verde "   el rol $BASE ya existía (contraseña actualizada)"
else
  sudo -u postgres psql -qc "CREATE ROLE $BASE LOGIN PASSWORD '$CLAVE';" >/dev/null
  verde "   rol $BASE creado"
fi
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$BASE'" | grep -q 1; then
  verde "   la base $BASE ya existía"
else
  sudo -u postgres createdb -O "$BASE" "$BASE"
  verde "   base $BASE creada"
fi

# Que escuche solo en localhost. Es el valor por defecto de Debian y Ubuntu;
# se comprueba en vez de suponerlo, porque una imagen de proveedor puede venir
# con otra cosa y eso no se nota hasta que ya es tarde.
CONF="$(sudo -u postgres psql -tAc 'SHOW config_file')"
if grep -Eq "^\s*listen_addresses\s*=\s*'(\*|0\.0\.0\.0)'" "$CONF"; then
  rojo "   ATENCION: PostgreSQL esta escuchando fuera de localhost."
  rojo "   Revisa listen_addresses en $CONF antes de seguir."
  exit 1
fi
verde "   la base solo escucha en localhost"

# --------------------------------------------------------------- 4. el código
paso "4 de 8 · El proyecto"
# El repositorio se clona de la cuenta anónima. Si ya está, se actualiza.
if [[ -d "$RAIZ/.git" ]]; then
  sudo -u "$USUARIO" git -C "$RAIZ" pull --ff-only || rojo "   no pude actualizar; sigo con lo que hay"
  verde "   repositorio actualizado"
elif [[ -n "${VIGIA_REPO:-}" ]]; then
  sudo -u "$USUARIO" git clone --depth 50 "$VIGIA_REPO" "$RAIZ/repo-tmp"
  shopt -s dotglob
  mv "$RAIZ/repo-tmp"/* "$RAIZ"/
  shopt -u dotglob
  rmdir "$RAIZ/repo-tmp"
  chown -R "$USUARIO:$USUARIO" "$RAIZ"
  verde "   repositorio clonado"
else
  rojo "   No hay codigo en $RAIZ y no diste VIGIA_REPO."
  rojo "   Copia el proyecto ahi, o corre:"
  rojo "     sudo VIGIA_REPO=https://github.com/TUCUENTA/vigia.git bash servidor/instalar.sh"
  exit 1
fi

# ------------------------------------------------------------ 5. Python
paso "5 de 8 · Entorno de Python"
if [[ ! -d "$RAIZ/.venv" ]]; then
  sudo -u "$USUARIO" python3 -m venv "$RAIZ/.venv"
fi
sudo -u "$USUARIO" "$RAIZ/.venv/bin/pip" install -q --upgrade pip
sudo -u "$USUARIO" "$RAIZ/.venv/bin/pip" install -q -e "$RAIZ"
verde "   entorno listo en $RAIZ/.venv"

# ------------------------------------------------------------ 6. el .env
paso "6 de 8 · Configuración"
ENV="$RAIZ/.env"
if [[ -f "$ENV" ]]; then
  verde "   $ENV ya existe; NO lo toco"
else
  install -o "$USUARIO" -g "$USUARIO" -m 600 /dev/null "$ENV"
  cat > "$ENV" <<EOF
# Configuracion del servidor de Vigia. NUNCA entra a git.
# Permisos 600 y dueno $USUARIO: ningun otro usuario del sistema lo puede leer.

VIGIA_DSN=postgresql://$BASE:$CLAVE@localhost:5432/$BASE
PGPASSWORD=$CLAVE

# --- Socrata (datos.gov.co) --------------------------------------------
# El token de aplicacion. La Key Secret es equivalente a tu contrasena de
# datos.gov.co: si alguna vez la escribes en otro sitio que no sea este
# archivo, revocala y generala de nuevo.
SOCRATA_TOKEN=
SOCRATA_SECRET=

# --- Telegram -----------------------------------------------------------
# El token que da @BotFather y el id del chat al que te escribe el bot.
TELEGRAM_TOKEN=
TELEGRAM_CHAT=

# --- Sitio --------------------------------------------------------------
# La direccion publica, solo para escribirla en el aviso de Telegram.
VIGIA_SITIO=
EOF
  chown "$USUARIO:$USUARIO" "$ENV"
  chmod 600 "$ENV"
  verde "   escrito $ENV con la base ya configurada"
  rojo  "   FALTA QUE LO EDITES: el token de Socrata y el de Telegram."
fi

# ------------------------------------------------------- 7. migraciones
paso "7 de 8 · Migraciones"
for m in "$RAIZ"/migraciones/*.sql; do
  PGPASSWORD="$CLAVE" psql -h localhost -U "$BASE" -d "$BASE" -q -f "$m" >/dev/null
done
verde "   $(ls -1 "$RAIZ"/migraciones/*.sql | wc -l) migraciones aplicadas"

# ---------------------------------------------------------- 8. systemd
paso "8 de 8 · El temporizador"
install -m 644 "$RAIZ/servidor/vigia.service" /etc/systemd/system/vigia.service
install -m 644 "$RAIZ/servidor/vigia.timer"   /etc/systemd/system/vigia.timer
systemctl daemon-reload
systemctl enable --now vigia.timer
verde "   temporizador activo"

chown -R "$USUARIO:$USUARIO" "$RAIZ"
chmod +x "$RAIZ"/servidor/*.sh

cat <<FIN

$(verde "  Vigía instalado en $RAIZ")

  Lo que falta, y lo tienes que hacer tú:

  1. Edita la configuración y pon los tokens:
       sudo nano $RAIZ/.env

  2. Trae el histórico. Doce meses son unas cinco horas; déjalo corriendo:
       sudo -u $USUARIO $RAIZ/servidor/vigia-historia.sh 12

  3. Corre el ciclo una vez a mano para ver que todo funciona:
       sudo systemctl start vigia.service
       journalctl -u vigia.service -f

  El ciclo corre solo todos los días a las 05:40 (hora de Bogotá).
  Para ver cuándo toca el siguiente:
       systemctl list-timers vigia.timer

FIN
