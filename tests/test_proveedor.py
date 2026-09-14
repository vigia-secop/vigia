"""Identidad canónica de Proveedor (historia 1.5).

Ninguna de estas pruebas sale a la red. Los casos salen de mediciones reales
sobre `jbjy-vk9h` hechas el 2026-09-04 y anotadas en `proveedor.py`.
"""

from __future__ import annotations

import pytest

from vigia.normalizado.proveedor import (
    DocumentoNoUtilizable,
    IdentidadProveedor,
    Proveedor,
    ResumenProveedores,
    TIPO_GRUPO_PROVISIONAL,
    agrupar,
    canonizar_documento,
    digito_de_verificacion,
    identidad_del_contrato,
)


def contrato(documento, tipo="NIT", nombre="ACME S.A.S."):
    return {
        "documento_proveedor": documento,
        "tipodocproveedor": tipo,
        "proveedor_adjudicado": nombre,
    }


# --------------------------------------------------------------- canonizar


@pytest.mark.parametrize(
    "escrito",
    ["900.123.456", "900-123-456", "900 123 456", "  900123456  ", "900.123-456"],
)
def test_puntos_guiones_y_espacios_dan_la_misma_forma(escrito):
    # Primer criterio de aceptación de la historia, literal.
    assert canonizar_documento(escrito, tipo="NIT").numero == "900123456"


def test_el_tipo_forma_parte_de_la_identidad():
    # Un NIT y una cédula con los mismos dígitos son dos entidades distintas.
    # Fundirlas inventaría una concentración que no existe.
    nit = canonizar_documento("900123456", tipo="NIT")
    cedula = canonizar_documento("900123456", tipo="Cédula de Ciudadanía")

    assert nit.numero == cedula.numero
    assert nit != cedula
    assert nit.clave != cedula.clave


def test_el_tipo_se_normaliza_sin_tildes_ni_mayusculas():
    uno = canonizar_documento("79123456", tipo="Cédula de Ciudadanía")
    otro = canonizar_documento("79123456", tipo="CEDULA DE CIUDADANIA")

    assert uno == otro


# ------------------------------------------------- el centinela «No Definido»


def test_no_definido_no_es_una_identidad():
    # 175 836 contratos del histórico nacional traen esta cadena literal.
    # Canonizarla produciría un único proveedor `NODEFINIDO` que aparecería
    # como el contratista más concentrado del país. Medido el 2026-09-04.
    with pytest.raises(DocumentoNoUtilizable, match="centinela"):
        canonizar_documento("No Definido", tipo="NIT")


@pytest.mark.parametrize("centinela", ["N/A", "NO APLICA", "SIN DOCUMENTO", "---", "  "])
def test_cualquier_texto_sin_digitos_se_rechaza(centinela):
    # La regla es «sin un solo dígito no es un documento», no una lista de
    # centinelas conocidos: una lista siempre se queda corta.
    with pytest.raises(DocumentoNoUtilizable):
        canonizar_documento(centinela, tipo="NIT")


def test_un_documento_ausente_o_de_otro_tipo_se_rechaza():
    for valor in (None, 900123456, ["900123456"]):
        with pytest.raises(DocumentoNoUtilizable):
            canonizar_documento(valor, tipo="NIT")


def test_las_uniones_temporales_no_se_funden_entre_si():
    # El caso real: seis UT y consorcios distintos, todos con documento
    # «No Definido». Lo que NO puede pasar, pase lo que pase, es que los seis
    # terminen siendo un solo proveedor gigante llamado NODEFINIDO.
    filas = [
        contrato("No Definido", nombre=n)
        for n in ("UT NUTRIENDO EL PAE 2026", "UT NOC 2022", "CONSORCIO INTER-IPES",
                  "Consorcio M.S 2024", "UT INTER SALUD LA LOMA 2023", "UT CONDEMEC")
    ]

    proveedores, resumen = agrupar(filas)

    # Sin la marca `es_grupo` la fuente no dice que sean uniones, y sin decirlo
    # no se les inventa identidad: podrían ser cualquier cosa.
    assert proveedores == {}
    assert resumen.sin_documento_utilizable == 6
    assert resumen.proveedores == 0


# ------------------------------------------------ dígito de verificación


# Documentos REALES de tipo NIT y diez dígitos, tomados de `jbjy-vk9h` el
# 2026-09-04. Los 16 de la muestra que empiezan por 8 o 9 verificaron su
# dígito; ninguno se eligió por cuadrar. Si alguien invierte la tabla de pesos
# —el error que tuvo la primera versión— estas tres se caen.
@pytest.mark.parametrize(
    "documento",
    ["8050200844", "8911014508", "9015833598", "8909809583", "8600001893", "9001841446"],
)
def test_el_digito_de_verificacion_cuadra_con_nits_reales(documento):
    assert digito_de_verificacion(documento[:9]) == int(documento[9])


def test_una_cedula_de_diez_digitos_etiquetada_como_nit_no_pierde_su_ultimo_digito():
    # `1051676908` es uno de los nueve documentos de la muestra que empiezan
    # por 1 y que la fuente etiqueta «NIT». Ocho de esos nueve NO verifican el
    # DV: son cédulas enteras, no NIT con dígito. A este le cuadra por azar
    # —una de cada once— y aun así no se le toca, porque el rango manda.
    assert canonizar_documento("1051676908", tipo="NIT").numero == "1051676908"


def test_a_un_nit_con_su_dv_se_le_quita_el_dv():
    # `8600001893` sale de la fuente: 860000189 es el NIT y 3 su dígito.
    con_dv = canonizar_documento("860000189-3", tipo="NIT")
    sin_dv = canonizar_documento("860000189", tipo="NIT")

    assert con_dv == sin_dv
    assert con_dv.numero == "860000189"


def test_a_una_cedula_de_diez_digitos_no_se_le_toca_nada():
    # La regla del DV es SOLO para NIT. Con tipo cédula no se toca ni aunque
    # el número esté en el rango de los NIT y el dígito cuadre.
    cedula = canonizar_documento("8600001893", tipo="Cédula de Ciudadanía")

    assert cedula.numero == "8600001893"


def test_un_nit_de_diez_digitos_que_no_verifica_se_deja_entero():
    assert canonizar_documento("8600001890", tipo="NIT").numero == "8600001890"


def test_el_dv_de_algo_que_no_son_digitos_es_desconocido():
    assert digito_de_verificacion("ABC") is None
    assert digito_de_verificacion("") is None


# ------------------------------------------------------ variantes de nombre


def test_un_mismo_documento_con_tres_nombres_es_un_solo_proveedor():
    # Segundo criterio de aceptación: una sola identidad, Y las variantes
    # registradas y consultables.
    filas = [
        contrato("900123456", nombre="CONSTRUCTORA ANDINA S.A.S."),
        contrato("900.123.456", nombre="Constructora Andina SAS"),
        contrato("900123456", nombre="CONSTRUCTORA ANDINA S.A.S."),
    ]

    proveedores, resumen = agrupar(filas)

    assert resumen.proveedores == 1
    proveedor = next(iter(proveedores.values()))
    assert proveedor.contratos == 3
    assert proveedor.cuantas_variantes == 2
    assert resumen.con_varias_variantes == 1


def test_el_nombre_principal_es_el_mas_frecuente():
    proveedor = Proveedor(identidad=IdentidadProveedor("NIT", "900123456"))
    for nombre in ("ACME SAS", "ACME S.A.S.", "ACME SAS"):
        proveedor.registrar(nombre)

    assert proveedor.nombre_principal == "ACME SAS"


def test_el_empate_se_rompe_siempre_igual():
    # Si el nombre mostrado cambiara entre dos corridas sobre los mismos
    # datos, ningún reporte sería reproducible.
    uno = Proveedor(identidad=IdentidadProveedor("NIT", "1"))
    otro = Proveedor(identidad=IdentidadProveedor("NIT", "1"))
    for nombre in ("ZETA", "ALFA"):
        uno.registrar(nombre)
    for nombre in ("ALFA", "ZETA"):
        otro.registrar(nombre)

    assert uno.nombre_principal == otro.nombre_principal == "ALFA"


def test_un_contrato_sin_nombre_cuenta_igual_pero_no_inventa_variante():
    proveedor = Proveedor(identidad=IdentidadProveedor("NIT", "1"))
    proveedor.registrar(None)
    proveedor.registrar("   ")

    assert proveedor.contratos == 2
    assert proveedor.cuantas_variantes == 0
    assert proveedor.nombre_principal is None


# ----------------------------------------------------------------- resumen


def test_el_resumen_no_se_puede_construir_si_las_cuentas_no_cuadran():
    with pytest.raises(ValueError, match="incoherentes"):
        ResumenProveedores(
            contratos_leidos=10, contratos_agrupados=5,
            sin_documento_utilizable=3, proveedores=5, con_varias_variantes=0,
        )


def test_agrupar_no_puede_crear_mas_proveedores_que_contratos():
    with pytest.raises(ValueError, match="agrupar no puede crear"):
        ResumenProveedores(
            contratos_leidos=2, contratos_agrupados=2,
            sin_documento_utilizable=0, proveedores=3, con_varias_variantes=0,
        )


def test_sin_contratos_la_proporcion_es_desconocida_no_cero():
    _, resumen = agrupar([])

    assert resumen.contratos_leidos == 0
    assert resumen.proporcion_sin_documento is None


def test_la_mezcla_real_se_cuenta_entera():
    # Proporciones parecidas a las medidas: mayoría personas naturales, unos
    # pocos NIT, y un puñado sin documento utilizable.
    filas = (
        [contrato(f"7912345{i}", tipo="Cédula de Ciudadanía", nombre=f"PERSONA {i}") for i in range(8)]
        + [contrato("900123456", nombre="ACME"), contrato("900.123.456", nombre="Acme SAS")]
        + [contrato("No Definido", nombre="UT ALGO")]
    )

    proveedores, resumen = agrupar(filas)

    assert resumen.contratos_leidos == 11
    assert resumen.contratos_agrupados == 10
    assert resumen.sin_documento_utilizable == 1
    assert resumen.proveedores == 9
    assert round(resumen.proporcion_sin_documento, 4) == round(1 / 11, 4)


# ------------------------------------------- uniones temporales y consorcios
#
# LO QUE ESTE BLOQUE PROTEGE. Medido el 2026-09-04: de los 175 836 contratos
# con documento «No Definido», 160 543 son borradores y cancelados —papeles que
# nunca adjudicaron a nadie— y 15 293 son contratos de verdad, de los cuales
# 15 291 (el 99,99 %) vienen marcados `es_grupo = 'Si'`. Ese último grupo es el
# hueco real de vigilancia, y no puede quedarse invisible.


def grupo(nombre, id_contrato, documento="No Definido", es_grupo="Si"):
    return {
        "documento_proveedor": documento,
        "tipodocproveedor": "No Definido",
        "proveedor_adjudicado": nombre,
        "es_grupo": es_grupo,
        "id_contrato": id_contrato,
    }


def test_una_union_temporal_sin_documento_recibe_identidad_provisional():
    identidad = identidad_del_contrato(grupo("UT PAE 2026", "CO1.PCCNTR.111"))

    assert identidad.provisional
    assert identidad.tipo == TIPO_GRUPO_PROVISIONAL
    assert identidad.numero == "CO1.PCCNTR.111"


def test_dos_uniones_distintas_no_se_funden_aunque_no_tengan_documento():
    # El error que este diseño existe para no cometer: seis uniones distintas
    # convertidas en el contratista más concentrado de Colombia.
    filas = [
        grupo(n, f"CO1.PCCNTR.{i}")
        for i, n in enumerate(
            ("UT NUTRIENDO EL PAE 2026", "UT NOC 2022", "CONSORCIO INTER-IPES",
             "Consorcio M.S 2024", "UT INTER SALUD LA LOMA 2023", "UT CONDEMEC")
        )
    ]

    proveedores, resumen = agrupar(filas)

    assert resumen.proveedores == 6
    assert resumen.contratos_provisionales == 6
    assert resumen.proveedores_provisionales == 6
    assert all(p.contratos == 1 for p in proveedores.values())
    # y sobre todo: ninguno se quedó fuera del conteo
    assert resumen.sin_documento_utilizable == 0


def test_dos_uniones_con_el_mismo_nombre_siguen_siendo_dos():
    # El nombre lo teclea cada entidad y no es único en el país. Agrupar por
    # nombre inventaría una concentración; la identidad va por contrato.
    proveedores, resumen = agrupar(
        [grupo("UNION TEMPORAL SALUD 2024", "CO1.PCCNTR.1"),
         grupo("UNION TEMPORAL SALUD 2024", "CO1.PCCNTR.2")]
    )

    assert resumen.proveedores == 2
    assert resumen.proveedores_provisionales == 2


def test_una_identidad_provisional_no_puede_concentrar_nada():
    # Por construcción: tantas identidades como contratos.
    filas = [grupo(f"UT {i}", f"CO1.PCCNTR.{i}") for i in range(50)]

    _, resumen = agrupar(filas)

    assert resumen.proveedores_provisionales == resumen.contratos_provisionales


def test_un_borrador_sin_grupo_sigue_sin_identidad():
    # Son 160 543 en el histórico. No tienen proveedor porque nunca lo tuvieron:
    # inventárselo sería peor que dejarlos fuera.
    with pytest.raises(DocumentoNoUtilizable):
        identidad_del_contrato(grupo("Sin Descripcion", "CO1.PCCNTR.9", es_grupo="No"))


def test_una_union_temporal_CON_nit_se_agrupa_de_verdad():
    # 25 866 de los 39 767 contratos de grupo sí traen NIT. Esos no son un
    # hueco: se agrupan como cualquier otro proveedor, y no son provisionales.
    filas = [
        {**grupo("UT VIAS DEL SUR", "CO1.PCCNTR.1", documento="900123456"),
         "tipodocproveedor": "NIT"},
        {**grupo("U.T. Vías del Sur", "CO1.PCCNTR.2", documento="900.123.456"),
         "tipodocproveedor": "NIT"},
    ]

    proveedores, resumen = agrupar(filas)

    assert resumen.proveedores == 1
    assert resumen.contratos_provisionales == 0
    unico = next(iter(proveedores.values()))
    assert not unico.provisional
    assert unico.contratos == 2


def test_el_que_no_trae_id_contrato_no_recibe_identidad_inventada():
    sin_id = grupo("UT SIN NUMERO", "CO1.PCCNTR.1")
    del sin_id["id_contrato"]

    with pytest.raises(DocumentoNoUtilizable):
        identidad_del_contrato(sin_id)


def test_lo_que_no_se_puede_vigilar_suma_los_dos_huecos():
    filas = (
        [contrato("900123456")]                                   # identidad real
        + [grupo("UT A", "CO1.PCCNTR.1")]                          # provisional
        + [grupo("Sin Descripcion", "CO1.PCCNTR.2", es_grupo="No")]  # sin identidad
    )

    _, resumen = agrupar(filas)

    assert resumen.contratos_con_identidad_real == 1
    assert round(resumen.proporcion_fuera_de_concentracion, 4) == round(2 / 3, 4)


def test_un_resumen_con_mas_identidades_provisionales_que_contratos_se_rechaza():
    with pytest.raises(ValueError, match="cada una lleva el número de su contrato"):
        ResumenProveedores(
            contratos_leidos=2, contratos_agrupados=2,
            sin_documento_utilizable=0, proveedores=2, con_varias_variantes=0,
            contratos_provisionales=1, proveedores_provisionales=2,
        )


# ----------------------------- el centinela de ceros (lo encontro el Panel) --


@pytest.mark.parametrize(
    "centinela", ["000000000", "0", "00", "11111111", "999999999", "0-0-0"]
)
def test_un_documento_de_un_solo_digito_repetido_no_es_una_identidad(centinela):
    # La regla anterior -«que tenga al menos un digito»- los dejaba pasar.
    # Medido en la base real el 2026-09-05: `000000000` habia fundido TRES
    # consorcios distintos en un solo proveedor con tres razones sociales.
    with pytest.raises(DocumentoNoUtilizable, match="repetido"):
        canonizar_documento(centinela, tipo="NIT")


def test_tres_consorcios_con_ceros_no_se_funden_en_uno():
    # El caso exacto que salio en la ventana real.
    filas = [
        grupo("CONSORCIO INTER CANCHA UNION", "CO1.PCCNTR.1", documento="000000000"),
        grupo("CONSORCIO OTRO 2026", "CO1.PCCNTR.2", documento="000000000"),
        grupo("UT TERCERA", "CO1.PCCNTR.3", documento="0"),
    ]

    proveedores, resumen = agrupar(filas)

    assert resumen.proveedores == 3
    assert resumen.proveedores_provisionales == 3
    assert all(p.contratos == 1 for p in proveedores.values())


def test_un_documento_de_ceros_sin_grupo_se_queda_sin_identidad():
    with pytest.raises(DocumentoNoUtilizable):
        identidad_del_contrato(
            grupo("QUIEN SABE", "CO1.PCCNTR.9", documento="000000000", es_grupo="No")
        )
