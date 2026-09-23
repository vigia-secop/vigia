"""Panel de Vigía: convierte `panel.json` en una página que se puede leer.

    python -m vigia.panel                 # lee panel.json, escribe panel.html
    python -m vigia.panel --json otro.json --salida otro.html

No consulta la base ni la fuente: lee el JSON que produjo `panel.sql`. Esa
separación es a propósito —el que consulta y el que dibuja son dos trabajos— y
además permite guardar el JSON de cada Ciclo y volver a dibujarlo después.

LO QUE ESTE PANEL NO HACE, Y NO ES UN OLVIDO. No emite alertas. No dice que
nada sea irregular. Muestra la forma de la contratación de una ventana y, sobre
todo, **cuánto de esa ventana queda fuera del alcance de cada medición**. Las
Reglas de la épica 4 vendrán después; hasta que existan y estén calibradas, un
panel que señalara con el dedo estaría inventando.

Por eso el bloque de cobertura va SEGUNDO, antes que cualquier ranking: un
ranking de contratistas sin saber sobre qué parte del universo se calculó es
justo la clase de número que se lee mal.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

from vigia import estilo
from vigia.documento import escribir as documento

CODIGO_USO = 2
CODIGO_FALLO = 1

#: Paleta categórica de `orden`, validada con el comprobador de la guía de
#: visualización (banda de luminosidad, piso de croma, separación para daltonismo
#: y contraste sobre el fondo, en claro y en oscuro). No se elige por gusto: se
#: comprobó. Cada color va pegado a UNA categoría y no rota nunca.
COLOR_ORDEN = {
    "TERRITORIAL": ("#0091A8", "#22A0B8"),
    "NACIONAL": ("#B0561B", "#CE7830"),
    "CORPORACION AUTONOMA": ("#5B4B8A", "#7C71C9"),
    "SIN DECLARAR": ("#6E7A7D", "#8A9497"),
}

ETIQUETA_ORDEN = {
    "TERRITORIAL": "Territorial",
    "NACIONAL": "Nacional",
    "CORPORACION AUTONOMA": "Corporación Autónoma",
    "SIN DECLARAR": "Sin declarar",
}

#: Nombres que la fuente escribe cuando la entidad no diligenció la razón
#: social. No invalidan la identidad —el documento puede estar perfecto— pero
#: mostrarlos como si fueran el nombre de un contratista engaña al que lee.
NOMBRES_CENTINELA = {"NO DEFINIDO", "SIN DESCRIPCION", "NO DEFINIDA", "NO APLICA"}


def pesos(valor) -> str:
    """Un valor en pesos, escrito como se escribe la plata en Colombia."""
    if valor is None:
        return "—"
    return "$" + f"{float(valor):,.0f}".replace(",", ".")


def _colombiano(texto: str) -> str:
    """Pasa un número con formato inglés a colombiano: miles con punto,
    decimales con coma. Se hace en dos tiempos porque un `replace` directo
    convertiría el punto decimal en punto de miles."""
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def compacto(valor) -> str:
    """Pesos en escala legible. La contratación pública va de un millón a
    cientos de miles de millones; en cifra completa no se compara nada."""
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


def porcentaje(parte, total) -> str:
    if not total:
        return "—"
    return f"{100 * float(parte) / float(total):.1f} %".replace(".", ",")


def e(texto) -> str:
    return html.escape(str(texto)) if texto is not None else ""


def nombre_legible(nombre, identificador=None) -> str:
    """El nombre del proveedor, o una marca honesta si la fuente no lo trajo.

    El segundo parámetro se llama `identificador` y no `documento` para no
    tapar la función `documento` importada arriba. Hoy no rompería nada; es
    una trampa puesta para quien edite esto mañana.
    """
    limpio = (nombre or "").strip()
    if not limpio or limpio.upper() in NOMBRES_CENTINELA:
        if identificador:
            return f"(sin razón social declarada) · {identificador}"
        return "(sin razón social declarada)"
    return limpio


def _barra(fraccion: float) -> str:
    ancho = max(0.0, min(1.0, fraccion)) * 100
    return f'<span class="barra"><span class="barra-relleno" style="width:{ancho:.2f}%"></span></span>'


def _filas_proveedores(datos: dict, completo: bool = False) -> str:
    filas = datos.get("proveedores") or []
    if not filas:
        return '<p class="vacio">Ningún contrato con identidad de proveedor en esta ventana.</p>'
    tope = max(float(f["valor"] or 0) for f in filas) or 1
    cuerpo = []
    for f in filas:
        cuerpo.append(
            "<tr>"
            f'<td class="nom">{e(nombre_legible(f.get("nombre"), documento(f.get("tipo"), f.get("numero"), completo=completo)))}'
            f'<span class="doc">{e(documento(f.get("tipo"), f.get("numero"), completo=completo))}</span>'
            "</td>"
            f'<td class="num">{numero(f["contratos"])}</td>'
            f'<td class="num">{numero(f["entidades"])}</td>'
            f'<td class="val" title="{pesos(f["valor"])}">{compacto(f["valor"])}'
            f'{_barra(float(f["valor"] or 0) / tope)}</td>'
            "</tr>"
        )
    return (
        '<div class="tabla-scroll"><table class="tabla">'
        "<thead><tr><th>Proveedor</th><th class=\"num\">Contratos</th>"
        "<th class=\"num\">Entidades</th><th class=\"val\">Valor</th></tr></thead>"
        f"<tbody>{''.join(cuerpo)}</tbody></table></div>"
    )


def _filas_uniones(datos: dict) -> str:
    filas = datos.get("uniones_temporales") or []
    if not filas:
        return '<p class="vacio">Ninguna unión temporal sin documento en esta ventana.</p>'
    cuerpo = []
    for f in filas:
        cuerpo.append(
            "<tr>"
            f'<td class="nom">{e(nombre_legible(f.get("nombre")))}</td>'
            f'<td>{e(f.get("entidad") or "—")}</td>'
            f'<td>{e(f.get("departamento") or "—")}</td>'
            f'<td><span class="pill">{e(f.get("estado") or "—")}</span></td>'
            f'<td class="val">{compacto(f.get("valor"))}</td>'
            "</tr>"
        )
    return (
        '<div class="tabla-scroll"><table class="tabla">'
        "<thead><tr><th>Unión temporal o consorcio</th><th>Entidad</th>"
        "<th>Departamento</th><th>Estado</th><th class=\"val\">Valor</th></tr></thead>"
        f"<tbody>{''.join(cuerpo)}</tbody></table></div>"
    )


def _barra_ordenes(datos: dict) -> str:
    filas = datos.get("ordenes") or []
    total = sum(float(f["valor"] or 0) for f in filas) or 1
    segmentos, leyenda = [], []
    for f in filas:
        clave = f["orden"]
        pct = 100 * float(f["valor"] or 0) / total
        etiqueta = ETIQUETA_ORDEN.get(clave, clave)
        segmentos.append(
            f'<span class="seg" style="width:{pct:.2f}%;--c:var(--orden-{_slug(clave)})" '
            f'title="{e(etiqueta)}: {pesos(f["valor"])} en {numero(f["contratos"])} contratos"></span>'
        )
        leyenda.append(
            '<li><span class="punto" style="background:var(--orden-'
            f'{_slug(clave)})"></span><span class="ley-nom">{e(etiqueta)}</span>'
            f'<span class="ley-val">{compacto(f["valor"])}</span>'
            f'<span class="ley-sec">{numero(f["contratos"])} contratos · '
            f'{porcentaje(f["valor"], total)} del valor</span></li>'
        )
    return (
        f'<div class="apilada">{"".join(segmentos)}</div>'
        f'<ul class="leyenda">{"".join(leyenda)}</ul>'
    )


def _slug(texto: str) -> str:
    return texto.lower().replace(" ", "-")


#: Palabras que en español NO se capitalizan dentro de un nombre propio.
#: `str.title()` produce «Valle Del Cauca» y «Bogota, D.C.» se le desarma.
_ENLACES = {"de", "del", "la", "las", "los", "y", "e"}


def titulo_es(nombre: str) -> str:
    """Capitaliza un nombre propio como se escribe en español."""
    palabras = nombre.split()
    salida = []
    for i, palabra in enumerate(palabras):
        bajo = palabra.lower()
        if "." in palabra:          # D.C., S.A.S.: se dejan tal cual
            salida.append(palabra)
        elif i > 0 and bajo in _ENLACES:
            salida.append(bajo)
        else:
            salida.append(palabra.capitalize())
    return " ".join(salida)


def _barras_departamentos(datos: dict, tope_filas: int = 12) -> str:
    filas = (datos.get("departamentos") or [])[:tope_filas]
    if not filas:
        return ""
    tope = max(float(f["valor"] or 0) for f in filas) or 1
    items = []
    for f in filas:
        pct = 100 * float(f["valor"] or 0) / tope
        sin = f["codigo"] == "--"
        clase = ' class="sin"' if sin else ""
        items.append(
            f"<li{clase}>"
            f'<span class="cod">{e(f["codigo"])}</span>'
            f'<span class="dep">{e(titulo_es(f["nombre"]))}</span>'
            f'<span class="pista"><span class="marca" style="width:{pct:.2f}%"></span></span>'
            f'<span class="cifra" title="{pesos(f["valor"])}">{compacto(f["valor"])}</span>'
            f'<span class="cuenta">{numero(f["contratos"])}</span>'
            "</li>"
        )
    return f'<ul class="barras">{"".join(items)}</ul>'


def _filas_entidades(datos: dict) -> str:
    filas = (datos.get("entidades") or [])[:15]
    if not filas:
        return ""
    cuerpo = []
    for f in filas:
        cuerpo.append(
            "<tr>"
            f'<td class="nom">{e(f["nombre"])}<span class="doc">NIT {e(f.get("nit") or "—")}</span>'
            "</td>"
            f'<td class="num">{numero(f["contratos"])}</td>'
            f'<td class="num">{numero(f.get("proveedores"))}</td>'
            f'<td class="val">{compacto(f["valor"])}</td>'
            "</tr>"
        )
    return (
        '<div class="tabla-scroll"><table class="tabla">'
        "<thead><tr><th>Entidad</th><th class=\"num\">Contratos</th>"
        "<th class=\"num\">Proveedores</th><th class=\"val\">Valor</th></tr></thead>"
        f"<tbody>{''.join(cuerpo)}</tbody></table></div>"
    )


def _filas_mayores(datos: dict) -> str:
    filas = (datos.get("contratos_mayores") or [])[:10]
    if not filas:
        return ""
    cuerpo = []
    for f in filas:
        marca = (
            '<span class="pill pill-ut">unión temporal</span>'
            if f.get("es_union_temporal") else ""
        )
        # LAS ERRATAS x10^n YA NO LLEGAN HASTA AQUÍ. El 2026-09-11 encabezaba
        # esta tabla la ALCALDÍA DE TIPACOQUE —unos 3.000 habitantes— con
        # $431.340.000.000, contra un presupuesto de $431.340.000: el mismo
        # número con tres ceros de más. Durante cuatro días se marcó la fila y
        # se dejó donde estaba. No alcanzó: un renglón marcado en un ranking
        # sigue siendo un renglón en un ranking, y el puesto es lo que se lee.
        #
        # Desde el 2026-09-15 `panel.sql` las aparta del universo publicable,
        # igual que los valores imposibles, y declara en cobertura cuántas
        # apartó y cuánto sumaban. Aquí no queda nada que marcar.
        cuerpo.append(
            "<tr>"
            f'<td class="nom">{e(nombre_legible(f.get("proveedor")))} {marca}'
            f'<span class="doc">{e(f["id_contrato"])}</span></td>'
            f'<td>{e(f.get("entidad") or "—")}</td>'
            f'<td>{e(titulo_es(f.get("departamento") or "—"))}</td>'
            f'<td class="val">{compacto(f.get("valor"))}</td>'
            "</tr>"
        )
    nota = ""
    return (
        '<div class="tabla-scroll"><table class="tabla">'
        "<thead><tr><th>Proveedor</th><th>Entidad</th><th>Departamento</th>"
        "<th class=\"val\">Valor</th></tr></thead>"
        f"<tbody>{''.join(cuerpo)}</tbody></table></div>{nota}"
    )


def _cobertura(datos: dict) -> str:
    c = datos["cobertura"]
    total = c["contratos"] or 1
    real = c["con_proveedor_real"]
    ut = c["union_temporal_sin_documento"]
    sin = c["sin_identidad_de_proveedor"]

    def medida(titulo, dentro, fuera, explica, detalle=""):
        pct = 100 * dentro / total
        return (
            '<div class="medida">'
            f'<div class="medida-cab"><h3>{titulo}</h3>'
            f'<span class="medida-pct">{porcentaje(dentro, total)}</span></div>'
            f'<span class="barra barra-ancha"><span class="barra-relleno" '
            f'style="width:{pct:.2f}%"></span></span>'
            f'<p class="medida-txt">{explica}</p>'
            + (f'<p class="medida-det">{detalle}</p>' if detalle else "")
            + "</div>"
        )

    return (
        '<div class="medidas">'
        + medida(
            "Concentración por proveedor",
            real, total - real,
            f"<strong>{numero(real)}</strong> de {numero(total)} contratos tienen "
            "identidad de proveedor con la que se puede medir concentración.",
            f"Fuera: {numero(ut)} de unión temporal o consorcio sin documento "
            f"({compacto(c['valor_union_temporal'])}, "
            f"{porcentaje(c['valor_union_temporal'], datos['ventana']['valor'])} del valor) "
            f"y {numero(sin)} sin identidad ninguna.",
        )
        + medida(
            "Cruce con el Proceso",
            c["enlazados_a_proceso"], c["huerfanos"],
            f"<strong>{numero(c['enlazados_a_proceso'])}</strong> contratos encontraron "
            "su Proceso. Sin ese cruce no hay modalidad, ni fecha de publicación, "
            "ni plazo que medir.",
            f"Huérfanos: {numero(c['huerfanos'])} traen la llave y no encontraron "
            "Proceso — casi siempre porque el Proceso es anterior a la ventana ingerida.",
        )
        + medida(
            "Corte territorial",
            total - c["sin_departamento"], c["sin_departamento"],
            f"<strong>{numero(total - c['sin_departamento'])}</strong> contratos tienen "
            "código DIVIPOLA de departamento.",
            f"Sin territorio: {numero(c['sin_departamento'])}. El municipio va con "
            "nombre y sin código: «Argelia» son tres municipios distintos.",
        )
        + _fuera_de_escala(c, total)
        + _errata_potencia_diez(c, total, datos.get("erratas"))
        + "</div>"
    )


def _fuera_de_escala(c: dict, total: int) -> str:
    """El aviso de los valores que no pueden ser ciertos.

    **Solo aparece cuando hay alguno.** Un aviso permanente que casi siempre
    dice cero se vuelve parte del decorado y deja de leerse el día que importa;
    y además insinuaría que la fuente está peor de lo que está.

    Va dentro del bloque de cobertura y no en un ranking porque no es un
    hallazgo sobre nadie: es un defecto de la fuente que nos obliga a decir
    sobre cuánto NO estamos calculando. Se enseña el valor declarado a
    propósito — es el tamaño que tendría la mentira si no los excluyéramos.
    """
    cuantos = c.get("valor_fuera_de_escala") or 0
    if not cuantos:
        return ""
    declarado = c.get("valor_declarado_fuera_de_escala") or 0
    return (
        '<div class="medida medida-aviso">'
        '<div class="medida-cab"><h3>Valores que no pueden ser ciertos</h3>'
        f'<span class="medida-pct">{numero(cuantos)}</span></div>'
        '<p class="medida-txt"><strong>'
        f"{numero(cuantos)} de {numero(total)} contratos"
        '</strong> declaran un valor por encima de los 100 billones de pesos: la '
        "quinta parte del presupuesto nacional de un año, en un solo contrato. "
        "No puede ser cierto. <strong>Están fuera de todos los totales y "
        "rankings de esta página.</strong></p>"
        '<p class="medida-det">Suman '
        f"{compacto(declarado)} tal como la fuente los publica — ese es el tamaño "
        "que tendría el error si se sumaran. Vigía no corrige la fuente ni adivina "
        "el valor verdadero: los aparta y lo dice. Se listan en «Qué revisar "
        "primero».</p></div>"
    )


def _errata_potencia_diez(c: dict, total: int, erratas: list | None = None) -> str:
    """Los contratos tecleados con ceros de más, y por qué no están en la tabla.

    **Solo aparece cuando hay alguno**, por la misma razón que el aviso de
    arriba: un cartel permanente que casi siempre dice cero deja de leerse.

    Este aviso es el que reemplazó a una etiqueta. Del 11 al 15 de septiembre
    de 2026 el contrato de Tipacoque —$431.340.000.000 contra un presupuesto
    de $431.340.000— se quedó dentro de los rankings con una marca al lado.
    Una marca no le quita el puesto a nadie, y el puesto es lo que se lee: la
    fundación que lo firmó apareció segunda entre los proveedores del país.

    Así que ahora se apartan, como los valores imposibles, y se dice aquí
    cuántos son y cuánto sumaban. No se corrige la fuente ni se adivina el
    valor verdadero — eso le toca a quien abra la ficha en el SECOP.

    **APARTAR NO ES DEJAR DE PUBLICAR.** Un aviso que dijera solo «4 contratos,
    $816,6 mil millones» escondería el hallazgo detrás de un conteo: quien lee
    no sabría a quién mirar, y eso es justamente lo que sirve. Por eso debajo
    van **todas**, una por una, con nombre, las dos cifras y el enlace al
    SECOP. Un valor mal tecleado en una base pública es algo que vale la pena
    mirar; esconderlo detrás de un número sería el mismo error que sumarlo.

    Lo que cambia respecto de tenerlo en el ranking no es el dato, es la
    afirmación. En «Proveedores por valor» el renglón dice *este es de los que
    más contrata del país*, y eso es falso. Aquí dice *este número está mal
    tecleado, ve y abre la ficha*, que es lo único que se puede sostener.
    """
    cuantos = c.get("errata_potencia_diez") or 0
    if not cuantos:
        return ""
    declarado = c.get("valor_declarado_errata") or 0
    fichas = "esa ficha" if cuantos == 1 else "esas fichas"
    return (
        '<div class="medida medida-aviso">'
        '<div class="medida-cab"><h3>Contratos con un cero de más</h3>'
        f'<span class="medida-pct">{numero(cuantos)}</span></div>'
        '<p class="medida-txt"><strong>'
        f"{numero(cuantos)} de {numero(total)} contratos"
        f"</strong> declaran un valor que es <strong>exactamente</strong> mil o "
        "diez mil veces el presupuesto oficial de su propio proceso. Esa es la "
        "firma de una tecla de más, no la de un sobrecosto. <strong>Están fuera "
        "de todos los totales y rankings de esta página.</strong></p>"
        '<p class="medida-det">Suman '
        f"{compacto(declarado)} tal como la fuente los publica. El mayor de "
        "ellos llegó a encabezar esta misma página antes de que se detectara. "
        "<strong>Aquí están todos</strong>, con las dos cifras y el enlace a la "
        f"ficha oficial: hasta que alguien no abra {fichas} en el SECOP, Vigía "
        "no afirma cuál es el valor verdadero.</p>"
        + _tabla_de_erratas(erratas)
        + "</div>"
    )


def _tabla_de_erratas(erratas: list | None) -> str:
    """Los contratos apartados, uno por uno, con las dos cifras y el enlace.

    Este bloque es la prueba de que apartar no es tapar, y es lo que el aviso
    de arriba promete. Sin él la página diría «4 contratos» y el lector se
    quedaría sin lo único accionable: cuáles, de quién, y dónde verlos.

    **Las dos cifras juntas son el argumento entero.** $431.340.000.000 al
    lado de $431.340.000 se explica solo, sin que Vigía tenga que acusar a
    nadie — y el enlace deja que cualquiera lo compruebe en la fuente en vez
    de creernos.

    Van todas, no una muestra: son pocas por definición, y escoger cuál
    mostrar sería volver a decidir por el lector.
    """
    filas = [f for f in (erratas or []) if f.get("valor")]
    if not filas:
        return ""
    cuerpo = []
    for f in filas:
        enlace = str(f.get("enlace") or "")
        ficha = (
            f'<a href="{e(enlace)}" target="_blank" rel="noopener noreferrer">'
            f'{e(f.get("id_contrato") or "ver ficha")}</a>'
            if enlace.startswith("https://") else e(f.get("id_contrato") or "—")
        )
        veces = f.get("veces")
        cuerpo.append(
            "<tr>"
            f'<td class="nom">{e(f.get("entidad") or "—")}'
            f'<span class="doc">{e(nombre_legible(f.get("proveedor")))}</span>'
            f'<span class="doc">{ficha}</span></td>'
            f'<td class="val">{compacto(f.get("valor"))}</td>'
            f'<td class="val">{compacto(f.get("presupuesto_del_proceso"))}</td>'
            f'<td class="num">{("×" + numero(veces)) if veces else "—"}</td>'
            "</tr>"
        )
    return (
        '<div class="tabla-scroll" style="margin-top:12px">'
        '<table class="tabla"><thead><tr>'
        "<th>Entidad, contratista y ficha</th>"
        '<th class="val">Valor publicado</th>'
        '<th class="val">Presupuesto del proceso</th>'
        '<th class="num">Veces</th>'
        "</tr></thead><tbody>" + "".join(cuerpo) + "</tbody></table></div>"
    )


def construir(datos: dict, *, completo: bool = False) -> str:
    v = datos["ventana"]
    generado = str(datos.get("generado_en", ""))[:19].replace("T", " ")
    c = datos["cobertura"]

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panel de Vigía SECOP</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
:root {{
  --papel:      #EEF1F1;
  --superficie: #FFFFFF;
  --borde:      #D3DADB;
  --borde-sutil:#E4E9E9;
  --tinta:      #0E1719;
  --tinta-2:    #3A4A4D;
  --tinta-3:    #6B7B7E;
  --acento:     #0091A8;
  --acento-flojo:#DCEFF3;
  --aviso:      #A8620F;
  --aviso-flojo:#F6E9D8;
  --orden-territorial:          #0091A8;
  --orden-nacional:             #B0561B;
  --orden-corporacion-autonoma: #5B4B8A;
  --orden-sin-declarar:         #6E7A7D;
  --sombra: 0 1px 2px rgba(14,23,25,.05), 0 8px 24px -16px rgba(14,23,25,.25);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --papel:      #10171A;
    --superficie: #171F22;
    --borde:      #2B383C;
    --borde-sutil:#212B2E;
    --tinta:      #E8EDED;
    --tinta-2:    #AEBDBF;
    --tinta-3:    #7C8C8F;
    --acento:     #22A0B8;
    --acento-flojo:#123239;
    --aviso:      #D9903F;
    --aviso-flojo:#31261A;
    --orden-territorial:          #22A0B8;
    --orden-nacional:             #CE7830;
    --orden-corporacion-autonoma: #7C71C9;
    --orden-sin-declarar:         #8A9497;
    --sombra: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
  }}
}}
:root[data-theme="dark"] {{
  --papel:      #10171A;
  --superficie: #171F22;
  --borde:      #2B383C;
  --borde-sutil:#212B2E;
  --tinta:      #E8EDED;
  --tinta-2:    #AEBDBF;
  --tinta-3:    #7C8C8F;
  --acento:     #22A0B8;
  --acento-flojo:#123239;
  --aviso:      #D9903F;
  --aviso-flojo:#31261A;
  --orden-territorial:          #22A0B8;
  --orden-nacional:             #CE7830;
  --orden-corporacion-autonoma: #7C71C9;
  --orden-sin-declarar:         #8A9497;
  --sombra: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
}}

*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--papel);
  color: var(--tinta);
  font-family: Archivo, "Segoe UI", system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}}
.envoltura {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 72px; }}

/* ---------------------------------------------------------- encabezado */
.cabecera {{
  display: flex; flex-wrap: wrap; gap: 16px 32px;
  align-items: baseline; justify-content: space-between;
  padding-bottom: 20px; border-bottom: 2px solid var(--tinta);
}}
.marca {{ display: flex; flex-direction: column; gap: 2px; }}
.marca h1 {{
  margin: 0; font-size: 30px; font-weight: 700; letter-spacing: -.02em;
  text-wrap: balance;
}}
.marca .sub {{
  font-family: "Source Serif 4", Georgia, serif; font-size: 15px;
  color: var(--tinta-2); max-width: 54ch;
}}
.sello {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 12px; color: var(--tinta-3); text-align: right;
  display: flex; flex-direction: column; gap: 2px;
}}
.sello b {{ color: var(--tinta-2); font-weight: 500; }}

/* --------------------------------------------------------------- cifras */
.cifras {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1px; background: var(--borde); border: 1px solid var(--borde);
  margin: 0 0 40px; border-top: none;
}}
.cifra-caja {{ background: var(--superficie); padding: 18px 20px 16px; }}
.cifra-caja .rot {{
  font-size: 11px; text-transform: uppercase; letter-spacing: .09em;
  color: var(--tinta-3); font-weight: 600;
}}
.cifra-caja .dat {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 26px; font-weight: 500; letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; margin-top: 4px;
}}
.cifra-caja .pie {{ font-size: 12.5px; color: var(--tinta-3); }}

/* -------------------------------------------------------------- bandas */
section {{ margin: 0 0 44px; }}
.banda-cab {{ margin-bottom: 14px; }}
.banda-cab h2 {{
  margin: 0; font-size: 13px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .1em; color: var(--acento);
}}
.banda-cab p {{
  margin: 6px 0 0; font-family: "Source Serif 4", Georgia, serif;
  font-size: 14.5px; color: var(--tinta-2); max-width: 68ch;
}}
.tarjeta {{
  background: var(--superficie); border: 1px solid var(--borde);
  padding: 20px; box-shadow: var(--sombra);
}}

/* ------------------------------------------------------------ cobertura */
.alcance {{ border-left: 3px solid var(--acento); }}
.medidas {{ display: grid; gap: 26px; }}
@media (min-width: 780px) {{ .medidas {{ grid-template-columns: repeat(3, 1fr); gap: 28px; }} }}
.medida-cab {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }}
.medida-cab h3 {{ margin: 0; font-size: 14px; font-weight: 600; }}
.medida-pct {{
  font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 15px;
  font-weight: 600; font-variant-numeric: tabular-nums; color: var(--acento);
}}
.barra {{
  display: block; height: 5px; background: var(--borde-sutil);
  margin-top: 6px; overflow: hidden;
}}
.barra-ancha {{ height: 8px; }}
.barra-relleno {{ display: block; height: 100%; background: var(--acento); }}
.medida-txt {{ margin: 10px 0 0; font-size: 13.5px; color: var(--tinta-2); }}
.medida-aviso {{ border-left: 3px solid var(--aviso); padding-left: 14px;
  background: var(--aviso-flojo); border-radius: 0 4px 4px 0; padding-right: 12px;
  padding-top: 10px; padding-bottom: 10px; }}
.medida-aviso .medida-pct {{ color: var(--aviso); }}
.medida-aviso .barra {{ display: none; }}
.medida-det {{
  margin: 6px 0 0; font-size: 12.5px; color: var(--tinta-3);
  border-left: 2px solid var(--aviso); padding-left: 9px;
}}
/* El contrato apartado, con nombre. Va un punto mas oscuro que el resto del
   detalle porque es lo unico accionable del aviso: el resto explica, este
   dice a quien mirar y donde. */
.medida-ejemplo {{ color: var(--tinta-2); line-height: 1.5; }}
.medida-ejemplo a {{ color: inherit; }}

/* -------------------------------------------------------------- apilada */
.apilada {{ display: flex; height: 34px; gap: 2px; }}
.apilada .seg {{ background: var(--c); }}
.leyenda {{
  list-style: none; margin: 16px 0 0; padding: 0;
  display: grid; gap: 12px;
}}
@media (min-width: 700px) {{ .leyenda {{ grid-template-columns: repeat(3, 1fr); }} }}
.leyenda li {{ display: grid; grid-template-columns: 10px 1fr; gap: 4px 9px; align-items: baseline; }}
.punto {{ width: 10px; height: 10px; border-radius: 50%; }}
.ley-nom {{ font-weight: 600; font-size: 14px; }}
.ley-val {{
  grid-column: 2; font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 15px; font-variant-numeric: tabular-nums;
}}
.ley-sec {{ grid-column: 2; font-size: 12.5px; color: var(--tinta-3); }}

/* --------------------------------------------------------------- barras */
.barras {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 9px; }}
.barras li {{
  display: grid; align-items: center; gap: 12px;
  grid-template-columns: 26px minmax(96px, 1.1fr) minmax(90px, 3fr) 152px 62px;
  font-size: 13.5px;
}}
.barras .cod {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 11.5px; color: var(--tinta-3);
}}
.barras .dep {{ font-weight: 500; }}
.barras .pista {{ background: var(--borde-sutil); height: 14px; }}
.barras .marca {{ display: block; height: 100%; background: var(--acento); }}
.barras li.sin .marca {{ background: var(--tinta-3); }}
.barras li.sin .dep {{ color: var(--tinta-3); font-style: italic; }}
.barras .cifra, .barras .cuenta {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-variant-numeric: tabular-nums; text-align: right; font-size: 13px;
  white-space: nowrap;
}}
.barras .cuenta {{ color: var(--tinta-3); }}
@media (max-width: 640px) {{
  .barras li {{ grid-template-columns: 24px 1fr 132px; }}
  .barras .pista, .barras .cuenta {{ display: none; }}
}}

/* --------------------------------------------------------------- tablas */
.tabla-scroll {{ overflow-x: auto; }}
.tabla {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
.tabla th {{
  text-align: left; font-size: 11px; text-transform: uppercase;
  letter-spacing: .08em; color: var(--tinta-3); font-weight: 600;
  padding: 0 12px 8px 0; border-bottom: 1px solid var(--borde);
  white-space: nowrap;
}}
.tabla td {{
  padding: 9px 12px 9px 0; border-bottom: 1px solid var(--borde-sutil);
  vertical-align: top;
}}
.tabla tr:last-child td {{ border-bottom: none; }}
.tabla .num, .tabla .val {{
  text-align: right; font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-variant-numeric: tabular-nums; white-space: nowrap;
}}
.tabla .val {{ min-width: 152px; }}
.tabla .nom {{ font-weight: 500; min-width: 220px; }}
.tabla .doc {{
  display: block; font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 11px; color: var(--tinta-3); font-weight: 400;
}}
.pill {{
  display: inline-block; font-size: 11px; padding: 1px 7px;
  background: var(--acento-flojo); color: var(--tinta-2); white-space: nowrap;
}}
.pill-ut {{ background: var(--aviso-flojo); color: var(--aviso); }}
.pill-errata {{ background: var(--aviso-flojo); color: var(--aviso);
  border: 1px solid var(--aviso); display: inline-block; margin-top: 4px; }}
/* La marca de errata usa el mismo par de tokens de aviso que la unión
   temporal, con borde para que se distinga de ella de un vistazo: las dos
   dicen «ojo con esta fila», pero por motivos distintos. */
.pill-errata {{ background: var(--aviso-flojo); color: var(--aviso);
  border: 1px solid var(--aviso); }}
.nota-errata {{ margin: 10px 0 0; font-size: 12.5px; line-height: 1.55;
  color: var(--tinta-2); border-left: 3px solid var(--aviso);
  background: var(--aviso-flojo); padding: 9px 12px; border-radius: 0 4px 4px 0; }}
.vacio {{ color: var(--tinta-3); font-style: italic; margin: 0; }}

/* ----------------------------------------------------------------- nota */
.nota {{
  border: 1px solid var(--borde); border-left: 3px solid var(--aviso);
  background: var(--superficie); padding: 18px 20px;
  font-family: "Source Serif 4", Georgia, serif; font-size: 14.5px;
  color: var(--tinta-2); max-width: 74ch;
}}
.nota h2 {{
  margin: 0 0 8px; font-family: Archivo, sans-serif; font-size: 13px;
  text-transform: uppercase; letter-spacing: .1em; color: var(--aviso);
}}
.nota p {{ margin: 0 0 10px; }}
.nota p:last-child {{ margin-bottom: 0; }}
footer {{
  margin-top: 48px; padding-top: 18px; border-top: 1px solid var(--borde);
  font-size: 12px; color: var(--tinta-3);
  font-family: "IBM Plex Mono", ui-monospace, monospace;
}}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
{estilo.NAV_CSS}
</style>
</head>
<body>

<div class="envoltura">

  <header class="cabecera">
    <div class="marca">
      <h1>Vigía SECOP · Panel</h1>
      <span class="sub">La forma de la contratación en la ventana ingerida — y,
        sobre todo, cuánto de ella queda fuera del alcance de cada medición.</span>
    </div>
    <div class="sello">
      <span>ventana <b>{e(v.get("desde"))} → {e(v.get("hasta"))}</b></span>
      <span>generado {e(generado)}</span>
    </div>
  </header>

  {estilo.menu("panel.html")}

  <div class="cifras">
    <div class="cifra-caja">
      <div class="rot">Contratos</div>
      <div class="dat">{numero(v["contratos"])}</div>
      <div class="pie">firmados en la ventana</div>
    </div>
    <div class="cifra-caja">
      <div class="rot">Valor</div>
      <div class="dat">{compacto(v["valor"])}</div>
      <div class="pie">{pesos(v["valor"])}</div>
    </div>
    <div class="cifra-caja">
      <div class="rot">Entidades</div>
      <div class="dat">{numero(v["entidades"])}</div>
      <div class="pie">contratantes distintas</div>
    </div>
    <div class="cifra-caja">
      <div class="rot">Proveedores</div>
      <div class="dat">{numero(v["proveedores"])}</div>
      <div class="pie">identidades reales, sin contar uniones sin documento</div>
    </div>
  </div>

  <section>
    <div class="banda-cab">
      <h2>Alcance de la vigilancia</h2>
      <p>Va antes que cualquier ranking, y no por cortesía: un listado de
        contratistas sin saber sobre qué parte del universo se calculó es
        justo la clase de número que se lee mal.</p>
    </div>
    <div class="tarjeta alcance">{_cobertura(datos)}</div>
  </section>

  <section>
    <div class="banda-cab">
      <h2>Proveedores por valor</h2>
      <p>Ordenado por valor contratado. <strong>No es una alerta</strong>: que
        alguien encabece esta lista no dice nada por sí solo. Las uniones
        temporales sin documento están excluidas — cada una vale por un solo
        contrato y aparecerían con una concentración de 1 que no significa nada.</p>
    </div>
    <div class="tarjeta">{_filas_proveedores(datos, completo)}</div>
  </section>

  <section>
    <div class="banda-cab">
      <h2>Uniones temporales y consorcios sin documento</h2>
      <p>{numero(c["union_temporal_sin_documento"])} contratos
        ({compacto(c["valor_union_temporal"])},
        {porcentaje(c["valor_union_temporal"], v["valor"])} del valor de la ventana).
        Cada uno tiene identidad propia y marcada: se cuentan y se ven, pero no
        se les puede medir concentración hasta conocer a sus integrantes.</p>
    </div>
    <div class="tarjeta">{_filas_uniones(datos)}</div>
  </section>

  <section>
    <div class="banda-cab">
      <h2>Orden administrativo</h2>
      <p>Tres valores, no dos. Las Corporaciones Autónomas Regionales no son ni
        nacionales ni territoriales. La distinción importa desde el 7 de agosto
        de 2026: el cambio de gobierno movió lo nacional y no movió lo
        territorial, donde alcaldes y gobernadores siguen en su periodo.</p>
    </div>
    <div class="tarjeta">{_barra_ordenes(datos)}</div>
  </section>

  <section>
    <div class="banda-cab">
      <h2>Departamentos por valor</h2>
      <p>Código DIVIPOLA del DANE. El valor no sigue al número de contratos, que
        es justamente lo que hace útil el corte territorial.</p>
    </div>
    <div class="tarjeta">{_barras_departamentos(datos)}</div>
  </section>

  <section>
    <div class="banda-cab">
      <h2>Entidades por valor</h2>
      <p>Cuántos proveedores distintos usa cada entidad es la columna que la
        Regla de concentración por ordenador (4.4) mirará cuando exista.</p>
    </div>
    <div class="tarjeta">{_filas_entidades(datos)}</div>
  </section>

  <section>
    <div class="banda-cab">
      <h2>Contratos mayores</h2>
      <p>Los diez de más valor de la ventana, con su identificador del SECOP.</p>
    </div>
    <div class="tarjeta">{_filas_mayores(datos)}</div>
  </section>

  <div class="nota">
    <h2>Qué no hace este panel</h2>
    <p>No emite alertas y no califica ningún contrato. Muestra la forma de una
      ventana de contratación y el alcance real de cada medición.</p>
    <p>Las Reglas —oferente único, plazo exprés, posible fraccionamiento,
      concentración— vendrán después, y ninguna se enciende sin calibrar antes
      contra datos reales. Una alerta inventada le costaría a alguien su
      reputación, y es exactamente lo que este proyecto no se puede permitir.</p>
  </div>

  <footer>Vigía SECOP · datos de datos.gov.co (SECOP II) · generado {e(generado)}</footer>
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        prog="vigia.panel",
        description="Dibuja el Panel de Vigía a partir de panel.json.",
    )
    analizador.add_argument("--json", default="panel.json")
    analizador.add_argument("--salida", default="panel.html")
    analizador.add_argument(
        "--documentos-completos", action="store_true",
        help="Escribe los documentos de personas naturales sin enmascarar.",
    )
    opciones = analizador.parse_args(argv)

    origen = Path(opciones.json)
    if not origen.exists():
        print(
            f"no existe {origen}: córrelo primero con EJECUTAR-panel.bat",
            file=sys.stderr,
        )
        return CODIGO_USO
    try:
        datos = json.loads(origen.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"{origen} no es JSON válido: {error}", file=sys.stderr)
        return CODIGO_FALLO

    for seccion in ("ventana", "cobertura"):
        if seccion not in datos:
            print(f"a {origen} le falta la sección «{seccion}»", file=sys.stderr)
            return CODIGO_FALLO

    salida = Path(opciones.salida)
    salida.write_text(
        construir(datos, completo=opciones.documentos_completos), encoding="utf-8")
    print(f"Panel escrito en {salida.resolve()}")
    print(f"  {numero(datos['ventana']['contratos'])} contratos, "
          f"{compacto(datos['ventana']['valor'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
