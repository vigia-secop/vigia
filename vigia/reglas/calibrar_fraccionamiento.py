"""Corre la Regla de fraccionamiento en modo calibración y escribe el informe.

    python -m vigia.reglas.calibrar_fraccionamiento \
        --json calibracion-fraccionamiento.json \
        --salida calibracion-fraccionamiento.txt

QUÉ HACE Y QUÉ NO. Corre la Regla sobre los grupos que trajo la consulta y
deja un informe para leer con los ojos. **No publica nada, no manda nada a
ninguna cola y no activa la Regla.** Calibrar es probar; activar es un acto
aparte que hace una persona con este informe delante.

LAS TRES CUENTAS, Y SON TRES Y NO DOS:

1. **Encendió** — el grupo pasa del umbral.
2. **No encendió** — se miró y no pasaba. Es el resultado normal.
3. **NO SE PUDO MIRAR** — la entidad tiene un techo imposible o muy pocas
   mínimas cuantías, así que su tope no significa nada.

La tercera es la que casi siempre falta en este tipo de herramientas, y es la
que decide si el resultado vale. Una entidad con un techo de cuarenta y cuatro
mil millones nunca encenderá — y eso NO quiere decir que no fraccione. Si se
contara junto con las que no encendieron, la Regla estaría afirmando «limpia»
sobre algo que no miró.

Por eso los grupos ciegos se apartan ANTES de llamar a `calibrar`: si entraran,
inflarían el denominador y la tasa saldría más baja de lo que es. Se cuentan
aparte y se declaran arriba del informe, que es donde se leen.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from vigia.reglas import fraccionamiento
from vigia.reglas.calibracion import Recorte, calibrar
from vigia.reglas.modelo import CALIBRACION

CODIGO_USO = 2
CODIGO_FALLO = 1

#: Por qué este recorte y no otro. `Recorte` exige un motivo y no por
#: formalismo: seis meses después, la pregunta que decide si una calibración
#: vale es «¿sobre qué se calibró y por qué ese pedazo?».
MOTIVO = (
    "Todas las mínimas cuantías ingeridas que cruzaron con su proceso, sin "
    "las erratas x10^n. Es el universo entero de la modalidad y no una "
    "muestra: la bandera solo puede hablar de mínimas cuantías, así que el "
    "recorte natural es esa modalidad completa."
)


def separar(grupos, umbrales: Mapping[str, Any]):
    """Parte los grupos en los que se pueden mirar y los que no.

    Se hace ANTES de calibrar y no dentro, a propósito: un grupo que no se
    puede evaluar no es un grupo evaluado, y meterlo en el denominador haría
    que la tasa dijera menos de lo que pasa.
    """
    mirables, ciegos = [], []
    minimo = int(umbrales.get(
        "minimas_de_la_entidad", fraccionamiento.MINIMAS_DE_LA_ENTIDAD_POR_DEFECTO))
    for g in grupos:
        minimas = g.get("minimas_entidad")
        if not fraccionamiento.techo_creible(g, umbrales):
            ciegos.append((g, "techo no creíble"))
        elif minimas is None or int(minimas) < minimo:
            ciegos.append((g, f"menos de {minimo} mínimas cuantías"))
        else:
            mirables.append(g)
    return mirables, ciegos


def _pesos(valor) -> str:
    if valor is None:
        return "—"
    return "$" + f"{float(valor):,.0f}".replace(",", ".")


def informe(datos: Mapping[str, Any], *, momento: datetime) -> str:
    grupos = list(datos.get("grupos") or [])
    recorte_datos = datos.get("recorte") or {}

    regla = fraccionamiento.crear(momento)
    version = regla.versiones[-1]
    regla.mover_a(CALIBRACION)

    mirables, ciegos = separar(grupos, version.umbrales)

    lineas = [
        "CALIBRACION DE LA BANDERA DE FRACCIONAMIENTO",
        "=" * 62,
        f"Regla {regla.codigo} v{version.version} · estado {regla.estado}",
        f"Corrida {momento.isoformat(timespec='seconds')}",
        "",
        "EL RECORTE",
        f"  minimas cuantias medibles : {recorte_datos.get('minimas_medibles')}",
        f"  entidades                 : {recorte_datos.get('entidades')}",
        f"  del {recorte_datos.get('desde')} al {recorte_datos.get('hasta')}",
        f"  grupos de dos o mas       : {len(grupos)}",
        "",
        "LA COBERTURA, QUE VA ANTES QUE EL RESULTADO",
    ]

    if ciegos:
        entidades_ciegas = {g["nit_entidad"] for g, _ in ciegos}
        motivos = Counter(m for _, m in ciegos)
        lineas.append(
            f"  NO SE PUDIERON MIRAR {len(ciegos)} grupos "
            f"de {len(entidades_ciegas)} entidades."
        )
        for motivo, cuantos in motivos.most_common():
            lineas.append(f"    - {cuantos} por {motivo}")
        lineas += [
            "  Eso NO quiere decir que esas entidades esten limpias: quiere",
            "  decir que su tope no significa nada y la bandera no las alcanza.",
        ]
    else:
        lineas.append("  Todos los grupos se pudieron mirar.")

    lineas += ["", "EL RESULTADO"]

    if not mirables:
        lineas += [
            "  No quedo ni un grupo que evaluar. No es que la Regla no",
            "  encontrara nada: es que no se le puso nada delante.",
        ]
        return "\n".join(lineas) + "\n"

    resultado = calibrar(
        mirables,
        regla=regla, version=version,
        recorte=Recorte(nombre="minimas cuantias, universo completo", motivo=MOTIVO),
        evaluador=fraccionamiento.evaluar,
        consultado_en=momento, momento=momento,
        dimension="nombre_entidad",
    )

    lineas.append("  " + resultado.resumen())
    lineas.append(f"  identidades unicas en la muestra: "
                  f"{resultado.identidades_unicas} de {len(resultado.muestra)}")

    if resultado.distribucion:
        lineas += ["", "  DONDE ENCIENDE (top 10 entidades)"]
        top = sorted(resultado.distribucion.items(),
                     key=lambda kv: (-kv[1], kv[0]))[:10]
        for entidad, cuantas in top:
            lineas.append(f"    {cuantas:>3}  {entidad[:52]}")
        # Si enciende casi todo sobre una sola entidad, la tasa global miente.
        mayor = top[0][1] if top else 0
        if resultado.encendidas and mayor / resultado.encendidas > 0.5:
            lineas.append(
                "    OJO: mas de la mitad de las alertas son de UNA entidad. "
                "La tasa global no describe al pais."
            )

    lineas += ["", "  LA MUESTRA PARA LEER CON LOS OJOS "
                   f"({len(resultado.muestra)} de {resultado.encendidas})", ""]
    for i, alerta in enumerate(resultado.muestra, 1):
        v = alerta.expediente.valores_disparadores
        lineas += [
            f"  {i:>2}. {str(v.get('entidad'))[:56]}",
            f"      mes {v.get('mes')} · {v.get('contratos')} contratos · "
            f"{_pesos(v.get('suma'))}",
            f"      techo de la entidad {_pesos(v.get('techo_de_la_entidad'))} "
            f"· x{v.get('veces_el_techo')}",
            f"      contratos: {', '.join(list(v.get('contratos_ids') or [])[:4])}",
            "",
        ]

    lineas += [
        "-" * 62,
        "ESTO NO ES UNA PUBLICACION NI UNA ACUSACION.",
        "Cada contrato de estos grupos cabia en el tope: lo que pasa del tope",
        "es la suma. Compras repetidas, entregas por tramos y urgencias",
        "producen esta misma forma. Y mismo proveedor + misma entidad + mismo",
        "mes no quiere decir el mismo objeto.",
        "",
        f"La Regla sigue en «{regla.estado}». Activarla es un acto aparte, de",
        "una persona, con este informe delante.",
    ]
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vigia.reglas.calibrar_fraccionamiento")
    p.add_argument("--json", default="calibracion-fraccionamiento.json")
    p.add_argument("--salida", default="calibracion-fraccionamiento.txt")
    o = p.parse_args(argv)

    ruta = Path(o.json)
    if not ruta.exists():
        print(f"no existe {ruta}", file=sys.stderr)
        return CODIGO_USO
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"{ruta} no es JSON válido: {error}", file=sys.stderr)
        return CODIGO_USO

    texto = informe(datos, momento=datetime.now(timezone.utc))
    Path(o.salida).write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
