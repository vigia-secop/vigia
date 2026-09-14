"""Campos que la fuente empezó a traer y que nadie ha revisado todavía."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence


@dataclass(frozen=True)
class Novedad:
    """Un campo declarado por la fuente que no está en el esquema esperado."""

    dataset: str
    campo: str
    detectado_en: datetime

    def __post_init__(self) -> None:
        if self.detectado_en.tzinfo is None:
            raise ValueError(
                f"detectado_en debe traer zona horaria; se recibió {self.detectado_en!r}"
            )
        object.__setattr__(self, "detectado_en", self.detectado_en.astimezone(timezone.utc))

    @property
    def llave(self) -> tuple[str, str]:
        return (self.dataset, self.campo)


class RepositorioNovedades(Protocol):
    """Registro de novedades de esquema.

    Conserva la primera detección de cada campo y actualiza la última. La
    primera responde «desde cuándo la fuente trae esto»; la última, «sigue
    trayéndolo».
    """

    def registrar(self, novedades: Sequence[Novedad]) -> None:
        ...


class RepositorioNovedadesEnMemoria:
    """Registro en memoria, para pruebas y corridas en seco."""

    def __init__(self) -> None:
        self._primera: dict[tuple[str, str], datetime] = {}
        self._ultima: dict[tuple[str, str], datetime] = {}

    def registrar(self, novedades: Sequence[Novedad]) -> None:
        for novedad in novedades:
            llave = novedad.llave
            self._primera.setdefault(llave, novedad.detectado_en)
            self._ultima[llave] = max(
                novedad.detectado_en, self._ultima.get(llave, novedad.detectado_en)
            )

    def __len__(self) -> int:
        return len(self._primera)

    def registradas(self) -> dict[tuple[str, str], tuple[datetime, datetime]]:
        return {
            llave: (self._primera[llave], self._ultima[llave]) for llave in self._primera
        }
