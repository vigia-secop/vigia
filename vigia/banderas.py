"""La página pública de banderas: `docs/banderas.html`.

    python -m vigia.banderas --json banderas.json --salida docs/banderas.html

**ES LA PRIMERA PÁGINA DE VIGÍA QUE SEÑALA ALGO**, y por eso está escrita al
revés que las demás: primero lo que no dice, después lo que dice.

Todas las otras páginas describen. Ésta publica una ficha por entidad con
nombre propio, y una ficha así se lee como una acusación aunque no lo sea. La
defensa no es el tono: es que **cada afirmación de la ficha se pueda comprobar
en un clic**, y que lo que no se puede sostener no esté escrito.

LAS TRES AFIRMACIONES DE UNA FICHA, y no hay una cuarta:

1. Que esos contratos existen, con esos valores y esas fechas.
2. Que son de mínima cuantía y del mismo contratista.
3. Que su suma supera la mínima cuantía más cara que esa misma entidad firmó.

La tercera es una operación aritmética sobre las dos primeras. No se compara
contra ningún tope de la ley: se compara a la entidad consigo misma, y el
corte sale del percentil 95 de las entidades de su mismo tamaño de techo.

LO QUE LA PÁGINA NO DICE, Y VA ESCRITO ARRIBA Y EN CADA FICHA:

- No dice que se haya violado la ley. Cada contrato cabía en el tope.
- No dice que sea la misma compra. La fuente no publica el objeto en un
  formato comparable, así que Vigía **no puede saberlo**.
- No dice que haya intención, y no menciona a ningún funcionario.
- No hay ranking ni «los peores». Es una lista ordenada por fecha.

EL ORDEN DE LA PÁGINA ES DELIBERADO. La cobertura va antes que las fichas: sin
saber a cuántas entidades **no alcanza** la bandera, la lista se lee como «éstas
son las que fraccionan en Colombia», que es falso. La bandera no alcanza a las
entidades con pocas mínimas cuantías ni a las que tienen un techo imposible.

NINGUNA PERSONA NATURAL SALE NOMBRADA. Si el contratista es persona natural se
publica «Persona natural» y el documento enmascarado — el interés público está
en la entidad que firmó y en la cifra, no en el nombre de un particular.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from vigia import estilo
from vigia.documento import escribir as documento
from vigia.marca import ojo
from vigia.reglas import fraccionamiento
from vigia.reglas.calibracion import Recorte, calibrar
from vigia.reglas.calibrar_fraccionamiento import MOTIVO, separar
from vigia.reglas.modelo import CALIBRACION
from vigia.sitio import LEMA, TITULO

CODIGO_USO = 2
CODIGO_FALLO = 1

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def pesos(valor) -> str:
    if valor is None:
        return "—"
    return "$" + f"{float(valor):,.0f}".replace(",", ".")


def numero(valor) -> str:
    if valor is None:
        return "—"
    return f"{int(valor):,}".replace(",", ".")


def e(texto) -> str:
    return html.escape(str(texto)) if texto is not None else ""


def _fecha(valor) -> date:
    return date.fromisoformat(str(valor)[:10])


def _mes_largo(valor) -> str:
    d = _fecha(valor)
    return f"{MESES[d.month - 1]} de {d.year}"


def _dia(valor) -> str:
    d = _fecha(valor)
    return f"{d.day} de {MESES[d.month - 1]}"


def _proveedor(grupo: Mapping[str, Any]) -> str:
    """Cómo se nombra al contratista, que es donde se decide si esto es
    publicable o no.

    De una EMPRESA sale su documento completo: es información pública de un
    contrato público y sin ella la ficha no se puede comprobar. De una PERSONA
    NATURAL no sale ni el nombre ni el documento entero. `documento.escribir`
    con `completo=False` es la misma función que usa el resto del sitio.
    """
    return documento(grupo.get("proveedor_tipo"),
                     grupo.get("proveedor_numero"), completo=False)


def _ficha(alerta, grupo: Mapping[str, Any]) -> str:
    v = alerta.expediente.valores_disparadores
    detalle = list(grupo.get("detalle") or [])

    filas = []
    for c in detalle:
        enlace = str(c.get("enlace") or "")
        ident = e(c.get("id_contrato") or "—")
        ficha = (f'<a href="{e(enlace)}" target="_blank" rel="noopener noreferrer">'
                 f"{ident}</a>") if enlace.startswith("https://") else ident
        filas.append(
            "<tr>"
            f"<td>{ficha}</td>"
            f'<td>{e(_dia(c.get("fecha"))) if c.get("fecha") else "—"}</td>'
            f'<td class="n">{pesos(c.get("valor"))}</td>'
            "</tr>"
        )

    return (
        '<article class="ficha">'
        f'<h3>{e(grupo.get("nombre_entidad") or "—")}</h3>'
        f'<p class="titular"><strong>{numero(v.get("contratos"))} contratos de '
        f"mínima cuantía al mismo contratista en {e(_mes_largo(grupo['mes']))}."
        "</strong></p>"
        f'<p class="cuentas">Suman <strong>{pesos(v.get("suma"))}</strong>. '
        "La mínima cuantía más cara que esta entidad firmó en el período es "
        f'<strong>{pesos(v.get("techo_de_la_entidad"))}</strong> — los '
        f'{numero(v.get("contratos"))} juntos son <strong>'
        f'{e(v.get("veces_el_techo"))} veces</strong> esa cifra.</p>'
        f'<p class="cuentas">Contratista: <span class="doc">'
        f'{e(_proveedor(grupo))}</span></p>'
        '<p class="limite">Cada uno de estos contratos está por debajo del tope '
        "de la entidad y ninguno, por sí solo, requería un proceso "
        "competitivo.</p>"
        '<div class="tabla-scroll"><table class="tabla"><thead><tr>'
        "<th>Contrato</th><th>Firmado</th><th class=\"n\">Valor</th>"
        f'</tr></thead><tbody>{"".join(filas)}</tbody></table></div>'
        # LA PRUEBA DE VOCABULARIO DE ESTE PROYECTO ME CORRIGIÓ AQUÍ.
        #
        # La primera versión decía «Vigía no afirma que exista irregularidad».
        # Es una negación, y aun así `test_reglas.py` la rechazó por llevar la
        # palabra. Fui a discutirlo y la prueba tenía razón dos veces:
        #
        # 1. Un guardia que sepa distinguir negaciones es un guardia al que se
        #    le puede dar la vuelta con una frase bien puesta.
        # 2. Y sobre todo: la palabra se planta igual. Puesta debajo del nombre
        #    de una alcaldía, quien pase el ojo por encima lee «irregularidad»
        #    y el «no afirma» se le queda atrás.
        #
        # Así que la ficha ya no niega nada: dice lo que es.
        '<p class="descargo"><em>Lo anterior son hechos comprobables, no una '
        "conclusión sobre nadie. "
        "Esta ficha describe una forma en los datos públicos: varios contratos "
        "pequeños a un mismo contratista dentro de un mes. Compras repetidas, "
        "entregas por tramos y urgencias producen esta misma forma. La fuente "
        "no publica el objeto contractual en un formato comparable, así que "
        "Vigía <strong>no puede saber</strong> si se trata de una misma compra "
        "dividida o de compras distintas.</em></p>"
        "</article>"
    )


CSS = """
.aviso-mayor { border-left:3px solid var(--aviso); background:var(--aviso-flojo);
  border-radius:0 8px 8px 0; padding:18px 20px; margin-top:26px; }
.aviso-mayor h2 { margin:0 0 8px; font-size:18px; }
.aviso-mayor p { margin:8px 0 0; }
.aviso-mayor ul { margin:10px 0 0; padding-left:20px; }
.aviso-mayor li { margin:6px 0; }
.ficha { background:var(--superficie); border:1px solid var(--borde);
  border-radius:8px; padding:20px 22px; margin-top:20px; }
.ficha h3 { margin:0; font-size:19px; letter-spacing:-.01em; }
.titular { margin:10px 0 0; font-size:16px; }
.cuentas { margin:10px 0 0; font-size:15px; color:var(--tinta-2); }
.limite { margin:10px 0 0; font-size:14px; color:var(--tinta-3); }
.descargo { margin:14px 0 0; padding-top:12px; border-top:1px solid var(--borde-sutil);
  font-size:13px; color:var(--tinta-3); line-height:1.55; }
.tabla { width:100%; border-collapse:collapse; font-size:14px; margin-top:12px; }
.tabla th { text-align:left; font-size:11.5px; text-transform:uppercase;
  letter-spacing:.06em; color:var(--tinta-3); border-bottom:1px solid var(--borde);
  padding:0 10px 8px 0; font-weight:600; }
.tabla td { padding:9px 10px 9px 0; border-bottom:1px solid var(--borde-sutil); }
.tabla .n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.tabla-scroll { overflow-x:auto; }
.doc { font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:13px; }
.vacio { color:var(--tinta-3); font-style:italic; }
footer { margin-top:46px; padding-top:18px; border-top:1px solid var(--borde);
  font-size:12.5px; color:var(--tinta-3); }
"""


def construir(datos: Mapping[str, Any], *, momento: datetime) -> str:
    grupos = list(datos.get("grupos") or [])
    recorte = datos.get("recorte") or {}

    regla = fraccionamiento.crear(momento)
    version = regla.versiones[-1]
    regla.mover_a(CALIBRACION)

    mirables, ciegos = separar(grupos, version.umbrales)
    if not mirables:
        raise ValueError("no quedó ni un grupo que evaluar")

    por_clave = {}
    for g in mirables:
        clave = "|".join((str(g.get("nit_entidad") or ""),
                          str(g.get("proveedor_tipo") or ""),
                          str(g.get("proveedor_numero") or ""),
                          str(g.get("mes") or "")))
        por_clave[clave] = g

    resultado = calibrar(
        mirables, regla=regla, version=version,
        recorte=Recorte(nombre="minimas cuantias, universo completo", motivo=MOTIVO),
        evaluador=fraccionamiento.evaluar,
        consultado_en=momento, momento=momento,
        dimension="nombre_entidad",
        tamano_muestra=len(mirables),
    )

    # Por fecha y no por tamaño: un ranking por «veces» convertiría la página
    # en «los peores», que es justo lo que no es.
    alertas = sorted(
        resultado.muestra,
        key=lambda a: (str(a.expediente.valores_disparadores.get("mes")),
                       str(a.expediente.valores_disparadores.get("entidad") or "")),
    )
    fichas = "".join(
        _ficha(a, por_clave[a.expediente.id_registro_fuente]) for a in alertas
    )
    if not fichas:
        fichas = ('<p class="vacio">Ningún grupo superó el corte de su tramo en '
                  "este período. Se miró y no había.</p>")

    entidades_ciegas = len({g["nit_entidad"] for g, _ in ciegos})
    entidades_con_ficha = len({
        a.expediente.valores_disparadores.get("nit_entidad") for a in alertas})

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Banderas · Vigía SECOP</title>
<meta name="robots" content="noindex">
<style>
{estilo.tokens()}
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
    {estilo.menu("banderas.html")}
  </header>

  <h2 class="pagina">Banderas</h2>
  <p class="sub">Formas en los datos que vale la pena mirar. No son conclusiones
    sobre nadie.</p>
  <p class="per">{numero(len(alertas))} fichas ·
    {numero(entidades_con_ficha)} entidades ·
    de {e(recorte.get("desde"))} a {e(recorte.get("hasta"))}</p>

  <div class="aviso-mayor">
    <h2>Léase esto antes que las fichas</h2>
    <p>Cada ficha de abajo dice <strong>tres cosas, y ninguna más</strong>:</p>
    <ul>
      <li>Que esos contratos existen, con esos valores y esas fechas.</li>
      <li>Que son de mínima cuantía y del mismo contratista.</li>
      <li>Que su suma supera la mínima cuantía más cara que esa misma entidad
        firmó en el período.</li>
    </ul>
    <p>La tercera es una operación aritmética sobre las dos primeras.
    <strong>No se compara contra ningún tope de la ley</strong>: se compara a
    cada entidad consigo misma y con las entidades de su mismo tamaño.</p>
    <p><strong>Lo que Vigía no dice, y no es una omisión:</strong> no dice que
    se haya violado la ley —cada contrato cabía en el tope—, no dice que sea la
    misma compra —la fuente no publica el objeto en un formato comparable—, no
    dice que haya intención, y no menciona a ningún funcionario. No hay ranking
    ni «los peores»: la lista va por fecha.</p>
  </div>

  <h2>Sobre cuánto alcanza a mirar esta bandera</h2>
  <p class="sub">Va antes que las fichas, a propósito.</p>
  <div class="tarjeta alcance">
    <p style="margin:0">Se miraron <strong>{numero(resultado.evaluados)} grupos</strong>
    de contratos de mínima cuantía repetidos al mismo contratista dentro de un
    mes, sobre {numero(recorte.get("minimas_medibles"))} mínimas cuantías de
    {numero(recorte.get("entidades"))} entidades.</p>
    <p style="margin:10px 0 0"><strong>{numero(len(ciegos))} grupos de
    {numero(entidades_ciegas)} entidades quedaron fuera del alcance</strong>
    porque su tope no significa nada: o tienen muy pocas mínimas cuantías para
    saber cuál es, o su contrato más caro es un valor imposible que la fuente
    trae mal.</p>
    <p style="margin:10px 0 0"><strong>Eso no quiere decir que esas entidades
    estén limpias.</strong> Quiere decir que esta bandera no las alcanza, y
    quien lea la lista de abajo tiene que saberlo: no son «las que fraccionan
    en Colombia», son las que esta medición pudo ver.</p>
  </div>

  <h2>Las fichas</h2>
  <p class="sub">Por fecha. Cada contrato enlaza a su ficha oficial en SECOP.</p>
  {fichas}

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
    p = argparse.ArgumentParser(prog="vigia.banderas")
    p.add_argument("--json", default="banderas.json")
    p.add_argument("--salida", default="docs/banderas.html")
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
        pagina = construir(datos, momento=datetime.now(timezone.utc))
    except (KeyError, ValueError) as error:
        print(f"no se pudo construir la página: {error}", file=sys.stderr)
        return CODIGO_FALLO

    # LA MISMA BARRERA QUE EL RESTO DEL SITIO, y aquí importa más que en
    # ninguna otra página: es la única que nombra entidades una por una.
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
    print(f"Banderas escritas en {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
