"""Lista de revisión: qué mirar primero.

    python -m vigia.revision            # lee revision.json, escribe revision.html

QUÉ ES ESTO Y QUÉ NO ES. **No son alertas.** Ninguna fila afirma que haya un
problema. Son contratos y procesos que vale la pena mirar antes que los otros,
cada uno con la razón concreta por la que está listado — y todas las razones
son hechos sobre el dato, medidos y verificables:

- un contrato grande cuya razón social la fuente no diligenció,
- una unión temporal sin documento moviendo mucha plata,
- un contrato que trae llave de cruce y no encontró su Proceso,
- un mismo documento con varias razones sociales,
- un proceso competitivo con un solo oferente que aun así estuvo entre los más
  mirados de su modalidad.

Que algo esté aquí significa «esto todavía no lo sabemos» o «esto es grande y
conviene verlo». **Nunca «esto está mal».** La diferencia es todo el proyecto.

POR QUÉ EXISTE ESTA PÁGINA Y NO LAS REGLAS DE LA ÉPICA 4. Porque las Reglas
todavía no están calibradas y encenderlas sin calibrar es peor que no tenerlas.
La primera que se intentó —oferente único— murió con dos mediciones: marcaba el
52,8 % de su propio universo, y cuando se buscó el criterio relativo que la
salvara, los datos dijeron lo contrario de la hipótesis. Un proceso que termina
con una sola oferta es, por regla, uno que **nadie miró** (mediana de 16
visualizaciones contra 32), no uno muy mirado al que nadie se presentó.

Mientras tanto, esta lista da algo que sí se puede usar mañana por la mañana
sin afirmar nada que no se pueda sostener.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vigia.documento import escribir as documento
from vigia.panel import compacto, e, numero, pesos, titulo_es

CODIGO_USO = 2
CODIGO_FALLO = 1


def _valor(f, clave="valor"):
    v = f.get(clave)
    return float(v) if v is not None else None


def _percentil(f) -> str:
    """El percentil de atención dentro de su modalidad, escrito como se lee.

    Se muestra al lado de las visualizaciones porque el número crudo no dice
    nada solo: 28 visualizaciones son muchas en una menor cuantía y pocas en
    una licitación de obra. El percentil es lo que hace comparable la fila con
    su propia modalidad, que es la única comparación honesta.
    """
    v = f.get("percentil")
    return "—" if v is None else f"p{int(v)}"


def _tabla(titulo, porque, filas, columnas, encabezados, vacio):
    if not filas:
        return (
            f'<section><div class="cab"><h2>{e(titulo)}</h2>'
            f'<p>{porque}</p></div>'
            f'<div class="tarjeta"><p class="vacio">{e(vacio)}</p></div></section>'
        )
    cuerpo = "".join(f"<tr>{''.join(columnas(f))}</tr>" for f in filas)
    celdas = []
    for n in encabezados:
        clase = ' class="num"' if n.startswith("~") else ""
        celdas.append(f"<th{clase}>{e(n.lstrip('~'))}</th>")
    cabeza = "".join(celdas)
    return (
        f'<section><div class="cab"><h2>{e(titulo)}</h2><p>{porque}</p></div>'
        f'<div class="tarjeta"><div class="scroll"><table>'
        f"<thead><tr>{cabeza}</tr></thead><tbody>{cuerpo}</tbody></table></div></div></section>"
    )


def construir(datos: dict, *, completo: bool = False) -> str:
    v = datos.get("ventana") or {}
    c = datos.get("conteos") or {}
    # Va aparte porque necesita el cruce con Procesos y `conteos` solo recorre
    # `contrato`. `or {}` para que una página vieja —un JSON generado antes de
    # que esta sección existiera— siga dibujándose en vez de reventar.
    ce = datos.get("conteo_erratas") or {}
    generado = str(datos.get("generado_en", ""))[:19].replace("T", " ")

    def tarjeta(rotulo, cuantos, valor, pie):
        return (
            '<div class="caja">'
            f'<div class="rot">{e(rotulo)}</div>'
            f'<div class="dat">{numero(cuantos)}</div>'
            f'<div class="plata">{compacto(valor)}</div>'
            f'<div class="pie">{pie}</div></div>'
        )

    resumen = (
        '<div class="cifras">'
        + tarjeta("Sin razón social", c.get("sin_razon_social"),
                  c.get("valor_sin_razon_social"),
                  "hay documento, falta el nombre del contratista")
        + tarjeta("Uniones sin documento", c.get("uniones"), c.get("valor_uniones"),
                  "se cuentan, pero no se les puede medir concentración")
        + tarjeta("Huérfanos", c.get("huerfanos"), c.get("valor_huerfanos"),
                  "traen llave de cruce y no encontraron su Proceso")
        # La cuarta caja solo sale cuando hay alguno: un contador permanente en
        # cero se vuelve decorado y deja de leerse el día que deja de ser cero.
        + (tarjeta("Valores imposibles", c.get("imposibles"),
                   c.get("valor_imposibles"),
                   "errata de la fuente · fuera de todos los totales")
           if c.get("imposibles") else "")
        + (tarjeta("Erratas ×10ⁿ", ce.get("erratas"), ce.get("valor_erratas"),
                   "el valor cabe en la realidad y aun así está mal")
           if ce.get("erratas") else "")
        + "</div>"
    )

    # LA ERRATA QUE EL TECHO NO ATAJA, Y VA ANTES QUE TODO LO DEMÁS.
    #
    # El 2026-09-11 esta página mostró a la ALCALDÍA DE TIPACOQUE —municipio de
    # unos 3.000 habitantes— firmando $431.340.000.000 con una fundación. Leído
    # así es una bomba, y es falso: el presupuesto del proceso era
    # $431.340.000, el mismo número con TRES CEROS DE MÁS.
    #
    # La guarda de valores imposibles (1e14) no lo atajó y nunca pudo: 431 mil
    # millones es un contrato perfectamente posible. Esa fila salía desnuda
    # porque la comparación contra el presupuesto de su propio proceso no
    # estaba hecha. Ahora está, y va arriba: quien abra esta página tiene que
    # ver el desmentido antes que la cifra.
    erratas = _tabla(
        "Cifras que parecen enormes y son una tecla de más",
        "El valor adjudicado de estos contratos es <strong>exactamente mil o "
        "diez mil veces</strong> el presupuesto oficial de su propio proceso. "
        "Un sobrecosto real da una proporción cualquiera —2,3; 12,4—; solo una "
        "errata de tecleo cae justo sobre una potencia de diez. "
        "<strong>La columna «probablemente era» es el presupuesto del proceso, "
        "no una corrección nuestra</strong>: Vigía no toca lo que la fuente "
        "publicó. Antes de creerle a una de estas cifras —y antes de "
        "compartirla— abre la ficha del SECOP. "
        "<strong>Publicar una de estas como hallazgo destruiría en un día la "
        "credibilidad que este proyecto no tiene todavía.</strong>",
        datos.get("erratas_x1000") or [],
        lambda f: (
            (f'<td class="id"><a href="{e(f["enlace"])}" target="_blank" '
             f'rel="noopener">{e(f["id_contrato"])}</a></td>') if f.get("enlace")
            else f'<td class="id">{e(f["id_contrato"])}</td>',
            f'<td>{e(f.get("entidad"))}</td>',
            f'<td>{e(f.get("proveedor") or "—")}'
            + (f'<span class="otros">'
               f'{e(documento(f.get("tipo"), f.get("documento"), completo=completo))}'
               "</span>" if f.get("documento") else "")
            + "</td>",
            f'<td class="num">{compacto(_valor(f))}</td>',
            f'<td class="num">{compacto(_valor(f, "valor_probable"))}</td>',
            f'<td class="num">{e(str(f.get("ceros_de_mas") or "—"))}</td>',
        ),
        ["Contrato", "Entidad", "Proveedor", "~Valor publicado",
         "~Probablemente era", "Ceros de más"],
        "Ninguna en esta ventana: ningún contrato es una potencia de diez "
        "exacta del presupuesto de su proceso.",
    )

    imposibles = _tabla(
        "Valores que no pueden ser ciertos",
        "Estos contratos declaran más de <strong>100 billones de pesos</strong>: "
        "la quinta parte del presupuesto nacional de un año, en un solo contrato. "
        "No es una acusación contra nadie — es una <strong>errata de la "
        "fuente</strong>, y la más común es el mismo número con tres ceros de "
        "más. Se muestran con el valor <em>tal como la fuente lo publica</em>: "
        "Vigía no corrige la fuente ni adivina cuál era el número verdadero. "
        "<strong>Están fuera de todos los totales y rankings del Panel</strong>, "
        "porque mientras uno de estos esté dentro de una suma, esa suma es falsa.",
        datos.get("valores_imposibles") or [],
        lambda f: (
            f'<td class="id">{e(f["id_contrato"])}</td>',
            f'<td>{e(f.get("entidad"))}</td>',
            f'<td>{e(f.get("proveedor") or "—")}'
            + (f'<span class="otros">{e(documento(None, f.get("documento"), completo=completo))}</span>'
               if f.get("documento") else "")
            + "</td>",
            f'<td class="num">{compacto(_valor(f))}</td>',
            f'<td><span class="pill">{e(f.get("estado") or "—")}</span></td>',
        ),
        ["Contrato", "Entidad", "Proveedor", "~Valor declarado", "Estado"],
        "Ninguno. Todos los valores de esta ventana caben en la realidad.",
    )

    sin_nombre = _tabla(
        "Contratos grandes sin razón social",
        "La fuente trae el documento del contratista pero no su nombre. No es un "
        "error nuestro: el campo llega literalmente como «No Definido». El mayor "
        "de la ventana es uno de estos.",
        datos.get("sin_razon_social") or [],
        lambda f: (
            # El identificador va como ENLACE a la ficha oficial. Es lo que de
            # verdad permite comprobar: allí está el nombre, el documento, el
            # objeto y los soportes, en la fuente y no en nuestra copia.
            (f'<td class="id"><a href="{e(f["enlace"])}" target="_blank" '
             f'rel="noopener">{e(f["id_contrato"])}</a></td>') if f.get("enlace")
            else f'<td class="id">{e(f["id_contrato"])}</td>',
            f'<td>{e(documento(f.get("tipo"), f.get("documento"), completo=completo))}</td>',
            f'<td>{e(f.get("entidad"))}</td>',
            f'<td>{e(titulo_es(f.get("departamento") or "—"))}</td>',
            f'<td class="num">{compacto(_valor(f))}</td>',
            f'<td><span class="pill">{e(f.get("estado") or "—")}</span></td>',
        ),
        ["Contrato", "Documento", "Entidad", "Departamento", "~Valor", "Estado"],
        "Ninguno en esta ventana.",
    )

    uniones = _tabla(
        "Uniones temporales y consorcios sin documento",
        "Cada uno tiene identidad propia y marcada: se cuentan y se ven, pero no "
        "se les puede medir concentración hasta conocer a sus integrantes.",
        datos.get("uniones_sin_documento") or [],
        lambda f: (
            f'<td class="id">{e(f["id_contrato"])}</td>',
            f'<td>{e(f.get("nombre") or "—")}</td>',
            f'<td>{e(f.get("entidad"))}</td>',
            f'<td>{e(titulo_es(f.get("departamento") or "—"))}</td>',
            f'<td class="num">{compacto(_valor(f))}</td>',
            f'<td><span class="pill">{e(f.get("estado") or "—")}</span></td>',
        ),
        ["Contrato", "Unión temporal", "Entidad", "Departamento", "~Valor", "Estado"],
        "Ninguna en esta ventana.",
    )

    huerfanos = _tabla(
        "Huérfanos de alto valor",
        "Traen la llave de cruce y no encontraron su Proceso. Sin Proceso no hay "
        "modalidad, ni fecha de publicación, ni plazo que medir: quedan fuera de "
        "casi toda Regla futura. Suele ser porque el Proceso es anterior a la "
        "ventana ingerida.",
        datos.get("huerfanos_grandes") or [],
        lambda f: (
            f'<td class="id">{e(f["id_contrato"])}</td>',
            f'<td class="id">{e(f.get("proceso_de_compra") or "—")}</td>',
            f'<td>{e(f.get("proveedor") or "—")}</td>',
            f'<td>{e(f.get("entidad"))}</td>',
            f'<td class="num">{compacto(_valor(f))}</td>',
        ),
        ["Contrato", "Llave de cruce", "Proveedor", "Entidad", "~Valor"],
        "Ninguno en esta ventana.",
    )

    variantes = _tabla(
        "Un documento, varias razones sociales",
        "El mismo contratista escrito de más de una forma. Puede ser un cambio de "
        "nombre legítimo o puede ser otra cosa; en los dos casos conviene verlo.",
        datos.get("proveedores_con_varios_nombres") or [],
        lambda f: (
            f'<td class="id">{e(documento(f.get("tipo"), f.get("numero"), completo=completo))}</td>',
            f'<td>{e(f.get("nombre_principal") or "—")}'
            + (f'<span class="otros">{e(" · ".join((f.get("nombres") or [])[1:4]))}</span>'
               if f.get("nombres") else "")
            + "</td>",
            f'<td class="num">{numero(f.get("variantes"))}</td>',
            f'<td class="num">{numero(f.get("contratos"))}</td>',
        ),
        ["Documento", "Nombres vistos", "~Formas", "~Contratos"],
        "Ninguno en esta ventana.",
    )

    competitivos = _tabla(
        "Un solo oferente, y aun así de los más mirados de su modalidad",
        "<strong>Esto NO es una bandera</strong>, y lo medido el 6 de septiembre "
        "lo dice más fuerte de lo que se esperaba. De 2.334 procesos competitivos "
        "adjudicados, los que terminaron con un solo proveedor tuvieron una "
        "<strong>mediana de 16 visualizaciones</strong>; los que terminaron con "
        "varios, <strong>32</strong>. Una sola oferta es, por regla, la marca de "
        "un proceso que nadie miró — no de uno muy mirado al que nadie se "
        "presentó. Solo 30 de 1.239 superan el percentil 90 de su propia "
        "modalidad, cuando por azar serían unos 124. Son estos, y se listan "
        "porque son el caso raro dentro del caso raro y mirarlos sale barato.",
        datos.get("competitivos_con_un_oferente") or [],
        lambda f: (
            (f'<td class="id"><a href="{e(f["enlace"])}" target="_blank" rel="noopener">'
             f'{e(f["id_del_proceso"])}</a></td>') if f.get("enlace")
            else f'<td class="id">{e(f["id_del_proceso"])}</td>',
            f'<td>{e(f.get("entidad"))}</td>',
            f'<td>{e(f.get("modalidad"))}</td>',
            f'<td class="num">{numero(f.get("visualizaciones"))}</td>',
            f'<td class="num">{_percentil(f)}</td>',
            f'<td class="num">{compacto(_valor(f))}</td>',
        ),
        ["Proceso", "Entidad", "Modalidad", "~Vistas", "~Percentil", "~Valor"],
        "Ninguno en esta ventana.",
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qué revisar primero</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
:root {{
  --papel:#EEF1F1; --superficie:#FFFFFF; --borde:#D3DADB; --borde-sutil:#E4E9E9;
  --tinta:#0E1719; --tinta-2:#3A4A4D; --tinta-3:#6B7B7E;
  --acento:#0091A8; --acento-flojo:#DCEFF3; --aviso:#A8620F; --aviso-flojo:#F6E9D8;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --papel:#10171A; --superficie:#171F22; --borde:#2B383C; --borde-sutil:#212B2E;
    --tinta:#E8EDED; --tinta-2:#AEBDBF; --tinta-3:#7C8C8F;
    --acento:#22A0B8; --acento-flojo:#123239; --aviso:#D9903F; --aviso-flojo:#31261A;
  }}
}}
:root[data-theme="dark"] {{
  --papel:#10171A; --superficie:#171F22; --borde:#2B383C; --borde-sutil:#212B2E;
  --tinta:#E8EDED; --tinta-2:#AEBDBF; --tinta-3:#7C8C8F;
  --acento:#22A0B8; --acento-flojo:#123239; --aviso:#D9903F; --aviso-flojo:#31261A;
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--papel); color:var(--tinta);
  font-family:Archivo,"Segoe UI",system-ui,sans-serif; font-size:15px; line-height:1.55; }}
.envoltura {{ max-width:1180px; margin:0 auto; padding:32px 20px 72px; }}
header.top {{ display:flex; flex-wrap:wrap; gap:14px 30px; align-items:baseline;
  justify-content:space-between; padding-bottom:18px; border-bottom:2px solid var(--tinta); }}
h1 {{ margin:0; font-size:29px; letter-spacing:-.02em; }}
.lede {{ font-family:"Source Serif 4",Georgia,serif; font-size:15px;
  color:var(--tinta-2); max-width:60ch; margin:4px 0 0; }}
.sello {{ font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--tinta-3);
  text-align:right; }}
.cifras {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
  gap:1px; background:var(--borde); border:1px solid var(--borde); border-top:none;
  margin:0 0 12px; }}
.caja {{ background:var(--superficie); padding:16px 18px 14px; }}
.caja .rot {{ font-size:11px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--tinta-3); font-weight:600; }}
.caja .dat {{ font-family:"IBM Plex Mono",monospace; font-size:25px; margin-top:3px;
  font-variant-numeric:tabular-nums; }}
.caja .plata {{ font-family:"IBM Plex Mono",monospace; font-size:14px; color:var(--acento); }}
.caja .pie {{ font-size:12px; color:var(--tinta-3); margin-top:3px; }}
.privado {{ border:1px solid var(--aviso); background:var(--aviso-flojo);
  border-radius:6px; padding:14px 16px; margin:0 0 14px; font-size:14px;
  color:var(--tinta-2); }}
.privado strong {{ color:var(--tinta); }}
.aviso {{ border:1px solid var(--borde); border-left:3px solid var(--aviso);
  background:var(--superficie); padding:16px 18px; margin:0 0 36px;
  font-family:"Source Serif 4",Georgia,serif; font-size:14.5px; color:var(--tinta-2);
  max-width:78ch; }}
.aviso strong {{ color:var(--tinta); }}
section {{ margin:0 0 40px; }}
.cab {{ margin-bottom:12px; }}
.cab h2 {{ margin:0; font-size:13px; font-weight:700; text-transform:uppercase;
  letter-spacing:.1em; color:var(--acento); }}
.cab p {{ margin:6px 0 0; font-family:"Source Serif 4",Georgia,serif; font-size:14.5px;
  color:var(--tinta-2); max-width:74ch; }}
.tarjeta {{ background:var(--superficie); border:1px solid var(--borde); padding:16px 18px; }}
.scroll {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
th {{ text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--tinta-3); font-weight:600; padding:0 12px 8px 0;
  border-bottom:1px solid var(--borde); white-space:nowrap; }}
th.num {{ text-align:right; }}
td {{ padding:9px 12px 9px 0; border-bottom:1px solid var(--borde-sutil); vertical-align:top; }}
tr:last-child td {{ border-bottom:none; }}
.num {{ text-align:right; font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums; white-space:nowrap; }}
.id {{ font-family:"IBM Plex Mono",monospace; font-size:11.5px; white-space:nowrap; }}
.id a {{ color:var(--acento); }}
.otros {{ display:block; font-size:11.5px; color:var(--tinta-3); }}
.pill {{ display:inline-block; font-size:11px; padding:1px 7px;
  background:var(--acento-flojo); color:var(--tinta-2); white-space:nowrap; }}
.vacio {{ color:var(--tinta-3); font-style:italic; margin:0; }}
footer {{ margin-top:44px; padding-top:16px; border-top:1px solid var(--borde);
  font-family:"IBM Plex Mono",monospace; font-size:11.5px; color:var(--tinta-3); }}
</style>
</head>
<body>
<div class="envoltura">
  <header class="top">
    <div>
      <h1>Qué revisar primero</h1>
      <p class="lede">Contratos y procesos que vale la pena mirar antes que los
        otros, cada uno con la razón por la que está aquí.</p>
    </div>
    <div class="sello">ventana {e(v.get("desde"))} → {e(v.get("hasta"))}<br>
      {numero(v.get("contratos"))} contratos · {compacto(v.get("valor"))}<br>
      generado {e(generado)}</div>
  </header>

  {resumen}

  <div class="privado"><strong>Esta página no se comparte.</strong> Lleva
  nombres de contratistas y documentos de personas naturales. Los documentos
  van enmascarados —se ven los últimos tres dígitos, suficiente para
  distinguir dos filas y no para reconstruir un número— pero los nombres y las
  entidades van completos. <strong>No la mandes por chat ni por correo, y no le
  hagas capturas.</strong> Para ir a mirar un contrato al SECOP se usa el
  identificador del contrato, que está completo en la primera columna.</div>

  <div class="aviso"><strong>Esto no son alertas.</strong> Ninguna fila de esta
  página afirma que haya un problema con un contrato, una entidad o una persona.
  Todos los criterios son hechos sobre el dato —falta un nombre, falta un cruce,
  falta un documento— y estar en esta lista significa «esto todavía no lo
  sabemos» o «esto es grande y conviene verlo». Las Reglas de verdad vendrán
  después, y ninguna se enciende sin calibrar antes contra datos reales.</div>

  {erratas}
  {imposibles}
  {sin_nombre}
  {uniones}
  {competitivos}
  {huerfanos}
  {variantes}

  <footer>Vigía SECOP · indicadores estadísticos · no constituyen imputación</footer>
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vigia.revision")
    ap.add_argument("--json", default="revision.json")
    ap.add_argument("--salida", default="revision.html")
    ap.add_argument(
        "--documentos-completos", action="store_true",
        help=("Escribe los documentos de personas naturales sin enmascarar. "
              "Se pide a sabiendas, y la página resultante es un dato personal."),
    )
    o = ap.parse_args(argv)

    origen = Path(o.json)
    if not origen.exists():
        print(f"no existe {origen}", file=sys.stderr)
        return CODIGO_USO
    datos = json.loads(origen.read_text(encoding="utf-8"))
    if "conteos" not in datos:
        print(f"a {origen} le falta la sección «conteos»", file=sys.stderr)
        return CODIGO_FALLO

    Path(o.salida).write_text(
        construir(datos, completo=o.documentos_completos), encoding="utf-8")
    c = datos["conteos"]
    print(f"Lista de revisión escrita en {Path(o.salida).resolve()}")
    print(f"  {numero(c.get('sin_razon_social'))} sin razón social · "
          f"{numero(c.get('uniones'))} uniones sin documento · "
          f"{numero(c.get('huerfanos'))} huérfanos")
    # Los imposibles se gritan, no se listan al lado de los demás. Cuando hay
    # uno, cualquier total publicado sin la guarda estaría mal por órdenes de
    # magnitud, y eso tiene que verse en la corrida del ciclo — no solo en una
    # página que a lo mejor nadie abre ese día.
    if c.get("imposibles"):
        print(f"  ATENCION: {numero(c['imposibles'])} contrato(s) con valor "
              f"imposible ({compacto(c.get('valor_imposibles'))} declarados). "
              "Estan fuera de todos los totales; se listan en revision.html.")
    # Las erratas ×10ⁿ también se gritan, y por una razón distinta: NO están
    # fuera de ningún total. El valor cabe en la realidad, así que entra en
    # todas las sumas y en todos los rankings por valor. Mientras una de estas
    # esté dentro, el contrato más grande de la ventana puede ser una tecla.
    ce = datos.get("conteo_erratas") or {}
    if ce.get("erratas"):
        print(f"  ATENCION: {numero(ce['erratas'])} contrato(s) con valor "
              f"exactamente 10^n veces el presupuesto de su proceso "
              f"({compacto(ce.get('valor_erratas'))}). Casi seguro son erratas "
              "de tecleo y SI estan dentro de los totales. Ver revision.html "
              "antes de publicar cualquier ranking por valor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
