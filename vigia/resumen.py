"""Resumen semanal y mensual, normalizado por día hábil.

    python -m vigia.resumen --json resumen.json --salida resumen.html

LA REGLA DE ESTE MÓDULO, Y NO ES NEGOCIABLE: **ninguna comparación entre dos
períodos se hace con conteos crudos.** Todo lo que se compara va dividido entre
los días hábiles del período.

El 2026-09-03 los conteos crudos decían que la contratación había caído un
45,7 % después del cambio de gobierno. Era el almanaque: nueve días hábiles
antes contra cinco después, por dos festivos. Normalizado, la diferencia real
era del 1,0 %. Un resumen semanal que no haga esa división repetirá ese error
cada lunes, y cada lunes alguien puede creérselo.

Por eso el encabezado de cada comparación dice cuántos días hábiles tiene cada
lado. No es un detalle técnico escondido: es el dato sin el cual la cifra de al
lado no significa nada.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from vigia.calendario import dias_habiles, es_festivo, nombre_del_festivo
from vigia.panel import compacto, e, numero, pesos, titulo_es

CODIGO_USO = 2
CODIGO_FALLO = 1


def _fecha(texto) -> date:
    return date.fromisoformat(str(texto)[:10])


def variacion(actual: float | None, previo: float | None) -> str:
    """La variación entre dos ritmos ya normalizados.

    `—` cuando alguno de los dos lados no se puede calcular. No es 0 %: es que
    la pregunta no tiene respuesta, y un 0 % haría creer que no cambió nada.
    """
    if actual is None or previo is None or previo == 0:
        return "—"
    cambio = 100 * (actual - previo) / previo
    signo = "+" if cambio > 0 else ""
    return f"{signo}{cambio:.1f} %".replace(".", ",")


def _clase(actual: float | None, previo: float | None) -> str:
    if actual is None or previo is None or previo == 0:
        return "neutro"
    cambio = (actual - previo) / previo
    if abs(cambio) < 0.05:
        return "neutro"
    return "sube" if cambio > 0 else "baja"


def _festivos_del_rango(desde: date, hasta: date) -> list[str]:
    from datetime import timedelta
    nombres, dia = [], desde
    while dia <= hasta:
        if es_festivo(dia) and dia.weekday() < 5:
            nombres.append(f"{dia.strftime('%d/%m')} {nombre_del_festivo(dia)}")
        dia += timedelta(days=1)
    return nombres


def _fila(rotulo, actual, previo, habiles_a, habiles_p, *, dinero=False):
    ritmo_a = actual / habiles_a if habiles_a else None
    ritmo_p = previo / habiles_p if habiles_p else None
    formato = compacto if dinero else (lambda v: numero(round(v)) if v is not None else "—")
    return (
        "<tr>"
        f"<td class='rot'>{e(rotulo)}</td>"
        f"<td class='num'>{formato(actual)}</td>"
        f"<td class='num'>{formato(ritmo_a) if ritmo_a is not None else '—'}</td>"
        f"<td class='num'>{formato(ritmo_p) if ritmo_p is not None else '—'}</td>"
        f"<td class='num var {_clase(ritmo_a, ritmo_p)}'>{variacion(ritmo_a, ritmo_p)}</td>"
        "</tr>"
    )


def construir(datos: dict, *, titulo: str = "Resumen") -> str:
    p = datos["periodo"]
    ant = datos["anterior"]
    a, b = datos["actual"], datos["anterior_cifras"]
    d_desde, d_hasta = _fecha(p["desde"]), _fecha(p["hasta"])
    a_desde, a_hasta = _fecha(ant["desde"]), _fecha(ant["hasta"])
    hab_a = dias_habiles(d_desde, d_hasta)
    hab_p = dias_habiles(a_desde, a_hasta)
    festivos_a = _festivos_del_rango(d_desde, d_hasta)
    festivos_p = _festivos_del_rango(a_desde, a_hasta)
    generado = str(datos.get("generado_en", ""))[:19].replace("T", " ")

    filas = "".join([
        _fila("Contratos", a["contratos"], b["contratos"], hab_a, hab_p),
        _fila("Valor", float(a["valor"]), float(b["valor"]), hab_a, hab_p, dinero=True),
        _fila("Entidades contratantes", a["entidades"], b["entidades"], hab_a, hab_p),
        _fila("Proveedores distintos", a["proveedores"], b["proveedores"], hab_a, hab_p),
        _fila("Nacional", a["nacional"], b["nacional"], hab_a, hab_p),
        _fila("Territorial", a["territorial"], b["territorial"], hab_a, hab_p),
        _fila("Corporación Autónoma", a["car"], b["car"], hab_a, hab_p),
        _fila("Uniones sin documento", a["uniones"], b["uniones"], hab_a, hab_p),
        _fila("Huérfanos", a["huerfanos"], b["huerfanos"], hab_a, hab_p),
    ])

    def lista(clave, columnas):
        filas_html = []
        for f in (datos.get(clave) or []):
            celdas = "".join(columnas(f))
            filas_html.append(f"<tr>{celdas}</tr>")
        return "".join(filas_html) or "<tr><td colspan='4' class='vacio'>sin datos</td></tr>"

    deps = lista("departamentos", lambda f: (
        f"<td class='rot'>{e(f['codigo'])} · {e(titulo_es(f['nombre']))}</td>",
        f"<td class='num'>{numero(f['contratos'])}</td>",
        f"<td class='num' colspan='2'>{compacto(f['valor'])}</td>",
    ))
    provs = lista("proveedores", lambda f: (
        f"<td class='rot'>{e((f['nombre'] or '(sin razón social)'))}"
        f"<span class='doc'>{e(f['numero'])}</span></td>",
        f"<td class='num'>{numero(f['contratos'])}</td>",
        f"<td class='num'>{numero(f['entidades'])}</td>",
        f"<td class='num'>{compacto(f['valor'])}</td>",
    ))
    uts = lista("uniones", lambda f: (
        f"<td class='rot'>{e(f['nombre'] or '—')}</td>",
        f"<td colspan='2'>{e(f['entidad'] or '—')}</td>",
        f"<td class='num'>{compacto(f['valor'])}</td>",
    ))

    aviso_festivos = ""
    if festivos_a or festivos_p:
        aviso_festivos = (
            "<p class='festivos'><strong>Festivos en juego:</strong> "
            + (f"en este período, {', '.join(festivos_a)}. " if festivos_a else "")
            + (f"En el anterior, {', '.join(festivos_p)}." if festivos_p else "")
            + "</p>"
        )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)} de Vigía SECOP</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400&display=swap">
<style>
:root {{
  --papel:#EEF1F1; --superficie:#FFFFFF; --borde:#D3DADB; --borde-sutil:#E4E9E9;
  --tinta:#0E1719; --tinta-2:#3A4A4D; --tinta-3:#6B7B7E;
  --acento:#0091A8; --sube:#1D6B4F; --baja:#A8451B; --aviso:#A8620F;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --papel:#10171A; --superficie:#171F22; --borde:#2B383C; --borde-sutil:#212B2E;
    --tinta:#E8EDED; --tinta-2:#AEBDBF; --tinta-3:#7C8C8F;
    --acento:#22A0B8; --sube:#4FB489; --baja:#D98055; --aviso:#D9903F;
  }}
}}
:root[data-theme="dark"] {{
  --papel:#10171A; --superficie:#171F22; --borde:#2B383C; --borde-sutil:#212B2E;
  --tinta:#E8EDED; --tinta-2:#AEBDBF; --tinta-3:#7C8C8F;
  --acento:#22A0B8; --sube:#4FB489; --baja:#D98055; --aviso:#D9903F;
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--papel); color:var(--tinta);
  font-family:Archivo,"Segoe UI",system-ui,sans-serif; font-size:15px; line-height:1.55; }}
.envoltura {{ max-width:940px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ margin:0; font-size:27px; letter-spacing:-.02em; }}
.cab {{ display:flex; flex-wrap:wrap; gap:12px 28px; align-items:baseline;
  justify-content:space-between; padding-bottom:18px; border-bottom:2px solid var(--tinta); }}
.sello {{ font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--tinta-3);
  text-align:right; display:flex; flex-direction:column; }}
.habiles {{ display:grid; gap:1px; background:var(--borde); border:1px solid var(--borde);
  border-top:none; grid-template-columns:1fr 1fr; margin-bottom:12px; }}
.habiles div {{ background:var(--superficie); padding:14px 18px; }}
.habiles .rotu {{ font-size:11px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--tinta-3); font-weight:600; }}
.habiles .fechas {{ font-family:"IBM Plex Mono",monospace; font-size:13px; }}
.habiles .cuenta {{ font-family:"IBM Plex Mono",monospace; font-size:21px; }}
.festivos {{ margin:0 0 26px; font-family:"Source Serif 4",Georgia,serif; font-size:14px;
  color:var(--tinta-2); border-left:3px solid var(--aviso); padding-left:12px; }}
.nota-metodo {{ font-family:"Source Serif 4",Georgia,serif; font-size:14.5px;
  color:var(--tinta-2); max-width:66ch; margin:0 0 16px; }}
h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.1em;
  color:var(--acento); margin:36px 0 12px; }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px;
  background:var(--superficie); border:1px solid var(--borde); }}
th {{ text-align:right; font-size:10.5px; text-transform:uppercase; letter-spacing:.07em;
  color:var(--tinta-3); font-weight:600; padding:10px 14px; border-bottom:1px solid var(--borde); }}
th:first-child {{ text-align:left; }}
td {{ padding:9px 14px; border-bottom:1px solid var(--borde-sutil); }}
tr:last-child td {{ border-bottom:none; }}
.rot {{ font-weight:500; }}
.doc {{ display:block; font-family:"IBM Plex Mono",monospace; font-size:11px;
  color:var(--tinta-3); font-weight:400; }}
.num {{ text-align:right; font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums; white-space:nowrap; }}
.var.sube {{ color:var(--sube); font-weight:500; }}
.var.baja {{ color:var(--baja); font-weight:500; }}
.var.neutro {{ color:var(--tinta-3); }}
.vacio {{ color:var(--tinta-3); font-style:italic; }}
footer {{ margin-top:44px; padding-top:16px; border-top:1px solid var(--borde);
  font-family:"IBM Plex Mono",monospace; font-size:11.5px; color:var(--tinta-3); }}
</style>
</head>
<body>
<div class="envoltura">
  <header class="cab">
    <h1>{e(titulo)}</h1>
    <div class="sello"><span>generado {e(generado)}</span></div>
  </header>

  <div class="habiles">
    <div>
      <div class="rotu">Este período</div>
      <div class="fechas">{d_desde} → {d_hasta}</div>
      <div class="cuenta">{hab_a} <span style="font-size:13px">días hábiles</span></div>
    </div>
    <div>
      <div class="rotu">El anterior</div>
      <div class="fechas">{a_desde} → {a_hasta}</div>
      <div class="cuenta">{hab_p} <span style="font-size:13px">días hábiles</span></div>
    </div>
  </div>
  {aviso_festivos}

  <p class="nota-metodo">Toda comparación de esta página va dividida entre los
  días hábiles de cada período. Comparar los totales crudos de dos semanas
  distintas hace decir cosas que no pasaron: en agosto de 2026, dos festivos
  convirtieron una diferencia real del 1,0 % en una caída aparente del 45,7 %.</p>

  <h2>Ritmo por día hábil</h2>
  <table>
    <thead><tr><th>Medida</th><th>Total</th><th>Por día hábil</th>
      <th>Anterior</th><th>Variación</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>

  <h2>Departamentos por valor</h2>
  <table><thead><tr><th>Departamento</th><th>Contratos</th><th colspan="2">Valor</th></tr></thead>
    <tbody>{deps}</tbody></table>

  <h2>Proveedores por valor</h2>
  <table><thead><tr><th>Proveedor</th><th>Contratos</th><th>Entidades</th><th>Valor</th></tr></thead>
    <tbody>{provs}</tbody></table>

  <h2>Uniones temporales sin documento</h2>
  <table><thead><tr><th>Unión temporal</th><th colspan="2">Entidad</th><th>Valor</th></tr></thead>
    <tbody>{uts}</tbody></table>

  <footer>Vigía SECOP · indicadores estadísticos · no emite alertas y no califica ningún contrato</footer>
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vigia.resumen")
    ap.add_argument("--json", default="resumen.json")
    ap.add_argument("--salida", default="resumen.html")
    ap.add_argument("--titulo", default="Resumen semanal")
    o = ap.parse_args(argv)

    origen = Path(o.json)
    if not origen.exists():
        print(f"no existe {origen}", file=sys.stderr)
        return CODIGO_USO
    datos = json.loads(origen.read_text(encoding="utf-8"))
    for seccion in ("periodo", "actual", "anterior_cifras"):
        if seccion not in datos:
            print(f"a {origen} le falta «{seccion}»", file=sys.stderr)
            return CODIGO_FALLO

    Path(o.salida).write_text(construir(datos, titulo=o.titulo), encoding="utf-8")
    print(f"{o.titulo} escrito en {Path(o.salida).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
