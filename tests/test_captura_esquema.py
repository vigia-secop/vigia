"""Captura del esquema esperado por línea de comandos.

Es la pieza de la que depende la confianza en toda la validación: si escribe
mal, la alarma queda calibrada contra algo que nadie verificó.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from tests.conftest import CAMPOS_CONTRATOS, FuenteFalsa
from vigia.schema import __main__ as captura
from vigia.schema.definiciones import EsquemaEsperado
from vigia.tiempo import hoy_en_colombia


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for variable in ("VIGIA_DOMINIO_SOCRATA", "VIGIA_TOKEN_SOCRATA"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("VIGIA_DOMINIO_SOCRATA", "https://fuente.falsa")


@pytest.fixture
def fuente(monkeypatch):
    def instalar(**opciones):
        doble = FuenteFalsa([], **opciones)
        monkeypatch.setattr(
            captura,
            "crear_cliente_http",
            lambda **_: httpx.Client(transport=httpx.MockTransport(doble)),
        )
        return doble

    return instalar


def test_la_captura_escribe_el_esquema_declarado(fuente, tmp_path: Path, capsys):
    fuente(columnas=CAMPOS_CONTRATOS)

    # Se compara contra el MISMO reloj que usa el código —hora de Colombia—, no
    # contra `date.today()`, que es la del sistema: en una máquina en UTC las
    # dos coinciden y el error se vuelve invisible. Y se acota entre antes y
    # después para que cruzar la medianoche no vuelva la prueba intermitente.
    antes = hoy_en_colombia()
    codigo = captura.main(
        ["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)]
    )
    despues = hoy_en_colombia()

    assert codigo == 0
    escrito = EsquemaEsperado.para("contratos", tmp_path)
    assert escrito.campos == frozenset(CAMPOS_CONTRATOS)
    assert escrito.id_socrata == "jbjy-vk9h"
    assert escrito.capturado_en in {antes, despues}
    assert escrito.procedencia == "https://fuente.falsa/api/views/jbjy-vk9h.json"
    assert "primera captura" in capsys.readouterr().out


def test_la_captura_dice_qué_campos_entran_y_cuáles_salen(fuente, tmp_path: Path, capsys):
    fuente(columnas=CAMPOS_CONTRATOS)
    captura.main(["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)])

    fuente(columnas=(CAMPOS_CONTRATOS - {"valor_del_contrato"}) | {"valor_reintegro"})
    codigo = captura.main(
        ["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)]
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "entran (1): valor_reintegro" in salida
    assert "SALEN (1): valor_del_contrato" in salida
    # Recapturar un campo que desapareció es como se apaga esta alarma sin querer.
    assert "antes de versionar" in salida


def test_una_recaptura_sin_cambios_lo_dice(fuente, tmp_path: Path, capsys):
    fuente(columnas=CAMPOS_CONTRATOS)
    captura.main(["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)])

    fuente(columnas=CAMPOS_CONTRATOS)
    captura.main(["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)])

    assert "Sin cambios" in capsys.readouterr().out


def test_una_fuente_caida_no_toca_el_archivo_existente(fuente, tmp_path: Path, capsys):
    fuente(columnas=CAMPOS_CONTRATOS)
    captura.main(["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)])
    antes = (tmp_path / "contratos.json").read_text(encoding="utf-8")

    fuente(fallo_metadatos=503)
    codigo = captura.main(
        ["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)]
    )

    assert codigo == 1
    assert "503" in capsys.readouterr().err
    assert (tmp_path / "contratos.json").read_text(encoding="utf-8") == antes


@pytest.mark.skipif(
    # `os.name` primero: Python corta el `or` y nunca evalúa `geteuid`, que no
    # existe en Windows. Sin ese orden, el módulo entero no se puede importar
    # allá y se pierden TODAS sus pruebas, no solo esta.
    os.name != "posix" or os.geteuid() == 0,
    reason=(
        "el permiso de solo lectura de un directorio solo se comporta así en "
        "POSIX, y root lo ignora"
    ),
)
def test_un_directorio_no_escribible_termina_en_error(fuente, tmp_path: Path, capsys):
    fuente(columnas=CAMPOS_CONTRATOS)
    bloqueado = tmp_path / "solo-lectura"
    bloqueado.mkdir()
    bloqueado.chmod(0o500)

    try:
        codigo = captura.main(
            ["--capturar", "--dataset", "contratos", "--directorio", str(bloqueado)]
        )
    finally:
        bloqueado.chmod(0o700)

    assert codigo == 1
    assert "no se pudo escribir" in capsys.readouterr().err


def test_el_archivo_escrito_es_json_ordenado(fuente, tmp_path: Path):
    fuente(columnas={"zeta", "alfa", "medio"})

    captura.main(["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)])

    datos = json.loads((tmp_path / "contratos.json").read_text(encoding="utf-8"))
    assert datos["campos"] == ["alfa", "medio", "zeta"]


def test_una_captura_sin_campos_no_se_escribe(fuente, tmp_path: Path, capsys):
    # `columnas()` ya rechaza unos metadatos sin campos; esto fija que la
    # captura no puede producir un esperado vacío, que desactivaría todo.
    fuente(columnas=[])

    codigo = captura.main(
        ["--capturar", "--dataset", "contratos", "--directorio", str(tmp_path)]
    )

    assert codigo == 1
    assert not (tmp_path / "contratos.json").exists()
