"""Pruebas del techo de lo posible.

Esta guarda existe por un caso concreto, y las pruebas lo usan con nombre
propio: el 2026-09-06 la fuente publicó un proceso de la ESE Hospital Local
San José con **$8 054 481 856 630 300** adjudicados. Ocho mil billones de
pesos en un renglón.

Lo que hay que proteger aquí no es el algoritmo —es una comparación— sino las
dos formas de equivocarse que tendrían consecuencias:

1. **Dejar pasar un imposible** hace falso todo total que Vigía publique, y sin
   fallar: el número sale, se lee, y está mal.
2. **Atajar un contrato real** es peor. Colombia tiene contratos de billones de
   pesos que son ciertos, y esconder uno sería exactamente el daño que este
   proyecto existe para no hacer.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from vigia.normalizado.escala import (
    TECHO_DE_CONTRATO,
    TECHO_FUENTE,
    TECHO_VIGENTE_DESDE,
    fuera_de_escala,
)


class TestElCasoQueLoOrigino:
    def test_el_hospital_de_los_ocho_mil_billones_no_pasa(self):
        assert fuera_de_escala(Decimal("8054481856630300"))

    def test_el_mismo_numero_con_tres_ceros_de_mas_todavia_cabe(self):
        # `431 340 000` publicado como `431 340 000 000` es la errata más
        # común, y **este techo NO la ataja**: 431 mil millones es un contrato
        # perfectamente posible. Se deja escrito para que nadie crea que la
        # guarda cubre más de lo que cubre — esa errata se busca aparte,
        # comparando contratos de la misma entidad y proveedor.
        assert not fuera_de_escala(Decimal("431340000000"))


class TestNoAtajaContratosReales:
    @pytest.mark.parametrize("valor,que_es", [
        (Decimal("1370000000000"), "el huérfano de TRANSMILENIO, $1,37 billones"),
        (Decimal("118274783168"), "el PAE de Medellín, $118 mil millones"),
        (Decimal("72001177364"), "la licitación mayor con un solo oferente"),
        (Decimal("10000000000000"), "diez billones: más que cualquier contrato visto"),
    ])
    def test_un_contrato_grande_pero_posible_pasa(self, valor, que_es):
        assert not fuera_de_escala(valor), que_es

    def test_el_techo_esta_dos_ordenes_por_encima_de_lo_mayor_visto(self):
        # El contrato público más grande de Colombia vive en el orden de 10^12.
        # Si alguien aprieta el techo hasta ahí, esta prueba lo para: un techo
        # que separa «grande» de «muy grande» esconde contratos ciertos, que es
        # el error contrario y peor.
        mayor_visto_plausible = Decimal("1e12")
        assert TECHO_DE_CONTRATO >= mayor_visto_plausible * 100


class TestNoConfundeFaltarConSerImposible:
    def test_un_contrato_sin_valor_no_esta_fuera_de_escala(self):
        # «No está» es otra cosa que «no puede ser», y ya se cuenta aparte en
        # el bloque de cobertura. Confundirlos haría que el Panel reportara
        # como imposibles contratos que simplemente no traen la cifra.
        assert not fuera_de_escala(None)

    def test_un_valor_negativo_pasa_a_proposito(self):
        # Existe en la fuente, normalmente en modificaciones. Se deja pasar
        # para no esconder algo que sí merece verse.
        assert not fuera_de_escala(Decimal("-5000000"))

    def test_cero_pasa(self):
        assert not fuera_de_escala(Decimal("0"))


class TestElBordeExacto:
    def test_justo_en_el_techo_ya_es_imposible(self):
        assert fuera_de_escala(TECHO_DE_CONTRATO)

    def test_un_peso_por_debajo_todavia_cabe(self):
        assert not fuera_de_escala(TECHO_DE_CONTRATO - 1)

    def test_acepta_float_e_int_sin_perder_el_borde(self):
        # El valor llega de PostgreSQL como Decimal y de JSON como float o int.
        # Si la conversión perdiera precisión, el borde se movería según de
        # dónde vino el número, que es la clase de diferencia que nadie
        # encuentra hasta que ya publicó mal.
        assert fuera_de_escala(1e14)
        assert fuera_de_escala(100_000_000_000_000)
        assert not fuera_de_escala(99_999_999_999_999)


class TestElTopeEstaDocumentadoComoPideLa2_1:
    """La historia 2.1 exige que todo tope normativo lleve fecha de vigencia y
    fuente citable. Un número que nadie puede rastrear no se puede defender
    delante de nadie, y este número decide qué contratos desaparecen de los
    totales que Vigía publica."""

    def test_lleva_fecha_de_vigencia(self):
        assert TECHO_VIGENTE_DESDE == "2026-09-06"

    def test_lleva_fuente_citable(self):
        assert "Presupuesto General de la Nación" in TECHO_FUENTE
        assert "Hacienda" in TECHO_FUENTE


class TestLaBaseYElCodigoNoSePuedenSeparar:
    def test_la_migracion_009_usa_el_mismo_techo_que_el_modulo(self):
        # `contrato.valor_fuera_de_escala` es una columna GENERADA con el techo
        # escrito en SQL. Si alguien cambia uno de los dos y no el otro, el
        # Panel excluiría un conjunto de contratos y la lista de revisión
        # mostraría otro, sin que nada falle.
        from pathlib import Path

        sql = (Path(__file__).parent.parent / "migraciones"
               / "009_valores_fuera_de_escala.sql").read_text(encoding="utf-8")
        assert "valor >= 1e14" in sql
        assert Decimal("1e14") == TECHO_DE_CONTRATO
