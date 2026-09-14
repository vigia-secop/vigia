#!/usr/bin/env bash
# TRAER HISTORIA HACIA ATRÁS. Una sola vez, y tarda horas.
#
#     sudo -u vigia /opt/vigia/servidor/vigia-historia.sh 12
#
# POR QUÉ HACE FALTA, Y ES LA RAZÓN DE QUE EXISTA EL SERVIDOR. La medición de
# concentración por proveedor —la 4.3— es la única de este proyecto que
# sobrevivió al fondo: con un mínimo de cinco contratos por entidad, la mediana
# de lo que se lleva el mayor proveedor es 29,3 % y solo el 2,1 % de las
# entidades pasa del 90 %. Minoría medida, no norma.
#
# Lo único que la bloquea es la ventana. Una entidad con seis contratos en dos
# meses, cinco al mismo proveedor, puede ser perfectamente normal vista sobre
# un año. Publicar esa lista con dos meses de datos sería señalar a alguien con
# una foto, que es la misma clase de error que mató a las otras tres banderas.
#
# Y NO HAY QUE ESPERAR UN AÑO PARA TENER UN AÑO. Los datos de SECOP son
# históricos: están ahí, hacia atrás. La concentración se mide sobre contratos
# FIRMADOS, y todos los contratos firmados en 2025 siguen ahí para mirarlos
# hoy. Eso no vale para todo —las visualizaciones de un proceso solo valen si
# las viste el día que estaban— pero para la 4.3 vale entero.
#
# CUÁNTO TARDA. Un mes son unos 24 minutos entre los dos datasets. Doce meses,
# unas cinco horas. Veinticuatro, unas diez. Déjalo corriendo y vete.
#
# SE PUEDE CORTAR Y RETOMAR. Cada tramo es independiente y la capa cruda
# reconoce los repetidos, así que volver a correrlo no duplica nada.

set -uo pipefail

MESES="${1:-12}"
RAIZ="${VIGIA_RAIZ:-/opt/vigia}"
cd "$RAIZ"

if [[ -f "$RAIZ/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$RAIZ/.env"
  set +a
fi

PY="$RAIZ/.venv/bin/python"
export PGOPTIONS="-c client_min_messages=warning"

mkdir -p "$RAIZ/bitacora"
REGISTRO="$RAIZ/bitacora/historia-$(date +%Y-%m-%d-%H%M).txt"

decir() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$REGISTRO"; }

decir "HISTORIA · $MESES meses hacia atrás"
decir "estimado: ~$(( MESES * 24 / 60 )) horas. No hace falta que mires."

FALLOS=0
for (( m=1; m<=MESES; m++ )); do
  # Los tramos se solapan un día a propósito: un registro justo en la frontera
  # es mejor traerlo dos veces —la capa cruda lo descarta— que dejarlo en el
  # hueco entre dos tramos, donde no lo echaría de menos nadie.
  HASTA="$(date -d "-$((m-1)) month" +%Y-%m-%d)"
  DESDE="$(date -d "-$m month" +%Y-%m-%d)"
  for d in contratos procesos; do
    decir "mes $m de $MESES · $d · $DESDE a $HASTA"
    if ! "$PY" -m vigia --dataset "$d" --desde "$DESDE" --hasta "$HASTA" >>"$REGISTRO" 2>&1; then
      FALLOS=$((FALLOS+1))
      decir "  falló este tramo; sigo con el siguiente (lo que ya entró se queda)"
    fi
  done
done

# La normalización va UNA SOLA VEZ al final, no por tramo: es la parte cara y
# recalcula todo de todos modos, así que hacerla doce veces sería tirar horas.
decir "normalizando todo lo traído (una sola vez)"
"$PY" -m vigia.normalizado >>"$REGISTRO" 2>&1

decir "listo · $FALLOS tramo(s) fallido(s) · registro en $REGISTRO"
decir "ahora toca volver a medir la 4.3:"
decir "  psql -h localhost -U vigia -d vigia -f medir-concentracion.sql"
"$PY" -m vigia.telegrama --texto "Vigía · histórico de $MESES meses terminado ($FALLOS tramo(s) fallido(s)). Ya se puede volver a medir la concentración con historia de verdad." >>"$REGISTRO" 2>&1
