---
title: 'Historia 1.2 — Ingesta incremental con marca de agua y ventana de solapamiento'
type: 'feature'
created: '2026-09-02'
status: 'done'
baseline_commit: 'NO_VCS'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-02.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Hoy cada ingesta exige decir a mano qué rango traer. Sin un cursor persistido no hay Ciclo diario desatendido, y sin registro de Ciclo no se puede distinguir «no había nada nuevo» de «falló y nadie se enteró».

**Approach:** Una marca de agua por dataset sobre la **fecha del hecho** —el campo que la fuente siempre llena—, que cada Ciclo avanza solo si terminó bien, y que se lee retrocediendo una ventana de solapamiento porque el SECOP publica con retraso. Cada Ciclo deja un registro con sus cursores y sus conteos, incluida la señal de que la ventana se está quedando corta.

## Boundaries & Constraints

**Always:**

- El cursor es la fecha del hecho: `fecha_de_firma` en Contratos, `fecha_de_publicacion_del` en Procesos. **Nunca `ultima_actualizacion` ni `:updated_at`** — refutados por medición el 2026-09-02.
- La ventana de solapamiento se resta de la marca en cada Ciclo. Su tamaño es configuración con valor por defecto, no una constante en el código.
- La marca avanza **solo** cuando el Ciclo termina completo. Un Ciclo que aborta deja la marca donde estaba.
- Un Ciclo que no encuentra nada nuevo es un registro válido, con conteo cero y estado `completo`. Un Ciclo fallido queda con estado `fallido` y su causa.
- Todo Ciclo queda registrado con cursor de entrada, cursor de salida, vistos, insertados, duplicados, páginas, inicio, fin y estado (AD-4).
- El primer Ciclo de un dataset exige un `--desde` explícito. Sin marca previa, arrancar por su cuenta sería inventar el alcance del histórico.
- La señal de ventana corta se calcula y se reporta en cada Ciclo: cuántos registros nuevos entraron con fecha de hecho anterior a la marca previa, y cuántos cayeron en el día más viejo de la ventana.

**Ask First:**

- Cambiar el campo de fecha de hecho de un dataset.
- Avanzar la marca sobre un Ciclo que no terminó completo.
- Cambiar el valor por defecto de la ventana de solapamiento.

**Never:**

- Reintentos con espera, concurrencia o paralelismo. Un fallo aborta el Ciclo y la marca no avanza; reanudar es volver a correrlo.
- El barrido completo periódico — es la historia 1.7.
- Huérfanos y porcentaje de cruce — es la 1.4. El registro de Ciclo deja la columna, sin llenarla.
- Programación o cron — es la 6.1.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Primer Ciclo | Sin marca, con `--desde` explícito | Ingiere el rango pedido; la marca queda en `hasta` | N/A |
| Primer Ciclo sin `--desde` | Sin marca y sin rango | Error de uso que dice que el primer Ciclo se acota a mano | Nada se consulta |
| Ciclo incremental | Marca en 2026-08-20, ventana 30 días | Consulta desde 2026-07-21 hasta hoy; la marca avanza a hoy | N/A |
| Registro que vuelve por el solapamiento | Ya presente, sin cambios | 0 insertados, cuenta como duplicado | N/A |
| Ciclo sin nada nuevo | Rango sin registros | Ciclo `completo` y vacío, conteo cero, marca avanzada | Distinguible de un fallo por el estado |
| Fallo a mitad de Ciclo | La página 2 devuelve 500 | Ciclo queda `fallido` con la causa; **la marca no avanza** | El siguiente Ciclo reanuda desde la marca vieja |
| Registro publicado con retraso | Firmado antes de la marca previa, visto ahora | Entra, y se cuenta como recuperado por el solapamiento | N/A |
| Ventana quedándose corta | Registros nuevos en el día más viejo de la ventana | El Ciclo reporta ese conteo como señal de alarma | N/A |
| Marca por delante del rango | Marca posterior a `hasta` | Error de uso nombrando ambas fechas | Nada se consulta |
| Registro sin fecha de hecho | La clave no viene en el contenido | Se ingiere igual; se cuenta aparte como «sin fecha de hecho» | No rompe el Ciclo |

</frozen-after-approval>

## Code Map

Se apoya en la 1.1 (capa cruda idempotente, `ingerir`, `ResumenCiclo`) y en la 1.3 (validación previa). Lo nuevo es el estado entre Ciclos, que hasta ahora no existía.

- `vigia/ingest/estado.py` — `MarcaDeAgua`, `RegistroDeCiclo`, sus Protocols y las implementaciones en memoria. El estado del pipeline, independiente del motor.
- `vigia/ingest/estado_postgres.py` — implementaciones psycopg. La marca se escribe en la misma transacción que cierra el Ciclo.
- `vigia/ingest/ciclo.py` — `fecha_de_hecho(dataset, contenido)`; `ingerir` cuenta recuperados y borde de ventana; `ejecutar_ciclo(...)` envuelve a `ingerir` con marca y registro.
- `migraciones/003_estado_ingesta.sql` — tablas `ingesta_marca` y `ciclo`.
- `vigia/__main__.py` — `--desde` pasa a ser opcional; nuevos `--ventana-dias` y el modo incremental.
- `tests/test_estado.py`, `tests/test_cli.py`, `tests/test_postgres.py`.

## Tasks & Acceptance

**Execution:**

- [x] `vigia/ingest/estado.py` — `MarcaDeAgua` y `RegistroDeCiclo` con sus Protocols y dobles en memoria.
- [x] `migraciones/003_estado_ingesta.sql` — `ingesta_marca` (una fila por dataset) y `ciclo` (append-only, con estado y causa).
- [x] `vigia/ingest/estado_postgres.py` — persistencia, con marca y cierre de Ciclo en una sola transacción.
- [x] `vigia/ingest/ciclo.py` — extraer la fecha de hecho de cada registro y contar recuperados y borde de ventana.
- [x] `vigia/ingest/ciclo.py` — `ejecutar_ciclo`: leer marca, restar ventana, ingerir, y cerrar el Ciclo avanzando la marca solo si terminó completo.
- [x] `vigia/__main__.py` — modo incremental, `--ventana-dias`, y el error de uso del primer Ciclo sin `--desde`.
- [x] `tests/` — cada fila de la matriz, más la persistencia y la atomicidad marca/Ciclo contra Postgres real.
- [x] `README.md` — el Ciclo incremental, la ventana y qué hacer cuando la señal de ventana corta se enciende.

**Acceptance Criteria:**

- Dado un dataset con marca registrada, cuando se ejecuta un Ciclo, entonces solo se consultan registros con fecha de hecho posterior a la marca menos la ventana, y al terminar la marca queda en el extremo derecho del rango.
- Dado un fallo a mitad de Ciclo, cuando el Ciclo se interrumpe, entonces la marca no avanza y queda un registro de Ciclo `fallido` con su causa.
- Dado un Ciclo sin registros nuevos, cuando termina, entonces queda `completo` con conteo cero, distinguible de un fallido por su estado.
- Dado un Ciclo terminado, cuando se consulta su registro, entonces informa cuántos registros entraron con fecha de hecho anterior a la marca previa y cuántos en el día más viejo de la ventana.

## Spec Change Log

## Design Notes

**Por qué la fecha del hecho y no una marca de actualización.** Medido el 2026-09-02:
`ultima_actualizacion` viene vacío en ~40% de los contratos y en el 100% de los más
recientes; `:updated_at` es inútil porque la fuente recarga el dataset completo y cada
recarga mueve todas las filas. `fecha_de_firma` y `fecha_de_publicacion_del` sí vienen
siempre: son la razón de ser del registro.

**Por qué el solapamiento no es un parche.** El SECOP publica con retraso: un contrato
firmado el día 1 puede aparecer el día 12. Sin ventana, avanzar la marca a «hoy» lo
perdería para siempre. Con ventana, ese contrato entra tarde y la idempotencia de la 1.1
hace que lo ya visto no cueste una sola fila. El costo del solapamiento son peticiones,
no datos duplicados.

**La señal de ventana corta.** Si en cada Ciclo siguen apareciendo registros nuevos en el
día más viejo de la ventana, la ventana no alcanza. Es la única forma de enterarse antes
de perder algo, y por eso va en el registro de Ciclo y no en un log que nadie lee.

**Marca y cierre en una transacción.** Si el Ciclo se registra como completo pero la
marca no avanza, el Ciclo siguiente repite trabajo — molesto pero inofensivo. Si la marca
avanza y el Ciclo no queda registrado, se pierde la trazabilidad que AD-4 exige. Van
juntos.

## Verification

**Commands:**

- `pytest` — expected: toda la suite pasa; las de integración se omiten sin `VIGIA_DSN_PRUEBAS`.
- `VIGIA_DSN_PRUEBAS=... pytest -m postgres` — expected: la marca no avanza tras un Ciclo fallido, leído desde otra conexión.
- `python -m vigia --dataset contratos --desde 2026-08-01 --hasta 2026-08-02` — expected: primer Ciclo, marca en 2026-08-02.
- `python -m vigia --dataset contratos` — expected: Ciclo incremental desde la marca menos la ventana.

## Suggested Review Order

**Lo que hace que la marca sea confiable**

- La marca avanza solo tras un Ciclo completo, y en la misma transacción que lo registra.
  [`estado_postgres.py:57`](../../vigia/ingest/estado_postgres.py#L57)

- Leer la marca cierra su propia transacción: sin esto, el bloque de arriba degradaba a SAVEPOINT y no confirmaba nada.
  [`estado_postgres.py:53`](../../vigia/ingest/estado_postgres.py#L53)

- La prueba que lo demuestra, leída desde otra conexión con la primera abierta.
  [`test_postgres.py:446`](../../tests/test_postgres.py#L446)

**La ventana de solapamiento**

- Retroceder la marca antes de consultar, y registrar el fallo pase lo que pase.
  [`ciclo.py:283`](../../vigia/ingest/ciclo.py#L283)

- La señal de ventana corta, contada solo sobre lo insertado y solo si `desde` vino de la marca.
  [`ciclo.py:198`](../../vigia/ingest/ciclo.py#L198)

- `--hasta` futuro se rechaza: fijaría la marca adelante y atascaría el dataset.
  [`__main__.py:186`](../../vigia/__main__.py#L186)

**Las invariantes en el motor**

- Conteos coherentes, señales acotadas por lo insertado, completo con cursor.
  [`003_estado_ingesta.sql:49`](../../migraciones/003_estado_ingesta.sql#L49)

- Parámetros por nombre: veinte valores posicionales se cruzan sin que nada proteste.
  [`estado_postgres.py:65`](../../vigia/ingest/estado_postgres.py#L65)

**Periféricos**

- El doble de la fuente ahora aplica el `$where` de verdad.
  [`conftest.py:102`](../../tests/conftest.py#L102)
