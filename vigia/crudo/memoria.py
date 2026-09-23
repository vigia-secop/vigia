"""Almacenes sin base de datos: uno que retiene y otro que solo cuenta.

`RepositorioEnMemoria` existe para que la suite de pruebas ejercite el Ciclo
completo sin infraestructura. Su semántica de conflicto debe seguir siendo
idéntica a la de `vigia.crudo.postgres`; si una de las dos cambia, la otra deja
de ser un doble válido, y `test_postgres_y_memoria_cuentan_igual` lo vigila.

`RepositorioNulo` es para las corridas en seco: recorre sin retener nada, para
que ver qué traería un rango amplio no cueste la memoria de traerlo.
"""

from __future__ import annotations

from typing import Sequence

from vigia.crudo.modelo import RegistroCrudo
from vigia.crudo.repositorio import ResultadoGuardado


class RepositorioEnMemoria:
    """Almacén de solo inserción respaldado por un diccionario."""

    def __init__(self) -> None:
        self._registros: dict[tuple[str, str, str], RegistroCrudo] = {}
        #: (dataset, id_fila_fuente) de todo lo guardado, en cualquier versión.
        #: Es lo que responde «¿esta identidad ya existía?» sin recorrer todo.
        self._identidades: set[tuple[str, str]] = set()

    def guardar_pagina(self, registros: Sequence[RegistroCrudo]) -> ResultadoGuardado:
        insertados = 0
        duplicados = 0
        # Se fotografía ANTES de insertar, como en Postgres: lo que entra en
        # esta página no puede contarse a sí mismo como «ya estaba».
        ya_existian = set(self._identidades)
        nuevos: dict[tuple[str, str, str], RegistroCrudo] = {}
        for registro in registros:
            llave = registro.llave
            if llave in self._registros or llave in nuevos:
                duplicados += 1
                continue
            nuevos[llave] = registro
            insertados += 1
        # La página entra completa: nada se publica hasta terminar de recorrerla.
        self._registros.update(nuevos)
        self._identidades.update(llave[:2] for llave in nuevos)
        return ResultadoGuardado(
            insertados=insertados,
            duplicados=duplicados,
            insertadas=frozenset(llave[1:] for llave in nuevos),
            ids_nuevos=frozenset(
                llave[1] for llave in nuevos if llave[:2] not in ya_existian
            ),
        )

    def __len__(self) -> int:
        return len(self._registros)

    @property
    def registros(self) -> tuple[RegistroCrudo, ...]:
        """Lo almacenado, en orden de inserción."""
        return tuple(self._registros.values())


class RepositorioNulo:
    """Descarta todo lo que recibe y solo lleva la cuenta.

    No puede decir cuántos registros serían nuevos: eso solo lo sabe la base
    contra la que se compara, y en seco no hay ninguna. Así que no lo finge —
    informa **cero insertados**, que es la única afirmación segura sobre un
    almacén que no escribe— y deja el resto en `duplicados` para que los
    conteos del Ciclo cuadren. El único número con significado aquí es
    `vistos`, y es el único que la corrida en seco imprime.

    Como consecuencia, en seco tampoco pueden encenderse las señales que se
    calculan sobre lo insertado: ventana corta, recuperados y sin fecha de
    hecho salen siempre en cero. La corrida en seco lo dice.
    """

    def __init__(self) -> None:
        self.vistos = 0

    def guardar_pagina(self, registros: Sequence[RegistroCrudo]) -> ResultadoGuardado:
        self.vistos += len(registros)
        return ResultadoGuardado(insertados=0, duplicados=len(registros))
