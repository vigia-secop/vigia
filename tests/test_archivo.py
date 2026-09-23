"""Pruebas del archivo: el recorrido por día, semana y mes.

Lo que se comprueba aquí no es que se vea bonito, sino las cosas que lo harían
dañino o inútil si fallaran:

1. Que **cada período diga contra qué se comparó**, y que lo que dice sea lo
   que de verdad calculó. Rotular «el día hábil anterior» una comparación que
   en realidad fue contra el día anterior con contratos es la clase de error
   que nadie descubre, porque el número sale.
2. Que **un período recortado se declare recortado**. Un mes al que le faltan
   doce días no se compara con uno entero, y quien lea «agosto» sin saberlo va
   a compararlos igual.
3. Que **las erratas ×10ⁿ queden fuera de las cifras y publicadas aparte**, con
   el mismo detalle que el resto del sitio.
4. Que **el HTML no se pueda romper con el dato**: una razón social con un `<`
   no puede desarmar la página ni escaparse al JSON embebido.
"""

from __future__ import annotations

import json

import pytest

from vigia import archivo, panel


def _datos(**cambios) -> dict:
    base = {
        "generado_en": "2026-09-19T08:00:00",
        "rango": {"desde": "2026-08-03", "hasta": "2026-08-14",
                  "contratos": 40, "valor": 4000000000},
        "dias": [
            {"dia": "2026-08-03", "contratos": 10, "valor": 1000000000,
             "entidades": 5, "proveedores": 9},
            {"dia": "2026-08-10", "contratos": 20, "valor": 2000000000,
             "entidades": 8, "proveedores": 18},
            {"dia": "2026-08-14", "contratos": 10, "valor": 1000000000,
             "entidades": 4, "proveedores": 10},
        ],
        "semanas": [
            {"desde": "2026-08-03", "hasta": "2026-08-09", "contratos": 10,
             "valor": 1000000000, "entidades": 5, "proveedores": 9},
            {"desde": "2026-08-10", "hasta": "2026-08-16", "contratos": 30,
             "valor": 3000000000, "entidades": 12, "proveedores": 28},
        ],
        "meses": [
            {"desde": "2026-08-01", "hasta": "2026-08-31", "contratos": 40,
             "valor": 4000000000, "entidades": 15, "proveedores": 37},
        ],
        "mayores": {},
        "erratas": {},
    }
    base.update(cambios)
    return base


class TestCadaPeriodoDiceContraQueSeCompara:
    def test_un_dia_se_compara_con_el_mismo_dia_de_la_semana_anterior(self):
        # Un lunes contra un domingo no dice nada. El 3 y el 10 de agosto son
        # los dos lunes: del primero al segundo el valor se duplica, y eso es
        # +100 %. Si la página comparara «con el día anterior de la lista»,
        # el 10 se compararía con el 3 igual — pero el 14 (viernes) se
        # compararía con el 10 (lunes), que es justo lo que no se debe hacer.
        pagina = archivo.construir(_datos())
        assert "+100,0 %" in pagina
        assert "igual día, semana anterior" in pagina

    def test_un_dia_sin_su_par_de_la_semana_anterior_lo_dice(self):
        # El 14 de agosto no tiene 7 de agosto en los datos. La página no
        # inventa una comparación: dice que no la hay.
        pagina = archivo.construir(_datos())
        assert "Sin igual día, semana anterior con qué comparar." in pagina

    def test_no_promete_el_dia_habil_anterior(self):
        # La primera versión rotulaba así una comparación que no era esa.
        assert "el día hábil anterior" not in archivo.construir(_datos())


class TestUnPeriodoRecortadoSeDeclara:
    def test_el_mes_incompleto_dice_cuantos_dias_le_faltan(self):
        pagina = archivo.construir(_datos())
        assert "faltan" in pagina
        assert "No se contrató menos — se ha mirado menos." in pagina

    def test_un_dia_nunca_lleva_nota_de_recorte(self):
        # Un día es un día: o está o no está. La nota solo aplica a semanas
        # y meses, que sí se pueden partir.
        fila = {"dia": "2026-08-03"}
        assert archivo._nota_de_cobertura(
            "d2026-08-03", fila,
            archivo._fecha("2026-08-03"), archivo._fecha("2026-08-14")) == ""


class TestLasErratasSeApartanYSePublican:
    @staticmethod
    def _con_errata():
        return archivo.construir(_datos(erratas={
            "m2026-08-01": {
                "cuantas": 1, "valor": 431340000000,
                "filas": [{
                    "id_contrato": "CO1.PCCNTR.9762242",
                    "proveedor": "FUNDACION MIL COLORES MAS",
                    "entidad": "ALCALDÍA MUNICIPAL DE TIPACOQUE",
                    "valor": 431340000000,
                    "presupuesto_del_proceso": 431340000,
                    "veces": 1000,
                }],
            }
        }))

    def test_dice_cuanto_se_aparto_y_de_donde(self):
        p = self._con_errata()
        assert "quedaron fuera de las cifras de arriba" in p
        assert "$431,3 mil millones" in p

    def test_publica_el_contrato_con_las_dos_cifras(self):
        # Apartar no es tapar: la fila sale con nombre y con el presupuesto
        # del proceso al lado, que es el argumento entero.
        p = self._con_errata()
        assert "FUNDACION MIL COLORES MAS" in p
        assert "ALCALDÍA MUNICIPAL DE TIPACOQUE" in p
        assert "$431,3 millones" in p

    def test_sin_erratas_no_sale_el_bloque(self):
        # Un aviso permanente que casi siempre está vacío deja de leerse.
        assert "quedaron fuera de las cifras de arriba" not in archivo.construir(_datos())


class TestElDatoNoPuedeRomperLaPagina:
    def test_una_razon_social_con_html_se_escapa(self):
        pagina = archivo.construir(_datos(mayores={
            "m2026-08-01": [{
                "id_contrato": "X", "valor": 1000000,
                "proveedor": "<script>alert(1)</script>",
                "entidad": "E", "departamento": "D",
            }]
        }))
        assert "<script>alert(1)</script>" not in pagina
        assert "&lt;script&gt;" in pagina

    def test_el_json_embebido_no_puede_cerrar_el_script(self):
        # El bloque de paneles va dentro de un <script>. Un «</script>» en
        # cualquier razón social lo cerraría antes de tiempo y el resto de la
        # página quedaría escrito como texto suelto en la pantalla.
        pagina = archivo.construir(_datos(mayores={
            "m2026-08-01": [{
                "id_contrato": "X", "valor": 1000000,
                "proveedor": "CIERRA </script> AQUI",
                "entidad": "E", "departamento": "D",
            }]
        }))
        cuerpo = pagina.split('<script type="application/json" id="paneles">')[1]
        assert "</script>" not in cuerpo.split("</script>")[0] + ""
        assert "\\u003c" in cuerpo


class TestLaEscalaDelMapa:
    def test_los_cortes_son_cuantiles_y_no_tramos_iguales(self):
        # Con un día enorme y muchos pequeños, unos cortes equiespaciados
        # dejarían todo en el primer tono y el mapa no diría nada.
        valores = [1.0] * 40 + [1000000.0]
        cortes = archivo.escalones(valores)
        assert cortes, "tiene que haber cortes"
        assert cortes[0] < 1000000.0

    def test_un_dia_sin_contratos_no_es_el_tono_mas_claro(self):
        # «Cero» y «lo más bajo que hubo» no son lo mismo, y el mapa los
        # distingue: el cero tiene su propio tono y su renglón en la leyenda.
        assert archivo.tono(0, [10, 20, 30, 40]) == 0
        assert archivo.tono(5, [10, 20, 30, 40]) == 1

    def test_sin_ningun_valor_no_revienta(self):
        assert archivo.escalones([]) == []
        assert archivo.tono(None, []) == 0


class TestElFormatoEsElMismoDelResto:
    """`archivo.py` repite las funciones de formato de `panel.py`. La copia es
    a propósito —cada página se dibuja sola— pero tiene que decir lo mismo, y
    esta prueba es lo que lo garantiza. Mismo trato que `test_estilo.py` le da
    a la paleta."""

    @pytest.mark.parametrize("valor", [0, 1, 999, 1234567, 431340000000,
                                       33910000000000, None])
    def test_compacto_dice_lo_mismo_en_las_dos(self, valor):
        assert archivo.compacto(valor) == panel.compacto(valor)

    @pytest.mark.parametrize("valor", [0, 7, 1540, 262467, None])
    def test_numero_dice_lo_mismo_en_las_dos(self, valor):
        assert archivo.numero(valor) == panel.numero(valor)

    def test_pesos_dice_lo_mismo_en_las_dos(self):
        assert archivo.pesos(431340000) == panel.pesos(431340000)


class TestLaPaginaSeArmaEntera:
    def test_trae_las_tres_pestanas_y_el_calendario(self):
        pagina = archivo.construir(_datos())
        for modo in ("d", "s", "m"):
            assert f'data-modo="{modo}"' in pagina
        assert 'class="calendario"' in pagina

    def test_el_json_de_paneles_tiene_los_tres_ordenes(self):
        pagina = archivo.construir(_datos())
        crudo = pagina.split('id="paneles">')[1].split("</script>")[0]
        carga = json.loads(crudo.replace("\\u003c", "<"))
        assert len(carga["orden"]["d"]) == 3
        assert len(carga["orden"]["s"]) == 2
        assert len(carga["orden"]["m"]) == 1
        # Cada día del mapa sabe a qué semana y a qué mes pertenece: es lo que
        # permite cambiar de pestaña sin perder lo que se estaba mirando.
        assert carga["mapa"]["s"]["2026-08-12"] == "s2026-08-10"
        assert carga["mapa"]["m"]["2026-08-12"] == "m2026-08-01"

    def test_sin_un_solo_dia_se_niega_a_dibujar(self):
        # Una página de archivo vacía se lee como «no se contrató nada», que
        # es falso: lo que pasa es que no hay nada ingerido.
        with pytest.raises(ValueError):
            archivo.construir(_datos(dias=[]))

    def test_enlaza_de_vuelta_a_las_otras_paginas(self):
        pagina = archivo.construir(_datos())
        for destino in ("index.html", "semana.html", "panel.html",
                        "revision.html"):
            assert f'href="{destino}"' in pagina

    def test_respeta_a_quien_pidio_menos_movimiento(self):
        # Un sistema operativo puede pedir que nada se mueva, y hay gente que
        # lo activa por mareo, no por gusto. Ignorarlo es hacerle daño.
        assert "prefers-reduced-motion" in archivo.construir(_datos())
