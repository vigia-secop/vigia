"""El Panel: que no parezca que se contradice cuando no se contradice."""

from vigia.panel import _cobertura


def _datos(publicados: int, en_cobertura: int) -> dict:
    return {
        "ventana": {"contratos": publicados, "valor": 42_842_232_358_747},
        "cobertura": {
            "contratos": en_cobertura,
            "con_proveedor_real": 337_104,
            "union_temporal_sin_documento": 1_521,
            "sin_identidad_de_proveedor": 29,
            "valor_union_temporal": 12_070_000_000_000,
            "enlazados_a_proceso": 321_645,
            "huerfanos": 17_009,
            "sin_departamento": 6_061,
        },
    }


def test_cuando_los_dos_totales_difieren_la_pagina_lo_explica():
    """Lo que un analista ve en diez segundos y nadie le explica.

    El 2026-10-15 la cabecera del Panel decia «338.651 contratos» y la
    seccion de cobertura, cuatro parrafos mas abajo, «de 338.654». La
    diferencia son las tres erratas de un cero de mas: se apartan de toda
    suma de valor y siguen siendo contratos publicados. Es correcto, y leido
    con lupa parece un error de cuentas.
    """
    html = _cobertura(_datos(publicados=338_651, en_cobertura=338_654))

    assert "338.654" in html and "338.651" in html
    assert "cero de más" in html
    assert "fuera de toda suma de valor" in html


def test_cuando_coinciden_no_se_dice_nada():
    # Una nota permanente que casi siempre sobra es decorado, y el decorado
    # le quita peso a lo que si importa.
    html = _cobertura(_datos(publicados=338_654, en_cobertura=338_654))

    assert "fuera de toda suma de valor" not in html


def test_sin_dato_de_ventana_la_pagina_se_dibuja_igual():
    # El JSON lo produce panel.sql; si algun dia deja de traer el total de la
    # ventana, el Panel sale sin la nota y no se cae.
    datos = _datos(publicados=338_651, en_cobertura=338_654)
    datos["ventana"].pop("contratos")

    html = _cobertura(datos)

    assert "Concentración por proveedor" in html
