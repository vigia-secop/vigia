"""Códigos DIVIPOLA de municipio (historia 1.9).

Ninguna prueba sale a la red ni depende de la tabla real capturada: se usa
una fixture con los casos que importan. Si la tabla real está presente, la
última prueba comprueba sus invariantes contra lo medido el 2026-09-05.
"""

from __future__ import annotations

import pytest

from vigia.normalizado.divipola import (
    RUTA_TABLA,
    Municipio,
    TablaDeMunicipios,
    TablaDeMunicipiosNoDisponible,
    leer_tabla,
)

# Los tres «Argelia» reales, más vecinos para que la fixture no sea trivial.
MUESTRA = [
    Municipio("05055", "ARGELIA"),
    Municipio("19050", "ARGELIA"),
    Municipio("76054", "ARGELIA"),
    Municipio("05001", "MEDELLÍN"),
    Municipio("19001", "POPAYÁN"),
    Municipio("11001", "BOGOTÁ, D.C."),
]


@pytest.fixture
def tabla():
    return TablaDeMunicipios(MUESTRA)


def test_el_mismo_nombre_en_departamentos_distintos_da_codigos_distintos(tabla):
    # El fallo que esta historia existe para evitar.
    antioquia = tabla.codigo(departamento="05", municipio="Argelia")
    cauca = tabla.codigo(departamento="19", municipio="Argelia")
    valle = tabla.codigo(departamento="76", municipio="Argelia")

    assert (antioquia, cauca, valle) == ("05055", "19050", "76054")
    assert len({antioquia, cauca, valle}) == 3


def test_sin_departamento_no_se_responde_aunque_el_nombre_sea_unico(tabla):
    # «MEDELLIN» es único en el país, pero la regla es una sola: el municipio
    # se identifica por el par. Una excepción «solo cuando no hay ambigüedad»
    # se vuelve ambigua el día que la fuente añada otro con ese nombre.
    assert tabla.codigo(departamento=None, municipio="Medellín") is None
    assert tabla.codigo(departamento="05", municipio="Medellín") == "05001"


def test_el_nombre_se_normaliza_sin_tildes_ni_mayusculas(tabla):
    assert tabla.codigo(departamento="19", municipio="popayan") == "19001"
    assert tabla.codigo(departamento="19", municipio="  POPAYÁN  ") == "19001"


def test_un_municipio_que_no_esta_no_recibe_codigo_inventado(tabla):
    assert tabla.codigo(departamento="05", municipio="Ciudad Gótica") is None
    # Y el par importa: Argelia existe, pero no en Boyacá.
    assert tabla.codigo(departamento="15", municipio="Argelia") is None


def test_el_centinela_no_definido_no_recibe_codigo(tabla):
    # MEDIDO EN LA BASE REAL (2026-09-05): «NO DEFINIDO» aparece como nombre
    # de municipio en 28 departamentos distintos. Es un centinela, igual que
    # el «No Definido» del documento de proveedor. Codificarlo por el nombre
    # habria creado un municipio fantasma con contratos de medio pais.
    for departamento in ("05", "19", "76"):
        assert tabla.codigo(departamento=departamento, municipio="No Definido") is None


def test_un_municipio_sin_nombre_no_recibe_codigo(tabla):
    assert tabla.codigo(departamento="05", municipio=None) is None
    assert tabla.codigo(departamento="05", municipio="   ") is None


def test_se_cuentan_los_nombres_repetidos_entre_departamentos(tabla):
    # En la fixture solo «ARGELIA» se repite.
    assert tabla.nombres_repetidos_entre_departamentos == 1


def test_dos_municipios_con_el_mismo_nombre_en_un_departamento_se_denuncian():
    # No debería existir. Si existiera, ni el par serviría de llave, y hay que
    # saberlo antes de codificar nada, no después.
    rota = TablaDeMunicipios([Municipio("05055", "ARGELIA"), Municipio("05056", "Argelia")])

    assert rota.colisiones_dentro_del_mismo_departamento == [("05", "ARGELIA")]


# ---------------------------------------------------------- carga del archivo


def _escribir(tmp_path, filas):
    ruta = tmp_path / "divipola_municipios.csv"
    ruta.write_text(
        "codigo,nombre\n" + "\n".join(f"{c},{n}" for c, n in filas),
        encoding="utf-8",
    )
    return ruta


def test_un_nombre_con_coma_sobrevive_al_csv(tmp_path):
    # DIVIPOLA llama al municipio 11001 «BOGOTA, D.C.», CON coma. La primera
    # version del capturador daba por hecho que ningun municipio traia coma y
    # abortaba; abortó en la primera corrida, contra Bogota. El nombre va
    # citado, y esta prueba lo fija.
    ruta = tmp_path / "divipola_municipios.csv"
    # Relleno para llegar al tamano esperado, con prefijos de departamento
    # que existen y sin chocar con los dos codigos de arriba.
    filas = [f"05{i:03d},MUNICIPIO A{i}" for i in range(56, 1000)]
    filas += [f"08{i:03d},MUNICIPIO B{i}" for i in range(1, 177)]
    ruta.write_text(
        'codigo,nombre\n11001,"BOGOTA, D.C."\n05055,ARGELIA\n' + "\n".join(filas),
        encoding="utf-8",
    )

    tabla = leer_tabla(ruta)

    assert tabla.codigo(departamento="11", municipio="Bogotá, D.C.") == "11001"


def test_sin_tabla_capturada_se_avisa_en_vez_de_devolver_vacio(tmp_path):
    # Un municipio sin código porque la tabla no está NO es lo mismo que uno
    # que la fuente no supo decir. Confundirlos esconde una avería.
    with pytest.raises(TablaDeMunicipiosNoDisponible, match="capturar-divipola"):
        leer_tabla(tmp_path / "no-existe.csv")


def test_una_captura_truncada_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, [("05001", "MEDELLIN"), ("19001", "POPAYAN")])

    with pytest.raises(TablaDeMunicipiosNoDisponible, match="se esperaban"):
        leer_tabla(ruta)


def test_un_codigo_que_no_es_de_cinco_digitos_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path, [("5001", "MEDELLIN")])

    with pytest.raises(TablaDeMunicipiosNoDisponible, match="cinco d"):
        leer_tabla(ruta)


def test_un_municipio_de_un_departamento_inexistente_se_rechaza(tmp_path):
    # Si el prefijo no está en la tabla de la 1.6, una de las dos está mal, y
    # callarlo dejaría municipios colgando de un departamento que no existe.
    ruta = _escribir(tmp_path, [("00001", "NINGUNA PARTE")])

    with pytest.raises(TablaDeMunicipiosNoDisponible, match="no está en la tabla"):
        leer_tabla(ruta)


@pytest.mark.skipif(not RUTA_TABLA.exists(), reason="la tabla aún no se ha capturado")
def test_la_tabla_real_cuadra_con_lo_medido():
    # Medido contra la tabla capturada el 2026-09-05: 1 122 municipios y
    # 1 037 nombres distintos. Los nombres COMPARTIDOS son 66 tal como los
    # escribe el DANE y 67 al normalizar -CHIMÁ (Córdoba) y CHIMA (Santander)
    # solo chocan al quitar la tilde-.
    #
    # NO son 85. Esa resta (1 122 - 1 037) cuenta filas sobrantes, no nombres:
    # un nombre repetido cuatro veces aporta 3 a la resta y 1 aquí. Esta
    # prueba se escribió con el 85 inferido y la tabla real la tumbó.
    tabla = leer_tabla(RUTA_TABLA)

    assert len(tabla) == 1122
    assert tabla.nombres_repetidos_entre_departamentos == 67
    assert tabla.colisiones_dentro_del_mismo_departamento == []
    assert tabla.codigo(departamento="05", municipio="Argelia") == "05055"
    assert tabla.codigo(departamento="19", municipio="Argelia") == "19050"
    assert tabla.codigo(departamento="76", municipio="Argelia") == "76054"
    # Los dos que solo se distinguen por la tilde, cada uno en su sitio.
    assert tabla.codigo(departamento="23", municipio="Chimá") == "23168"
    assert tabla.codigo(departamento="68", municipio="Chima") == "68176"
