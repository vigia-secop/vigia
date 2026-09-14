"""Pruebas de la lista de revisión.

La lista de revisión es la única página que hoy le dice a alguien «mira esto
antes que lo otro». Por eso lo que se comprueba aquí no es que se vea bonita,
sino las tres cosas que la harían dañina si fallaran:

1. Que **no afirme nada**. La página lleva escrito que no son alertas, y el
   vocabulario prohibido (2.6) ya recorre este módulo con todos los demás.
2. Que **una tabla vacía se vea distinta de una tabla que no se calculó**. Es
   la misma distinción de la 2.5: «se miró y no había» no es «no se miró».
3. Que **el HTML no se pueda romper con el dato**. Los nombres de entidad y de
   proveedor vienen de la fuente sin ninguna garantía; una razón social con un
   `<` no puede desarmar la página.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vigia.revision import CODIGO_FALLO, CODIGO_USO, construir, main

DATOS = Path(__file__).parent / "datos"

MINIMO = {
    "generado_en": "2026-09-06T17:00:00",
    "ventana": {"desde": "2026-08-26", "hasta": "2026-09-02"},
    "conteos": {
        "sin_razon_social": 5,
        "valor_sin_razon_social": 118352585823,
        "uniones": 102,
        "valor_uniones": 358964624020,
        "huerfanos": 0,
        "valor_huerfanos": 0,
    },
}


def _con(**secciones):
    datos = json.loads(json.dumps(MINIMO))
    datos.update(secciones)
    return construir(datos)


class TestNoAfirmaNada:
    def test_la_pagina_dice_que_no_son_alertas(self):
        assert "no son alertas" in _con().lower()

    def test_lleva_el_pie_de_no_imputacion(self):
        assert "no constituyen imputación" in _con()


class TestVacioNoEsLoMismoQueNada:
    def test_una_seccion_sin_filas_lo_dice_con_palabras(self):
        # Si una tabla vacía se dibujara igual que una tabla ausente, quien la
        # lea no sabría si ahí no hay nada o si eso no se calculó, que es
        # exactamente la confusión que el modo calibración existe para evitar.
        assert "Ninguno en esta ventana." in _con(sin_razon_social=[])

    def test_llenar_una_seccion_le_quita_a_esa_su_texto_de_vacio(self):
        # Se compara contra la página vacía en vez de buscar la frase suelta:
        # varias secciones usan el mismo texto, y buscarla a secas pasaría
        # aunque la sección llena siguiera diciendo que no hay nada.
        frase = "Ninguno en esta ventana."
        vacia = _con(sin_razon_social=[])
        llena = _con(sin_razon_social=[{
            "id_contrato": "CO1.PCCNTR.9842896",
            "tipo": "NIT", "documento": "900445736",
            "entidad": "DISTRITO DE MEDELLIN", "departamento": "ANTIOQUIA",
            "valor": 118274783168, "estado": "En ejecucion",
        }])
        assert "CO1.PCCNTR.9842896" in llena
        assert llena.count(frase) == vacia.count(frase) - 1


class TestElDatoNoRompeLaPagina:
    def test_una_razon_social_con_html_sale_escapada(self):
        pagina = _con(sin_razon_social=[{
            "id_contrato": "CO1.X", "tipo": "NIT", "documento": "1",
            "entidad": '<script>alert("x")</script>',
            "departamento": "BOGOTA", "valor": 1, "estado": "Activo",
        }])
        assert "<script>" not in pagina
        assert "&lt;script&gt;" in pagina

    def test_un_valor_nulo_no_levanta(self):
        # La fuente publica contratos sin valor. No es un caso raro y la
        # página no puede caerse por eso.
        pagina = _con(sin_razon_social=[{
            "id_contrato": "CO1.X", "tipo": None, "documento": None,
            "entidad": None, "departamento": None, "valor": None, "estado": None,
        }])
        assert "CO1.X" in pagina


class TestTodoTokenDeEstiloEstaDefinido:
    def test_no_queda_ninguna_variable_css_sin_definir(self):
        # Un `var(--algo)` sin su `--algo:` no falla en ninguna parte: el
        # navegador simplemente dibuja mal y en silencio. Aquí no.
        import re

        pagina = _con()
        usados = set(re.findall(r"var\((--[a-z0-9-]+)\)", pagina))
        definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", pagina))
        assert usados - definidos == set()


class TestLasTresPaginasSeAbrenBienDesdeElDisco:
    """Las tres páginas se abren con doble clic desde una carpeta de Windows,
    no las sirve nadie. Sin `<meta charset="utf-8">` el navegador adivina, y en
    un Windows en español adivina cp1252: «Vigía» sale «VigÃ­a» y «razón
    social» sale «razÃ³n social» en TODAS las páginas del proyecto.

    Estuvo así hasta el 2026-09-06. Se escribieron pensadas para publicarse,
    donde algo más pone la cabecera; abiertas desde el disco no hay ese algo.
    """

    # Las cargas no se escriben a mano: son la salida de verdad de `panel.sql`,
    # `resumen.sql` y `revision.sql`, guardada en `tests/datos/`. Una carga
    # inventada se queda vieja en silencio cuando la consulta cambia de forma,
    # y entonces la prueba deja de mirar la página que se dibuja de verdad.
    @staticmethod
    def _pagina(cual):
        from vigia import panel, resumen

        datos = json.loads(
            (DATOS / f"{cual}-minimo.json").read_text(encoding="utf-8"))
        if cual == "revision":
            return construir(datos)
        if cual == "panel":
            return panel.construir(datos)
        return resumen.construir(datos, titulo="Resumen semanal")

    @pytest.mark.parametrize("cual", ["revision", "panel", "resumen"])
    def test_lleva_doctype_y_charset(self, cual):
        pagina = self._pagina(cual)
        assert pagina.startswith("<!doctype html>")
        assert '<meta charset="utf-8">' in pagina
        assert '<html lang="es">' in pagina
        # Y el cuerpo tiene que abrirse y cerrarse: un `<style>` seguido de
        # contenido sin `<body>` funciona por indulgencia del navegador, no
        # por estar bien.
        assert pagina.count("<body>") == 1 and pagina.count("</body>") == 1
        assert pagina.index("<body>") < pagina.index("</body>")


class TestLaLineaDeComandos:
    def test_sin_archivo_devuelve_codigo_de_uso(self, tmp_path, capsys):
        assert main(["--json", str(tmp_path / "no-existe.json")]) == CODIGO_USO

    def test_un_json_sin_conteos_no_se_dibuja(self, tmp_path):
        # Sin `conteos` la página saldría con las tres cajas en blanco y nadie
        # sabría si es que no hay nada o si la consulta se quedó corta.
        origen = tmp_path / "revision.json"
        origen.write_text(json.dumps({"ventana": {}}), encoding="utf-8")
        assert main(["--json", str(origen)]) == CODIGO_FALLO

    def test_escribe_el_html_donde_se_le_pide(self, tmp_path):
        origen = tmp_path / "revision.json"
        salida = tmp_path / "afuera.html"
        origen.write_text(json.dumps(MINIMO), encoding="utf-8")
        assert main(["--json", str(origen), "--salida", str(salida)]) == 0
        assert salida.read_text(encoding="utf-8").startswith("<!doctype html>")


class TestLaErrataQueElTechoNoAtaja:
    """El 2026-09-11 esta página mostró $431.340.000.000 de la ALCALDÍA DE
    TIPACOQUE —municipio de unos 3.000 habitantes— sin ninguna marca. El
    presupuesto del proceso era $431.340.000: el mismo número con tres ceros
    de más.

    La guarda de valores imposibles (1e14) no lo atajó y **nunca pudo**: 431
    mil millones es un contrato posible. Está escrito así en
    `tests/test_escala.py` desde antes, y aun así la fila salió desnuda,
    porque nadie había hecho la comparación contra el presupuesto del propio
    proceso. Esa comparación es lo que estas pruebas cuidan.
    """

    FILA = {
        "id_contrato": "CO1.PCCNTR.9762242",
        "entidad": "ALCALDÍA MUNICIPAL DE TIPACOQUE",
        "proveedor": "FUNDACION MIL COLORES MAS",
        "tipo": "NIT",
        "documento": "900555111",
        "valor": 431340000000,
        "valor_probable": 431340000,
        "ceros_de_mas": 3,
        "estado": "En ejecución",
        "enlace": "https://community.secop.gov.co/x",
    }

    def _pagina(self):
        return _con(erratas_x1000=[self.FILA],
                    conteo_erratas={"erratas": 1, "valor_erratas": 431340000000})

    def test_la_fila_sale_con_el_valor_del_proceso_al_lado(self):
        # Sin esta columna la cifra grande queda sola en la página y se lee
        # como un hallazgo. La columna ES el desmentido.
        p = self._pagina()
        assert "$431,3 mil millones" in p
        assert "$431,3 millones" in p

    def test_dice_que_el_valor_probable_no_es_una_correccion_nuestra(self):
        assert "no una corrección nuestra" in self._pagina()

    def test_avisa_de_no_compartirla_como_hallazgo(self):
        # Lo que de verdad hace daño no es que la cifra esté en la base: es que
        # alguien la publique. El aviso va en la misma tabla, no en un anexo.
        assert "credibilidad" in self._pagina()

    def test_sin_erratas_la_tabla_dice_con_palabras_que_miro_y_no_habia(self):
        assert "Ninguna en esta ventana" in _con(erratas_x1000=[])

    def test_un_json_viejo_sin_la_seccion_sigue_dibujandose(self):
        # `conteo_erratas` nació después que la página. Un JSON generado antes
        # tiene que seguir abriéndose: si revienta, el día que alguien corra
        # una versión nueva contra un volcado viejo se queda sin página.
        assert _con().startswith("<!doctype html>")

    def test_la_caja_de_erratas_no_sale_cuando_no_hay_ninguna(self):
        # Un contador permanente en cero se vuelve decorado y deja de leerse
        # el día que deja de ser cero. Misma regla que los valores imposibles.
        assert "Erratas" not in _con(conteo_erratas={"erratas": 0,
                                                     "valor_erratas": 0})


class TestElPanelMarcaLaErrataEnLugarDeEsconderla:
    """En el Panel la fila de Tipacoque encabezaba «Contratos mayores». Ahí es
    donde la vio el usuario, y ahí es donde tiene que ir el desmentido.

    La fila **no se saca** de la tabla: sacarla sería corregir la fuente a ojo,
    y Vigía no corrige la fuente. Se marca, y la marca dice contra qué se
    comparó.
    """

    @staticmethod
    def _panel(marcada: bool):
        from vigia import panel

        datos = json.loads(
            (DATOS / "panel-minimo.json").read_text(encoding="utf-8"))
        datos["contratos_mayores"] = [{
            "id_contrato": "CO1.PCCNTR.9762242",
            "proveedor": "FUNDACION MIL COLORES MAS",
            "entidad": "ALCALDÍA MUNICIPAL DE TIPACOQUE",
            "departamento": "BOYACA",
            "valor": 431340000000,
            "estado": "En ejecución",
            "es_union_temporal": False,
            "errata_probable": marcada,
            "valor_probable": 431340000 if marcada else None,
        }]
        return panel.construir(datos)

    def test_la_fila_sigue_en_la_tabla(self):
        assert "CO1.PCCNTR.9762242" in self._panel(True)

    def test_lleva_la_marca_con_el_valor_del_proceso(self):
        p = self._panel(True)
        assert "probable errata" in p
        assert "$431,3 millones en el proceso" in p

    def test_la_nota_explica_que_es_una_tecla_y_no_un_sobrecosto(self):
        assert "tecla de más" in self._panel(True)

    def test_un_contrato_grande_normal_no_lleva_marca_ni_nota(self):
        # Esta es la prueba que impide que la marca se vuelva decorado. Un
        # contrato grande de verdad —y los hay— tiene que salir limpio.
        p = self._panel(False)
        assert "CO1.PCCNTR.9762242" in p
        assert "probable errata" not in p
        # Se busca el párrafo, no la clase: la regla CSS `.nota-errata` está
        # siempre en la hoja de estilo, la haya o no. Comprobar la clase
        # suelta daría una prueba que nunca falla.
        assert '<p class="nota-errata"' not in p
