"""Territorio y orden administrativo (historia 1.6).

Ninguna prueba sale a la red. Los casos salen de mediciones reales sobre
`jbjy-vk9h` y del dataset oficial `vcjz-niiq`, hechas el 2026-09-05 y anotadas
en `territorio.py`.
"""

from __future__ import annotations

import pytest

from vigia.normalizado.territorio import (
    DEPARTAMENTOS_DIVIPOLA,
    ORDEN_CORPORACION_AUTONOMA,
    ORDEN_NACIONAL,
    ORDEN_TERRITORIAL,
    Territorio,
    clasificar_orden,
    codigo_departamento,
    desde_contenido,
    nombre_oficial,
)

#: Los 33 nombres de departamento TAL COMO LOS ESCRIBE EL SECOP, tomados de
#: `jbjy-vk9h` el 2026-09-05 agrupando agosto de 2026 completo. No es una lista
#: inventada: es el universo entero de valores distintos de ese mes, menos
#: «No Definido».
DEPARTAMENTOS_DEL_SECOP = [
    "Distrito Capital de Bogotá", "Antioquia", "Valle del Cauca", "Santander",
    "Cundinamarca", "Atlántico", "Bolívar", "Tolima", "Meta", "Quindío",
    "Magdalena", "Boyacá", "Norte de Santander", "Huila", "Risaralda", "Cauca",
    "Casanare", "Caldas", "Nariño", "Amazonas", "Cesar", "Putumayo",
    "La Guajira", "Caquetá", "Sucre", "Córdoba", "Arauca", "Vichada",
    "San Andrés, Providencia y Santa Catalina", "Chocó", "Guainía", "Guaviare",
    "Vaupés",
]


def contrato(**campos):
    base = {
        "orden": "Territorial",
        "departamento": "Antioquia",
        "ciudad": "Medellín",
    }
    base.update(campos)
    return base


# ------------------------------------------------------------------- orden


def test_el_orden_tiene_tres_valores_no_dos():
    # Medido: Corporación Autónoma son 2 224 contratos en agosto de 2026 y
    # 1 800 en todo 2019. Aparece en los dos cortes, con siete años entre
    # ellos: no es ruido de un mes.
    assert clasificar_orden("Nacional") == ORDEN_NACIONAL
    assert clasificar_orden("Territorial") == ORDEN_TERRITORIAL
    assert clasificar_orden("Corporación Autónoma") == ORDEN_CORPORACION_AUTONOMA


def test_una_corporacion_autonoma_no_es_nacional_ni_territorial():
    car = desde_contenido(contrato(orden="Corporación Autónoma"))

    assert car.orden == ORDEN_CORPORACION_AUTONOMA
    assert not car.es_nacional
    assert car.orden != ORDEN_TERRITORIAL


@pytest.mark.parametrize("valor", ["No Definido", "", None, "Otra cosa", 7])
def test_un_orden_que_no_se_reconoce_queda_desconocido_no_territorial(valor):
    # Rellenar con el valor más común convertiría «no sé» en un dato, y una
    # serie que los mezcle atribuiría al cambio de gobierno lo que no es.
    assert clasificar_orden(valor) is None


def test_el_orden_se_normaliza_sin_tildes_ni_mayusculas():
    assert clasificar_orden("CORPORACION AUTONOMA") == ORDEN_CORPORACION_AUTONOMA
    assert clasificar_orden("  nacional  ") == ORDEN_NACIONAL


# -------------------------------------------------------------- DIVIPOLA


def test_la_tabla_tiene_los_33_departamentos():
    # 32 departamentos más Bogotá D.C.
    assert len(DEPARTAMENTOS_DIVIPOLA) == 33
    assert len(set(DEPARTAMENTOS_DIVIPOLA.values())) == 33


@pytest.mark.parametrize("nombre", DEPARTAMENTOS_DEL_SECOP)
def test_todo_nombre_que_escribe_el_secop_resuelve_a_un_codigo(nombre):
    # ESTA es la prueba que importa. Si mañana alguien reescribe la tabla o
    # quita un alias, aquí se cae, y no en un reporte con un hueco silencioso.
    assert codigo_departamento(nombre) is not None


def test_los_33_nombres_del_secop_dan_33_codigos_distintos():
    codigos = {codigo_departamento(n) for n in DEPARTAMENTOS_DEL_SECOP}

    assert len(codigos) == 33
    assert None not in codigos


def test_bogota_no_falla_en_silencio():
    # El fallo que este módulo existe para evitar. El DANE escribe
    # «BOGOTÁ, D.C.» y el SECOP «Distrito Capital de Bogotá». Un cruce por
    # nombre deja sin código al 16 % de los contratos del país, sin avisar.
    assert codigo_departamento("Distrito Capital de Bogotá") == "11"
    assert codigo_departamento("BOGOTÁ, D.C.") == "11"


def test_san_andres_tampoco():
    # El otro nombre que no coincide: el DANE le antepone «ARCHIPIÉLAGO DE».
    assert codigo_departamento("San Andrés, Providencia y Santa Catalina") == "88"
    assert codigo_departamento(
        "Archipiélago de San Andrés, Providencia y Santa Catalina"
    ) == "88"


@pytest.mark.parametrize("nombre", ["No Definido", "Cundinamarca del Sur", "", None])
def test_un_departamento_desconocido_se_queda_sin_codigo(nombre):
    assert codigo_departamento(nombre) is None


def test_el_nombre_que_se_guarda_es_el_oficial_no_el_de_la_entidad():
    # Para que dos contratos del mismo departamento se muestren igual aunque
    # la fuente los llame distinto.
    territorio = desde_contenido(contrato(departamento="Distrito Capital de Bogotá"))

    assert territorio.departamento_codigo == "11"
    assert territorio.departamento_nombre == "BOGOTA, D.C."


def test_sin_codigo_se_conserva_el_nombre_que_trajo_la_fuente():
    # No se pierde: es lo único con lo que se podrá diagnosticar por qué no
    # resolvió.
    territorio = desde_contenido(contrato(departamento="Vichada del Norte"))

    assert territorio.departamento_codigo is None
    assert territorio.departamento_nombre == "VICHADA DEL NORTE"
    assert territorio.sin_departamento


def test_el_codigo_de_algo_que_no_existe_no_tiene_nombre():
    assert nombre_oficial("00") is None
    assert nombre_oficial(None) is None


# ------------------------------------------------------------- municipio


def test_el_municipio_viaja_con_nombre_y_sin_codigo():
    # A propósito. «Argelia» son tres municipios distintos —Antioquia (16
    # contratos), Cauca (16) y Valle del Cauca (15)—, con conteos casi
    # iguales: fundirlos no se vería raro en ningún reporte.
    antioquia = desde_contenido(contrato(departamento="Antioquia", ciudad="Argelia"))
    cauca = desde_contenido(contrato(departamento="Cauca", ciudad="Argelia"))

    assert antioquia.municipio_nombre == cauca.municipio_nombre == "ARGELIA"
    # Lo que los separa hoy es el departamento, que es la mitad de la llave
    # verdadera. La otra mitad —el código de municipio— es historia aparte.
    assert antioquia.departamento_codigo != cauca.departamento_codigo


def test_un_contrato_sin_ciudad_no_inventa_municipio():
    assert desde_contenido(contrato(ciudad=None)).municipio_nombre is None
    assert desde_contenido(contrato(ciudad="   ")).municipio_nombre is None


# ---------------------------------------------------------------- lectura


def test_una_fila_completa_se_lee_entera():
    territorio = desde_contenido({
        "orden": "Nacional",
        "departamento": "Valle del Cauca",
        "ciudad": "Cali",
    })

    assert territorio == Territorio(
        orden=ORDEN_NACIONAL,
        departamento_codigo="76",
        departamento_nombre="VALLE DEL CAUCA",
        municipio_nombre="CALI",
    )
    assert territorio.es_nacional
    assert not territorio.sin_departamento
    assert not territorio.sin_orden


def test_una_fila_vacia_no_revienta_ni_inventa():
    territorio = desde_contenido({})

    assert territorio.sin_orden
    assert territorio.sin_departamento
    assert territorio.municipio_nombre is None
