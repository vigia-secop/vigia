"""Avisar por Telegram. Sin librerías, sin dependencias, sin secretos en el código.

    python -m vigia.telegrama --texto "Vigía: las seis puertas en verde."
    cat mensaje.txt | python -m vigia.telegrama

QUÉ MANDA Y QUÉ NO. Manda el resultado del semáforo y el hilo de la semana ya
escrito. **No publica nada en ninguna parte**: Telegram es el canal por el que
el servidor te habla a ti, no por el que Vigía le habla al país. El hilo llega
para que lo leas y lo publiques tú.

LAS CREDENCIALES VIVEN EN EL ENTORNO, NO AQUÍ. `TELEGRAM_TOKEN` y
`TELEGRAM_CHAT` se leen del `.env` del servidor, que está fuera de git. Si
alguna vez este archivo llevara el token escrito, bastaría con que el
repositorio se hiciera público —que es justo lo que va a pasar— para que
cualquiera pudiera escribir en tu bot.

SI NO HAY CREDENCIALES, NO ES UN ERROR. En el equipo de escritorio no las hay
y no hacen falta: el mensaje se imprime por consola y ya. Un aviso que revienta
el ciclo por no poder avisar sería peor que no avisar.

POR QUÉ `urllib` Y NO `requests`. Porque esto corre en un servidor que se
instala solo y cada dependencia es una cosa más que puede faltar a las cinco y
media de la mañana. La biblioteca estándar basta.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

#: Telegram corta los mensajes en 4096 caracteres. Se parte antes, por líneas,
#: para que el corte caiga entre renglones y no en mitad de una cifra.
LIMITE = 4000


def _trozos(texto: str, limite: int = LIMITE) -> list[str]:
    if len(texto) <= limite:
        return [texto]
    partes, actual = [], ""
    for linea in texto.splitlines(keepends=True):
        # Una sola línea más larga que el límite se parte a lo bruto: es raro
        # y es mejor que perderla.
        while len(linea) > limite:
            if actual:
                partes.append(actual)
                actual = ""
            partes.append(linea[:limite])
            linea = linea[limite:]
        if len(actual) + len(linea) > limite:
            partes.append(actual)
            actual = ""
        actual += linea
    if actual:
        partes.append(actual)
    return partes


def enviar(texto: str, *, token: str | None = None, chat: str | None = None,
           tiempo: float = 15.0) -> bool:
    """Manda el mensaje. Devuelve si se pudo, y nunca levanta.

    Que no levante es a propósito: esto se llama al final del ciclo diario, y
    una excepción aquí dejaría la corrida marcada como fallida por un problema
    de red que no tiene nada que ver con los datos.
    """
    token = token or os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat = chat or os.environ.get("TELEGRAM_CHAT", "").strip()
    if not token or not chat:
        print("(sin TELEGRAM_TOKEN o TELEGRAM_CHAT: el aviso no se manda)",
              file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    bien = True
    for trozo in _trozos(texto):
        datos = urllib.parse.urlencode({
            "chat_id": chat,
            "text": trozo,
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        peticion = urllib.request.Request(url, data=datos)
        try:
            with urllib.request.urlopen(peticion, timeout=tiempo) as r:
                respuesta = json.loads(r.read().decode("utf-8"))
            if not respuesta.get("ok"):
                print(f"Telegram respondió: {respuesta}", file=sys.stderr)
                bien = False
        except (urllib.error.URLError, OSError, ValueError) as error:
            # El token NO se imprime nunca, ni siquiera en un error: los
            # registros del servidor se leen, se copian y se pegan.
            print(f"no se pudo avisar por Telegram: {error}", file=sys.stderr)
            bien = False
    return bien


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vigia.telegrama")
    p.add_argument("--texto", default="",
                   help="el mensaje; si falta, se lee de la entrada estándar")
    p.add_argument("--archivo", default="")
    o = p.parse_args(argv)

    if o.archivo:
        from pathlib import Path
        texto = Path(o.archivo).read_text(encoding="utf-8")
    elif o.texto:
        texto = o.texto
    else:
        texto = sys.stdin.read()

    texto = texto.strip()
    if not texto:
        print("nada que mandar", file=sys.stderr)
        return 2

    # Siempre por consola, aunque se mande: el registro del servidor tiene que
    # poder contar lo que pasó sin depender de que Telegram estuviera arriba.
    print(texto)
    enviar(texto)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
