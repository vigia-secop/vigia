"""El conjunto de campos esperados por dataset, como dato versionado.

No se escribe a mano: se captura de la fuente y se revisa. Una lista inventada
produce faltantes falsos el primer día; una capturada hace que el `diff` de un
cambio de esquema sea legible en el control de versiones, con su fecha y su
procedencia.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

#: Los archivos capturados viven junto al código que los lee.
DIRECTORIO_ESPERADO = Path(__file__).parent / "esperado"


class EsquemaEsperadoAusente(FileNotFoundError):
    """No hay esquema utilizable para ese dataset.

    Cubre tanto el archivo que no existe como el que existe pero no se puede
    leer o no dice lo que debería. En los tres casos el Ciclo no arranca: sin
    referencia no hay nada contra qué comparar, y seguir de todos modos
    equivaldría a no tener validación.
    """


@dataclass(frozen=True)
class EsquemaEsperado:
    """Los campos que un dataset traía la última vez que alguien lo revisó."""

    dataset: str
    id_socrata: str
    capturado_en: date
    procedencia: str
    campos: frozenset[str]

    def __post_init__(self) -> None:
        if not self.campos:
            # Un esperado vacío no reporta ningún faltante: apagaría la
            # validación entera sin que nada lo delate.
            raise ValueError(
                f"el esquema esperado de {self.dataset!r} no declara ningún campo; "
                f"un esperado vacío desactiva la validación en silencio"
            )

    @classmethod
    def desde_archivo(cls, ruta: Path, *, dataset: str | None = None) -> EsquemaEsperado:
        if not ruta.is_file():
            raise EsquemaEsperadoAusente(
                f"no hay esquema esperado capturado en {ruta}; "
                f"captúralo con `python -m vigia.schema --capturar --dataset <nombre>` "
                f"y revisa el archivo antes de confiar en él"
            )
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            esquema = cls(
                dataset=datos["dataset"],
                id_socrata=datos["id_socrata"],
                capturado_en=date.fromisoformat(datos["capturado_en"]),
                procedencia=datos["procedencia"],
                campos=frozenset(datos["campos"]),
            )
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
            # El README pide revisar y versionar estos archivos a mano: un
            # archivo a medio editar es un caso esperable, no un imposible.
            raise EsquemaEsperadoAusente(
                f"el esquema esperado en {ruta} no se pudo leer: {error}. "
                f"Corrígelo o recaptúralo con "
                f"`python -m vigia.schema --capturar --dataset <nombre>`"
            ) from error

        if dataset is not None and esquema.dataset != dataset:
            raise EsquemaEsperadoAusente(
                f"el archivo {ruta} dice ser el esquema de {esquema.dataset!r} "
                f"y se pidió el de {dataset!r}"
            )
        return esquema

    @classmethod
    def para(cls, dataset: str, directorio: Path = DIRECTORIO_ESPERADO) -> EsquemaEsperado:
        return cls.desde_archivo(directorio / f"{dataset}.json", dataset=dataset)

    def escribir(self, directorio: Path = DIRECTORIO_ESPERADO) -> Path:
        """Escribe el archivo de forma atómica.

        Una escritura interrumpida dejaría truncado justo el archivo del que
        depende toda la validación, y el Ciclo siguiente no arrancaría.
        """
        directorio.mkdir(parents=True, exist_ok=True)
        ruta = directorio / f"{self.dataset}.json"
        # Campos ordenados y sangría fija: el archivo se lee en un `diff`, y un
        # orden inestable convertiría cada captura en un cambio ilegible.
        contenido = (
            json.dumps(
                {
                    "dataset": self.dataset,
                    "id_socrata": self.id_socrata,
                    "capturado_en": self.capturado_en.isoformat(),
                    "procedencia": self.procedencia,
                    "campos": sorted(self.campos),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        descriptor, temporal = tempfile.mkstemp(dir=directorio, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
                archivo.write(contenido)
            os.replace(temporal, ruta)
        except BaseException:
            Path(temporal).unlink(missing_ok=True)
            raise
        return ruta

    def diferencia(self, otro: EsquemaEsperado) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Campos que `otro` añade y campos que `otro` pierde frente a este."""
        return (
            tuple(sorted(otro.campos - self.campos)),
            tuple(sorted(self.campos - otro.campos)),
        )
