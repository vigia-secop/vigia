"""El archivo de Vigía: `docs/archivo.html`, el recorrido por día, semana y mes.

    python -m vigia.archivo --json archivo.json --salida docs/archivo.html

POR QUÉ EXISTE. `index.html` es el día de hoy y `semana.html` el período recién
cerrado. Entre los dos no había forma de preguntar «¿y el martes pasado?» ni
«¿cómo fue agosto entero?». Los datos estaban en la base desde el principio; lo
que faltaba era el recorrido.

UNA SOLA PÁGINA Y NINGUNA CONSULTA. El sitio es HTML quieto en GitHub Pages: no
hay nada del otro lado que responda a un clic. Así que todo lo que el lector
pueda llegar a pedir viene ya adentro, en un bloque JSON, y el navegador solo
elige qué mostrar. Ventaja secundaria y nada menor: se abre igual de rápido el
día cincuenta que el primero, y funciona sin conexión.

SOBRE EL MOVIMIENTO, que es lo que se pidió. Aquí se mueve lo que informa:
la barra crece hasta su valor —que es la magnitud haciéndose visible—, el
tooltip sigue al cursor, y cambiar de período atenúa y repinta en vez de
saltar, para que el ojo entienda que cambió el contenido y no la página.
Nada aparece por scroll, ninguna cifra cuenta hacia arriba, nada rebota. Vigía
se lee como un registro y esa sobriedad es parte de por qué le creerían; una
página de contratación pública que se comporta como una campaña se lee como
una campaña.

LO QUE ESTA PÁGINA NO HACE. No señala. No hay banderas aquí ni adjetivos sobre
nadie: es la misma ventana de siempre, cortada por días, semanas y meses.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from vigia import estilo
from vigia.calendario import es_festivo, es_habil, nombre_del_festivo
from vigia.marca import ojo
from vigia.sitio import LEMA, TITULO

CODIGO_USO = 2
CODIGO_FALLO = 1

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


# ---------------------------------------------------------------- formateo
# Estas cuatro funciones son las mismas de `panel.py`. Están repetidas a
# propósito y con una prueba que las ata: `test_archivo.py` compara la salida
# de las dos parejas sobre los mismos números, así que el día que alguien
# cambie el formato en una sola, la prueba lo dice. Es el mismo trato que
# `estilo.py` tiene con la paleta.

def pesos(valor) -> str:
    if valor is None:
        return "—"
    return "$" + f"{float(valor):,.0f}".replace(",", ".")


def _colombiano(texto: str) -> str:
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def compacto(valor) -> str:
    if valor is None:
        return "—"
    v = float(valor)
    if abs(v) >= 1e12:
        return "$" + _colombiano(f"{v / 1e12:,.2f}") + " billones"
    if abs(v) >= 1e9:
        return "$" + _colombiano(f"{v / 1e9:,.1f}") + " mil millones"
    if abs(v) >= 1e6:
        return "$" + _colombiano(f"{v / 1e6:,.1f}") + " millones"
    return pesos(v)


def numero(valor) -> str:
    if valor is None:
        return "—"
    return f"{int(valor):,}".replace(",", ".")


def e(texto) -> str:
    return html.escape(str(texto)) if texto is not None else ""


def _fecha(valor) -> date:
    return date.fromisoformat(str(valor)[:10])


def _largo(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


# ------------------------------------------------------------------ escala
def escalones(valores: list[float]) -> list[float]:
    """Los cuatro cortes que parten los días en cinco tonos.

    **Cuantiles y no tramos iguales.** La contratación pública es de cola muy
    larga: con cortes equiespaciados, un solo día grande deja todos los demás
    en el tono más claro y el mapa no dice nada. Con cuantiles, cada tono lleva
    aproximadamente la quinta parte de los días y el mapa recupera su trabajo,
    que es enseñar en qué días pasó más.

    A cambio hay que publicar los cortes —van en la leyenda— porque un color
    sin su escala al lado no es un dato, es una impresión.
    """
    limpios = sorted(v for v in valores if v and v > 0)
    if not limpios:
        return []
    cortes = []
    for i in (1, 2, 3, 4):
        pos = int(round(i * len(limpios) / 5))
        pos = max(0, min(len(limpios) - 1, pos))
        cortes.append(float(limpios[pos]))
    # Cortes repetidos (pocos días, o muchos días iguales) se colapsan: una
    # leyenda con dos escalones idénticos confunde más de lo que explica.
    unicos: list[float] = []
    for c in cortes:
        if not unicos or c > unicos[-1]:
            unicos.append(c)
    return unicos


def tono(valor: float | None, cortes: list[float]) -> int:
    """0 = sin contratos; 1..5 = de menos a más."""
    if not valor or valor <= 0:
        return 0
    for i, c in enumerate(cortes):
        if valor <= c:
            return i + 1
    return len(cortes) + 1


# ------------------------------------------------------------------- mapa
def _celdas_del_mes(mes: date, por_dia: dict, cortes: list[float],
                    desde: date, hasta: date) -> str:
    """Un mes del calendario. Lunes a domingo, como se lee un calendario."""
    primero = mes.replace(day=1)
    siguiente = (primero + timedelta(days=32)).replace(day=1)
    ultimo = siguiente - timedelta(days=1)

    celdas = []
    # Huecos hasta el primer lunes, para que las columnas sean días de semana.
    for _ in range(primero.weekday()):
        celdas.append('<span class="cel fuera" aria-hidden="true"></span>')

    d = primero
    while d <= ultimo:
        clave = d.isoformat()
        datos = por_dia.get(clave)
        if d < desde or d > hasta:
            # Fuera de lo ingerido. NO es un día sin contratos: es un día que
            # no hemos mirado, y confundirlos sería afirmar una caída que no
            # ocurrió. Se dibuja distinto y se dice en la leyenda.
            celdas.append(
                f'<span class="cel nodata" title="{e(_largo(d))}: '
                'sin ingerir" aria-hidden="true"></span>'
            )
        else:
            t = tono(float(datos["valor"]) if datos else 0, cortes)
            festivo = nombre_del_festivo(d)
            clases = f"cel t{t}"
            if not es_habil(d):
                clases += " sinjornada"
            etiqueta = _largo(d)
            if datos:
                etiqueta += (f" · {numero(datos['contratos'])} contratos · "
                             f"{compacto(datos['valor'])}")
            else:
                etiqueta += " · sin contratos firmados"
            if festivo:
                etiqueta += f" · {festivo}"
            elif d.weekday() >= 5:
                etiqueta += " · fin de semana"
            celdas.append(
                f'<button type="button" class="{clases}" data-dia="{clave}" '
                f'aria-label="{e(etiqueta)}"><span class="cn">{d.day}</span></button>'
            )
        d += timedelta(days=1)

    return (
        '<div class="mes">'
        f'<h3>{MESES[mes.month - 1]} <span>{mes.year}</span></h3>'
        '<div class="dow">'
        + "".join(f"<span>{x}</span>" for x in DIAS_SEMANA)
        + "</div>"
        f'<div class="rej">{"".join(celdas)}</div>'
        "</div>"
    )


def _leyenda(cortes: list[float]) -> str:
    """La escala, escrita. Un color sin su corte al lado es una impresión."""
    if not cortes:
        return ""
    trozos = [
        '<span class="lg-it"><span class="cel t1"></span>'
        f"hasta {compacto(cortes[0])}</span>"
    ]
    for i in range(1, len(cortes)):
        trozos.append(
            f'<span class="lg-it"><span class="cel t{i + 1}"></span>'
            f"hasta {compacto(cortes[i])}</span>"
        )
    trozos.append(
        f'<span class="lg-it"><span class="cel t{len(cortes) + 1}"></span>'
        f"más de {compacto(cortes[-1])}</span>"
    )
    return (
        '<div class="leyenda"><span class="lg-tit">Valor firmado en el día</span>'
        + "".join(trozos)
        + '<span class="lg-it"><span class="cel t0"></span>sin contratos</span>'
        '<span class="lg-it"><span class="cel sinjornada t0"></span>'
        "sin jornada hábil</span>"
        '<span class="lg-it"><span class="cel nodata"></span>sin ingerir</span>'
        "</div>"
    )


def _tabla_de_dias(dias: list[dict]) -> str:
    """El mapa, en palabras. Existe porque un color no se puede leer en voz
    alta, y porque quien no distingue estos tonos también tiene derecho al
    dato. Va plegada para no competir con el mapa."""
    filas = "".join(
        "<tr>"
        f"<td>{e(_largo(_fecha(f['dia'])))}</td>"
        f'<td class="n">{numero(f["contratos"])}</td>'
        f'<td class="n">{compacto(f["valor"])}</td>'
        f'<td class="n">{numero(f["entidades"])}</td>'
        "</tr>"
        for f in dias
    )
    return (
        "<details class=\"tabla-dias\"><summary>Ver los mismos días como tabla"
        "</summary><div class=\"tabla-scroll\"><table class=\"tabla\">"
        "<thead><tr><th>Día</th><th class=\"n\">Contratos</th>"
        "<th class=\"n\">Valor</th><th class=\"n\">Entidades</th></tr></thead>"
        f"<tbody>{filas}</tbody></table></div></details>"
    )


# -------------------------------------------------------------------- CSS
CSS = """
/* La cifra de una caja no se parte en dos renglones: «$960,9 millones» a 27px
   no cabe en una columna de 245px, y un numero cortado se lee mal antes de
   leerse bien. Columna un poco mas ancha y cuerpo un poco menor. */
.cifras { grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); }
.caja .dat { font-size:22px; }

.nav-tabs { display:flex; gap:8px; margin:26px 0 0; flex-wrap:wrap; }
.nav-tabs button { font:inherit; font-size:14px; padding:8px 16px; cursor:pointer;
  background:var(--superficie); color:var(--tinta-2); border:1px solid var(--borde);
  border-radius:999px; transition:background .18s ease, color .18s ease,
  border-color .18s ease; }
.nav-tabs button:hover { border-color:var(--acento); color:var(--tinta); }
.nav-tabs button[aria-pressed="true"] { background:var(--acento); color:#fff;
  border-color:var(--acento); font-weight:600; }
.nav-tabs button:focus-visible { outline:2px solid var(--acento); outline-offset:2px; }

.calendario { display:grid; gap:22px; grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
  margin-top:16px; }
.mes h3 { margin:0 0 8px; font-size:14px; font-weight:600; text-transform:capitalize; }
.mes h3 span { color:var(--tinta-3); font-weight:400; }
.dow, .rej { display:grid; grid-template-columns:repeat(7,1fr); gap:3px; }
.dow span { font-size:10.5px; color:var(--tinta-3); text-align:center; padding-bottom:2px; }
.cel { aspect-ratio:1; border-radius:3px; border:1px solid var(--borde-sutil);
  background:var(--superficie); padding:0; display:flex; align-items:center;
  justify-content:center; font:inherit; font-size:10px; color:var(--tinta-3);
  cursor:pointer; transition:transform .12s ease, box-shadow .12s ease; }
.cel.fuera { border:0; background:none; cursor:default; }
.cel.nodata { background:var(--borde-sutil); border-color:transparent; cursor:default; }
.cel.t1 { background:var(--cal-1); } .cel.t2 { background:var(--cal-2); }
.cel.t3 { background:var(--cal-3); } .cel.t4 { background:var(--cal-4); }
.cel.t5 { background:var(--cal-5); }
.cel.t3 .cn, .cel.t4 .cn, .cel.t5 .cn { color:#fff; }
.cel.sinjornada { background-image:repeating-linear-gradient(135deg,
  transparent 0 3px, var(--borde) 3px 4px); }
button.cel:hover { transform:scale(1.18); box-shadow:0 1px 6px rgba(0,0,0,.18);
  z-index:2; position:relative; }
button.cel:focus-visible { outline:2px solid var(--acento); outline-offset:1px; }
.cel.sel { box-shadow:0 0 0 2px var(--tinta); z-index:3; position:relative; }
.cel.ensel { box-shadow:0 0 0 2px var(--acento); z-index:1; position:relative; }
.cn { pointer-events:none; }

.leyenda { display:flex; flex-wrap:wrap; gap:14px; align-items:center;
  margin-top:16px; font-size:12px; color:var(--tinta-3); }
.lg-tit { font-weight:600; color:var(--tinta-2); }
.lg-it { display:flex; align-items:center; gap:5px; }
.lg-it .cel { width:12px; height:12px; aspect-ratio:auto; cursor:default; }

.periodo-cab { display:flex; align-items:baseline; justify-content:space-between;
  gap:12px; flex-wrap:wrap; margin-top:40px; }
.periodo-cab h2 { margin:0; }
.mover { display:flex; gap:6px; }
.mover button { font:inherit; font-size:18px; line-height:1; width:36px; height:36px;
  border-radius:8px; border:1px solid var(--borde); background:var(--superficie);
  color:var(--tinta-2); cursor:pointer; transition:border-color .15s ease,
  color .15s ease; }
.mover button:hover:not(:disabled) { border-color:var(--acento); color:var(--tinta); }
.mover button:disabled { opacity:.35; cursor:default; }
.mover button:focus-visible { outline:2px solid var(--acento); outline-offset:2px; }

#vista { transition:opacity .16s ease; }
#vista.cambiando { opacity:.25; }

.pista { display:block; background:var(--borde-sutil); border-radius:3px;
  height:6px; margin-top:6px; overflow:hidden; }
.relleno { display:block; height:100%; background:var(--acento); border-radius:3px;
  width:0; transition:width .5s cubic-bezier(.22,.61,.36,1); }

.tabla { width:100%; border-collapse:collapse; font-size:14px; }
.tabla th { text-align:left; font-size:11.5px; text-transform:uppercase;
  letter-spacing:.06em; color:var(--tinta-3); border-bottom:1px solid var(--borde);
  padding:0 10px 8px 0; font-weight:600; }
.tabla td { padding:10px 10px 10px 0; border-bottom:1px solid var(--borde-sutil);
  vertical-align:top; }
.tabla .n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.tabla-scroll { overflow-x:auto; }
.doc { display:block; font-size:12px; color:var(--tinta-3);
  font-family:"IBM Plex Mono",ui-monospace,monospace; }
.tabla-dias { margin-top:20px; font-size:14px; }
.tabla-dias summary { cursor:pointer; color:var(--tinta-2); }
.tabla-dias summary:focus-visible { outline:2px solid var(--acento); outline-offset:2px; }

.tip { position:fixed; pointer-events:none; z-index:50; background:var(--tinta);
  color:var(--papel); padding:7px 10px; border-radius:6px; font-size:12.5px;
  line-height:1.45; max-width:250px; opacity:0; transition:opacity .12s ease; }
.tip.on { opacity:1; }
.tip b { color:inherit; }

.vacio { color:var(--tinta-3); font-style:italic; margin:0; }
.enlaces { display:flex; gap:10px; flex-wrap:wrap; margin-top:46px; }
.enlaces a { font-size:14px; padding:9px 16px; border:1px solid var(--borde);
  border-radius:999px; text-decoration:none; color:var(--tinta-2);
  background:var(--superficie); transition:border-color .15s ease, color .15s ease; }
.enlaces a:hover { border-color:var(--acento); color:var(--tinta); }
footer { margin-top:46px; padding-top:18px; border-top:1px solid var(--borde);
  font-size:12.5px; color:var(--tinta-3); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition:none !important; animation:none !important; }
  button.cel:hover { transform:none; }
}
"""

#: La rampa secuencial del mapa: UN solo tono, de claro a oscuro, mezclando el
#: acento con la superficie de cada tema. Un solo tono porque lo que el mapa
#: codifica es magnitud, no identidad; un arcoíris aquí diría que el martes es
#: de otra especie que el miércoles.
#:
#: La oscura no es la clara invertida: se vuelve a mezclar contra el fondo
#: oscuro, que es donde una inversión ingenua deja el paso más claro brillando
#: como un error.
RAMPA_CLARA = ["#D9EEF2", "#A6D8E1", "#66BDCB", "#33A7B9", "#0091A8"]
RAMPA_OSCURA = ["#193239", "#1B4C57", "#1E6C7C", "#20869A", "#22A0B8"]


def _rampa_css() -> str:
    claro = "".join(f"  --cal-{i + 1}:{c};\n" for i, c in enumerate(RAMPA_CLARA))
    oscuro = "".join(f"  --cal-{i + 1}:{c};\n" for i, c in enumerate(RAMPA_OSCURA))
    oscuro_ind = "".join(
        f"    --cal-{i + 1}:{c};\n" for i, c in enumerate(RAMPA_OSCURA)
    )
    return (
        ":root {\n" + claro + "}\n"
        '@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n'
        + oscuro_ind + "  }\n}\n"
        ':root[data-theme="dark"] {\n' + oscuro + "}\n"
    )


# ------------------------------------------------------------- los paneles
# CADA PERÍODO SE DIBUJA EN PYTHON, NO EN EL NAVEGADOR.
#
# La tentación era mandar los números crudos y que el JavaScript los formateara
# al hacer clic. Eso obliga a escribir dos veces la misma regla —el punto de
# miles, «mil millones», la comparación contra el período anterior— en dos
# lenguajes, y dos copias de una regla son dos copias que se separan.
#
# Así que el navegador no calcula NADA: recibe el HTML de los ciento y pico de
# períodos ya escrito y solo elige cuál enseñar. Pesa unos cientos de kilobytes
# —menos que una foto— y a cambio no hay una sola cifra que pueda salir
# formateada distinto según por dónde se entre.


def _tiles(act: dict, ant: dict | None, etiqueta_ant: str) -> str:
    def variacion(clave: str) -> str:
        if not ant or not ant.get(clave):
            return f'<div class="pie">Sin {etiqueta_ant} con qué comparar.</div>'
        a, b = float(act.get(clave) or 0), float(ant[clave])
        pct = 100 * (a - b) / b
        cls = "sube" if pct > 0.05 else ("baja" if pct < -0.05 else "neutro")
        signo = "+" if pct > 0 else ""
        return (f'<div class="var {cls}">{signo}{pct:.1f} %</div>'
                f'<div class="pie">vs. {etiqueta_ant}</div>').replace(".", ",", 1)

    return (
        '<div class="cifras">'
        '<div class="caja"><div class="rot">Contratos</div>'
        f'<div class="dat">{numero(act["contratos"])}</div>{variacion("contratos")}</div>'
        '<div class="caja"><div class="rot">Valor firmado</div>'
        f'<div class="dat" title="{pesos(act["valor"])}">{compacto(act["valor"])}</div>'
        f'{variacion("valor")}</div>'
        '<div class="caja"><div class="rot">Entidades</div>'
        f'<div class="dat">{numero(act["entidades"])}</div>{variacion("entidades")}</div>'
        '<div class="caja"><div class="rot">Contratistas</div>'
        f'<div class="dat">{numero(act.get("proveedores"))}</div>'
        '<div class="pie">Sin las uniones temporales sin documento.</div></div>'
        "</div>"
    )


def _mayores(filas: list | None) -> str:
    filas = filas or []
    if not filas:
        return ('<p class="vacio">No se firmó ningún contrato con valor en este '
                "período.</p>")
    tope = max(float(f["valor"] or 0) for f in filas) or 1
    cuerpo = []
    for f in filas:
        ancho = 100 * float(f["valor"] or 0) / tope
        cuerpo.append(
            "<tr>"
            f'<td>{e(f.get("proveedor") or "—")}'
            f'<span class="doc">{e(f.get("entidad") or "—")}</span>'
            f'<span class="doc">{e(f.get("id_contrato") or "")}</span></td>'
            f'<td class="n">{compacto(f["valor"])}'
            f'<span class="pista"><span class="relleno" data-ancho="{ancho:.2f}">'
            "</span></span></td>"
            "</tr>"
        )
    return (
        '<div class="tabla-scroll"><table class="tabla">'
        "<thead><tr><th>Contratista, entidad y contrato</th>"
        '<th class="n">Valor</th></tr></thead>'
        f'<tbody>{"".join(cuerpo)}</tbody></table></div>'
    )


def _erratas(bloque: dict | None) -> str:
    """Lo que se apartó de las cifras de arriba, con nombre y las dos cifras.

    Va en TODOS los períodos que tengan alguna, con el mismo detalle con que
    la página da sus propios números. Apartar sin decirlo sería esconder, y la
    cifra que se enseña —lo que sumarían— es el tamaño exacto del error.
    """
    if not bloque or not bloque.get("cuantas"):
        return ""
    cuantas = int(bloque["cuantas"])
    plural = "" if cuantas == 1 else "s"
    filas = "".join(
        "<tr>"
        f'<td>{e(f.get("proveedor") or "—")}'
        f'<span class="doc">{e(f.get("entidad") or "—")}</span>'
        f'<span class="doc">{e(f.get("id_contrato") or "")}</span></td>'
        f'<td class="n">{compacto(f.get("valor"))}<span class="doc">publicado</span></td>'
        f'<td class="n">{compacto(f.get("presupuesto_del_proceso"))}'
        f'<span class="doc">presupuesto'
        + (f' · ×{numero(f["veces"])}' if f.get("veces") else "")
        + "</span></td></tr>"
        for f in (bloque.get("filas") or [])
    )
    return (
        '<div class="tarjeta alcance" style="margin-top:22px">'
        f"<p style=\"margin:0\"><strong>{numero(cuantas)} contrato{plural} "
        "quedaron fuera de las cifras de arriba.</strong> Su valor es "
        "exactamente mil o diez mil veces el presupuesto oficial de su propio "
        "proceso: la firma de una tecla de más, no la de un sobrecosto. "
        f"Sumaban {compacto(bloque.get('valor'))} — ese habría sido el tamaño "
        "del error. Apartarlos no es taparlos, así que aquí están:</p>"
        '<div class="tabla-scroll" style="margin-top:10px"><table class="tabla">'
        "<thead><tr><th>Contratista, entidad y contrato</th>"
        '<th class="n">Valor</th><th class="n">Contra qué se comparó</th>'
        f"</tr></thead><tbody>{filas}</tbody></table></div></div>"
    )


def _titulo(clave: str, fila: dict) -> str:
    tipo = clave[0]
    if tipo == "d":
        d = _fecha(fila["dia"])
        nombre = ["lunes", "martes", "miércoles", "jueves", "viernes",
                  "sábado", "domingo"][d.weekday()]
        cierre = ""
        if es_festivo(d):
            cierre = f" · {nombre_del_festivo(d)}"
        elif d.weekday() >= 5:
            cierre = " · fin de semana"
        return f"{nombre.capitalize()} {_largo(d)}{cierre}"
    if tipo == "s":
        a, b = _fecha(fila["desde"]), _fecha(fila["hasta"])
        return f"Semana del {_largo(a)} al {_largo(b)}"
    m = _fecha(fila["desde"])
    return f"{MESES[m.month - 1].capitalize()} de {m.year}"


def _nota_de_cobertura(clave: str, fila: dict, desde: date, hasta: date) -> str:
    """Si el período está cortado por lo que hemos ingerido, se dice.

    Un mes al que le faltan doce días no se puede comparar con uno entero, y
    quien lea «agosto» sin saberlo va a compararlos igual. Es la misma
    distinción de siempre: «se miró y no había» no es «no se miró».
    """
    if clave[0] == "d":
        return ""
    a, b = _fecha(fila["desde"]), _fecha(fila["hasta"])
    recortado_inicio = a < desde
    recortado_final = b > hasta
    if not (recortado_inicio or recortado_final):
        return ""
    cubre_a = max(a, desde)
    cubre_b = min(b, hasta)
    faltan = (b - cubre_b).days + (cubre_a - a).days
    cual = "mes" if clave[0] == "m" else "semana"
    return (
        '<p class="pie" style="margin-top:10px">Este ' + cual + " va del "
        f"{_largo(a)} al {_largo(b)}, pero Vigía solo tiene ingerido del "
        f"{_largo(cubre_a)} al {_largo(cubre_b)}: <strong>faltan {faltan} "
        "día(s)</strong>. No se contrató menos — se ha mirado menos.</p>"
    )


JS = """
// EL NAVEGADOR NO CALCULA NADA. Recibe el HTML de cada periodo ya escrito en
// Python y solo elige cual enseñar. Sin esta regla habria dos copias del
// formato de cifras -una en cada lenguaje- y el dia que alguien cambie una,
// la pagina diria dos cosas distintas segun por donde se entre.
(function () {
  var P = JSON.parse(document.getElementById('paneles').textContent);
  var vista = document.getElementById('vista');
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.nav-tabs button'));
  var celdas = Array.prototype.slice.call(document.querySelectorAll('button.cel'));
  var anterior = document.getElementById('anterior');
  var siguiente = document.getElementById('siguiente');
  var tip = document.getElementById('tip');
  var modo = 'd', clave = P.inicial.d;

  function claveDe(modo, dia) { return (P.mapa[modo] || {})[dia] || null; }

  function pintar(nueva) {
    if (!nueva || !P.paneles[nueva]) { return; }
    clave = nueva;
    vista.classList.add('cambiando');
    window.setTimeout(function () {
      vista.innerHTML = P.paneles[clave];
      vista.classList.remove('cambiando');
      // Las barras arrancan en cero y crecen hasta su valor: la magnitud
      // haciendose visible, no un adorno. Un cuadro de render las separa
      // del momento en que entran al documento, que es lo que hace que la
      // transicion de CSS de verdad ocurra.
      window.requestAnimationFrame(function () {
        Array.prototype.forEach.call(vista.querySelectorAll('.relleno'), function (r) {
          r.style.width = r.getAttribute('data-ancho') + '%';
        });
      });
    }, 120);

    var dentro = P.dias[clave] || [];
    celdas.forEach(function (c) {
      var d = c.getAttribute('data-dia');
      c.classList.toggle('ensel', dentro.indexOf(d) !== -1);
      c.classList.toggle('sel', modo === 'd' && d === clave.slice(1));
    });

    var lista = P.orden[modo];
    var i = lista.indexOf(clave);
    anterior.disabled = i <= 0;
    siguiente.disabled = i < 0 || i >= lista.length - 1;
    // La almohadilla se actualiza para que cada periodo tenga URL propia y se
    // pueda mandar por chat. Va en try porque NO siempre se puede: dentro de
    // un iframe sin origen -la vista previa de un editor, un embebido- el
    // navegador lo prohibe y lanza SecurityError. Se vio el 2026-09-19 en la
    // vista previa de la aplicacion de escritorio.
    //
    // Que la URL no se pueda actualizar no es razon para que la pagina deje de
    // funcionar: es una comodidad, no el contenido. Se intenta y se sigue.
    try {
      if (history.replaceState) { history.replaceState(null, '', '#' + clave); }
    } catch (err) { /* iframe sin origen: sin URL por periodo, y ya. */ }
  }

  tabs.forEach(function (b) {
    b.addEventListener('click', function () {
      var nuevo = b.getAttribute('data-modo');
      // Al cambiar de pestaña no se vuelve al principio: se enseña el periodo
      // que CONTIENE lo que se estaba mirando. Es la diferencia entre «y esa
      // semana como fue» y empezar la busqueda de nuevo.
      var dia = clave.slice(1);
      var destino = claveDe(nuevo, dia) || P.inicial[nuevo];
      modo = nuevo;
      tabs.forEach(function (o) {
        o.setAttribute('aria-pressed', String(o === b));
      });
      pintar(destino);
    });
  });

  celdas.forEach(function (c) {
    c.addEventListener('click', function () {
      pintar(claveDe(modo, c.getAttribute('data-dia')));
    });
    c.addEventListener('mouseenter', function () {
      tip.textContent = c.getAttribute('aria-label');
      tip.classList.add('on');
    });
    c.addEventListener('mouseleave', function () { tip.classList.remove('on'); });
  });

  document.addEventListener('mousemove', function (ev) {
    if (!tip.classList.contains('on')) { return; }
    var x = ev.clientX + 14, y = ev.clientY + 16;
    if (x + tip.offsetWidth > window.innerWidth - 8) { x = ev.clientX - tip.offsetWidth - 14; }
    if (y + tip.offsetHeight > window.innerHeight - 8) { y = ev.clientY - tip.offsetHeight - 14; }
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  });

  function mover(paso) {
    var lista = P.orden[modo];
    var i = lista.indexOf(clave);
    if (i >= 0 && i + paso >= 0 && i + paso < lista.length) { pintar(lista[i + paso]); }
  }
  anterior.addEventListener('click', function () { mover(-1); });
  siguiente.addEventListener('click', function () { mover(1); });
  document.addEventListener('keydown', function (ev) {
    if (ev.target && /^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName)) { return; }
    if (ev.key === 'ArrowLeft') { mover(-1); }
    if (ev.key === 'ArrowRight') { mover(1); }
  });

  // Entrar por un enlace con almohadilla abre ese periodo: cada dia, cada
  // semana y cada mes tiene URL propia y se puede mandar por chat.
  var h = (location.hash || '').replace('#', '');
  if (h && P.paneles[h]) {
    modo = h.charAt(0);
    tabs.forEach(function (o) {
      o.setAttribute('aria-pressed', String(o.getAttribute('data-modo') === modo));
    });
    clave = h;
  }
  pintar(clave);
})();
"""


def construir(datos: dict) -> str:
    dias = datos.get("dias") or []
    semanas = datos.get("semanas") or []
    meses = datos.get("meses") or []
    if not dias:
        raise ValueError("el archivo no trae ni un día con contratos")

    rango = datos.get("rango") or {}
    desde, hasta = _fecha(rango["desde"]), _fecha(rango["hasta"])
    por_dia = {str(f["dia"])[:10]: f for f in dias}
    cortes = escalones([float(f["valor"] or 0) for f in dias])
    mayores = datos.get("mayores") or {}
    erratas = datos.get("erratas") or {}

    # Un panel por período, y el índice que dice a qué período pertenece cada
    # día en cada modo. Los dos se construyen del mismo recorrido para que no
    # puedan desalinearse.
    paneles: dict[str, str] = {}
    orden: dict[str, list[str]] = {"d": [], "s": [], "m": []}
    mapa: dict[str, dict[str, str]] = {"d": {}, "s": {}, "m": {}}
    dias_de: dict[str, list[str]] = {}

    # CONTRA QUÉ SE COMPARA CADA COSA, y esta decisión no es cosmética.
    #
    # Un día NO se compara con el día anterior: un lunes contra un domingo no
    # dice nada, y la primera versión de esta página rotulaba «vs. el día hábil
    # anterior» una comparación que en realidad era contra el día anterior con
    # contratos —fuera hábil o no—. Rotular algo que no se calculó es la clase
    # de error que nadie descubre porque el número sale.
    #
    # Así que un día se compara con el MISMO día de la semana anterior, que es
    # la regla que ya usa la portada. Una semana con la semana anterior y un
    # mes con el mes anterior sí son consecutivos y se comparan directo.
    grupos = [("d", dias, "dia", "igual día, semana anterior"),
              ("s", semanas, "desde", "la semana anterior"),
              ("m", meses, "desde", "el mes anterior")]

    for tipo, filas, campo_inicio, etiqueta_ant in grupos:
        previo: dict | None = None
        for fila in filas:
            if tipo == "d":
                previo = por_dia.get(
                    (_fecha(fila["dia"]) - timedelta(days=7)).isoformat())
            clave = tipo + str(fila[campo_inicio])[:10]
            orden[tipo].append(clave)
            if tipo == "d":
                cubiertos = [str(fila["dia"])[:10]]
            else:
                a, b = _fecha(fila["desde"]), _fecha(fila["hasta"])
                cubiertos = []
                d = a
                while d <= b:
                    cubiertos.append(d.isoformat())
                    d += timedelta(days=1)
            dias_de[clave] = cubiertos
            for d in cubiertos:
                mapa[tipo][d] = clave

            paneles[clave] = (
                f"<h2>{e(_titulo(clave, fila))}</h2>"
                + _nota_de_cobertura(clave, fila, desde, hasta)
                + _tiles(fila, previo, etiqueta_ant)
                + "<h2>Los contratos más grandes</h2>"
                '<p class="sub">Por valor firmado. No es una señal de nada: '
                "un contrato grande es grande.</p>"
                + _mayores(mayores.get(clave))
                + _erratas(erratas.get(clave))
            )
            if tipo != "d":
                previo = fila

    inicial = {t: (orden[t][-1] if orden[t] else "") for t in ("d", "s", "m")}

    primer_mes = desde.replace(day=1)
    ultimo_mes = hasta.replace(day=1)
    calendario, m = [], primer_mes
    while m <= ultimo_mes:
        calendario.append(_celdas_del_mes(m, por_dia, cortes, desde, hasta))
        m = (m + timedelta(days=32)).replace(day=1)

    carga = json.dumps(
        {"paneles": paneles, "orden": orden, "mapa": mapa,
         "dias": dias_de, "inicial": inicial},
        ensure_ascii=False,
    ).replace("<", "\\u003c")

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>El archivo · Vigía SECOP</title>
<meta name="description" content="La contratación pública colombiana día por día,
semana por semana y mes por mes, desde {e(_largo(desde))}.">
<style>
{estilo.tokens()}
{_rampa_css()}
{estilo.BASE}
{estilo.NAV_CSS}
{CSS}
</style>
</head>
<body>
<div class="env">
  <header class="top">
    <div class="marca">{ojo(alto=44, color="currentColor")}<h1>{TITULO}</h1></div>
    <p class="lema">{LEMA}</p>
    {estilo.menu("archivo.html")}
  </header>

  <h2 class="pagina">El archivo</h2>
  <p class="sub">La contratación pública, día por día.</p>
  <p class="per">Del {e(_largo(desde))} al {e(_largo(hasta))} ·
    {numero(rango.get("contratos"))} contratos · {compacto(rango.get("valor"))}</p>

  <h2>Escoge un período</h2>
  <p class="sub">Haz clic en un día del mapa. La pestaña decide si eso significa
    ese día, su semana o su mes. También sirven las flechas ← y →.</p>

  <div class="nav-tabs" role="group" aria-label="Granularidad">
    <button type="button" data-modo="d" aria-pressed="true">Día</button>
    <button type="button" data-modo="s" aria-pressed="false">Semana</button>
    <button type="button" data-modo="m" aria-pressed="false">Mes</button>
  </div>

  <div class="calendario">{"".join(calendario)}</div>
  {_leyenda(cortes)}
  {_tabla_de_dias(dias)}

  <div class="periodo-cab">
    <h2 style="margin:0">Lo que se firmó</h2>
    <div class="mover">
      <button type="button" id="anterior" aria-label="Período anterior">←</button>
      <button type="button" id="siguiente" aria-label="Período siguiente">→</button>
    </div>
  </div>

  <div id="vista"></div>

  <footer>
    Datos de SECOP vía datos.gov.co · método abierto · cualquiera puede rehacer
    las cuentas.<br>
    Vigía publica estadística descriptiva sobre datos públicos. No señala a
    nadie ni afirma que exista una conducta contraria a la ley.
  </footer>
</div>
<div class="tip" id="tip" role="status" aria-live="polite"></div>
<script type="application/json" id="paneles">{carga}</script>
<script>{JS}</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vigia.archivo")
    p.add_argument("--json", default="archivo.json")
    p.add_argument("--salida", default="docs/archivo.html")
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

    try:
        pagina = construir(datos)
    except (KeyError, ValueError) as error:
        print(f"no se pudo construir el archivo: {error}", file=sys.stderr)
        return CODIGO_FALLO

    # LA MISMA BARRERA QUE EL RESTO DEL SITIO. Si alguna vez entra un documento
    # de identidad sin enmascarar, no se escribe el archivo. Vale más una
    # página que falta que una página que no se puede retirar.
    from vigia.documento import persona_sin_enmascarar

    sospechas = persona_sin_enmascarar(pagina)
    if sospechas:
        print("NO SE ESCRIBIO: la pagina trae documentos sin enmascarar:",
              file=sys.stderr)
        for s in sospechas[:5]:
            print(f"  {s}", file=sys.stderr)
        return CODIGO_FALLO

    salida = Path(o.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(pagina, encoding="utf-8")
    print(f"Archivo escrito en {salida}")
    print(f"  {len(datos.get('dias') or [])} días · "
          f"{len(datos.get('semanas') or [])} semanas · "
          f"{len(datos.get('meses') or [])} meses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
