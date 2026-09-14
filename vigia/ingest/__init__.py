"""Ingesta: consulta a la API del SECOP y escritura a la capa cruda."""

from vigia.ingest.ciclo import (
    RangoInvalido,
    ResumenCiclo,
    ejecutar_ciclo,
    fecha_de_hecho,
    filtro_por_rango,
    ingerir,
)
from vigia.ingest.datasets import CONTRATOS, DATASETS, PROCESOS, DatasetSecop
from vigia.ingest.estado import (
    EstadoCiclo,
    MarcaDeAgua,
    RegistroDeCiclo,
    RepositorioEstado,
    RepositorioEstadoEnMemoria,
)
from vigia.ingest.socrata import ClienteSocrata, ErrorFuente, Pagina

__all__ = [
    "CONTRATOS",
    "DATASETS",
    "PROCESOS",
    "ClienteSocrata",
    "DatasetSecop",
    "ErrorFuente",
    "EstadoCiclo",
    "MarcaDeAgua",
    "Pagina",
    "RangoInvalido",
    "RegistroDeCiclo",
    "RepositorioEstado",
    "RepositorioEstadoEnMemoria",
    "ResumenCiclo",
    "ejecutar_ciclo",
    "fecha_de_hecho",
    "filtro_por_rango",
    "ingerir",
]
