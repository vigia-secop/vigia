"""La portada del sitio: `docs/index.html`, rehecha todos los días.

    python -m vigia.portada --json portada.json --salida docs/index.html

QUÉ ES, Y POR QUÉ ES DIARIA. El boletín semanal es lo que se publica en X una
vez por semana. La portada es otra cosa: es **el registro**. Quien entre un
martes tiene que ver el martes. Un año de portadas sin un solo hueco y sin una
sola cifra desmentida es lo único que convierte a Vigía de «una página con
gráficas» en un sitio que alguien cita.

DE DÓNDE SALE. Únicamente de `portada.sql`, que enmascara el documento de las
personas naturales **en la consulta**. Este módulo no tiene forma de sacar una
cédula a internet aunque yo me equivoque al dibujar: nunca la recibe.

EL ORDEN DE LA PÁGINA ES UNA POSICIÓN, NO UNA MAQUETA. La cobertura —qué parte
de lo firmado hoy no se puede mirar— va **antes** que cualquier ranking. Es lo
que casi nadie publica en Colombia y es lo que hace honesto todo lo que viene
después. Si algún día alguien mueve ese bloque más abajo «porque se ve mejor
arriba el ranking», ese día el sitio cambió de oficio.

LOS DÍAS SIN JORNADA NO SE MAQUILLAN. Un domingo tiene cuarenta contratos y no
es una caída del 99 %: es un domingo. La página lo dice con todas sus letras en
vez de enseñar una variación que asustaría a cualquiera. Es la misma lección
que dejó el 3 de septiembre, cuando los conteos crudos decían −45,7 % y la
diferencia real, descontando dos festivos, era del 1,0 %.

LAS ERRATAS SE MARCAN, NO SE ESCONDEN. Un contrato cuyo valor es exactamente
mil veces el presupuesto de su proceso sigue apareciendo en la tabla del día,
con su marca y con el presupuesto al lado. Quitarlo sería corregir la fuente a
ojo; publicarlo sin marca sería lo que estuvimos a punto de hacer el 11 de
septiembre con la Alcaldía de Tipacoque.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from vigia.calendario import dias_habiles, es_habil, nombre_del_festivo
from vigia.documento import persona_sin_enmascarar
from vigia import estilo
from vigia.estilo import BASE, tokens
from vigia.marca import TINTA, ojo
from vigia.panel import compacto, e, numero, titulo_es
from vigia.sitio import LEMA, TITULO, _dia_mes, _favicon, pct, variacion

CODIGO_USO = 2
CODIGO_FALLO = 1

DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes",
               "sábado", "domingo")

#: Lo específico de esta página. Va en una cadena normal y no en un f-string a
#: propósito: el CSS está lleno de llaves y duplicarlas a mano ya produjo dos
#: erratas en este proyecto. Aquí no hay nada que duplicar.
ESTILO = """
.estado { margin-top:14px; font-size:13px; color:var(--tinta-3);
  font-family:"IBM Plex Mono",ui-monospace,monospace; }
.festivo { margin-top:22px; border-left:3px solid var(--aviso);
  background:var(--aviso-flojo); border-radius:0 6px 6px 0; padding:14px 18px;
  font-family:"Source Serif 4",Georgia,serif; font-size:16px; color:var(--tinta-2); }
.festivo strong { color:var(--tinta); }
.tabla-env { overflow-x:auto; }
table.dia { border-collapse:collapse; width:100%; font-size:14px; }
table.dia th { text-align:left; font-size:11.5px; letter-spacing:.07em;
  text-transform:uppercase; color:var(--tinta-3); font-weight:600;
  padding:0 12px 8px 0; white-space:nowrap; }
table.dia td { padding:11px 12px 11px 0; border-top:1px solid var(--borde-sutil);
  vertical-align:top; }
table.dia td.n { font-family:"IBM Plex Mono",ui-monospace,monospace;
  text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
table.dia th.n { text-align:right; padding-right:0; }
table.dia td:last-child, table.dia th:last-child { padding-right:0; }
.doc { display:block; font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:12px; color:var(--tinta-3); margin-top:3px; }
.marca-fila { display:inline-block; font-size:11.5px; font-weight:600;
  padding:2px 8px; border-radius:11px; margin-top:6px; white-space:nowrap;
  background:var(--aviso-flojo); color:var(--aviso); }
.marca-fila.errata { border:1px solid var(--aviso); }
.serie { margin-top:6px; }
.serie svg { width:100%; height:auto; display:block; }
.calidad { list-style:none; margin:0; padding:0; }
.calidad li { display:flex; justify-content:space-between; gap:14px;
  padding:8px 0; border-bottom:1px solid var(--borde-sutil); font-size:14.5px; }
.calidad li:last-child { border-bottom:0; }
.calidad b { font-family:"IBM Plex Mono",ui-monospace,monospace; font-weight:600;
  font-variant-numeric:tabular-nums; }
.enlaces { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }
.enlaces a { display:inline-block; padding:7px 14px; border-radius:6px;
  border:1px solid var(--borde); text-decoration:none; font-size:14px;
  background:var(--superficie); }
"""


def _fecha(texto) -> date:
    return date.fromisoformat(str(texto)[:10])


def _dia_largo(d: date) -> str:
    return f"{DIAS_SEMANA[d.weekday()]} {_dia_mes(d)} de {d.year}"


def _nota_del_dia(d: date) -> str:
    """La frase que explica un día flojo antes de que alguien lo malinterprete.

    Cadena vacía cuando el día es hábil: no hay nada que explicar y una nota
    permanente se vuelve decorado.
    """
    festivo = nombre_del_festivo(d)
    if festivo:
        return (f"<strong>{e(festivo)}.</strong> Es festivo en Colombia, así que "
                "casi no hay jornada. Las cifras de hoy no se comparan con las "
                "de un día hábil, y aquí no se presentan como una caída.")
    if d.weekday() == 5:
        return ("<strong>Es sábado.</strong> Lo poco que aparece son "
                "publicaciones rezagadas, no actividad de un día de trabajo.")
    if d.weekday() == 6:
        return ("<strong>Es domingo.</strong> Lo poco que aparece son "
                "publicaciones rezagadas, no actividad de un día de trabajo.")
    return ""


def _serie_svg(serie: list) -> str:
    """Veintiocho días de contratos firmados.

    Un solo tono. Los días sin jornada hábil van rayados **con el mismo color**
    y no con otro: no son otra categoría, son el mismo dato en un día en que no
    se trabaja. La única cifra etiquetada directamente es el máximo, porque es
    la única que hace falta leer sin pasar el cursor.
    """
    filas = [f for f in (serie or []) if f.get("contratos") is not None]
    if not filas:
        return '<p class="vacio">Sin serie disponible.</p>'

    tope = max(int(f["contratos"]) for f in filas) or 1
    x0, x1, base, alto = 34.0, 556.0, 116.0, 92.0
    paso = (x1 - x0) / len(filas)
    ancho = min(14.0, paso - 4)

    def y(v: float) -> float:
        return base - (float(v) / tope) * alto

    piezas = [
        '<defs><pattern id="sinjornada" width="5" height="5" '
        'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<rect width="5" height="5" fill="var(--borde-sutil)"></rect>'
        '<line x1="0" y1="0" x2="0" y2="5" stroke="var(--acento)" '
        'stroke-width="2"></line></pattern></defs>'
    ]

    # Una sola línea de referencia, en un número redondo que la serie alcanza
    # de verdad y que no coincide con el máximo — si coincidiera, la línea no
    # añadiría nada y el lector tendría dos etiquetas diciendo lo mismo.
    candidatos = [m * mag for mag in (1, 10, 100, 1000, 10000, 100000)
                  for m in (1, 2, 5)]
    referencia = max([c for c in candidatos if c < tope] or [tope])
    y_ref = y(referencia)
    piezas.append(
        f'<line x1="{x0}" y1="{y_ref:.1f}" x2="{x1}" y2="{y_ref:.1f}" '
        'stroke="var(--borde)" stroke-width="1" stroke-dasharray="3 4"></line>'
        f'<text x="{x0 - 6}" y="{y_ref + 4:.1f}" text-anchor="end" font-size="10" '
        'font-family="IBM Plex Mono, monospace" fill="var(--tinta-3)">'
        f'{numero(referencia)}</text>'
        f'<text x="{x0 - 6}" y="{base + 4:.1f}" text-anchor="end" font-size="10" '
        'font-family="IBM Plex Mono, monospace" fill="var(--tinta-3)">0</text>'
    )

    i_max = max(range(len(filas)), key=lambda i: int(filas[i]["contratos"]))
    for i, f in enumerate(filas):
        d = _fecha(f["dia"])
        v = int(f["contratos"])
        x = x0 + i * paso + (paso - ancho) / 2
        yt = y(v)
        # El radio se recorta a la mitad de la altura para que una barra de dos
        # píxeles no se dibuje al revés.
        r = min(3.0, (base - yt) / 2)
        camino = (f"M {x:.1f} {base:.1f} L {x:.1f} {yt + r:.1f} "
                  f"Q {x:.1f} {yt:.1f} {x + r:.1f} {yt:.1f} "
                  f"L {x + ancho - r:.1f} {yt:.1f} "
                  f"Q {x + ancho:.1f} {yt:.1f} {x + ancho:.1f} {yt + r:.1f} "
                  f"L {x + ancho:.1f} {base:.1f} Z")
        habil = es_habil(d)
        relleno = "var(--acento)" if habil else "url(#sinjornada)"
        borde = "" if habil else ' stroke="var(--acento)" stroke-width=".8"'
        etiqueta = "" if habil else " · sin jornada"
        piezas.append(
            f'<path d="{camino}" fill="{relleno}"{borde}>'
            f'<title>{e(_dia_largo(d))}: {numero(v)} contratos{etiqueta}</title></path>'
        )
        if i == i_max:
            piezas.append(
                f'<text x="{x + ancho / 2:.1f}" y="{yt - 6:.1f}" text-anchor="middle" '
                'font-size="10.5" font-weight="600" font-family="IBM Plex Mono, monospace" '
                f'fill="var(--tinta-2)">{numero(v)}</text>'
            )
        if i % 7 == 0:
            piezas.append(
                f'<text x="{x + ancho / 2:.1f}" y="{base + 18:.1f}" text-anchor="middle" '
                'font-size="9.5" font-family="Archivo, sans-serif" '
                f'fill="var(--tinta-3)">{d.day}/{d.month}</text>'
            )

    piezas.append(
        f'<line x1="{x0}" y1="{base:.1f}" x2="{x1}" y2="{base:.1f}" '
        'stroke="var(--borde)" stroke-width="1"></line>'
    )
    return ('<div class="serie"><svg viewBox="0 0 576 140" role="img" '
            'aria-label="Contratos firmados por día en los últimos 28 días">'
            + "".join(piezas) + "</svg></div>")


def _sin_prefijo_de_orden(texto: str) -> str:
    """Quita el «a. » con que el SQL ordena los tramos.

    El prefijo existe para que Postgres ordene «menos de $5 M» antes que «$5 M
    a $20 M», que alfabéticamente irían al revés. Es andamiaje de la consulta,
    no algo que deba leer nadie.
    """
    if len(texto) > 3 and texto[0].isalpha() and texto[1:3] == ". ":
        return texto[3:]
    return texto


def _barras_simples(filas, clave, formato=compacto, limite=8, titulo=True,
                    clave_nombre="nombre") -> str:
    filas = (filas or [])[:limite]
    if not filas:
        return '<p class="vacio">Nada que mostrar en este día.</p>'
    tope = max(float(f[clave] or 0) for f in filas) or 1
    cuerpo = []
    for f in filas:
        ancho = 100 * float(f[clave] or 0) / tope
        nombre = _sin_prefijo_de_orden(str(f[clave_nombre]))
        cuerpo.append(
            '<li><span class="et">'
            f'{e(titulo_es(nombre) if titulo else nombre)}</span>'
            f'<span class="bar"><span style="width:{ancho:.1f}%"></span></span>'
            f'<span class="ci">{formato(f[clave])}</span></li>'
        )
    return f'<ul class="barras">{"".join(cuerpo)}</ul>'


def _tabla_de_erratas(filas) -> str:
    """Los contratos apartados del día, con las dos cifras y el enlace.

    **Apartar no puede significar tapar.** Sacarlos de las cifras evita
    publicar un total que no se puede sostener; no publicarlos en absoluto
    sería esconder algo que puede estar mal, y eso es exactamente lo que este
    proyecto le reprocha a los demás.

    Un valor que no cuadra con el presupuesto de su propio proceso vale la
    pena mirarlo. Casi seguro es una tecla de más — pero «casi seguro» no es
    «seguro», y quien decide eso no es esta página: es quien abra la ficha.

    Las dos cifras juntas son el argumento entero y no obligan a Vigía a
    acusar a nadie. El enlace deja que cualquiera lo compruebe en la fuente
    en vez de creernos.
    """
    filas = [f for f in (filas or []) if f.get("valor")]
    if not filas:
        return ""
    cuerpo = []
    for f in filas:
        enlace = str(f.get("enlace") or "")
        ident = f.get("id_contrato") or "—"
        ficha = (
            f'<a href="{e(enlace)}" target="_blank" rel="noopener">{e(ident)}</a>'
            if enlace.startswith("https://") else e(ident)
        )
        veces = f.get("veces")
        cuerpo.append(
            "<tr>"
            f'<td>{e(f.get("proveedor") or "—")}'
            f'<span class="doc">{e(titulo_es(f.get("entidad") or "—"))}</span>'
            f'<span class="doc">{ficha}</span></td>'
            f'<td class="n">{compacto(f.get("valor"))}'
            f'<span class="doc">publicado</span></td>'
            f'<td class="n">{compacto(f.get("presupuesto_del_proceso"))}'
            f'<span class="doc">presupuesto'
            + (f" · ×{numero(veces)}" if veces else "")
            + "</span></td>"
            "</tr>"
        )
    return (
        '<div class="tabla-scroll" style="margin-top:10px">'
        '<table class="tabla"><thead><tr>'
        "<th>Contratista, entidad y ficha</th>"
        '<th class="n">Valor</th><th class="n">Contra qué se comparó</th>'
        "</tr></thead><tbody>" + "".join(cuerpo) + "</tbody></table></div>"
    )


def _mayores(filas) -> str:
    filas = filas or []
    if not filas:
        return '<p class="vacio">No se firmó ningún contrato con valor este día.</p>'
    cuerpo = []
    for f in filas:
        ident = f.get("id_contrato") or ""
        celda_id = (f'<a href="{e(f["enlace"])}" target="_blank" rel="noopener">'
                    f'{e(ident)}</a>') if f.get("enlace") else e(ident)
        # LAS ERRATAS ×10ⁿ YA NO LLEGAN A ESTA TABLA. Hasta el 2026-09-16 se
        # quedaban aquí con una etiqueta al lado y, sobre todo, seguían dentro
        # de las cifras del día: con una sola de ellas «lo que se contrató
        # hoy» pasaba de $6,8 mil millones a $823,5 mil millones.
        #
        # `portada.sql` las aparta ahora, y el aviso de más abajo dice cuántas
        # apartó y cuánto sumaban. Marcar una fila no le quita el peso a un
        # total; sacarla, sí — siempre que se diga.
        marca = ""
        if f.get("es_union"):
            marca = '<span class="marca-fila">unión temporal · sin documento</span>'
        # El identificador del contrato va DEBAJO del contratista y no en una
        # cuarta columna: en un teléfono, o incluso a 800 px, cuatro columnas
        # con un `CO1.PCCNTR.9762242` dentro se salen de la página. Y es el
        # enlace lo que importa —lleva a la ficha oficial, que es donde este
        # dato se puede defender—, no que esté alineado a la derecha.
        cuerpo.append(
            "<tr>"
            f'<td>{e(f.get("proveedor") or "—")}'
            + (f'<span class="doc">{e(f["documento"])}</span>' if f.get("documento") else "")
            + f'<span class="doc">{celda_id}</span>'
            + marca + "</td>"
            f'<td>{e(titulo_es(f.get("entidad") or "—"))}'
            f'<span class="doc">{e(titulo_es(f.get("departamento") or "sin declarar"))}</span></td>'
            f'<td class="n">{compacto(f.get("valor"))}</td>'
            "</tr>"
        )
    return ('<div class="tabla-env"><table class="dia"><thead><tr>'
            "<th>Contratista y contrato</th><th>Entidad</th>"
            "<th class=\"n\">Valor</th></tr></thead>"
            f'<tbody>{"".join(cuerpo)}</tbody></table></div>')


def construir(datos: dict) -> str:
    d = _fecha(datos["dia"])
    c = datos["cifras"]
    comp = datos.get("comparacion") or {}
    cob = datos["cobertura"]
    ven = datos.get("ventana") or {}
    cal = datos.get("calidad") or {}
    generado = str(datos.get("generado_en", ""))[:16].replace("T", " ")

    v_contratos, cl_contratos = variacion(c["contratos"], comp.get("contratos"))
    v_valor, cl_valor = variacion(float(c["valor"] or 0),
                                  float(comp["valor"]) if comp.get("valor") else None)

    # La comparación es contra el MISMO DÍA DE LA SEMANA anterior, no contra
    # ayer: un lunes contra un domingo no significa nada. Y si uno de los dos
    # fue festivo y el otro no, la comparación tampoco vale y se dice.
    d_previo = _fecha(comp["dia_anterior"]) if comp.get("dia_anterior") else None
    comparable = bool(d_previo) and es_habil(d) == es_habil(d_previo)
    if not comparable:
        v_contratos = v_valor = "—"
        cl_contratos = cl_valor = "neutro"

    nota_dia = _nota_del_dia(d)
    aviso_dia = f'<p class="festivo">{nota_dia}</p>' if nota_dia else ""

    mediana, promedio = c.get("mediana"), c.get("promedio")
    brecha = ""
    if mediana and promedio and float(mediana) > 0:
        veces = float(promedio) / float(mediana)
        if veces >= 3:
            brecha = (
                f" El promedio es <strong>{veces:.0f} veces la mediana</strong>: "
                "unos pocos contratos grandes lo empujan. Por eso se publican "
                "los dos números y no solo uno.".replace(".0 veces", " veces")
            )

    erratas_hoy = int(cal.get("erratas_hoy") or 0)
    aviso_errata = ""
    if erratas_hoy:
        cuantos = (
            "Un contrato de hoy tiene" if erratas_hoy == 1
            else f"{numero(erratas_hoy)} contratos de hoy tienen"
        )
        valor_ap = cal.get("valor_erratas_hoy")
        aviso_errata = (
            '<p class="festivo"><strong>'
            f"{cuantos} un valor que es "
            "exactamente mil o diez mil veces el presupuesto de su propio "
            "proceso.</strong> Eso es la firma de una tecla de más, no la de un "
            f"sobrecosto. Sumaban {compacto(valor_ap)} y están <strong>fuera "
            "de todas las cifras de esta página</strong> — ese habría sido el "
            "tamaño del error. Vigía no corrige lo que la fuente publicó ni "
            "adivina el valor verdadero: lo aparta, lo dice, y lo deja aquí "
            "abajo con el enlace a la ficha oficial.</p>"
            + _tabla_de_erratas(datos.get("erratas"))
        )

    primera, ultima = ven.get("primer_contrato"), ven.get("ultimo_contrato")
    dias_de_historia = ""
    if primera and ultima:
        dias_de_historia = f"{(_fecha(ultima) - _fecha(primera)).days + 1} días"

    meta = (f"{numero(c['contratos'])} contratos por {compacto(c['valor'])} "
            f"el {_dia_largo(d)}. {numero(c['entidades'])} entidades. "
            "Y qué parte de eso no se puede ver.")[:200]

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITULO} · {_dia_largo(d)}</title>
<meta name="description" content="{e(meta)}">
<link rel="icon" href="data:image/svg+xml,{_favicon()}">
<meta property="og:type" content="website">
<meta property="og:title" content="{TITULO} · {_dia_largo(d)}">
<meta property="og:description" content="{e(meta)}">
<meta property="og:image" content="img/vigia-card.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{TITULO} · {_dia_largo(d)}">
<meta name="twitter:description" content="{e(meta)}">
<meta name="twitter:image" content="img/vigia-card.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
{tokens()}
{BASE}
{estilo.NAV_CSS}
{ESTILO}
</style>
</head>
<body>
<div class="env">

  <header class="top">
    <div class="marca">{ojo(alto=54, color=TINTA)}<h1>{TITULO}</h1></div>
    <p class="lema">{LEMA}</p>
    <p class="per">{_dia_largo(d)}</p>
    <p class="estado">Página rehecha sola · datos al {e(generado)} ·
      histórico de {e(dias_de_historia or "—")}</p>
    {estilo.menu("index.html")}
  </header>

  {aviso_dia}

  <div class="cifras">
    <div class="caja"><div class="rot">Contratos firmados</div>
      <div class="dat">{numero(c["contratos"])}</div>
      <div class="var {cl_contratos}">{v_contratos}</div>
      <div class="pie">{'contra el mismo día de la semana pasada'
                        if comparable else 'sin comparación válida esta vez'}</div></div>
    <div class="caja"><div class="rot">Valor</div>
      <div class="dat">{compacto(c["valor"])}</div>
      <div class="var {cl_valor}">{v_valor}</div>
      <div class="pie">mediana {compacto(mediana)} · promedio {compacto(promedio)}</div></div>
    <div class="caja"><div class="rot">Entidades</div>
      <div class="dat">{numero(c["entidades"])}</div>
      <div class="pie">firmaron hoy</div></div>
    <div class="caja"><div class="rot">Contratistas</div>
      <div class="dat">{numero(c["proveedores"])}</div>
      <div class="pie">identidades distintas</div></div>
  </div>

  <h2>Qué parte de esto no se puede ver</h2>
  <p class="sub">Va primero a propósito. Es lo que casi nadie publica.</p>
  <div class="tarjeta alcance">
    <p style="margin:0">De los <strong>{numero(cob["contratos"])}</strong> contratos
    de hoy, <strong>{numero(cob["con_identidad"])}</strong>
    ({pct(cob["con_identidad"], cob["contratos"])}) traen una identidad de
    contratista con la que se puede trabajar. El resto no, y así se reparte:</p>
    <ul>
      <li><strong>{numero(cob["uniones"])}</strong> uniones temporales y consorcios
        sin documento — {compacto(cob["valor_uniones"])},
        {pct(cob["valor_uniones"], cob["valor"])} del valor del día. Cada una
        tiene identidad propia y provisional: <strong>ninguna medida de
        concentración las ve</strong>.</li>
      <li><strong>{numero(cob["sin_razon_social"])}</strong> contratos con documento
        pero sin razón social — {compacto(cob["valor_sin_razon_social"])}. La
        fuente los publica literalmente como «No Definido».</li>
      <li><strong>{numero(cob["sin_departamento"])}</strong> sin departamento
        utilizable, que no entran en el mapa de abajo.</li>
    </ul>
  </div>

  <h2>Los contratos más grandes de hoy</h2>
  <p class="sub">El NIT de una empresa va completo. Las personas naturales
    salen sin nombre y con el documento enmascarado.{brecha}</p>
  {aviso_errata}
  {_mayores(datos.get("mayores"))}

  <h2>Dónde se firmó</h2>
  <p class="sub">Por valor. El territorio sale del código DIVIPOLA de la fuente.</p>
  {_barras_simples(datos.get("departamentos"), "valor")}

  <h2>Bajo qué modalidad</h2>
  <p class="sub">Por número de contratos. Los que no tienen proceso enlazado se
    cuentan aparte en vez de repartirse.</p>
  {_barras_simples(datos.get("modalidades"), "contratos", formato=numero)}

  <h2>De qué tamaño</h2>
  <p class="sub">Por número de contratos en cada tramo.</p>
  {_barras_simples(datos.get("tramos"), "contratos", formato=numero, titulo=False,
                   clave_nombre="tramo")}

  <h2>Los últimos 28 días</h2>
  <p class="sub">Los días rayados no son días flojos: son días sin jornada
    hábil. Todo lo demás de esta página se compara por día hábil.</p>
  {_serie_svg(datos.get("serie"))}

  <h2>La calidad del dato, publicada aquí mismo</h2>
  <p class="sub">Un sitio que esconde sus defectos no merece que le crean los
    aciertos.</p>
  <div class="tarjeta">
    <ul class="calidad">
      <li><span>Erratas ×10ⁿ de hoy, fuera de todas las cifras</span><b>{numero(cal.get("erratas_hoy"))}</b></li>
      <li><span>Erratas ×10ⁿ en todo el histórico</span><b>{numero(cal.get("erratas_ventana"))}</b></li>
      <li><span>Valores imposibles, fuera de todos los totales</span><b>{numero(cal.get("imposibles"))}</b></li>
      <li><span>Contratos de hoy sin su proceso enlazado</span><b>{numero(cal.get("huerfanos_hoy"))}</b></li>
      <li><span>Histórico ingerido</span><b>{numero(ven.get("contratos"))} contratos</b></li>
    </ul>
  </div>

  <h2>Banderas</h2>
  <p class="sub">Ninguna encendida, y conviene decir por qué.</p>
  <div class="nota" style="margin-top:0">
    <p style="margin:0">Vigía midió tres posibles señales y <strong>las tres
    describían la mayoría del país</strong>: el 52,8 % de los procesos
    competitivos termina con un solo oferente y el 62,4 % adjudica entre el
    99,90 % y el 100 % del presupuesto. Marcar eso no es una señal: es el
    fondo.</p>
    <p style="margin:12px 0 0">Hay una cuarta viva —la concentración por
    proveedor, donde solo el 2,1 % de las entidades supera el 90 %— y le falta
    historia para poder publicarla sin señalar a nadie con una foto de dos
    meses. <strong>Cuando exista un indicador que aguante una medición, se
    publicará junto con su calibración.</strong> Antes no.</p>
  </div>

  <footer>
    Datos de SECOP vía datos.gov.co · método abierto · cualquiera puede rehacer
    las cuentas.<br>
    Vigía publica estadística descriptiva sobre datos públicos. No señala a
    nadie ni afirma que exista una conducta contraria a la ley.
  </footer>
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vigia.portada")
    p.add_argument("--json", default="portada.json")
    p.add_argument("--salida", default="docs/index.html")
    o = p.parse_args(argv)

    origen = Path(o.json)
    if not origen.exists():
        print(f"no encuentro {origen}", file=sys.stderr)
        return CODIGO_USO
    datos = json.loads(origen.read_text(encoding="utf-8"))
    for clave in ("dia", "cifras", "cobertura"):
        if clave not in datos:
            print(f"a {origen} le falta la sección «{clave}»", file=sys.stderr)
            return CODIGO_FALLO

    pagina = construir(datos)

    # La última comprobación, y se hace sobre el HTML ya armado y no sobre los
    # datos: es lo que de verdad se sube. El patrón no es «ninguna cadena de
    # dígitos» —eso ahogaría todos los NIT, que son justo lo que hay que
    # publicar— sino «ningún documento de PERSONA NATURAL escrito entero».
    escapados = persona_sin_enmascarar(pagina)
    if escapados:
        print("ABORTADO: la portada lleva documento(s) de persona natural sin "
              f"enmascarar ({len(escapados)}). No se escribió nada.",
              file=sys.stderr)
        return CODIGO_FALLO

    salida = Path(o.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(pagina, encoding="utf-8")
    d = _fecha(datos["dia"])
    print(f"Portada escrita en {salida.resolve()}")
    print(f"  {_dia_largo(d)} · {numero(datos['cifras']['contratos'])} contratos "
          f"· {compacto(datos['cifras']['valor'])}")
    if not es_habil(d):
        print("  (dia sin jornada habil: la pagina lo dice en vez de mostrar una caida)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
