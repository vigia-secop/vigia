"""El boletín: el hilo que se publica, y nada más que eso.

    python -m vigia.boletin --json boletin.json --salida boletin.txt

QUÉ PUBLICA VIGÍA, Y QUÉ NO. Publica **cómo se comportó la contratación
pública colombiana** en un período: cuánto, cuántos, dónde, bajo qué
modalidad, y —sobre todo— **qué parte de eso no se puede ver**. No publica
banderas, no publica nombres, no dice que nada esté mal.

Eso no es una versión descafeinada de la idea: es la idea. Hoy nadie publica
en Colombia, semana tras semana y con la cobertura declarada al lado, cuánto
contrató el Estado y qué fracción de esa plata queda fuera del alcance de
cualquier medición. Ese hueco es el producto.

POR QUÉ NO LLEVA NOMBRES. Un boletín se publica y no se puede despublicar. Las
Reglas que señalarían a alguien no están calibradas —tres murieron medidas— y
señalar sin Regla calibrada es exactamente la máquina de difamar que este
proyecto existe para no ser. Cuando haya una Regla que aguante, se discutirá
si se publica; hoy no la hay, así que no hay nada que discutir.

La barrera no es esta nota: es `vigia.publicacion`, que levanta.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from vigia.calendario import dias_habiles, es_festivo, nombre_del_festivo
from vigia.panel import compacto, numero, titulo_es
from vigia.publicacion import (NOTA, exigir_publicable, largo_en_x,
                               periodo_anterior_comparable)

CODIGO_USO = 2
CODIGO_FALLO = 1


def _fecha(texto) -> date:
    return date.fromisoformat(str(texto)[:10])


def _dia_mes(d: date) -> str:
    meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre")
    return f"{d.day} de {meses[d.month - 1]}"


def variacion(actual: float | None, previo: float | None) -> str:
    """El cambio entre dos ritmos YA normalizados por día hábil.

    Devuelve «—» cuando no se puede calcular. Nunca 0 %: un 0 % afirma que no
    cambió nada, y no saber no es lo mismo que no cambiar.
    """
    if actual is None or previo is None or previo == 0:
        return "—"
    cambio = 100 * (actual - previo) / previo
    return f"{'+' if cambio > 0 else ''}{cambio:.1f} %".replace(".", ",")


def pct(parte, total, decimales: int = 1) -> str:
    """Un porcentaje escrito como se escribe en Colombia: coma decimal.

    En un boletín que presume de rigor, un `23.08 %` con punto decimal
    desmiente al resto del texto antes de que nadie lea el número.
    """
    if not total:
        return "—"
    return f"{100 * float(parte) / float(total):.{decimales}f}".replace(".", ",") + " %"


def _festivos(desde: date, hasta: date) -> list[str]:
    nombres, dia = [], desde
    while dia <= hasta:
        if es_festivo(dia) and dia.weekday() < 5:
            nombres.append(nombre_del_festivo(dia))
        dia += timedelta(days=1)
    return nombres


def construir(datos: dict, *, periodo: str = "semana", enlace: str = "") -> list[str]:
    """El hilo, post por post. Levanta si algo no se puede publicar."""
    p, ant = datos["periodo"], datos["anterior"]
    a, b = datos["actual"], datos["anterior_cifras"]
    c = datos["cobertura"]
    d_desde, d_hasta = _fecha(p["desde"]), _fecha(p["hasta"])
    a_desde, a_hasta = _fecha(ant["desde"]), _fecha(ant["hasta"])
    hab_a = dias_habiles(d_desde, d_hasta)
    hab_p = dias_habiles(a_desde, a_hasta)

    def ritmo(v, habiles):
        return (float(v) / habiles) if habiles else None

    contratos_dia = ritmo(a["contratos"], hab_a)
    valor_dia = ritmo(float(a["valor"]), hab_a)
    posts: list[str] = []

    # 1. La cifra, y el período. Lo primero que se lee es lo único que muchos
    #    van a leer, así que lleva el número y la fecha, no un saludo.
    posts.append(
        f"Contratación pública en Colombia · {_dia_mes(d_desde)} al "
        f"{_dia_mes(d_hasta)} de {d_hasta.year}\n\n"
        f"{numero(a['contratos'])} contratos firmados\n"
        f"{compacto(a['valor'])}\n"
        f"{numero(a['entidades'])} entidades · {numero(a['proveedores'])} contratistas\n\n"
        f"Fuente: SECOP. Hilo con el detalle 👇"
    )

    # 2. El ritmo por día hábil. **Esta es la parte que nadie más publica** y
    #    la razón por la que el resto del hilo se sostiene: comparar dos
    #    semanas con conteos crudos es comparar almanaques.
    # Los festivos se nombran mientras quepan. Con un período largo son ocho o
    # diez y la lista sola revienta el post — lo encontró la barrera, no yo.
    # Cuando no caben se dice CUÁNTOS, que es el dato que importa: lo que
    # explica la diferencia entre dos períodos es el número de días hábiles,
    # no cómo se llaman los festivos.
    fest = sorted(set(_festivos(d_desde, d_hasta) + _festivos(a_desde, a_hasta)))
    if not fest:
        linea_fest = ""
    elif len(fest) <= 3:
        linea_fest = f"\n\nFestivos en juego: {', '.join(fest)}."
    else:
        linea_fest = f"\n\n{len(fest)} festivos en juego entre los dos períodos."
    if periodo_anterior_comparable(datos):
        posts.append(
            f"Por DÍA HÁBIL, que es la única comparación honesta "
            f"({hab_a} días hábiles ahora, {hab_p} en la {periodo} anterior):\n\n"
            f"{numero(round(contratos_dia)) if contratos_dia else '—'} contratos/día "
            f"({variacion(contratos_dia, ritmo(b['contratos'], hab_p))})\n"
            f"{compacto(valor_dia)}/día "
            f"({variacion(valor_dia, ritmo(float(b['valor']), hab_p))})"
            + linea_fest
        )
    else:
        # Sin período anterior ingerido, la comparación sería una caída del
        # 100 % inventada. Se dice que no hay, que es un dato en sí mismo.
        posts.append(
            f"Por DÍA HÁBIL ({hab_a} días hábiles):\n\n"
            f"{numero(round(contratos_dia)) if contratos_dia else '—'} contratos/día\n"
            f"{compacto(valor_dia)}/día\n\n"
            "Sin comparación con el período anterior: empieza antes de lo que "
            "tenemos ingerido, y compararlo daría una caída que no ocurrió."
            + linea_fest
        )

    # 3. LO QUE NO SE PUEDE VER. Va en el hilo y no en una nota al pie, y va
    #    antes que cualquier ranking. Un número de contratación sin su
    #    cobertura al lado es la clase de cifra que se cita mal.
    total = c["contratos"] or 1
    pct_ut = pct(c["valor_uniones"] or 0, a["valor"] or 1)
    posts.append(
        "Lo que estas cifras NO alcanzan a ver, dicho de frente:\n\n"
        f"· {numero(c['uniones'])} contratos de uniones temporales sin documento "
        f"({compacto(c['valor_uniones'])}, {pct_ut} del valor). No se les "
        "puede medir concentración.\n"
        f"· {numero(c['huerfanos'])} sin cruce con su proceso\n"
        f"· {numero(c['sin_departamento'])} sin departamento"
    )

    # 3b. LAS ERRATAS DE TECLEO, Y POR QUÉ ESTE POST ES EL QUE MÁS IMPORTA.
    #
    # Un contrato cuyo valor es EXACTAMENTE mil o diez mil veces el presupuesto
    # de su propio proceso no es un sobrecosto: es una tecla de más.
    #
    # Hasta el 2026-09-16 `boletin.sql` no las mencionaba, y este hilo se
    # publica en X. Probado contra el fixture: en una semana con cuatro de
    # ellas, el total habría salido **$823,5 mil millones en vez de $6,8 mil
    # millones**. Ciento veinte veces. Y un post no se puede retirar.
    #
    # Ahora están fuera de todas las cifras del hilo. Este post existe para
    # decir que se apartaron: apartar sin decirlo es esconder, y el número que
    # se enseña —lo que sumarían— es justo el tamaño del error evitado.
    #
    # Va solo si hay alguna. Un post permanente que casi siempre dice cero
    # deja de leerse el día que deja de decirlo.
    erratas = int(c.get("erratas") or 0)
    if erratas:
        plural = "" if erratas == 1 else "s"
        posts.append(
            f"Y {numero(erratas)} contrato{plural} quedaron FUERA de todo lo "
            "anterior.\n\n"
            "Su valor es exactamente mil o diez mil veces el presupuesto "
            "oficial de su propio proceso: una tecla de más, no un "
            "sobrecosto.\n\n"
            f"Sumaban {compacto(c.get('valor_erratas'))}. Ese habría sido el "
            "tamaño del error."
        )

    # 4. Geografía.
    deps = (datos.get("departamentos") or [])[:5]
    if deps:
        lineas = "\n".join(
            f"{i}. {titulo_es(f['nombre'])} — {compacto(f['valor'])}"
            for i, f in enumerate(deps, 1)
        )
        posts.append(f"Dónde se firmó, por valor:\n\n{lineas}")

    # 5. Modalidades.
    mods = (datos.get("modalidades") or [])[:5]
    if mods:
        total_m = sum(int(f["contratos"]) for f in datos.get("modalidades") or []) or 1
        lineas = "\n".join(
            f"· {f['modalidad']}: {pct(f['contratos'], total_m, 0)}"
            for f in mods
        )
        posts.append(f"Cómo se contrató (por número de contratos):\n\n{lineas}")

    # 6. La forma del gasto: convierte «billones» en algo que se entiende.
    tramos = datos.get("tramos") or []
    grandes = [t for t in tramos if int(t["orden"]) >= 5]
    if grandes and a["contratos"]:
        n_g = sum(int(t["contratos"]) for t in grandes)
        v_g = sum(float(t["valor"]) for t in grandes)
        posts.append(
            "La forma del gasto:\n\n"
            f"{numero(n_g)} contratos —el {pct(n_g, a['contratos'], 2)}— "
            f"se llevan {compacto(v_g)}, "
            f"el {pct(v_g, a['valor'] or 1)} de la plata.\n\n"
            "Pocos contratos grandes, muchísimos pequeños."
        )

    # 7. Qué es esto. Cierra el hilo y lleva la nota escrita, no enlazada: el
    #    tercer post circula sin el primero.
    # El cierre se arma contando: con enlace caben menos palabras, y un post
    # que rebota al publicarlo rebota justo cuando ya no hay tiempo de
    # arreglarlo. Se recorta aquí, no allá.
    cierre = f"{NOTA}\n\nDatos públicos, método abierto. Si algo le parece que "
    cierre += "vale la pena mirar, mírelo."
    if enlace:
        cierre += f"\n{enlace}"
    posts.append(cierre)

    # La barrera va al final y levanta. No se devuelve un hilo con reparos
    # «para que alguien decida»: o se puede publicar, o no sale de aquí.
    exigir_publicable(posts)
    return posts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vigia.boletin")
    ap.add_argument("--json", default="boletin.json")
    ap.add_argument("--salida", default="boletin.txt")
    ap.add_argument("--periodo", default="semana")
    ap.add_argument("--enlace", default="")
    o = ap.parse_args(argv)

    origen = Path(o.json)
    if not origen.exists():
        print(f"no existe {origen}", file=sys.stderr)
        return CODIGO_USO
    datos = json.loads(origen.read_text(encoding="utf-8"))
    for seccion in ("periodo", "actual", "anterior_cifras", "cobertura"):
        if seccion not in datos:
            print(f"a {origen} le falta la sección «{seccion}»", file=sys.stderr)
            return CODIGO_FALLO

    try:
        posts = construir(datos, periodo=o.periodo, enlace=o.enlace)
    except Exception as error:  # NoPublicable u otro
        print(f"NO SE PUBLICA: {error}", file=sys.stderr)
        return CODIGO_FALLO

    texto = "\n\n———\n\n".join(
        f"[{i}/{len(posts)}]  ({largo_en_x(p)} caracteres)\n{p}"
        for i, p in enumerate(posts, 1)
    )
    Path(o.salida).write_text(texto + "\n", encoding="utf-8")
    print(f"Boletín escrito en {Path(o.salida).resolve()}")
    print(f"  {len(posts)} posts · el más largo, "
          f"{max(largo_en_x(p) for p in posts)} de 280 caracteres")
    print("  revisado: sin documentos de identidad, sin vocabulario de imputación")
    return 0


if __name__ == "__main__":
    sys.exit(main())
