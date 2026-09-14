"""Calendario hábil colombiano.

POR QUÉ ESTO EXISTE, Y POR QUÉ ANTES QUE CUALQUIER RESUMEN.

El 2026-09-03 estuve a punto de reportar que la contratación cayó un **45,7 %**
después del cambio de gobierno del 7 de agosto. Los números eran ciertos:
79 789 procesos en los once días anteriores contra 43 321 en los once
posteriores. La conclusión era falsa entera. La ventana posterior tenía **cinco
días hábiles** y la anterior **nueve**, porque el 7 de agosto es festivo
—Batalla de Boyacá— y el 17 también —Asunción, trasladada al lunes por la Ley
Emiliani—. Normalizando por día hábil: 8 568 contra 7 621, y sobre el período
completo, **1,0 %** de diferencia.

Un resumen semanal o mensual que compare conteos crudos repetirá ese error
todas las semanas. Por eso el calendario va antes que el resumen, y no después.

POR QUÉ SE CALCULA Y NO SE COPIA UNA LISTA. Colombia celebra dieciocho
festivos al año y **doce se mueven**: la Ley 51 de 1983 —«Ley Emiliani»— los traslada al
lunes siguiente cuando no caen en lunes. Una lista pegada a mano vale para un
año y se pudre en silencio; el algoritmo vale para todos y se puede comprobar
contra fechas conocidas, que es lo que hacen las pruebas.

LO QUE NO CUBRE. Días cívicos locales, paros, y el hecho de que en Colombia se
contrata también en festivo. `es_habil` responde «¿es día hábil?», no «¿hubo
actividad?». Para lo segundo están los datos.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

#: Festivos de fecha fija. No se mueven nunca.
_FIJOS = (
    (1, 1),    # Año Nuevo
    (5, 1),    # Día del Trabajo
    (7, 20),   # Independencia
    (8, 7),    # Batalla de Boyacá
    (12, 8),   # Inmaculada Concepción
    (12, 25),  # Navidad
)

#: Festivos que la Ley Emiliani traslada al lunes siguiente si no caen en lunes.
_EMILIANI = (
    (1, 6),    # Reyes Magos
    (3, 19),   # San José
    (6, 29),   # San Pedro y San Pablo
    (8, 15),   # Asunción de la Virgen
    (10, 12),  # Día de la Raza
    (11, 1),   # Todos los Santos
    (11, 11),  # Independencia de Cartagena
)

#: Festivos que dependen de la Pascua. Los dos primeros NO se trasladan
#: —caen en jueves y viernes por definición—; los tres siguientes sí, y por eso
#: su desplazamiento ya viene sumado para caer en lunes.
_DESDE_PASCUA = (
    (-3, "Jueves Santo"),
    (-2, "Viernes Santo"),
    (39 + 4, "Ascensión"),          # +39 es el día litúrgico; +43 cae en lunes
    (60 + 4, "Corpus Christi"),     # +60 litúrgico; +64 en lunes
    (68 + 3, "Sagrado Corazón"),    # +68 litúrgico; +71 en lunes
)

#: Cuántos festivos distintos tiene un año colombiano.
#:
#: **No siempre son dieciocho, y esto lo comprobé después de suponerlo.** Hay
#: dieciocho celebraciones, pero dos pueden caer el mismo lunes: cuando el
#: Sagrado Corazón —Pascua + 68, trasladado— coincide con San Pedro y San Pablo
#: —29 de junio, trasladado—, el año tiene DIECISIETE festivos distintos.
#:
#: Pasa en 2025 y en 2030. El calendario oficial de la Alcaldía de Bogotá para
#: 2025 lista diecisiete, con el 30 de junio como único lunes de esa semana, y
#: este módulo lo reproduce fecha por fecha (ver `test_calendario.py`).
#:
#: La primera versión de este archivo afirmaba «dieciocho, siempre», y una
#: prueba parametrizada por año lo tumbó en 2025 y 2030. La afirmación era mía;
#: el algoritmo estaba bien.
FESTIVOS_MINIMOS = 17
FESTIVOS_MAXIMOS = 18


def domingo_de_pascua(anio: int) -> date:
    """El domingo de Pascua, por el algoritmo de Meeus/Jones/Butcher.

    Se escribe entero en vez de traer una librería porque son ocho líneas,
    porque una dependencia más es una dependencia que puede desaparecer, y
    porque así el cálculo se puede leer y comprobar aquí mismo.
    """
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(anio, mes, dia + 1)


def _al_lunes(dia: date) -> date:
    """El lunes siguiente, o el mismo día si ya es lunes (Ley Emiliani)."""
    return dia + timedelta(days=(7 - dia.weekday()) % 7)


@lru_cache(maxsize=64)
def festivos(anio: int) -> frozenset[date]:
    """Los festivos de un año en Colombia: diecisiete o dieciocho fechas."""
    dias = {date(anio, mes, dia) for mes, dia in _FIJOS}
    dias |= {_al_lunes(date(anio, mes, dia)) for mes, dia in _EMILIANI}
    pascua = domingo_de_pascua(anio)
    dias |= {pascua + timedelta(days=desfase) for desfase, _ in _DESDE_PASCUA}
    return frozenset(dias)


def es_festivo(dia: date) -> bool:
    return dia in festivos(dia.year)


def es_habil(dia: date) -> bool:
    """Lunes a viernes que no sea festivo."""
    return dia.weekday() < 5 and not es_festivo(dia)


def dias_habiles(desde: date, hasta: date) -> int:
    """Cuántos días hábiles hay entre dos fechas, ambas incluidas.

    Devuelve 0 si el rango está al revés, en vez de un número negativo que
    luego dividiría mal en algún promedio.
    """
    if hasta < desde:
        return 0
    total = 0
    dia = desde
    while dia <= hasta:
        if es_habil(dia):
            total += 1
        dia += timedelta(days=1)
    return total


def por_dia_habil(cantidad: float, desde: date, hasta: date) -> float | None:
    """Una cantidad repartida entre los días hábiles del rango.

    `None` cuando no hay ningún día hábil —una semana de Semana Santa entera,
    por ejemplo—. No es cero: es que la pregunta no tiene respuesta, y
    devolver cero haría creer que no hubo actividad.
    """
    habiles = dias_habiles(desde, hasta)
    if habiles == 0:
        return None
    return cantidad / habiles


def nombre_del_festivo(dia: date) -> str | None:
    """Cómo se llama el festivo, para poder decirlo en un reporte."""
    if not es_festivo(dia):
        return None
    nombres_fijos = {
        (1, 1): "Año Nuevo", (5, 1): "Día del Trabajo",
        (7, 20): "Independencia", (8, 7): "Batalla de Boyacá",
        (12, 8): "Inmaculada Concepción", (12, 25): "Navidad",
    }
    if (dia.month, dia.day) in nombres_fijos:
        return nombres_fijos[(dia.month, dia.day)]
    nombres_emiliani = {
        (1, 6): "Reyes Magos", (3, 19): "San José",
        (6, 29): "San Pedro y San Pablo", (8, 15): "Asunción",
        (10, 12): "Día de la Raza", (11, 1): "Todos los Santos",
        (11, 11): "Independencia de Cartagena",
    }
    for (mes, numero), nombre in nombres_emiliani.items():
        if _al_lunes(date(dia.year, mes, numero)) == dia:
            return nombre
    pascua = domingo_de_pascua(dia.year)
    for desfase, nombre in _DESDE_PASCUA:
        if pascua + timedelta(days=desfase) == dia:
            return nombre
    return "festivo"
