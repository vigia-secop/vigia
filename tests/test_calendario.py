"""Calendario hábil colombiano.

Los casos no salen de una tabla copiada: salen de fechas que se pueden
comprobar contra el calendario real, y de la medición que hizo falta el
2026-09-03 para no publicar una caída del 45,7 % que era puro calendario.
"""

from __future__ import annotations

from datetime import date

import pytest

from vigia.calendario import (
    FESTIVOS_MAXIMOS, FESTIVOS_MINIMOS, dias_habiles, domingo_de_pascua,
    es_festivo, es_habil,
    festivos, nombre_del_festivo, por_dia_habil,
)


@pytest.mark.parametrize("anio,esperada", [
    (2024, date(2024, 3, 31)),
    (2025, date(2025, 4, 20)),
    (2026, date(2026, 4, 5)),
    (2027, date(2027, 3, 28)),
])
def test_la_pascua_cae_donde_debe(anio, esperada):
    assert domingo_de_pascua(anio) == esperada


#: El calendario OFICIAL de 2025 (Alcaldía de Bogotá). Diecisiete fechas, no
#: dieciocho: el Sagrado Corazón y San Pedro y San Pablo caen el mismo lunes 30
#: de junio. Es la prueba más fuerte de este módulo, porque no comprueba una
#: propiedad sino el calendario entero de un año contra su fuente.
OFICIAL_2025 = {
    date(2025, 1, 1), date(2025, 1, 6), date(2025, 3, 24),
    date(2025, 4, 17), date(2025, 4, 18), date(2025, 5, 1),
    date(2025, 6, 2), date(2025, 6, 23), date(2025, 6, 30),
    date(2025, 7, 20), date(2025, 8, 7), date(2025, 8, 18),
    date(2025, 10, 13), date(2025, 11, 3), date(2025, 11, 17),
    date(2025, 12, 8), date(2025, 12, 25),
}


def test_el_calendario_de_2025_cuadra_fecha_por_fecha_con_el_oficial():
    assert festivos(2025) == OFICIAL_2025
    assert len(OFICIAL_2025) == 17


@pytest.mark.parametrize("anio", range(2020, 2031))
def test_un_anio_tiene_diecisiete_o_dieciocho_festivos(anio):
    # NO son siempre dieciocho. Esta prueba se escribió afirmando que sí, y
    # falló en 2025 y 2030: ahí el Sagrado Corazón y San Pedro y San Pablo
    # caen el mismo lunes. El algoritmo estaba bien; la afirmación era mía.
    assert FESTIVOS_MINIMOS <= len(festivos(anio)) <= FESTIVOS_MAXIMOS


@pytest.mark.parametrize("anio", [2025, 2030])
def test_los_anios_de_diecisiete_son_los_de_la_colision(anio):
    assert len(festivos(anio)) == FESTIVOS_MINIMOS


def test_el_7_de_agosto_no_se_mueve():
    # Batalla de Boyacá es de fecha fija. En 2026 cayó viernes.
    assert es_festivo(date(2026, 8, 7))
    assert date(2026, 8, 7).weekday() == 4


def test_la_asuncion_de_2026_se_traslada_al_17():
    # ESTE es el festivo que casi me hace publicar una caída falsa: el 15 de
    # agosto de 2026 cayó sábado, así que la Ley Emiliani lo mueve al lunes 17,
    # y la ventana «después del 7 de agosto» perdió otro día hábil.
    assert not es_habil(date(2026, 8, 17))
    assert nombre_del_festivo(date(2026, 8, 17)) == "Asunción"
    assert not es_festivo(date(2026, 8, 15))


def test_un_festivo_que_ya_cae_en_lunes_se_queda_donde_esta():
    # 12 de octubre de 2026 es lunes: no se mueve.
    assert date(2026, 10, 12).weekday() == 0
    assert es_festivo(date(2026, 10, 12))


def test_los_traslados_de_2026_se_pueden_verificar_uno_a_uno():
    esperados = {
        date(2026, 1, 12): "Reyes Magos",          # el 6 cayó martes
        date(2026, 3, 23): "San José",             # el 19 cayó jueves
        date(2026, 6, 29): "San Pedro y San Pablo",  # ya era lunes
        date(2026, 8, 17): "Asunción",             # el 15 cayó sábado
        date(2026, 11, 2): "Todos los Santos",     # el 1 cayó domingo
        date(2026, 11, 16): "Independencia de Cartagena",  # el 11, miércoles
    }
    for dia, nombre in esperados.items():
        assert es_festivo(dia), dia
        assert nombre_del_festivo(dia) == nombre


def test_semana_santa_de_2026():
    assert nombre_del_festivo(date(2026, 4, 2)) == "Jueves Santo"
    assert nombre_del_festivo(date(2026, 4, 3)) == "Viernes Santo"
    # El sábado y el domingo de Pascua NO son festivos de ley.
    assert not es_festivo(date(2026, 4, 4))


def test_los_moviles_de_pascua_caen_en_lunes():
    for dia in (date(2026, 5, 18), date(2026, 6, 8), date(2026, 6, 15)):
        assert es_festivo(dia), dia
        assert dia.weekday() == 0, dia


def test_un_sabado_no_es_habil_aunque_no_sea_festivo():
    assert not es_habil(date(2026, 9, 5))   # sábado
    assert not es_habil(date(2026, 9, 6))   # domingo
    assert es_habil(date(2026, 9, 4))       # viernes


def test_la_ventana_que_casi_produce_la_caida_falsa():
    # Once días naturales antes y después del 7 de agosto de 2026. Los conteos
    # crudos daban -45,7 %; el calendario explica por qué.
    antes = dias_habiles(date(2026, 7, 27), date(2026, 8, 6))
    despues = dias_habiles(date(2026, 8, 7), date(2026, 8, 17))

    assert antes == 9
    assert despues == 5
    # Casi la mitad de días hábiles. Comparar los conteos crudos habría
    # atribuido al cambio de gobierno lo que era el almanaque.
    assert despues < antes


def test_un_rango_al_reves_da_cero_y_no_un_negativo():
    assert dias_habiles(date(2026, 9, 10), date(2026, 9, 1)) == 0


def test_un_solo_dia_habil_cuenta_uno():
    assert dias_habiles(date(2026, 9, 4), date(2026, 9, 4)) == 1
    assert dias_habiles(date(2026, 9, 5), date(2026, 9, 5)) == 0


def test_repartir_por_dia_habil():
    # 100 contratos en una semana de cinco hábiles son 20 por día.
    assert por_dia_habil(100, date(2026, 9, 7), date(2026, 9, 11)) == 20


def test_sin_dias_habiles_la_pregunta_no_tiene_respuesta():
    # Un fin de semana. Devolver cero haría creer que no hubo actividad;
    # `None` dice que no se puede repartir.
    assert por_dia_habil(100, date(2026, 9, 5), date(2026, 9, 6)) is None
