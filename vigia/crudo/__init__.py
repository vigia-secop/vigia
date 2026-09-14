"""Capa cruda: la respuesta de la fuente tal como llegó, nunca modificada."""

from vigia.crudo.memoria import RepositorioEnMemoria, RepositorioNulo
from vigia.crudo.modelo import (
    CAMPO_ID_FUENTE,
    ContenidoNoSerializable,
    RegistroCrudo,
    RegistroSinIdentidad,
    hash_contenido,
)
from vigia.crudo.repositorio import ErrorAlmacen, RepositorioCrudo, ResultadoGuardado

__all__ = [
    "CAMPO_ID_FUENTE",
    "ContenidoNoSerializable",
    "ErrorAlmacen",
    "RegistroCrudo",
    "RegistroSinIdentidad",
    "RepositorioCrudo",
    "RepositorioEnMemoria",
    "RepositorioNulo",
    "ResultadoGuardado",
    "hash_contenido",
]
