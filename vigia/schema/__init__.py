"""Definición de columnas de los datasets y validación de su forma.

Es también el lugar donde vivirán las marcas de sensibilidad de persona
natural (AD-6) cuando llegue su historia.
"""

from vigia.schema.definiciones import (
    DIRECTORIO_ESPERADO,
    EsquemaEsperado,
    EsquemaEsperadoAusente,
)
from vigia.schema.novedades import (
    Novedad,
    RepositorioNovedades,
    RepositorioNovedadesEnMemoria,
)
from vigia.schema.validacion import (
    EsquemaCambiado,
    ResultadoValidacion,
    ValidadorDeEsquema,
)

__all__ = [
    "DIRECTORIO_ESPERADO",
    "EsquemaCambiado",
    "EsquemaEsperado",
    "EsquemaEsperadoAusente",
    "Novedad",
    "RepositorioNovedades",
    "RepositorioNovedadesEnMemoria",
    "ResultadoValidacion",
    "ValidadorDeEsquema",
]
