"""La marca de Vigía, rehecha como SVG a partir de las proporciones medidas.

Se reconstruye en vez de incrustar el JPG por tres razones concretas: se ve
nítida de 16 px de favicon a 1200 px de tarjeta, pesa medio kilobyte en vez de
doscientos, y toma el color del tema en vez de traer un fondo blanco pegado.

Las proporciones NO son a ojo. Salen de medir el original:
  · el ojo mide 408 x 254 px  ->  relación 1,61
  · los brazos de la V arrancan al 29,5 % de la altura, en el 25 % y el 75 %
  · el vértice cae al 75 % de la altura, centrado
"""

TINTA = "#04275D"

_ANCHO, _ALTO = 165.0, 104.0
_X0, _Y0, _W, _H = 2.0, 2.0, 161.0, 100.0


def _p(rx: float, ry: float) -> str:
    return f"{_X0 + rx * _W:.2f} {_Y0 + ry * _H:.2f}"


def ojo(alto: int = 100, color: str = "currentColor", trazo: float = 3.0) -> str:
    # El párpado: dos arcos cuadráticos. El control va a -0,5 y 1,5 porque en
    # una cuadrática el punto medio queda en (P0 + 2·P1 + P2)/4 — puesto ahí,
    # el arco toca exactamente el borde de la caja y no un poco antes.
    lente = (f"M {_p(0, .5)} Q {_p(.5, -.5)} {_p(1, .5)} "
             f"Q {_p(.5, 1.5)} {_p(0, .5)} Z")
    # La V va RELLENA y no trazada, porque en el original los brazos son
    # cuneiformes: anchos arriba y en punta abajo. Un trazo uniforme se ve
    # parecido de lejos y distinto de cerca.
    izq = (f"M {_p(.228, .295)} L {_p(.500, .795)} "
           f"L {_p(.500, .700)} L {_p(.272, .295)} Z")
    der = (f"M {_p(.772, .295)} L {_p(.500, .795)} "
           f"L {_p(.500, .700)} L {_p(.728, .295)} Z")
    return (
        f'<svg viewBox="0 0 {_ANCHO:.0f} {_ALTO:.0f}" height="{alto}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Vigía">'
        f'<path d="{lente}" fill="none" stroke="{color}" stroke-width="{trazo}"/>'
        f'<path d="{izq}" fill="{color}"/><path d="{der}" fill="{color}"/>'
        "</svg>"
    )
