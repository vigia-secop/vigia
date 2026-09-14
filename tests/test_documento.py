"""Pruebas del enmascarado de documentos.

POR QUÉ ESTAS PRUEBAS SON SERIAS. El modelo de amenaza original estaba mal:
protegía la lista de revisión de ser *publicada* —gitignore, generador aparte,
publicador que aborta— y todo eso funciona y está comprobado.

Lo que no cubría es que la página se **comparte**: se pega en un chat, se manda
por correo, se le hace una captura. Eso ocurrió el 2026-09-11 con veintitrés
cédulas, y ninguna de las barreras existentes podía haberlo evitado, porque
ninguna se interpone entre una persona y su propio archivo.

La única defensa contra eso es que el número no esté escrito en la página.
"""

from __future__ import annotations

import pytest

from vigia.documento import VISIBLES, es_de_persona, escribir


class TestLaCedulaNoSeVe:
    @pytest.mark.parametrize("tipo,numero,esperado_fin", [
        ("CEDULA DE CIUDADANIA", "1085291006", "006"),
        ("CEDULA DE CIUDADANIA", "73209333", "333"),
        ("Cédula de Ciudadanía", "1043029732", "732"),
        ("CEDULA DE EXTRANJERIA", "123456", "456"),
        ("PASAPORTE", "AT123456", "456"),
    ])
    def test_se_enmascara_y_solo_quedan_los_ultimos(self, tipo, numero, esperado_fin):
        salida = escribir(tipo, numero)
        assert numero not in salida, "el número completo NO puede aparecer"
        assert salida.endswith(esperado_fin)
        assert "•" in salida

    def test_las_cedulas_reales_del_incidente_quedan_ocultas(self):
        # Las que se pegaron en el chat del 2026-09-11. Si esta prueba falla,
        # es que el enmascarado dejó de funcionar para casos de verdad.
        for c in ("1085291006", "1005542885", "1001329572", "1118811027",
                  "1042424496", "1004350076", "1043029732", "73209333",
                  "1083050136", "15406045", "1088286306", "1214728430",
                  "38260810", "1076651546", "1085314808", "35534914",
                  "1051476760", "1088825148", "1043643009", "94360865",
                  "1000627801"):
            assert c not in escribir("CEDULA DE CIUDADANIA", c)

    def test_el_tipo_sigue_visible(self):
        # Saber que es una persona natural y no una empresa es parte del dato
        # y no identifica a nadie.
        assert "CEDULA" in escribir("CEDULA DE CIUDADANIA", "1085291006")


class TestElNitSiSeVe:
    """Un NIT identifica a una empresa: está en su factura y en su fachada.
    Esconderlo haría inservible la página sin proteger a ninguna persona."""

    @pytest.mark.parametrize("numero", ["900445736", "860524654", "900676568"])
    def test_el_nit_va_completo(self, numero):
        assert escribir("NIT", numero) == f"NIT {numero}"

    def test_un_tipo_desconocido_se_trata_como_empresa(self):
        # Ante la duda se muestra, porque la alternativa —enmascarar todo—
        # acabaría con alguien pidiendo la bandera de «completo» siempre, y
        # entonces la protección no existiría para nadie.
        assert escribir("NIT DE OTRO PAIS", "123456789") == "NIT DE OTRO PAIS 123456789"


class TestLosCasosQueRompen:
    def test_un_numero_muy_corto_se_esconde_entero(self):
        # «•12» parece protegido y no lo está: con dos dígitos visibles de un
        # documento de cuatro, adivinarlo es trivial.
        salida = escribir("CEDULA DE CIUDADANIA", "1234")
        assert "1234" not in salida
        assert salida.count("•") == 4

    def test_sin_numero_devuelve_el_tipo(self):
        assert escribir("CEDULA DE CIUDADANIA", None) == "CEDULA DE CIUDADANIA"
        assert escribir(None, None) == "—"

    def test_sin_tipo_pero_con_numero_se_muestra(self):
        # No se puede saber si es persona; se comporta como los demás campos
        # sin tipo del proyecto y se deja ver.
        assert escribir(None, "900445736") == "900445736"

    def test_la_misma_persona_se_ve_igual_en_dos_filas(self):
        # Es lo que hace que la página siga sirviendo: reconocer al mismo
        # contratista dos veces no necesita el número entero.
        a = escribir("CEDULA DE CIUDADANIA", "1085291006")
        b = escribir("CEDULA DE CIUDADANIA", "1085291006")
        assert a == b


class TestLaBanderaDeCompleto:
    def test_pedido_a_sabiendas_sale_entero(self):
        assert escribir("CEDULA DE CIUDADANIA", "1085291006", completo=True) \
            == "CEDULA DE CIUDADANIA 1085291006"

    def test_por_defecto_NO_sale_entero(self):
        # El valor por defecto es la decisión de diseño, no un detalle.
        assert "1085291006" not in escribir("CEDULA DE CIUDADANIA", "1085291006")


class TestQueCuentaComoPersona:
    @pytest.mark.parametrize("tipo", [
        "CEDULA DE CIUDADANIA", "Cédula de Extranjería", "PASAPORTE",
        "NUIP", "TARJETA DE IDENTIDAD", "REGISTRO CIVIL",
        "PERMISO POR PROTECCION TEMPORAL",
    ])
    def test_si(self, tipo):
        assert es_de_persona(tipo)

    @pytest.mark.parametrize("tipo", ["NIT", "nit", "", None])
    def test_no(self, tipo):
        assert not es_de_persona(tipo)
