"""Pruebas de la página de banderas.

**Es la única página de Vigía que señala algo**, y por eso es la única cuyas
pruebas son casi todas sobre lo que NO puede hacer.

Una ficha con el nombre de una alcaldía se lee como una acusación aunque el
texto diga lo contrario. Lo que la vuelve publicable no es el tono: es que
cada afirmación se pueda comprobar en un clic, que lo que no se puede
sostener no esté escrito, y que quien lea sepa **a cuántas entidades no
alcanza la medición** antes de leer la lista.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vigia.banderas import construir

AHORA = datetime(2026, 9, 19, 18, 0, tzinfo=timezone.utc)


def _texto(pagina: str) -> str:
    """El texto como lo lee una persona: sin etiquetas y en una sola línea.

    Las pruebas de redacción van contra ESTO y no contra el HTML: si fueran
    contra el fuente, un salto de línea puesto para que el código quepa en
    ochenta columnas rompería una prueba sin que la página haya cambiado.
    """
    import re
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", pagina))


def _grupo(**cambios):
    base = {
        "nit_entidad": "890399011",
        "nombre_entidad": "ALCALDIA MUNICIPIO DE VIJES",
        "proveedor_tipo": "NIT", "proveedor_numero": "900629234",
        "mes": "2026-07-01", "contratos": 6,
        "suma": 290911738, "techo": 73526697,
        "p95_entidad": 68000000, "minimas_entidad": 41,
        "contratos_ids": ["CO1.PCCNTR.1", "CO1.PCCNTR.2"],
        "detalle": [
            {"id_contrato": "CO1.PCCNTR.1", "valor": 150000000,
             "fecha": "2026-07-03",
             "enlace": "https://community.secop.gov.co/CO1.PCCNTR.1"},
            {"id_contrato": "CO1.PCCNTR.2", "valor": 140911738,
             "fecha": "2026-07-21", "enlace": None},
        ],
    }
    base.update(cambios)
    return base


def _datos(grupos=None, **recorte):
    r = {"minimas_medibles": 9423, "entidades": 1429, "grupos": 614,
         "desde": "2026-06-12", "hasta": "2026-09-14"}
    r.update(recorte)
    return {"recorte": r, "grupos": grupos if grupos is not None else [_grupo()]}


class TestLaPaginaDiceLoQueNoDice:
    def test_lo_que_no_dice_va_antes_que_las_fichas(self):
        p = construir(_datos(), momento=AHORA)
        assert p.index("Léase esto antes que las fichas") < p.index("Las fichas")

    def test_niega_las_cuatro_cosas_que_no_afirma(self):
        t = _texto(construir(_datos(), momento=AHORA))
        assert "no dice que se haya violado la ley" in t
        assert "no dice que sea la misma compra" in t
        assert "no dice que haya intención" in t
        assert "no menciona a ningún funcionario" in t

    def test_cada_ficha_lleva_su_propio_descargo(self):
        # El descargo de arriba no viaja: alguien puede llegar a una ficha por
        # un enlace directo, o pegarle una captura a otra persona.
        p = construir(_datos(), momento=AHORA)
        t = _texto(p)
        assert t.count("no puede saber") >= 1
        assert "hechos comprobables, no una conclusión sobre nadie" in t

    def test_el_descargo_no_usa_el_vocabulario_prohibido(self):
        # La primera versión decía «no afirma que exista irregularidad». Es una
        # negación, y aun así la palabra se planta: puesta bajo el nombre de
        # una alcaldía, quien pase el ojo lee la palabra y no el «no».
        from vigia.reglas.lenguaje import revisar
        assert revisar(_texto(construir(_datos(), momento=AHORA))) == []

    def test_dice_que_cada_contrato_cabia_en_el_tope(self):
        p = construir(_datos(), momento=AHORA)
        assert "está por debajo del tope de la entidad" in _texto(p)

    def test_no_usa_la_palabra_fraccionamiento_contra_la_entidad(self):
        # La palabra nombra la Regla, no la conducta de nadie. Si apareciera
        # dentro de una ficha, el descargo de al lado no la desharía.
        p = construir(_datos(), momento=AHORA)
        ficha = p.split('<article class="ficha">')[1]
        assert "fraccion" not in ficha.lower()


class TestLaCoberturaVaAntesQueLaLista:
    def test_declara_a_cuantas_entidades_no_alcanza(self):
        grupos = [_grupo(), _grupo(nit_entidad="999", minimas_entidad=2)]
        p = construir(_datos(grupos), momento=AHORA)
        assert "quedaron fuera del alcance" in _texto(p)

    def test_dice_que_fuera_de_alcance_no_es_limpia(self):
        grupos = [_grupo(), _grupo(nit_entidad="999", minimas_entidad=2)]
        p = construir(_datos(grupos), momento=AHORA)
        t = _texto(p)
        assert "no quiere decir que esas entidades estén limpias" in t
        assert "no son «las que fraccionan en Colombia»" in t

    def test_la_cobertura_va_antes_que_las_fichas(self):
        p = construir(_datos(), momento=AHORA)
        assert p.index("Sobre cuánto alcanza") < p.index("Las fichas")


class TestNingunaPersonaNaturalQuedaNombrada:
    def test_una_cedula_sale_enmascarada(self):
        p = construir(_datos([_grupo(proveedor_tipo="Cédula de Ciudadanía",
                                     proveedor_numero="1020304050")]),
                      momento=AHORA)
        assert "1020304050" not in p
        assert "•" in p

    def test_el_nit_de_una_empresa_sale_completo(self):
        # Sin el documento de la empresa la ficha no se puede comprobar, y es
        # información pública de un contrato público.
        p = construir(_datos(), momento=AHORA)
        assert "900629234" in p

    def test_la_barrera_del_sitio_no_encuentra_nada(self):
        from vigia.documento import persona_sin_enmascarar
        p = construir(_datos([
            _grupo(),
            _grupo(nit_entidad="800", proveedor_tipo="Cédula de Ciudadanía",
                   proveedor_numero="79123456"),
        ]), momento=AHORA)
        assert persona_sin_enmascarar(p) == []


class TestLaFichaSePuedeComprobar:
    def test_enlaza_cada_contrato_a_su_ficha_oficial(self):
        p = construir(_datos(), momento=AHORA)
        assert "community.secop.gov.co/CO1.PCCNTR.1" in p

    def test_un_contrato_sin_enlace_sale_igual_pero_sin_vinculo(self):
        # El dato importa aunque la fuente no traiga la URL. Lo que no se hace
        # es inventar un enlace que no lleve a ninguna parte.
        p = construir(_datos(), momento=AHORA)
        assert "CO1.PCCNTR.2" in p
        assert 'href="None"' not in p

    def test_pone_las_dos_cifras_y_cuantas_veces(self):
        p = construir(_datos(), momento=AHORA)
        assert "$290.911.738" in p       # la suma
        assert "$73.526.697" in p        # el techo de la entidad
        assert "veces" in p


class TestElOrdenNoEsUnRanking:
    def test_las_fichas_van_por_fecha_y_no_por_tamano(self):
        # Ordenar por «veces» convertiría la página en «los peores», que es
        # justo lo que no es.
        chico = _grupo(nit_entidad="111", nombre_entidad="ENTIDAD DE JUNIO",
                       mes="2026-06-01", suma=250000000)
        grande = _grupo(nit_entidad="222", nombre_entidad="ENTIDAD DE AGOSTO",
                        mes="2026-08-01", suma=400000000)
        p = construir(_datos([grande, chico]), momento=AHORA)
        assert p.index("ENTIDAD DE JUNIO") < p.index("ENTIDAD DE AGOSTO")

    def test_la_palabra_peores_solo_aparece_negada(self):
        # La página dice «no hay ranking ni los peores». Lo que no puede es
        # decirlo en otra parte, y menos dentro de una ficha.
        t = _texto(construir(_datos(), momento=AHORA))
        assert t.count("los peores") == 1
        assert "No hay ranking ni «los peores»" in t

    def test_ninguna_ficha_ordena_ni_puntua(self):
        p = construir(_datos(), momento=AHORA)
        ficha = p.split('<article class="ficha">')[1]
        for palabra in ("peor", "ranking", "puesto", "#1"):
            assert palabra not in ficha.lower()


class TestCuandoNoHayNadaQueEnsenar:
    def test_sin_grupos_que_encienden_lo_dice_sin_inventar(self):
        # «Se miró y no había» es un resultado, y se escribe así.
        flojo = _grupo(suma=80000000)  # 1,09 veces: por debajo de su corte
        p = construir(_datos([flojo]), momento=AHORA)
        assert "Se miró y no había" in _texto(p)

    def test_sin_un_solo_grupo_mirable_se_niega_a_dibujar(self):
        ciego = _grupo(minimas_entidad=2)
        with pytest.raises(ValueError):
            construir(_datos([ciego]), momento=AHORA)


class TestElDatoNoPuedeRomperLaPagina:
    def test_un_nombre_de_entidad_con_html_se_escapa(self):
        p = construir(_datos([_grupo(
            nombre_entidad="<script>alert(1)</script>")]), momento=AHORA)
        assert "<script>alert(1)</script>" not in p
        assert "&lt;script&gt;" in p
