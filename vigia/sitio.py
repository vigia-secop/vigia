"""El sitio público: `docs/`, que es lo que ve internet.

    python -m vigia.sitio --json boletin.json --docs docs

DE DÓNDE SALE LO QUE SE PUBLICA, Y DE DÓNDE NO. Este módulo lee **únicamente**
el JSON de `boletin.sql`, que por diseño no puede devolver el nombre ni el
documento de nadie. No lee `panel.json` ni `revision.json`, aunque tengan más
cosas y se vean mejor: esos llevan razones sociales y cédulas de contratistas
personas naturales, y viven en el escritorio.

Es la misma decisión que el boletín, por la misma razón: **lo que se publica no
se puede despublicar.** Una garantía que depende de acordarse no es una
garantía; una que depende de qué consulta alimenta el archivo, sí.

QUÉ PUBLICA. Cuánto contrató el Estado colombiano en el período, a qué ritmo
por día hábil, dónde, bajo qué modalidad — y, antes que cualquier ranking,
**qué parte de eso no se puede ver**. Ese último bloque es el producto: hoy
nadie lo publica en Colombia semana tras semana.

QUÉ NO PUBLICA. Banderas. No hay ninguna calibrada: se midieron tres y las tres
describían la mayoría del país. Hasta que exista una que aguante, el sitio no
señala a nadie, y lo dice en su propia página.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from vigia import estilo
from vigia.calendario import dias_habiles
from vigia.marca import TINTA, ojo
from vigia.panel import compacto, e, numero, pesos, titulo_es
from vigia.publicacion import (NOTA, exigir_publicable,
                               periodo_anterior_comparable)

CODIGO_USO = 2
CODIGO_FALLO = 1

TITULO = "Vigía"
LEMA = "Cuánto contrata el Estado colombiano, y qué parte no se puede ver."


def _fecha(texto) -> date:
    return date.fromisoformat(str(texto)[:10])


def _dia_mes(d: date) -> str:
    meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre")
    return f"{d.day} de {meses[d.month - 1]}"


def pct(parte, total, dec: int = 1) -> str:
    if not total:
        return "—"
    return f"{100 * float(parte) / float(total):.{dec}f}".replace(".", ",") + " %"


def variacion(actual, previo) -> tuple[str, str]:
    """El cambio y su clase de color. `—` cuando no se puede calcular."""
    if actual is None or previo is None or previo == 0:
        return "—", "neutro"
    cambio = 100 * (actual - previo) / previo
    texto = f"{'+' if cambio > 0 else ''}{cambio:.1f} %".replace(".", ",")
    if abs(cambio) < 5:
        return texto, "neutro"
    return texto, ("sube" if cambio > 0 else "baja")


def _barras(filas, clave_nombre, clave_valor, formato=compacto, limite=8,
            titulo=True) -> str:
    filas = (filas or [])[:limite]
    if not filas:
        return '<p class="vacio">Sin datos en este período.</p>'
    tope = max(float(f[clave_valor] or 0) for f in filas) or 1
    cuerpo = []
    for f in filas:
        ancho = 100 * float(f[clave_valor] or 0) / tope
        cuerpo.append(
            # `titulo_es` es para nombres propios. Aplicarlo a una etiqueta
            # que ya es una frase produce «Mas de 10 Mil Millones», que se lee
            # como un error de quien escribe y le resta a todo lo demás.
            '<li><span class="et">'
            f'{e(titulo_es(str(f[clave_nombre])) if titulo else str(f[clave_nombre]))}</span>'
            f'<span class="bar"><span style="width:{ancho:.1f}%"></span></span>'
            f'<span class="ci">{formato(f[clave_valor])}</span></li>'
        )
    return f'<ul class="barras">{"".join(cuerpo)}</ul>'


def _favicon() -> str:
    """El ojo como favicon, incrustado en la propia página.

    Va como `data:` y no como archivo aparte para que no dependa de una ruta:
    un favicon roto en GitHub Pages es de los errores que nadie ve y todo el
    mundo nota.
    """
    from urllib.parse import quote

    return quote(ojo(alto=32, color=TINTA), safe="")


def _resumen_meta(a, hab, desde, hasta) -> str:
    """La frase que se ve en la previsualización del enlace.

    Lleva la cifra y el ritmo por día hábil, que es lo que distingue a Vigía
    de repetir un total. Se corta a 200 caracteres porque más de eso lo corta
    X, y prefiero elegir yo dónde.
    """
    por_dia = (float(a["valor"]) / hab) if hab else None
    texto = (
        f'{numero(a["contratos"])} contratos por {compacto(a["valor"])} '
        f'en {hab} días hábiles — {compacto(por_dia)} al día. '
        f'{numero(a["entidades"])} entidades, {numero(a["proveedores"])} contratistas.'
    )
    return texto[:200]


def _erratas(c: dict) -> str:
    """Los contratos apartados por tener un cero de mas, y cuanto sumaban.

    **Solo aparece cuando hay alguno.** Un aviso permanente que casi siempre
    dice cero se vuelve decorado y deja de leerse el dia que importa.

    Hasta el 2026-09-16 esta pagina —y el hilo que la acompana— sumaba las
    erratas de tecleo sin marcarlas siquiera. Probado contra el fixture: una
    semana con cuatro de ellas habria publicado $823,5 mil millones en vez de
    $6,8 mil millones. Ciento veinte veces.

    Ahora estan fuera de todas las cifras de la pagina, y este parrafo existe
    para decirlo. Apartar sin decirlo es esconder; la cifra que se ensena es
    la que sumarian, o sea el tamano exacto del error que se evito.

    **AQUI NO VAN LOS NOMBRES, Y NO ES UN OLVIDO.** `boletin.sql` -la consulta
    que alimenta esta pagina y el hilo de X- tiene prohibido devolver el
    nombre de nadie, y esa prohibicion es la unica garantia que no depende de
    que alguien se acuerde. Romperla para listar cuatro erratas seria cambiar
    una garantia estructural por una comodidad.

    Asi que se enlaza el Panel, que si los publica uno por uno con las dos
    cifras y la ficha del SECOP. El dato sale igual; la garantia se queda.
    """
    cuantas = int(c.get("erratas") or 0)
    if not cuantas:
        return ""
    plural = "" if cuantas == 1 else "s"
    return (
        '<p class="alcance-errata" style="margin:14px 0 0">'
        f"<strong>{numero(cuantas)} contrato{plural} quedaron fuera de todas "
        "las cifras de esta página.</strong> Su valor adjudicado es "
        "<strong>exactamente</strong> mil o diez mil veces el presupuesto "
        "oficial de su propio proceso: la firma de una tecla de más, no la de "
        f"un sobrecosto. Sumaban {compacto(c.get('valor_erratas'))} tal como "
        "la fuente los publica — ese habría sido el tamaño del error.</p>"
        '<p class="alcance-errata" style="margin:6px 0 0">Apartarlos no es '
        "taparlos: un valor que no cuadra con el presupuesto de su propio "
        "proceso vale la pena mirarlo. Salen uno por uno, con las dos cifras "
        'y el enlace a la ficha oficial, en el <a href="panel.html">Panel</a>. '
        "Vigía no corrige la fuente ni adivina el valor verdadero.</p>"
    )


def construir(datos: dict, *, periodo: str = "semana", archivo: list | None = None) -> str:
    p, ant = datos["periodo"], datos["anterior"]
    a, b = datos["actual"], datos["anterior_cifras"]
    c = datos["cobertura"]
    d_desde, d_hasta = _fecha(p["desde"]), _fecha(p["hasta"])
    a_desde, a_hasta = _fecha(ant["desde"]), _fecha(ant["hasta"])
    hab_a = dias_habiles(d_desde, d_hasta)
    hab_p = dias_habiles(a_desde, a_hasta)
    generado = str(datos.get("generado_en", ""))[:10]

    def ritmo(v, h):
        return (float(v) / h) if h else None

    # Si el período anterior queda antes de lo que hemos traído, sus cifras
    # salen en cero y la «variación» sería una caída del 100 % inventada. Se
    # calla, y se dice por qué: callarse es un resultado, inventar no.
    comparable = periodo_anterior_comparable(datos)
    if comparable:
        v_contratos, cl_contratos = variacion(
            ritmo(a["contratos"], hab_a), ritmo(b["contratos"], hab_p))
        v_valor, cl_valor = variacion(
            ritmo(float(a["valor"]), hab_a), ritmo(float(b["valor"]), hab_p))
        pie_var = "por día hábil, contra el período anterior"
    else:
        v_contratos = v_valor = "sin comparación"
        cl_contratos = cl_valor = "neutro"
        pie_var = "no hay período anterior ingerido con que comparar"


    total_cob = c["contratos"] or 1
    pct_ut = pct(c["valor_uniones"] or 0, a["valor"] or 1)

    filas_archivo = ""
    if archivo:
        filas_archivo = "".join(
            f'<li><a href="semanas/{e(x["archivo"])}">{e(x["titulo"])}</a></li>'
            for x in archivo
        )
        filas_archivo = f'<ul class="archivo">{filas_archivo}</ul>'

    TINTA_TEMA = "currentColor"
    mods = datos.get("modalidades") or []
    total_m = sum(int(f["contratos"]) for f in mods) or 1

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITULO} · {_dia_mes(d_desde)} al {_dia_mes(d_hasta)} de {d_hasta.year}</title>
<meta name="description" content="{_resumen_meta(a, hab_a, d_desde, d_hasta)}">
<link rel="icon" href="data:image/svg+xml,{_favicon()}">
<!-- Lo que X, WhatsApp y LinkedIn muestran al compartir el enlace. El título
     y la descripción llevan las cifras de ESTA semana; la imagen es fija y se
     genera una sola vez, así publicar no necesita ninguna librería de imagen
     en el equipo de quien publica. -->
<meta property="og:type" content="website">
<meta property="og:title" content="{TITULO} · {_dia_mes(d_desde)} al {_dia_mes(d_hasta)}">
<meta property="og:description" content="{_resumen_meta(a, hab_a, d_desde, d_hasta)}">
<meta property="og:image" content="img/vigia-card.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{TITULO} · {_dia_mes(d_desde)} al {_dia_mes(d_hasta)}">
<meta name="twitter:description" content="{_resumen_meta(a, hab_a, d_desde, d_hasta)}">
<meta name="twitter:image" content="img/vigia-card.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
:root {{
  --papel:#EEF1F1; --superficie:#FFFFFF; --borde:#D3DADB; --borde-sutil:#E4E9E9;
  --tinta:#0E1719; --tinta-2:#3A4A4D; --tinta-3:#6B7B7E;
  --acento:#0091A8; --acento-flojo:#DCEFF3;
  --sube:#1D6B4F; --baja:#A8451B; --aviso:#A8620F; --aviso-flojo:#F6E9D8;
  --marca:#04275D;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --papel:#10171A; --superficie:#171F22; --borde:#2B383C; --borde-sutil:#212B2E;
    --tinta:#E8EDED; --tinta-2:#AEBDBF; --tinta-3:#7C8C8F;
    --acento:#22A0B8; --acento-flojo:#12313A;
    --sube:#4FB489; --baja:#D98055; --aviso:#D9903F; --aviso-flojo:#31261A;
    --marca:#8FB2E8;
  }}
}}
:root[data-theme="dark"] {{
  --papel:#10171A; --superficie:#171F22; --borde:#2B383C; --borde-sutil:#212B2E;
  --tinta:#E8EDED; --tinta-2:#AEBDBF; --tinta-3:#7C8C8F;
  --acento:#22A0B8; --acento-flojo:#12313A;
  --sube:#4FB489; --baja:#D98055; --aviso:#D9903F; --aviso-flojo:#31261A;
  --marca:#8FB2E8;
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--papel); color:var(--tinta);
  font-family:Archivo,"Segoe UI",system-ui,sans-serif; font-size:16px; line-height:1.6; }}
.env {{ max-width:800px; margin:0 auto; padding:40px 20px 80px; }}
header.top {{ border-bottom:2px solid var(--tinta); padding-bottom:20px; }}
.marca {{ display:flex; align-items:center; gap:14px; color:var(--marca); }}
.marca svg {{ flex:0 0 auto; }}
h1 {{ margin:0; font-size:30px; letter-spacing:-.02em; }}
.lema {{ margin:6px 0 0; color:var(--tinta-2); font-family:"Source Serif 4",Georgia,serif;
  font-size:18px; }}
.per {{ margin-top:14px; font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:13px; color:var(--tinta-3); }}
h2 {{ font-size:20px; margin:44px 0 4px; letter-spacing:-.01em; }}
h2 + .sub {{ margin:0 0 16px; color:var(--tinta-3); font-size:14.5px; }}
.cifras {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  margin-top:26px; }}
.caja {{ background:var(--superficie); border:1px solid var(--borde); border-radius:8px;
  padding:16px 18px; }}
.rot {{ font-size:12px; text-transform:uppercase; letter-spacing:.07em; color:var(--tinta-3); }}
.dat {{ font-size:27px; font-weight:600; letter-spacing:-.02em; margin-top:4px; }}
.var {{ font-size:13px; font-weight:600; margin-top:2px; }}
.sube {{ color:var(--sube); }} .baja {{ color:var(--baja); }} .neutro {{ color:var(--tinta-3); }}
.pie {{ font-size:12.5px; color:var(--tinta-3); margin-top:6px; }}
.tarjeta {{ background:var(--superficie); border:1px solid var(--borde);
  border-radius:8px; padding:18px 20px; }}
.alcance {{ border-left:3px solid var(--aviso); background:var(--aviso-flojo); }}
.alcance li {{ margin:8px 0; }}
.alcance ul {{ margin:10px 0 0; padding-left:20px; }}
.barras {{ list-style:none; margin:0; padding:0; }}
.barras li {{ display:grid; grid-template-columns:1fr 2fr auto; gap:12px;
  align-items:center; padding:7px 0; border-bottom:1px solid var(--borde-sutil); }}
.barras li:last-child {{ border-bottom:0; }}
.et {{ font-size:14px; }}
.ci {{ font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:13px;
  text-align:right; white-space:nowrap; }}
.bar {{ display:block; height:7px; background:var(--borde-sutil); border-radius:4px;
  overflow:hidden; }}
.bar > span {{ display:block; height:100%; background:var(--acento); }}
.nota {{ margin-top:44px; padding:18px 20px; border:1px solid var(--borde);
  border-radius:8px; background:var(--superficie); font-size:14.5px; color:var(--tinta-2); }}
.nota strong {{ color:var(--tinta); }}
.archivo {{ list-style:none; padding:0; margin:10px 0 0; }}
.archivo li {{ padding:6px 0; border-bottom:1px solid var(--borde-sutil); }}
a {{ color:var(--acento); }}
footer {{ margin-top:52px; padding-top:18px; border-top:1px solid var(--borde);
  font-size:13px; color:var(--tinta-3); }}
.vacio {{ color:var(--tinta-3); font-size:14px; margin:0; }}
@media (max-width:520px) {{
  .barras li {{ grid-template-columns:1fr auto; }}
  .bar {{ display:none; }}
}}
{estilo.NAV_CSS}
</style>
</head>
<body>
<div class="env">

  <header class="top">
    <div class="marca">{ojo(alto=54, color=TINTA_TEMA)}<h1>{TITULO}</h1></div>
    <p class="lema">{LEMA}</p>
    <p class="per">{_dia_mes(d_desde)} al {_dia_mes(d_hasta)} de {d_hasta.year}
      · {hab_a} días hábiles · datos al {generado}</p>
    {estilo.menu("semana.html")}
  </header>

  <div class="cifras">
    <div class="caja"><div class="rot">Contratos firmados</div>
      <div class="dat">{numero(a["contratos"])}</div>
      <div class="var {cl_contratos}">{v_contratos}</div>
      <div class="pie">{numero(round(ritmo(a["contratos"], hab_a) or 0))} al día · {pie_var}</div></div>
    <div class="caja"><div class="rot">Valor</div>
      <div class="dat">{compacto(a["valor"])}</div>
      <div class="var {cl_valor}">{v_valor}</div>
      <div class="pie">{compacto(ritmo(float(a["valor"]), hab_a))} al día</div></div>
    <div class="caja"><div class="rot">Entidades</div>
      <div class="dat">{numero(a["entidades"])}</div>
      <div class="pie">contrataron en el período</div></div>
    <div class="caja"><div class="rot">Contratistas</div>
      <div class="dat">{numero(a["proveedores"])}</div>
      <div class="pie">identidades distintas</div></div>
  </div>

  <h2>Todo se compara por día hábil</h2>
  <p class="sub">Y no por cortesía estadística.</p>
  <div class="tarjeta">
    <p style="margin:0">{'Este período tuvo <strong>%d días hábiles</strong>; el anterior, <strong>%d</strong>.' % (hab_a, hab_p) if comparable else 'Este período tuvo <strong>%d días hábiles</strong>. <strong>No se muestra comparación con el período anterior</strong> porque empieza antes del primer contrato que tenemos ingerido: sus cifras saldrían en cero y eso se leería como una caída que no ocurrió.' % hab_a} Comparar dos períodos con conteos
    crudos es comparar almanaques: el 3 de septiembre de 2026 los conteos sin
    normalizar decían que la contratación había caído un 45,7 % tras el cambio
    de gobierno. Eran dos festivos. La diferencia real era del 1,0 %.</p>
  </div>

  <h2>Lo que estas cifras no alcanzan a ver</h2>
  <p class="sub">Va antes que cualquier ranking, a propósito.</p>
  <div class="tarjeta alcance">
    <p style="margin:0">Una cifra de contratación pública sin saber sobre qué
    parte del universo se calculó es la clase de número que se lee mal. Estas
    son las partes que quedan fuera del alcance de cada medición:</p>
    <ul>
      <li><strong>{numero(c["uniones"])} contratos</strong> de uniones temporales
        y consorcios sin documento de identificación
        ({compacto(c["valor_uniones"])}, <strong>{pct_ut} del valor</strong>).
        Cada uno es su propia identidad: no se les puede medir concentración
        hasta conocer a sus integrantes, y la fuente no los publica.</li>
      <li><strong>{numero(c["huerfanos"])} contratos</strong>
        ({pct(c["huerfanos"], total_cob)}) traen llave de cruce y no encontraron
        su proceso: sin proceso no hay modalidad ni plazo que medir.</li>
      <li><strong>{numero(c["sin_departamento"])} contratos</strong>
        ({pct(c["sin_departamento"], total_cob)}) sin departamento declarado.</li>
      <li><strong>{numero(c["sin_valor"])} contratos</strong> sin valor.</li>
    </ul>
    {_erratas(c)}
  </div>

  <h2>Dónde se firmó</h2>
  <p class="sub">Por valor adjudicado.</p>
  <div class="tarjeta">{_barras(datos.get("departamentos"), "nombre", "valor")}</div>

  <h2>Cómo se contrató</h2>
  <p class="sub">Por número de contratos.</p>
  <div class="tarjeta">{_barras(mods, "modalidad", "contratos",
      formato=lambda v: pct(v, total_m, 0))}</div>

  <h2>La forma del gasto</h2>
  <p class="sub">Muchísimos contratos pequeños, muy pocos grandes.</p>
  <div class="tarjeta">{_barras(datos.get("tramos"), "tramo", "valor", limite=8,
      titulo=False)}</div>

  <div class="nota">
    <p style="margin:0 0 10px"><strong>Qué es esto, y qué no.</strong> {NOTA}</p>
    <p style="margin:0 0 10px">Vigía SECOP <strong>no señala contratos, ni
    entidades, ni personas</strong>. No publica banderas porque no tiene ninguna
    calibrada: se midieron tres sobre los datos reales y las tres describían la
    mayoría del país, no la excepción. Encender una regla sin calibrar es peor
    que no tenerla, porque una alerta inventada le cuesta a alguien su
    reputación y no hay forma de devolvérsela.</p>
    <p style="margin:0">Lo que sí hace es publicar los números, con su
    cobertura al lado, para que quien quiera investigar sepa por dónde empezar.
    Los datos vienen de <a href="https://www.datos.gov.co">datos.gov.co</a>,
    son públicos, y cualquiera puede rehacer estas cuentas.</p>
  </div>

  <h2>Ver el detalle</h2>
  <p class="sub">Las mismas cifras, contrato por contrato.</p>
  <div class="tarjeta">
    <ul class="archivo">
      <li><a href="archivo.html"><strong>El archivo</strong></a> — el mismo
        dato día por día, semana por semana y mes por mes, desde que hay
        historia. Va de primero porque es la pregunta que más se hace: «¿y
        cómo fue tal día?».</li>
      <li><a href="panel.html"><strong>Panel</strong></a> — entidades,
        contratistas, departamentos y modalidades, con el alcance de cada
        medición declarado antes que cualquier ranking.</li>
      <li><a href="revision.html"><strong>Qué revisar primero</strong></a> —
        contratos que vale la pena mirar, cada uno con el hecho concreto por el
        que está listado y el enlace a su ficha en SECOP. <strong>No son
        alertas.</strong></li>
    </ul>
    <p class="sub" style="margin:14px 0 0">El NIT de las empresas va completo;
    el documento de una persona natural va enmascarado. Para comprobar
    cualquier contrato se usa el enlace a SECOP, que lleva a la ficha oficial
    con todo el expediente.</p>
  </div>

  {f'<h2>Períodos anteriores</h2><div class="tarjeta">{filas_archivo}</div>'
   if filas_archivo else ''}

  <footer>Vigía SECOP · indicadores estadísticos · no constituyen imputación</footer>
</div>
</body>
</html>
"""


def texto_visible(html: str) -> list[str]:
    """El texto que una persona lee, sin etiquetas. Lo que revisa la barrera."""
    import re

    sin_estilo = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S | re.I)
    sin_tags = re.sub(r"<[^>]+>", " ", sin_estilo)
    return [t for t in (l.strip() for l in sin_tags.splitlines()) if t]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vigia.sitio")
    ap.add_argument("--json", default="boletin.json")
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--periodo", default="semana")
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

    docs = Path(o.docs)
    semanas = docs / "semanas"
    semanas.mkdir(parents=True, exist_ok=True)

    # El archivo se arma leyendo la carpeta, no una lista guardada: así no hay
    # dos verdades sobre qué períodos existen.
    previos = sorted((f.name for f in semanas.glob("*.html")), reverse=True)
    archivo = [{"archivo": n, "titulo": n[:-5]} for n in previos[:26]]

    html = construir(datos, periodo=o.periodo, archivo=archivo)

    # LA BARRERA, sobre el texto que de verdad se lee. Si algo no se puede
    # publicar, no se escribe nada: ni index, ni archivo.
    lineas = texto_visible(html)
    try:
        # El límite de 280 no aplica a una página web; se revisa el resto
        # partiendo el texto en trozos que sí caben.
        trozos = [l[i:i + 250] for l in lineas for i in range(0, len(l), 250)]
        exigir_publicable(trozos + [NOTA])
    except Exception as error:
        print(f"NO SE PUBLICA: {error}", file=sys.stderr)
        return CODIGO_FALLO

    # LA PORTADA YA NO ES ESTA PÁGINA, y el cambio es de fondo.
    #
    # Hasta el 2026-09-14 el boletín del período era también `index.html`: quien
    # entraba un miércoles veía la semana pasada. Eso está bien para un boletín
    # y mal para un registro — y lo que hace citable a Vigía es ser un registro:
    # quien entra un miércoles tiene que ver el miércoles.
    #
    # Así que el boletín se queda en `semana.html` y en su copia fechada, que es
    # la que tiene URL permanente y no cambia nunca; `index.html` lo escribe
    # `vigia/portada.py` todos los días. El publicador corre los dos, y si la
    # portada falla aborta antes de subir: nunca queda un `docs/` sin portada.
    sello = str(datos["periodo"]["desde"])[:10]
    (semanas / f"{sello}.html").write_text(html, encoding="utf-8")
    (docs / "semana.html").write_text(html, encoding="utf-8")
    (docs / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Sitio escrito en {docs.resolve()}")
    print(f"  semana.html y semanas/{sello}.html · {len(previos) + 1} período(s)")
    print("  revisado: sin documentos de identidad, sin vocabulario de imputación")
    return 0


if __name__ == "__main__":
    sys.exit(main())
