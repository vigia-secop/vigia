"""Que las cinco páginas públicas sean UN SITIO y no cinco callejones.

El 2026-09-19, abriendo `archivo.html` en un teléfono, lo primero que se leía
era «El archivo». Ni una vez la palabra Vigía. Y el menú estaba **al final**:
para pasar del archivo al panel había que recorrer la página entera.

Quien llega por un enlace que le mandaron no entra por la portada — entra por
donde lo mandaron. Si esa página no dice de quién es, la cifra que lea no es
de nadie; y si no tiene salida, el sitio se acaba ahí.

Estas pruebas son el seguro de que no vuelva a pasar en ninguna de las cinco.
"""

from __future__ import annotations

from vigia import estilo


class TestElMenuEstaEnTodasYArriba:
    def test_las_cinco_paginas_estan_en_el_menu(self):
        archivos = [a for a, _ in estilo.PAGINAS]
        assert archivos == ["index.html", "archivo.html", "semana.html",
                            "panel.html", "banderas.html", "revision.html"]

    def test_la_pagina_actual_no_se_enlaza_a_si_misma(self):
        # Un enlace que no lleva a ninguna parte se prueba una vez y enseña
        # que el menú no es de fiar.
        menu = estilo.menu("panel.html")
        assert '<span aria-current="page">Panel</span>' in menu
        assert 'href="panel.html"' not in menu

    def test_las_demas_si_se_enlazan(self):
        menu = estilo.menu("panel.html")
        for destino in ("index.html", "archivo.html", "semana.html",
                        "banderas.html", "revision.html"):
            assert f'href="{destino}"' in menu

    def test_un_nombre_que_no_es_pagina_no_marca_ninguna(self):
        # Si alguien escribe mal el nombre, el menú sale entero y navegable:
        # se pierde la marca de «estás aquí», no la salida.
        menu = estilo.menu("noexiste.html")
        assert "aria-current" not in menu
        assert menu.count("<a href=") == 6


class TestCadaPaginaDiceDeQuienEs:
    """La marca va arriba de todo y el nombre de la página debajo, no al revés."""

    @staticmethod
    def _paginas():
        # Las cargas se toman de las pruebas que ya las tienen, en vez de
        # copiarlas aquí: un fixture duplicado es un fixture que se queda
        # viejo en una de las dos copias y nadie se entera.
        import json
        from pathlib import Path

        from test_archivo import _datos as datos_archivo
        from test_portada import MINIMO as PORTADA

        from vigia import archivo, panel, portada, revision, sitio

        datos = Path(__file__).parent / "datos"
        leer = lambda n: json.loads((datos / n).read_text("utf-8"))

        return {
            "archivo.html": archivo.construir(datos_archivo()),
            "panel.html": panel.construir(leer("panel-minimo.json")),
            "revision.html": revision.construir(leer("revision-minimo.json")),
            "semana.html": sitio.construir(leer("boletin-minimo.json")),
            "index.html": portada.construir(PORTADA),
        }

    def test_todas_llevan_el_menu_del_sitio(self):
        for nombre, html in self._paginas().items():
            assert 'class="navsitio"' in html, f"{nombre} se quedó sin menú"

    def test_todas_nombran_a_vigia_en_el_encabezado(self):
        for nombre, html in self._paginas().items():
            encabezado = html.split("<h1>")[1].split("</h1>")[0]
            assert "Vig" in encabezado, f"{nombre} no dice Vigía en su <h1>"

    def test_cada_una_se_marca_a_si_misma_en_el_menu(self):
        for nombre, html in self._paginas().items():
            assert f'href="{nombre}"' not in html.split("</nav>")[0], (
                f"{nombre} se enlaza a sí misma en su propio menú")

    def test_el_menu_va_antes_que_el_contenido(self):
        # Arriba, no al final: esa fue la queja, y es lo que se prueba.
        for nombre, html in self._paginas().items():
            cuerpo = html.split("<body>")[1]
            assert cuerpo.index('class="navsitio"') < len(cuerpo) / 2, (
                f"el menú de {nombre} quedó en la mitad de abajo de la página")
