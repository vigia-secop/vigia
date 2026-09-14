"""Construcción del cliente HTTP hacia la fuente."""

from __future__ import annotations

import pytest

from vigia.ingest.socrata import ESPERA_POR_DEFECTO, crear_cliente_http


def test_el_token_viaja_en_la_cabecera_de_socrata():
    with crear_cliente_http(token="abc123") as cliente:
        assert cliente.headers["X-App-Token"] == "abc123"


def test_sin_token_no_se_manda_la_cabecera():
    with crear_cliente_http() as cliente:
        assert "X-App-Token" not in cliente.headers


def test_no_sigue_redirecciones_para_no_filtrar_el_token():
    # httpx conserva las cabeceras propias al redirigir a otro host, así que
    # seguir redirecciones entregaría la credencial de Socrata a un tercero.
    with crear_cliente_http(token="abc123") as cliente:
        assert cliente.follow_redirects is False


def test_la_espera_por_defecto_no_es_la_de_httpx():
    # La de httpx son 5 segundos: insuficiente para una página de 50.000 filas.
    with crear_cliente_http() as cliente:
        assert cliente.timeout.read == ESPERA_POR_DEFECTO


def test_una_espera_no_positiva_se_rechaza():
    with pytest.raises(ValueError, match="espera"):
        crear_cliente_http(espera=0)
