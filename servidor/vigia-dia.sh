#!/usr/bin/env bash
# EL DÍA DE VIGÍA EN EL SERVIDOR. Lo dispara systemd; también se puede correr
# a mano.
#
#     sudo -u vigia /opt/vigia/servidor/vigia-dia.sh
#
# ES EL MISMO CICLO QUE EN EL ESCRITORIO, con una diferencia que lo cambia
# todo: al final hay un semáforo, y **si una puerta se pone en rojo no se
# publica nada**. En el escritorio esa puerta era una persona leyendo. Aquí,
# a las cinco y media de la mañana, no hay nadie leyendo.
#
# LA INGESTA NO LLEVA FECHAS, a propósito. Arranca desde la marca de agua menos
# la ventana de solapamiento. Poner fechas fijas haría que un día sin correr
# dejara un hueco para siempre.
#
# UNA INGESTA FALLIDA NO MATA EL CICLO. Se sigue: lo que ya está en la base
# sigue siendo válido y un panel de ayer es mejor que ningún panel. Pero la
# puerta 1 lo ve y **no se publica** hasta que la ingesta vuelva a funcionar,
# porque publicar cifras de ayer con fecha de hoy sí sería mentir.

set -uo pipefail

RAIZ="${VIGIA_RAIZ:-/opt/vigia}"
cd "$RAIZ"

# El .env trae el DSN, la contraseña de la base y los tokens. `set -a` hace
# que todo lo que se defina ahí quede exportado sin tener que repetir `export`.
if [[ -f "$RAIZ/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$RAIZ/.env"
  set +a
fi

PY="$RAIZ/.venv/bin/python"
PSQL="$(command -v psql)"
export PGOPTIONS="-c client_min_messages=warning"

SELLO="$(date +%Y-%m-%d)"
mkdir -p "$RAIZ/bitacora"
REGISTRO="$RAIZ/bitacora/ciclo-$SELLO.txt"

decir() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$REGISTRO"; }
paso()  { printf '\n%s  == %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$REGISTRO"; }

paso "Ciclo de Vigía · $(date '+%Y-%m-%d %H:%M')"

# --- 0. Migraciones, en cada corrida. Todas son idempotentes, así que
#        reaplicarlas no cuesta nada; y sin esto una columna nueva existiría en
#        el código y no en la base, y las consultas fallarían en silencio.
paso "0 de 7 · Migraciones"
for m in "$RAIZ"/migraciones/*.sql; do
  "$PSQL" -h localhost -U vigia -d vigia -q -f "$m" >>"$REGISTRO" 2>&1
done
decir "migraciones al día"

# --- 1 y 2. Ingesta.
paso "1 de 7 · Contratos"
"$PY" -m vigia --dataset contratos >>"$REGISTRO" 2>&1
CODIGO_CONTRATOS=$?
decir "contratos: código $CODIGO_CONTRATOS"

paso "2 de 7 · Procesos"
"$PY" -m vigia --dataset procesos >>"$REGISTRO" 2>&1
CODIGO_PROCESOS=$?
decir "procesos: código $CODIGO_PROCESOS"

INGESTA_OK=1
DETALLE_INGESTA="los dos datasets entraron sin fallos"
if [[ $CODIGO_CONTRATOS -ne 0 || $CODIGO_PROCESOS -ne 0 ]]; then
  INGESTA_OK=0
  DETALLE_INGESTA="falló una ingesta (contratos=$CODIGO_CONTRATOS procesos=$CODIGO_PROCESOS); lo que hay en la base es de la corrida anterior"
fi

# --- 3. Normalizar. Se hace aunque una ingesta haya fallado.
paso "3 de 7 · Normalizar"
"$PY" -m vigia.normalizado >>"$REGISTRO" 2>&1
decir "normalización terminada"

# --- 4. Las páginas de trabajo, que son de donde salen los conteos que mira
#        el semáforo. La lista de revisión va DESPUÉS del panel: el panel dice
#        sobre qué parte del universo se está calculando.
paso "4 de 7 · Panel y lista de revisión"
"$PSQL" -h localhost -U vigia -d vigia -tA -q -f panel.sql -o panel.json 2>>"$REGISTRO"
"$PY" -m vigia.panel --json panel.json --salida docs/panel.html >>"$REGISTRO" 2>&1
"$PSQL" -h localhost -U vigia -d vigia -tA -q -f revision.sql -o revision.json 2>>"$REGISTRO"
"$PY" -m vigia.revision --json revision.json --salida docs/revision.html >>"$REGISTRO" 2>&1
decir "panel.html y revision.html construidos"

# --- 5. La portada del día.
#
# Se usa el ÚLTIMO DÍA CON CONTRATOS y no «hoy»: SECOP publica con rezago, y
# una portada en blanco a las cinco y media de la mañana no se lee como
# «todavía no hay datos», se lee como «este sitio está roto».
paso "5 de 7 · Portada del día"
ULTIMO="$("$PSQL" -h localhost -U vigia -d vigia -tA -c \
  "SELECT max(fecha_de_firma) FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE" \
  2>>"$REGISTRO" | tr -d '[:space:]')"
if [[ ! "$ULTIMO" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  decir "ALTO: no pude averiguar el último día con contratos"
  "$PY" -m vigia.telegrama --texto "Vigía · me detuve antes de construir la portada: la base no devolvió un último día con contratos. Revisa $REGISTRO." >>"$REGISTRO" 2>&1
  exit 1
fi
decir "último día con contratos: $ULTIMO"
"$PSQL" -h localhost -U vigia -d vigia -tA -q -v dia="'$ULTIMO'" -f portada.sql -o portada.json 2>>"$REGISTRO"
"$PY" -m vigia.portada --json portada.json --salida docs/index.html >>"$REGISTRO" 2>&1
PORTADA=$?

# --- 6. El boletín de la semana, si falta.
#
# La pregunta no es «¿qué día es hoy?» sino «¿ya existe el resumen de la última
# semana completa?». Un disparador que pasa no vuelve; esta pregunta se puede
# hacer cualquier día y da la misma respuesta correcta.
paso "6 de 7 · Boletín semanal"
LUNES_DE_ESTA="$(date -d "last monday" +%Y-%m-%d 2>/dev/null || date +%Y-%m-%d)"
DESDE="$(date -d "$LUNES_DE_ESTA -7 days" +%Y-%m-%d)"
HASTA="$(date -d "$LUNES_DE_ESTA -1 day" +%Y-%m-%d)"
BOLETIN="boletin-$DESDE.json"
HILO="boletin-semana-$DESDE.txt"
if [[ -f "$HILO" ]]; then
  decir "el hilo de la semana del $DESDE ya estaba hecho"
else
  "$PSQL" -h localhost -U vigia -d vigia -tA -q \
    -v desde="'$DESDE'" -v hasta="'$HASTA'" -f boletin.sql -o "$BOLETIN" 2>>"$REGISTRO"
  "$PY" -m vigia.boletin --json "$BOLETIN" --salida "$HILO" >>"$REGISTRO" 2>&1
  "$PY" -m vigia.sitio --json "$BOLETIN" --docs docs --periodo semana >>"$REGISTRO" 2>&1
  decir "boletín y semana.html de la semana del $DESDE"
fi

# --- 7. EL SEMÁFORO. Aquí se decide si algo sale a internet o no.
paso "7 de 7 · Las seis puertas"
POSTS_TMP=""
if [[ -f "$HILO" ]]; then POSTS_TMP="$HILO"; fi

"$PY" -m vigia.puertas \
  --revision revision.json \
  ${BOLETIN:+--boletin "$BOLETIN"} \
  ${POSTS_TMP:+--posts "$POSTS_TMP"} \
  --docs docs \
  --revisadas erratas-revisadas.txt \
  --detalle-ingesta "$DETALLE_INGESTA" \
  $( [[ $INGESTA_OK -eq 1 && $PORTADA -eq 0 ]] && echo --ingesta-ok ) \
  2>&1 | tee -a "$REGISTRO"
VERDE=${PIPESTATUS[0]}

MENSAJE="$("$PY" -m vigia.puertas \
  --revision revision.json \
  ${BOLETIN:+--boletin "$BOLETIN"} \
  ${POSTS_TMP:+--posts "$POSTS_TMP"} \
  --docs docs --revisadas erratas-revisadas.txt \
  --detalle-ingesta "$DETALLE_INGESTA" \
  --telegrama --sitio "${VIGIA_SITIO:-}" \
  $( [[ $INGESTA_OK -eq 1 && $PORTADA -eq 0 ]] && echo --ingesta-ok ) 2>/dev/null)"

if [[ $VERDE -ne 0 ]]; then
  decir "ALTO · no se publica nada"
  "$PY" -m vigia.telegrama --texto "$MENSAJE" >>"$REGISTRO" 2>&1
  exit 1
fi

# --- Publicar. Solo se llega aquí con las seis puertas en verde.
paso "Publicar"
git -C "$RAIZ" add -A docs .gitignore erratas-revisadas.txt >>"$REGISTRO" 2>&1
if git -C "$RAIZ" diff --cached --quiet; then
  decir "no cambió nada en docs/: no hay nada que subir"
else
  git -C "$RAIZ" commit -q -m "Vigía · $ULTIMO" >>"$REGISTRO" 2>&1
  if git -C "$RAIZ" push -q >>"$REGISTRO" 2>&1; then
    decir "publicado · $(git -C "$RAIZ" rev-parse --short HEAD)"
  else
    decir "ALTO · el push falló; el sitio sigue como estaba"
    "$PY" -m vigia.telegrama --texto "Vigía · las seis puertas dieron verde pero el push a GitHub falló. El sitio sigue como estaba. Revisa $REGISTRO." >>"$REGISTRO" 2>&1
    exit 1
  fi
fi

# El hilo va DESPUÉS de publicar y va entero: es lo único que te toca leer.
if [[ -f "$HILO" ]]; then
  "$PY" -m vigia.telegrama --texto "$MENSAJE" >>"$REGISTRO" 2>&1
  "$PY" -m vigia.telegrama --archivo "$HILO" >>"$REGISTRO" 2>&1
else
  "$PY" -m vigia.telegrama --texto "$MENSAJE" >>"$REGISTRO" 2>&1
fi

decir "ciclo completo"
