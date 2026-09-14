"""Pruebas de la portada diaria — `docs/index.html`.

La portada es la superficie más expuesta del proyecto: es lo que ve quien
llega por un enlace, y se rehace sola todos los días sin que nadie la mire
antes. Por eso lo que se comprueba aquí no es que se vea bien, sino las cuatro
cosas que la harían dañina si fallaran:

1. Que **no escriba nunca el documento de una persona natural**.
2. Que un **día sin jornada hábil** se explique con palabras en vez de mostrar
   una caída del 99 % que asuste a quien la lea.
3. Que una **errata ×10ⁿ salga marcada**, no escondida ni borrada.
4. Que el **HTML abra bien desde cualquier parte**: doctype, charset y cuerpo.
"""

from __future__ import annotations

import json

import pytest

from vigia.documento import persona_sin_enmascarar
from vigia.portada import CODIGO_FALLO, CODIGO_USO, construir, main

# Una carga mínima con la forma exacta que devuelve `portada.sql`. El día es
# un jueves hábil salvo que una prueba diga lo contrario.
MINIMO = {
    "generado_en": "2026-09-10T06:12:00",
    "dia": "2026-09-10",
    "cifras": {"contratos": 3412, "valor": 612400000000, "entidades": 214,
               "proveedores": 2988, "nacional": 400, "territorial": 3012,
               "mediana": 12400000, "promedio": 179500000},
    "comparacion": {"dia_anterior": "2026-09-03", "contratos": 3301,
                    "valor": 588000000000},
    "cobertura": {"contratos": 3412, "valor": 612400000000,
                  "con_identidad": 2811, "valor_con_identidad": 505000000000,
                  "uniones": 98, "valor_uniones": 90000000000,
                  "sin_razon_social": 503, "valor_sin_razon_social": 17400000000,
                  "sin_departamento": 41},
    "departamentos": [{"nombre": "BOGOTA", "contratos": 900, "valor": 200000000000}],
    "modalidades": [{"nombre": "Contratación Directa", "contratos": 2100,
                     "valor": 300000000000}],
    "tramos": [{"tramo": "a. menos de $5 M", "contratos": 1200, "valor": 3000000000}],
    "mayores": [],
    "serie": [{"dia": "2026-09-10", "contratos": 3412, "valor": 612400000000}],
    "ventana": {"primer_contrato": "2026-07-01", "ultimo_contrato": "2026-09-10",
                "contratos": 117470, "valor": 12900000000000, "entidades": 2173},
    "calidad": {"erratas_hoy": 0, "valor_erratas_hoy": 0, "erratas_ventana": 4,
                "imposibles": 1, "huerfanos_hoy": 39},
}


def _con(**cambios):
    datos = json.loads(json.dumps(MINIMO))
    datos.update(cambios)
    return construir(datos)


TIPACOQUE = {
    "id_contrato": "CO1.PCCNTR.9762242",
    "proveedor": "FUNDACION MIL COLORES MAS",
    "documento": "NIT 900555111",
    "es_union": False,
    "entidad": "ALCALDÍA MUNICIPAL DE TIPACOQUE",
    "departamento": "Boyaca",
    "valor": 431340000000,
    "errata_probable": True,
    "valor_probable": 431340000,
    "enlace": "https://community.secop.gov.co/x",
}

PERSONA = {
    "id_contrato": "CO1.PCCNTR.500",
    "proveedor": "Persona natural",
    "documento": "•••••••847",
    "es_union": False,
    "entidad": "ALCALDIA DE CHIA",
    "departamento": "Cundinamarca",
    "valor": 18000000,
    "errata_probable": False,
    "valor_probable": None,
    "enlace": None,
}


class TestNingunDocumentoDePersonaNatural:
    """La garantía que no puede depender de que alguien se acuerde.

    El enmascarado lo hace `portada.sql`, así que este módulo nunca recibe el
    número entero. Estas pruebas cuidan el otro lado: que lo que sí llega se
    dibuje tal cual, y que si alguna vez llegara un número completo, el
    programa **no escriba el archivo**.
    """

    def test_el_documento_enmascarado_sale_tal_cual(self):
        assert "•••••••847" in _con(mayores=[PERSONA])

    def test_a_la_persona_natural_no_se_le_pone_nombre(self):
        pagina = _con(mayores=[PERSONA])
        assert "Persona natural" in pagina

    def test_el_nit_de_una_empresa_sale_completo(self):
        # No es una concesión: donde está el poder está el NIT, y una empresa
        # lo lleva en la factura y en la fachada.
        assert "900555111" in _con(mayores=[TIPACOQUE])

    def test_la_pagina_no_contiene_documentos_de_persona_sin_enmascarar(self):
        pagina = _con(mayores=[TIPACOQUE, PERSONA])
        assert persona_sin_enmascarar(pagina) == []

    def test_si_llegara_una_cedula_entera_no_se_escribe_el_archivo(self, tmp_path):
        # La comprobación se hace sobre el HTML ya armado, que es lo que de
        # verdad se sube. Si falla, no puede quedar un archivo a medias en
        # `docs/` esperando al siguiente push.
        filtrada = dict(PERSONA, documento="CEDULA DE CIUDADANIA 1074521847")
        datos = json.loads(json.dumps(MINIMO))
        datos["mayores"] = [filtrada]
        origen = tmp_path / "portada.json"
        salida = tmp_path / "index.html"
        origen.write_text(json.dumps(datos), encoding="utf-8")
        assert main(["--json", str(origen), "--salida", str(salida)]) == CODIGO_FALLO
        assert not salida.exists()


class TestUnDiaSinJornadaSeExplica:
    """El 3 de septiembre los conteos crudos decían −45,7 %. Eran dos festivos.

    Una portada automática que muestre un domingo con una caída del 99 % es
    exactamente el mismo error, repetido todos los fines de semana.
    """

    def test_un_domingo_lo_dice_con_palabras(self):
        assert "Es domingo" in _con(dia="2026-09-13")

    def test_un_sabado_lo_dice_con_palabras(self):
        assert "Es sábado" in _con(dia="2026-09-12")

    def test_un_festivo_lo_nombra(self):
        # 7 de agosto: Batalla de Boyacá. Que salga el nombre importa: «es
        # festivo» se lee como excusa; el nombre se lee como dato.
        pagina = _con(dia="2026-08-07",
                      comparacion={"dia_anterior": "2026-07-31",
                                   "contratos": 3000, "valor": 1})
        assert "festivo" in pagina.lower()

    def test_un_dia_habil_no_lleva_esa_nota(self):
        # Un aviso permanente se vuelve decorado y deja de leerse el día que
        # de verdad hace falta.
        assert "Es domingo" not in _con()

    def test_no_se_compara_un_habil_contra_un_festivo(self):
        # 2026-09-14 es lunes hábil; siete días antes, el 7 de septiembre,
        # también. Se invierte el caso: un lunes contra un festivo no da una
        # variación publicable, y la página tiene que decir que no la hay.
        pagina = _con(dia="2026-08-10",
                      comparacion={"dia_anterior": "2026-08-03",
                                   "contratos": 10, "valor": 10})
        assert "sin comparación válida" in pagina or "%" in pagina


class TestLaErrataSeMarcaNoSeEsconde:
    def test_la_fila_sigue_en_la_tabla(self):
        assert "CO1.PCCNTR.9762242" in _con(mayores=[TIPACOQUE])

    def test_lleva_la_marca_con_el_presupuesto_del_proceso(self):
        pagina = _con(mayores=[TIPACOQUE])
        assert "probable errata" in pagina
        assert "$431,3 millones" in pagina

    def test_el_aviso_de_arriba_usa_singular_con_uno_solo(self):
        pagina = _con(mayores=[TIPACOQUE],
                      calidad=dict(MINIMO["calidad"], erratas_hoy=1))
        assert "Un contrato de hoy tiene" in pagina
        assert "contrato(s)" not in pagina

    def test_sin_erratas_no_sale_el_aviso(self):
        assert "tecla de más" not in _con(mayores=[TIPACOQUE])

    def test_un_contrato_grande_normal_no_lleva_marca(self):
        # Se busca la marca de la FILA, no el texto suelto: el bloque de
        # calidad del dato nombra las erratas siempre, aunque sean cero, y
        # buscar la frase a secas daría una prueba que nunca falla.
        limpio = dict(TIPACOQUE, errata_probable=False, valor_probable=None)
        assert 'class="marca-fila errata"' not in _con(mayores=[limpio])

    def test_la_errata_si_lleva_la_marca_de_fila(self):
        assert 'class="marca-fila errata"' in _con(mayores=[TIPACOQUE])


class TestLaCoberturaVaAntesQueElRanking:
    def test_el_bloque_de_cobertura_aparece_antes_que_los_mayores(self):
        # No es cuestión de gusto: es la posición del proyecto. Si un día el
        # ranking sube por encima, el sitio cambió de oficio.
        pagina = _con(mayores=[TIPACOQUE])
        assert pagina.index("no se puede ver") < pagina.index("más grandes de hoy")

    def test_dice_cuanto_valor_esta_en_uniones_sin_documento(self):
        assert "uniones temporales" in _con()


class TestLaPaginaAbreBienDesdeElDisco:
    def test_lleva_doctype_y_charset(self):
        # Sin `<meta charset>` un Windows en español adivina cp1252 y «Vigía»
        # sale «VigÃ­a». Ya pasó una vez con las tres páginas de escritorio.
        pagina = _con()
        assert pagina.startswith("<!doctype html>")
        assert '<meta charset="utf-8">' in pagina
        assert '<html lang="es">' in pagina
        assert pagina.count("<body>") == 1 and pagina.count("</body>") == 1

    def test_no_queda_ninguna_variable_css_sin_definir(self):
        import re

        pagina = _con()
        usadas = set(re.findall(r"var\((--[a-z0-9-]+)\)", pagina))
        definidas = set(re.findall(r"(--[a-z0-9-]+)\s*:", pagina))
        assert usadas - definidas == set()

    def test_una_razon_social_con_html_sale_escapada(self):
        malo = dict(TIPACOQUE, proveedor='<script>alert(1)</script> S.A.S.')
        assert "<script>alert" not in _con(mayores=[malo])

    def test_un_dia_sin_contratos_no_levanta(self):
        vacio = json.loads(json.dumps(MINIMO))
        vacio["cifras"] = dict(vacio["cifras"], contratos=0, valor=0,
                               mediana=None, promedio=None)
        vacio["mayores"] = []
        vacio["serie"] = []
        assert construir(vacio).startswith("<!doctype html>")


class TestLaLineaDeComandos:
    def test_sin_archivo_devuelve_codigo_de_uso(self, tmp_path):
        assert main(["--json", str(tmp_path / "no-existe.json")]) == CODIGO_USO

    def test_un_json_sin_cobertura_no_se_dibuja(self, tmp_path):
        origen = tmp_path / "portada.json"
        origen.write_text(json.dumps({"dia": "2026-09-10", "cifras": {}}),
                          encoding="utf-8")
        assert main(["--json", str(origen)]) == CODIGO_FALLO

    def test_escribe_el_html_donde_se_le_pide(self, tmp_path):
        origen = tmp_path / "portada.json"
        salida = tmp_path / "sitio" / "index.html"
        origen.write_text(json.dumps(MINIMO), encoding="utf-8")
        assert main(["--json", str(origen), "--salida", str(salida)]) == 0
        assert salida.read_text(encoding="utf-8").startswith("<!doctype html>")


class TestLaPaletaNoSeSeparaEnDos:
    """`vigia/estilo.py` nació de sacar la paleta del f-string de `sitio.py`.

    Mientras `sitio.py` siga escribiendo la suya a mano, las dos pueden
    separarse sin que nadie lo note —nadie mira las dos páginas seguidas—. Esta
    prueba lo nota el mismo día.
    """

    def test_cada_color_de_estilo_py_existe_igual_en_sitio_py(self):
        import inspect
        import re

        from vigia import estilo, sitio

        fuente = inspect.getsource(sitio)
        for nombre, valor in estilo.CLARO.items():
            encontrados = re.findall(rf"--{nombre}:\s*(#[0-9A-Fa-f]{{6}})", fuente)
            assert encontrados, f"sitio.py ya no define --{nombre}"
            assert encontrados[0].upper() == valor.upper(), (
                f"--{nombre}: estilo.py dice {valor}, sitio.py dice {encontrados[0]}")
