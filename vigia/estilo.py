"""La paleta del sitio público, en un solo sitio.

POR QUÉ EXISTE ESTE ARCHIVO. Hasta hoy la paleta vivía escrita a mano dentro
del f-string de `sitio.py`. Con una sola página eso no molesta. Con dos —el
boletín del período y la portada del día— molesta el día que alguien cambia un
color en una y no en la otra, y el sitio queda con dos identidades sin que
nadie lo note, porque nadie mira las dos páginas seguidas.

Los valores son exactamente los que ya tenía `sitio.py`. No se cambia ninguno
aquí: esto es mudanza, no rediseño. Y hay una prueba —`test_estilo.py`— que
compara estos números contra los que sigue escribiendo `sitio.py`, para que si
alguna vez se separan, se sepa el mismo día.

LOS TRES ESTADOS DEL TEMA, y son tres y no dos: el visitante puede tener el
tema en claro, en oscuro, o —lo más común— en «el del sistema», que no deja
ninguna marca en el documento. Por eso el bloque `:root` pelado lleva la
paleta clara completa, el `@media` la vuelve a definir para el oscuro del
sistema, y el `[data-theme="dark"]` otra vez para la elección explícita. Un
color definido solo dentro de un `@media` no existe en el estado sin marca, y
esa es la forma más común de publicar una página ilegible.
"""

from __future__ import annotations

#: Paleta clara. Es la que va en el `:root` pelado.
CLARO = {
    "papel": "#EEF1F1",
    "superficie": "#FFFFFF",
    "borde": "#D3DADB",
    "borde-sutil": "#E4E9E9",
    "tinta": "#0E1719",
    "tinta-2": "#3A4A4D",
    "tinta-3": "#6B7B7E",
    "acento": "#0091A8",
    "acento-flojo": "#DCEFF3",
    "sube": "#1D6B4F",
    "baja": "#A8451B",
    "aviso": "#A8620F",
    "aviso-flojo": "#F6E9D8",
    "marca": "#04275D",
}

#: Paleta oscura. No es una inversión automática de la clara: el acento y los
#: colores de variación se vuelven a elegir para que sigan leyéndose sobre un
#: fondo oscuro, que es donde una inversión ingenua se rompe.
OSCURO = {
    "papel": "#10171A",
    "superficie": "#171F22",
    "borde": "#2B383C",
    "borde-sutil": "#212B2E",
    "tinta": "#E8EDED",
    "tinta-2": "#AEBDBF",
    "tinta-3": "#7C8C8F",
    "acento": "#22A0B8",
    "acento-flojo": "#12313A",
    "sube": "#4FB489",
    "baja": "#D98055",
    "aviso": "#D9903F",
    "aviso-flojo": "#31261A",
    "marca": "#8FB2E8",
}


def _declaraciones(paleta: dict[str, str], sangria: str = "  ") -> str:
    return "\n".join(f"{sangria}--{k}:{v};" for k, v in paleta.items())


def tokens() -> str:
    """Los tres bloques de tema, listos para meter en un `<style>`.

    Devuelve CSS literal —sin llaves que haya que escapar— porque quien lo usa
    lo inserta dentro de un f-string, y duplicar llaves a mano es de donde han
    salido ya dos erratas en este proyecto.
    """
    return (
        ":root {\n" + _declaraciones(CLARO) + "\n}\n"
        '@media (prefers-color-scheme: dark) {\n'
        '  :root:not([data-theme="light"]) {\n'
        + _declaraciones(OSCURO, "    ") + "\n  }\n}\n"
        ':root[data-theme="dark"] {\n' + _declaraciones(OSCURO) + "\n}\n"
    )


#: Las reglas que comparten todas las páginas públicas. Lo específico de cada
#: página se queda en su módulo: aquí solo va lo que de verdad se repite.
BASE = """
*,*::before,*::after { box-sizing:border-box; }
body { margin:0; background:var(--papel); color:var(--tinta);
  font-family:Archivo,"Segoe UI",system-ui,sans-serif; font-size:16px; line-height:1.6; }
.env { max-width:800px; margin:0 auto; padding:40px 20px 80px; }
header.top { border-bottom:2px solid var(--tinta); padding-bottom:20px; }
.marca { display:flex; align-items:center; gap:14px; color:var(--marca); }
.marca svg { flex:0 0 auto; }
h1 { margin:0; font-size:30px; letter-spacing:-.02em; }
.lema { margin:6px 0 0; color:var(--tinta-2); font-family:"Source Serif 4",Georgia,serif;
  font-size:18px; }
.per { margin-top:14px; font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:13px; color:var(--tinta-3); }
h2 { font-size:20px; margin:44px 0 4px; letter-spacing:-.01em; }
h2 + .sub { margin:0 0 16px; color:var(--tinta-3); font-size:14.5px; }
.cifras { display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  margin-top:26px; }
.caja { background:var(--superficie); border:1px solid var(--borde); border-radius:8px;
  padding:16px 18px; }
.rot { font-size:12px; text-transform:uppercase; letter-spacing:.07em; color:var(--tinta-3); }
.dat { font-size:27px; font-weight:600; letter-spacing:-.02em; margin-top:4px;
  font-variant-numeric:tabular-nums; }
.var { font-size:13px; font-weight:600; margin-top:2px; }
.sube { color:var(--sube); } .baja { color:var(--baja); } .neutro { color:var(--tinta-3); }
.pie { font-size:12.5px; color:var(--tinta-3); margin-top:6px; }
.tarjeta { background:var(--superficie); border:1px solid var(--borde);
  border-radius:8px; padding:18px 20px; }
.alcance { border-left:3px solid var(--aviso); background:var(--aviso-flojo); }
.alcance ul { margin:10px 0 0; padding-left:20px; }
.alcance li { margin:8px 0; }
.barras { list-style:none; margin:0; padding:0; }
.barras li { display:grid; grid-template-columns:1fr 2fr auto; gap:12px;
  align-items:center; padding:7px 0; border-bottom:1px solid var(--borde-sutil); }
.barras li:last-child { border-bottom:0; }
.et { font-size:14px; }
.ci { font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:13px;
  text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.bar { display:block; height:7px; background:var(--borde-sutil); border-radius:4px;
  overflow:hidden; }
.bar > span { display:block; height:100%; background:var(--acento); }
.nota { margin-top:44px; padding:18px 20px; border:1px solid var(--borde);
  border-radius:8px; background:var(--superficie); font-size:14.5px; color:var(--tinta-2); }
.nota strong { color:var(--tinta); }
a { color:var(--acento); }
footer { margin-top:52px; padding-top:18px; border-top:1px solid var(--borde);
  font-size:13px; color:var(--tinta-3); }
.vacio { color:var(--tinta-3); font-size:14px; margin:0; }
@media (max-width:520px) {
  .barras li { grid-template-columns:1fr auto; }
  .bar { display:none; }
}
@media (prefers-reduced-motion: reduce) { * { transition:none !important; animation:none !important; } }
"""


# ---------------------------------------------------------------------------
# LA CABECERA COMPARTIDA: LA MARCA PRIMERO Y EL MENÚ ARRIBA
# ---------------------------------------------------------------------------
# El 2026-09-19, abriendo `archivo.html` en un teléfono, lo primero que se leía
# era «El archivo». Ni una vez la palabra Vigía. Quien llega por un enlace que
# le mandaron no entra por la portada: entra por donde lo mandaron, y si esa
# página no dice de quién es, la cifra que lea no es de nadie.
#
# Y el menú estaba **al final**. Para pasar del archivo al panel había que
# recorrer la página entera hasta abajo. Eso convierte cinco páginas en cinco
# callejones sin salida, que es lo contrario de un sitio.
#
# Así que las dos cosas van arriba y en un solo sitio: la marca, el lema y el
# menú. El nombre propio de cada página baja a ser un subtítulo, que es lo que
# siempre fue.
#
# LA PÁGINA EN LA QUE SE ESTÁ NO SE ENLAZA A SÍ MISMA. Va marcada con
# `aria-current` y sin `href`: un enlace que no lleva a ninguna parte se prueba
# una vez y enseña que el menú no es de fiar.

#: Las páginas públicas, en el orden en que tienen sentido: hoy, la historia,
#: el período cerrado, el detalle completo, y al final lo que hay que mirar.
PAGINAS = [
    ("index.html", "Hoy"),
    ("archivo.html", "El archivo"),
    ("semana.html", "El período"),
    ("panel.html", "Panel"),
    ("banderas.html", "Banderas"),
    ("revision.html", "Qué mirar primero"),
]

NAV_CSS = """
.navsitio { display:flex; flex-wrap:wrap; gap:7px; margin-top:16px; }
.navsitio a, .navsitio span { font-size:13.5px; padding:7px 13px; border-radius:999px;
  text-decoration:none; border:1px solid var(--borde); background:var(--superficie);
  color:var(--tinta-2); transition:border-color .15s ease, color .15s ease; }
.navsitio a:hover { border-color:var(--acento); color:var(--tinta); }
.navsitio a:focus-visible { outline:2px solid var(--acento); outline-offset:2px; }
.navsitio [aria-current="page"] { background:var(--tinta); border-color:var(--tinta);
  color:var(--papel); font-weight:600; }
.pagina { margin:34px 0 2px; font-size:24px; letter-spacing:-.02em; }
.pagina + .sub { margin:0 0 4px; color:var(--tinta-2); font-family:"Source Serif 4",Georgia,serif;
  font-size:17px; }
"""


def menu(activa: str) -> str:
    """El menú del sitio. `activa` es el nombre de archivo de esta página."""
    trozos = []
    for archivo, etiqueta in PAGINAS:
        if archivo == activa:
            trozos.append(f'<span aria-current="page">{etiqueta}</span>')
        else:
            trozos.append(f'<a href="{archivo}">{etiqueta}</a>')
    return ('<nav class="navsitio" aria-label="Secciones de Vigía">'
            + "".join(trozos) + "</nav>")
