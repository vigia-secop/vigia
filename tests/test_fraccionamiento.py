"""Pruebas de la bandera de fraccionamiento.

Esta es la primera candidata que sobrevivió a la prueba del fondo: de 9.423
mínimas cuantías, el 85,1 % es un contrato solo, así que agruparse **no es lo
normal**. Las tres anteriores describían a la mayoría del país y se tiraron.

Lo que se comprueba aquí no es que encuentre cosas, sino las cuatro que la
harían dañina:

1. Que **«no se pudo mirar» no se confunda con «está limpia»**. Una entidad con
   un techo imposible tiene un tope inalcanzable: ningún grupo suyo lo pasará
   nunca, y reportarla como limpia sería afirmar algo que no se miró.
2. Que **el corte sea el medido** y no uno más bajo. Bajarlo a 1,2 convierte
   41 hallazgos en 208 y la cola deja de leerse.
3. Que **la unidad sea el grupo**, no el contrato: 281 hallazgos y no 683
   avisos sueltos que por separado no significan nada.
4. Que **no se pueda activar sin calibrar**.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from vigia.reglas import fraccionamiento as fr
from vigia.reglas.modelo import ACTIVA, CALIBRACION, TransicionNoPermitida

AHORA = datetime(2026, 9, 19, 8, 39)

#: El caso real que abrió la historia: Alcaldía de Vijes, 6 contratos al mismo
#: proveedor en julio de 2026, $290,9 millones contra un techo de $73,5.
VIJES = {
    "nit_entidad": "890399011",
    "nombre_entidad": "ALCALDIA MUNICIPIO DE VIJES",
    "proveedor_tipo": "NIT",
    "proveedor_numero": "900629234",
    "mes": "2026-07-01",
    "contratos": 6,
    "suma": Decimal("290911738"),
    "techo": Decimal("73526697"),
    "p95_entidad": Decimal("68000000"),
    "minimas_entidad": 41,
    "contratos_ids": ["CO1.PCCNTR.1", "CO1.PCCNTR.2", "CO1.PCCNTR.3"],
}


def _regla():
    regla = fr.crear(AHORA)
    return regla, regla.versiones[-1]


def _evaluar(grupo):
    regla, version = _regla()
    return fr.evaluar(grupo, regla=regla, version=version,
                      consultado_en=AHORA, momento=AHORA)


class TestNoSePudoMirarNoEsEstaLimpia:
    """La distinción que sostiene toda la bandera."""

    def test_un_techo_imposible_levanta_en_vez_de_callar(self):
        # $44.118.060.000 fue el techo mayor del país en la primera corrida.
        # Una mínima cuantía de cuarenta y cuatro mil millones no existe: o la
        # modalidad está mal puesta, o es una errata. Con ese techo, esa
        # entidad nunca encendería — y eso NO significa que no fraccione.
        ciega = dict(VIJES, techo=Decimal("44118060000"),
                     p95_entidad=Decimal("50000000"))
        with pytest.raises(fr.NoSePuedeMirar):
            _evaluar(ciega)

    def test_una_entidad_con_pocas_minimas_tampoco_se_puede_mirar(self):
        # Con dos contratos, el «techo» es el único que hay. Es la misma
        # trampa aritmética que hundió la concentración por proveedor.
        poca = dict(VIJES, minimas_entidad=3)
        with pytest.raises(fr.NoSePuedeMirar):
            _evaluar(poca)

    def test_sin_percentil_no_se_juzga_el_techo(self):
        # Se prefiere no mirar a mirar mal.
        sin_p95 = dict(VIJES, p95_entidad=None)
        with pytest.raises(fr.NoSePuedeMirar):
            _evaluar(sin_p95)

    def test_un_techo_creible_si_se_mira(self):
        assert fr.techo_creible(VIJES, fr.umbrales_iniciales()) is True


class TestElCorteEsElQueSeMidio:
    def test_vijes_enciende(self):
        alerta = _evaluar(VIJES)
        assert alerta is not None
        assert alerta.expediente.valores_disparadores["veces_el_techo"] == "3.96"

    def test_pasarse_por_un_pelo_no_enciende(self):
        # 73 grupos se pasan por menos de 1,2 veces. Eso es ruido de redondeo
        # y de meses partidos, no un hallazgo.
        flojo = dict(VIJES, suma=Decimal("80000000"))  # 1,09 veces
        assert _evaluar(flojo) is None

    def test_en_el_borde_de_su_tramo_no_enciende(self):
        # El corte es «más de», no «o más»: en el borde se prefiere callar.
        from decimal import Decimal

        from vigia.reglas import fraccionamiento as fr
        corte = fr.corte_para(VIJES, fr.umbrales_iniciales())
        borde = dict(VIJES, suma=int(Decimal(VIJES["techo"]) * corte))
        assert _evaluar(borde) is None


class TestElCorteDependeDelTamanoDelTecho:
    """La corrección que salvó a la bandera de señalar a los municipios pobres.

    Con un corte único de ×2, la primera calibración encendió en el 12,7 % de
    las entidades con techo bajo y en el 0,5 % de las de techo alto:
    veinticinco veces más probable ser señalado por tener un tope pequeño. Y
    como la ley fija el tope según el presupuesto, techo pequeño es municipio
    pequeño.

    Con un corte por tramo la tasa se aplana (4,7 / 4,6 / 4,9 %) y lo que
    queda medido es ser raro **entre los pares**, no ser pobre.
    """

    def test_un_techo_pequeno_exige_pasarse_mucho_mas(self):
        from vigia.reglas import fraccionamiento as fr
        u = fr.umbrales_iniciales()
        pequeno = fr.corte_para({"techo": 49000000}, u)
        grande = fr.corte_para({"techo": 250000000}, u)
        assert pequeno > grande, (
            "si el corte no fuera mas exigente con los techos pequenos, la "
            "bandera volveria a senalar a los municipios pobres por serlo")

    def test_el_mismo_exceso_no_enciende_igual_en_los_dos_extremos(self):
        # Pasarse 2,5 veces: en un municipio con techo de $49 M es normal
        # entre sus pares; en una entidad grande es raro.
        chico = dict(VIJES, techo=49000000, p95_entidad=45000000,
                     suma=int(49000000 * 2.5))
        grande = dict(VIJES, nit_entidad="800000000", techo=250000000,
                      p95_entidad=200000000, suma=int(250000000 * 2.5))
        assert _evaluar(chico) is None
        assert _evaluar(grande) is not None

    def test_la_alerta_guarda_el_corte_de_su_tramo(self):
        # Sin esto, quien revise la alerta meses despues no puede saber
        # contra que se comparo esta entidad en particular.
        alerta = _evaluar(VIJES)
        assert alerta.expediente.valores_disparadores["corte_de_su_tramo"] == "1.95"

    def test_un_techo_sin_tramo_cae_en_el_respaldo(self):
        from vigia.reglas import fraccionamiento as fr
        assert fr.corte_para({"techo": 1}, {"tramos_de_techo": []}) == \
            fr.VECES_EL_TECHO_POR_DEFECTO

    def test_un_contrato_solo_no_es_un_grupo(self):
        # El 85,1 % de las mínimas cuantías del país es esto. Si encendiera
        # aquí, la bandera describiría el país como las tres anteriores.
        solo = dict(VIJES, contratos=1)
        assert _evaluar(solo) is None


class TestLaUnidadEsElGrupo:
    def test_el_expediente_apunta_al_grupo_y_no_a_un_contrato(self):
        alerta = _evaluar(VIJES)
        clave = alerta.expediente.id_registro_fuente
        assert clave == "890399011|NIT|900629234|2026-07-01"

    def test_el_expediente_lleva_los_contratos_para_poder_comprobar(self):
        alerta = _evaluar(VIJES)
        ids = alerta.expediente.valores_disparadores["contratos_ids"]
        assert ids == ["CO1.PCCNTR.1", "CO1.PCCNTR.2", "CO1.PCCNTR.3"]

    def test_sin_los_contratos_no_se_emite(self):
        # Una Alerta cuyo expediente no permite comprobar nada es una
        # afirmación sin respaldo.
        sin_ids = dict(VIJES, contratos_ids=[])
        assert _evaluar(sin_ids) is None

    def test_el_expediente_guarda_el_umbral_que_se_aplico(self):
        # Seis meses después, la pregunta es «¿con qué umbral se emitió esto?».
        alerta = _evaluar(VIJES)
        assert alerta.expediente.umbral_aplicado["veces_el_techo"] == "2"


class TestNaceEnBorradorYNoSeActivaSola:
    def test_nace_en_borrador(self):
        regla, _ = _regla()
        assert regla.estado == "borrador"

    def test_no_puede_saltar_a_activa_sin_calibrar(self):
        regla, _ = _regla()
        regla.mover_a(CALIBRACION)
        with pytest.raises(TransicionNoPermitida):
            regla.mover_a(ACTIVA)

    def test_la_descripcion_dice_lo_que_no_dice(self):
        # El vocabulario de esta Regla es parte de la Regla: si la descripción
        # afirmara una conducta, la bandera acusaría aunque el número fuera
        # correcto.
        regla, _ = _regla()
        assert "no dice nada sobre la conducta de nadie" in regla.descripcion
        assert "cabía en el tope" in regla.descripcion

    def test_los_umbrales_de_partida_son_los_medidos(self):
        u = fr.umbrales_iniciales()
        assert u["veces_el_techo"] == "2"
        assert u["contratos_minimos"] == 2
        assert u["minimas_de_la_entidad"] == 5
        assert u["techo_sobre_p95_maximo"] == "20"
