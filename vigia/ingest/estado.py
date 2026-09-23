"""El estado que sobrevive entre Ciclos: la marca de agua y el registro de Ciclos.

La marca dice hasta dónde se leyó. El registro dice qué pasó en cada intento —
incluidos los que no encontraron nada y los que fallaron, que son cosas
distintas y tienen que poder distinguirse (AD-4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from vigia.tiempo import a_utc as _a_utc


class EstadoCiclo:
    """Los estados en que puede terminar un Ciclo."""

    COMPLETO = "completo"
    FALLIDO = "fallido"

    TODOS = (COMPLETO, FALLIDO)


@dataclass(frozen=True)
class MarcaDeAgua:
    """Hasta qué fecha de hecho se leyó un dataset.

    La fecha es la del hecho —firma del contrato, publicación del proceso—, no
    la de la lectura: es lo único que la fuente llena siempre.
    """

    dataset: str
    fecha_hecho: date
    actualizada_en: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "actualizada_en", _a_utc(self.actualizada_en, "actualizada_en")
        )


@dataclass(frozen=True)
class RegistroDeCiclo:
    """Lo que un Ciclo hizo, terminara bien o mal.

    Un Ciclo vacío y un Ciclo fallido son ambos registros válidos y se
    distinguen por `estado`. Confundirlos es cómo un pipeline lleva un mes sin
    traer nada y nadie se entera.
    """

    dataset: str
    cursor_entrada: date | None
    cursor_salida: date | None
    desde: date
    hasta: date
    estado: str
    inicio: datetime
    fin: datetime
    paginas: int = 0
    vistos: int = 0
    insertados: int = 0
    duplicados: int = 0
    recuperados_por_solapamiento: int = 0
    en_borde_de_ventana: int = 0
    #: Ya los teníamos y cambiaron, en el día del borde. No es alarma: ver
    #: `ResumenCiclo.cambiados_en_borde`.
    cambiados_en_borde: int = 0
    sin_fecha_de_hecho: int = 0
    #: Reservado para la historia 1.4; el Ciclo todavía no sabe de huérfanos.
    huerfanos: int | None = None
    causa: str | None = None
    novedades: tuple[str, ...] = field(default_factory=tuple)
    #: Con qué ventana corrió, para poder calibrarla leyendo el histórico.
    ventana_dias: int | None = None
    #: `True` si `desde` salió de la marca menos la ventana. La señal de
    #: ventana corta solo significa algo cuando `desde` es un borde de ventana
    #: y no una fecha que pidió una persona.
    desde_derivado: bool = False

    def __post_init__(self) -> None:
        if self.estado not in EstadoCiclo.TODOS:
            raise ValueError(
                f"estado de Ciclo desconocido: {self.estado!r}; "
                f"se esperaba uno de {EstadoCiclo.TODOS}"
            )
        if self.estado == EstadoCiclo.FALLIDO and not self.causa:
            raise ValueError("un Ciclo fallido tiene que registrar su causa")
        if self.completo and self.cursor_salida is None:
            raise ValueError("un Ciclo completo tiene que dejar cursor de salida")
        conteos = {
            "paginas": self.paginas,
            "vistos": self.vistos,
            "insertados": self.insertados,
            "duplicados": self.duplicados,
            "recuperados_por_solapamiento": self.recuperados_por_solapamiento,
            "en_borde_de_ventana": self.en_borde_de_ventana,
            "cambiados_en_borde": self.cambiados_en_borde,
            "sin_fecha_de_hecho": self.sin_fecha_de_hecho,
        }
        negativos = sorted(nombre for nombre, valor in conteos.items() if valor < 0)
        if negativos:
            raise ValueError(f"conteos negativos en el Ciclo: {', '.join(negativos)}")
        if self.insertados + self.duplicados != self.vistos:
            raise ValueError(
                f"conteos incoherentes: insertados={self.insertados} + "
                f"duplicados={self.duplicados} no suma vistos={self.vistos}"
            )
        object.__setattr__(self, "inicio", _a_utc(self.inicio, "inicio"))
        object.__setattr__(self, "fin", _a_utc(self.fin, "fin"))

    @property
    def completo(self) -> bool:
        return self.estado == EstadoCiclo.COMPLETO

    @property
    def vacio(self) -> bool:
        """Terminó bien y no encontró nada. No es lo mismo que haber fallado."""
        return self.completo and self.vistos == 0

    @property
    def ventana_corta(self) -> bool:
        """Siguen entrando registros NUNCA VISTOS por el extremo viejo.

        Solo los nunca vistos: un registro que ya teníamos y que cambió no se
        pierde con una ventana corta, solo se ve tarde su versión nueva. El
        2026-09-20 esta alarma encendió con 1.506 y los 1.506 eran de esos.

        Solo aplica cuando `desde` se derivó de la marca: en un histórico
        pedido a mano, que haya registros nuevos en el primer día del rango es
        lo normal, no una alarma.
        """
        return self.desde_derivado and self.en_borde_de_ventana > 0

    #: Por debajo de esto no se juzga: en una corrida chica —un rango de un
    #: día, una prueba— que no se repita nada es normal.
    MINIMO_PARA_JUZGAR_REPETICION = 1000

    #: Un Ciclo diario normal repite casi todo: la ventana vuelve a leer lo de
    #: los días anteriores. El 2026-09-20 fueron 124.345 duplicados de 144.889
    #: (85,8 %). Por debajo de este 10 % ya no es «la fuente actualizó cosas»,
    #: es «la fuente devolvió otra cosa».
    UMBRAL_REPETICION = 0.10

    @property
    def fuente_cambio_todo(self) -> bool:
        """Casi nada de lo que llegó coincide con lo que ya estaba guardado.

        Pasó el 2026-09-22: 139.172 contratos vistos, 139.172 insertados, cero
        duplicados. No había ni un campo nuevo que avisara. La causa fue un
        cambio de formato de la fuente —los campos de plata pasaron de «0» a
        «0.000000»—, que le cambia el hash a TODOS los registros y mete una
        versión nueva de la base entera en un solo día.

        No es un error: el dato guardado sigue siendo el que llegó. Pero tiene
        que verse, porque cuesta espacio y porque la otra explicación posible
        —que la fuente haya cambiado las cifras de escala— sí rompería las
        cuentas del sitio, y en silencio.
        """
        if not self.completo or self.vistos < self.MINIMO_PARA_JUZGAR_REPETICION:
            return False
        return self.duplicados / self.vistos < self.UMBRAL_REPETICION


class RepositorioEstado(Protocol):
    """Marca de agua y registro de Ciclos.

    `cerrar_ciclo` escribe el registro y, solo si el Ciclo quedó completo,
    avanza la marca — en una sola transacción. Que un Ciclo se registre sin que
    la marca avance solo cuesta trabajo repetido; que la marca avance sin
    registro rompe la trazabilidad que AD-4 exige.
    """

    def marca(self, dataset: str) -> MarcaDeAgua | None:
        ...

    def cerrar_ciclo(self, registro: RegistroDeCiclo) -> None:
        ...


class RepositorioEstadoEnMemoria:
    """Estado en memoria, para pruebas y corridas en seco."""

    def __init__(self) -> None:
        self._marcas: dict[str, MarcaDeAgua] = {}
        self.ciclos: list[RegistroDeCiclo] = []

    def marca(self, dataset: str) -> MarcaDeAgua | None:
        return self._marcas.get(dataset)

    def fijar_marca(self, dataset: str, fecha_hecho: date, actualizada_en: datetime) -> None:
        """Siembra una marca directamente. Para pruebas y para arranques a mano."""
        self._marcas[dataset] = MarcaDeAgua(dataset, fecha_hecho, actualizada_en)

    def cerrar_ciclo(self, registro: RegistroDeCiclo) -> None:
        self.ciclos.append(registro)
        if not registro.completo or registro.cursor_salida is None:
            return
        anterior = self._marcas.get(registro.dataset)
        # La marca nunca retrocede: un reproceso de un rango viejo no debe
        # obligar a releer todo lo que ya se había leído después. Pero
        # `actualizada_en` sí se refresca siempre: responde «¿cuándo se
        # confirmó por última vez este dataset?», y congelarla haría creer que
        # la ingesta está detenida.
        fecha = registro.cursor_salida
        if anterior is not None:
            fecha = max(anterior.fecha_hecho, fecha)
        self._marcas[registro.dataset] = MarcaDeAgua(
            dataset=registro.dataset,
            fecha_hecho=fecha,
            actualizada_en=registro.fin,
        )
