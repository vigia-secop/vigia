"""Pruebas de la barrera de publicación.

Estas son las pruebas más serias del repositorio, y la razón es simple:
**todo lo demás se corrige en la siguiente corrida; esto no.** Un boletín
publicado ya circuló, y un borrado en X no borra las capturas ni las citas.

Así que lo que se comprueba aquí no es que la función funcione, sino que las
tres formas concretas de hacerle daño a alguien estén cerradas:

1. Publicar el documento de identidad de una persona natural contratista.
2. Publicar una palabra que afirme que alguien obró mal.
3. Publicar un post que se corta a la mitad, o un hilo sin decir qué es.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vigia.boletin import construir
from vigia.publicacion import (
    LIMITE_POST,
    periodo_anterior_comparable,
    NOTA,
    NoPublicable,
    exigir_publicable,
    largo_en_x,
    revisar,
)

DATOS = Path(__file__).parent / "datos"


def _hilo(*posts: str) -> list[str]:
    """Un hilo mínimo válido, al que se le añade lo que se quiera probar."""
    return [*posts, NOTA]


class TestNingunDocumentoDeIdentidad:
    """Una cédula publicada es un dato personal difundido sin autorización.
    No hay versión buena de esto: no depende del contexto ni de la intención.
    """

    @pytest.mark.parametrize("documento", [
        "5888679",        # una cédula real vista en la lista de revisión
        "52009479",       # otra
        "900445736",      # un NIT
        "860524654",      # otro NIT
    ])
    def test_un_documento_suelto_no_se_publica(self, documento):
        with pytest.raises(NoPublicable, match="documento"):
            exigir_publicable(_hilo(f"Contratista destacado: {documento}"))

    def test_tampoco_escondido_en_una_frase(self):
        with pytest.raises(NoPublicable):
            exigir_publicable(_hilo("El NIT 830501223 firmó tres contratos."))

    def test_una_cifra_de_dinero_con_puntos_SI_pasa(self):
        # `$1.910.424.437.064` lleva separadores de miles y es justo lo que el
        # boletín tiene que poder decir. Si la barrera lo atajara, sería
        # inservible y alguien la apagaría — que es como mueren las barreras.
        assert revisar(_hilo("El valor fue $1.910.424.437.064 en la semana.")) == []

    def test_un_ano_pasa(self):
        assert revisar(_hilo("Medido en 2026 sobre datos de 2025.")) == []

    def test_un_conteo_de_cuatro_cifras_pasa(self):
        assert revisar(_hilo("Se firmaron 8.432 contratos; antes 7150.")) == []


class TestNingunaImputacion:
    """En Colombia la injuria y la calumnia son delito, no solo un pleito
    civil. Publicar que alguien obró mal sin poder probarlo tiene consecuencias
    penales para quien publica."""

    @pytest.mark.parametrize("frase", [
        "Un contrato irregular en el Meta",          # vocabulario-permitido
        "Posible corrupcion en la adjudicación",     # vocabulario-permitido
        "Esto huele a fraude",                       # vocabulario-permitido
        "Contratación ilegal",                       # vocabulario-permitido
    ])
    def test_no_se_publica(self, frase):
        with pytest.raises(NoPublicable, match="imputacion"):
            exigir_publicable(_hilo(frase))

    def test_con_tilde_tampoco(self):
        with pytest.raises(NoPublicable):
            exigir_publicable(_hilo("Aquí hubo corrupción."))  # vocabulario-permitido


class TestElHiloSeTieneQuePoderLeer:
    def test_un_post_que_se_pasa_del_limite_no_se_publica(self):
        with pytest.raises(NoPublicable, match="limite"):
            exigir_publicable(_hilo("x" * (LIMITE_POST + 1)))

    def test_justo_en_el_limite_pasa(self):
        assert revisar(_hilo("x" * LIMITE_POST)) == []

    def test_un_enlace_cuenta_23_pase_lo_que_pase(self):
        # X cuenta todo enlace como 23 caracteres. Medir con `len()` haría que
        # un post con enlace largo se viera bien aquí y rebotara al publicarlo,
        # que es justo cuando ya no hay tiempo de arreglarlo.
        largo = "https://ejemplo.gov.co/" + "a" * 200
        assert largo_en_x(f"Ver: {largo}") == len("Ver: ") + 23

    def test_un_post_vacio_no_se_publica(self):
        with pytest.raises(NoPublicable, match="vacio"):
            exigir_publicable(["   ", NOTA])

    def test_sin_la_nota_el_hilo_no_sale(self):
        # El tercer post de un hilo circula sin el primero. Si la nota de qué
        # es esto vive solo en un enlace, para la mayoría no existe.
        with pytest.raises(NoPublicable, match="nota"):
            exigir_publicable(["Se firmaron 8.432 contratos esta semana."])


class TestElBoletinDeVerdadPasaLaBarrera:
    @staticmethod
    def _datos():
        return json.loads(
            (DATOS / "boletin-minimo.json").read_text(encoding="utf-8"))

    def test_se_construye_y_es_publicable(self):
        posts = construir(self._datos(), enlace="https://ejemplo.github.io")
        assert len(posts) >= 4
        assert revisar(posts) == []

    def test_lleva_la_cobertura_antes_que_cualquier_ranking(self):
        # El mismo principio que el Panel: un número de contratación pública
        # sin saber sobre cuánto se calculó es la clase de cifra que se cita
        # mal. En un hilo eso importa más, porque se cita suelto.
        posts = construir(self._datos())
        cobertura = next(i for i, p in enumerate(posts) if "NO alcanzan a ver" in p)
        rankings = [i for i, p in enumerate(posts)
                    if "Dónde se firmó" in p or "Cómo se contrató" in p]
        assert all(cobertura < r for r in rankings)

    def test_no_nombra_a_nadie(self):
        # La garantía de verdad está en `boletin.sql`, que no devuelve nombres.
        # Esta prueba vigila que el generador no los invente por otro lado.
        texto = "\n".join(construir(self._datos()))
        for palabra in ("NIT", "CEDULA", "CÉDULA", "S.A.S", "S.A.", "LTDA"):
            assert palabra not in texto

    def test_los_porcentajes_van_con_coma(self):
        # Un «23.08 %» con punto decimal desmiente al resto del texto antes de
        # que nadie lea el número.
        import re

        texto = "\n".join(construir(self._datos()))
        assert not re.search(r"\d\.\d+\s*%", texto)


class TestElSitioPublico:
    """`docs/` es lo que ve internet. Lo que se comprueba aquí es que salga de
    la fuente correcta y que nada se cuele por el camino."""

    @staticmethod
    def _html():
        from vigia.sitio import construir

        return construir(TestElBoletinDeVerdadPasaLaBarrera._datos())

    def test_pasa_la_barrera_de_publicacion(self):
        from vigia.sitio import texto_visible

        lineas = texto_visible(self._html())
        trozos = [l[i:i + 250] for l in lineas for i in range(0, len(l), 250)]
        assert revisar(trozos + [NOTA]) == []

    def test_no_trae_ningun_documento(self):
        import re

        from vigia.sitio import texto_visible

        texto = " ".join(texto_visible(self._html()))
        # Se quitan las cifras con separador de miles: son plata, no documentos.
        limpio = re.sub(r"\d{1,3}(\.\d{3})+", " ", texto)
        assert not re.search(r"(?<!\d)\d{6,12}(?!\d)", limpio)

    def test_no_trae_ninguna_cedula_sin_enmascarar(self):
        from vigia.documento import persona_sin_enmascarar

        assert persona_sin_enmascarar(self._html()) == []

    def test_la_palabra_NIT_puede_aparecer_explicando(self):
        # La portada explica que el NIT va completo y la cédula enmascarada.
        # Esa frase TIENE que poder escribirse: una prueba que la prohibiera
        # obligaría a explicar la política sin nombrarla, que es lo contrario
        # de lo que hace falta. Es la misma razón por la que la prueba de
        # vocabulario recorre el AST y perdona los docstrings.
        html = self._html()
        assert "NIT" in html
        assert "enmascarado" in html

    def test_la_cobertura_va_antes_que_los_rankings(self):
        html = self._html()
        assert (html.index("no alcanzan a ver") < html.index("Dónde se firmó"))

    def test_dice_que_no_tiene_banderas(self):
        # Si el sitio callara esto, un lector razonable supondría que la
        # ausencia de señalamientos significa que no hay nada que señalar.
        # Significa que todavía no sabemos señalar.
        html = self._html()
        assert "no señala contratos" in html
        assert "no tiene ninguna" in html or "no publica banderas" in html

    def test_se_abre_bien_desde_el_disco(self):
        html = self._html()
        assert html.startswith("<!doctype html>")
        assert '<meta charset="utf-8">' in html
        assert html.count("<body>") == 1 and html.count("</body>") == 1

    def test_no_queda_ningun_token_css_sin_definir(self):
        import re

        html = self._html()
        usados = set(re.findall(r"var\((--[a-z0-9-]+)\)", html))
        definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", html))
        assert usados - definidos == set()


class TestNoSeInventaUnaCaidaQueNoOcurrio:
    """La trampa más peligrosa de arrancar con historial parcial.

    Si el período anterior empieza antes del primer contrato ingerido, sus
    cifras salen en cero — no porque el Estado no contratara, sino porque no
    lo hemos traído. Comparar contra eso publica una caída del 100 % que es
    literalmente mentira. Es la misma distinción del modo calibración: «se
    miró y no había» no es «no se miró».
    """

    @staticmethod
    def _con(primer_contrato, anterior_desde):
        datos = json.loads(
            (DATOS / "boletin-minimo.json").read_text(encoding="utf-8"))
        datos["cobertura_temporal"] = {"primer_contrato": primer_contrato}
        datos["anterior"]["desde"] = anterior_desde
        return datos

    def test_si_el_anterior_empieza_antes_de_lo_ingerido_no_es_comparable(self):
        assert not periodo_anterior_comparable(self._con("2026-07-01", "2026-06-24"))

    def test_si_cae_dentro_de_lo_ingerido_si_es_comparable(self):
        assert periodo_anterior_comparable(self._con("2026-07-01", "2026-07-08"))

    def test_el_mismo_dia_cuenta_como_comparable(self):
        assert periodo_anterior_comparable(self._con("2026-07-01", "2026-07-01"))

    def test_sin_cobertura_temporal_no_se_compara(self):
        # Una carga vieja sin ese campo no debe estrenar la comparación por
        # descuido: ante la duda, callarse.
        datos = self._con("2026-07-01", "2026-07-08")
        del datos["cobertura_temporal"]
        assert not periodo_anterior_comparable(datos)

    def test_el_hilo_lo_dice_con_palabras(self):
        posts = construir(self._con("2026-07-01", "2026-06-24"))
        texto = "\n".join(posts)
        assert "Sin comparación" in texto
        assert "caída que no ocurrió" in texto

    def test_el_sitio_tambien(self):
        from vigia.sitio import construir as sitio

        html = sitio(self._con("2026-07-01", "2026-06-24"))
        assert "sin comparación" in html
        assert "una caída que no ocurrió" in html
