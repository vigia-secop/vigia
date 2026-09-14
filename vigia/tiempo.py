"""Reglas de tiempo compartidas.

Dos zonas conviven en este proyecto y confundirlas es un error caro:

- **UTC** para todo instante nuestro: `consultado_en`, `inicio`, `fin`. Son
  hechos del sistema y se almacenan en UTC (convención del spine).
- **Hora de Colombia** para las fechas de la fuente. Los datasets del SECOP
  traen marcas de tiempo flotantes, sin zona, que se leen en la del publicador.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

#: Colombia no tiene horario de verano: UTC-5 todo el año.
ZONA_COLOMBIA = timezone(timedelta(hours=-5))


def a_utc(momento: datetime, etiqueta: str) -> datetime:
    """Normaliza a UTC, rechazando un `datetime` sin zona.

    Un `datetime` ingenuo no significa nada por sí solo: quien lo escribe cree
    que es local y quien lo lee cree que es UTC. Rechazarlo en la frontera es
    más barato que perseguir el desfase después.
    """
    if momento.tzinfo is None:
        raise ValueError(
            f"{etiqueta} debe traer zona horaria; se recibió un datetime ingenuo: {momento!r}"
        )
    return momento.astimezone(timezone.utc)


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def hoy_en_colombia() -> "datetime.date":
    """El día de hoy en la zona del publicador, que es la que fecha los datos."""
    return datetime.now(ZONA_COLOMBIA).date()
