---
title: 'Historia 1.3 — Validación de esquema que falla ruidosamente'
type: 'feature'
created: '2026-09-02'
status: 'done'
baseline_commit: 'NO_VCS'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Si el SECOP cambia la forma de un dataset, hoy la ingesta lo guardaría sin protestar y el equipo lo descubriría semanas después, con un mes de datos incompletos ya adentro y sin saber desde cuándo.

**Approach:** Antes de traer la primera página, comparar el esquema declarado del dataset contra un conjunto de campos esperados capturado y versionado en el repositorio: un campo esperado que desaparece detiene el Ciclo nombrándolo; un campo nuevo lo deja seguir y queda registrado como novedad para revisión.

## Boundaries & Constraints

**Always:**

- La comparación es contra el **esquema declarado del dataset** (`/api/views/{id}.json`), nunca contra las claves de un registro. Socrata omite las claves nulas por fila: comparar fila a fila reportaría campos «faltantes» en cada Ciclo.
- El conjunto de campos esperados vive en el repositorio como dato versionado, capturado de la fuente y revisado por una persona. No se escribe a mano ni se autoactualiza.
- La validación corre **antes** de la primera petición de datos. Un campo faltante detiene el Ciclo sin haber traído ni escrito nada.
- El error de campo faltante nombra el dataset y cada campo ausente. Nunca un mensaje genérico.
- Un campo nuevo no detiene nada: el Ciclo sigue y la novedad queda persistida con la fecha en que se detectó.
- La misma novedad detectada en Ciclos sucesivos no se duplica; conserva su primera detección y actualiza la última.

**Ask First:**

- Cambiar un archivo de esquema esperado por una razón distinta a una captura revisada.
- Añadir una forma de saltarse la validación en una corrida normal.

**Never:**

- Autoactualizar el esquema esperado con lo que la fuente devuelva. Eso convierte la alarma en un sello de goma.
- Marcas de sensibilidad de persona natural (AD-6). El módulo `schema/` es su lugar futuro, pero no es esta historia.
- Marca de agua e ingesta incremental — es la 1.2.
- Validar tipos, formatos o valores. Esta historia mira presencia y ausencia de campos, nada más.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Esquema intacto | Los campos declarados coinciden con los esperados | El Ciclo procede; ninguna novedad | N/A |
| Campo esperado ausente | Falta `valor_del_contrato` en lo declarado | El Ciclo se detiene nombrando dataset y campo | Nada se pidió ni se escribió en la capa cruda |
| Varios campos ausentes | Faltan tres campos | El error los nombra todos, en orden estable | Un solo error, no tres Ciclos fallidos |
| Campo nuevo | Aparece `valor_reintegro` no esperado | El Ciclo procede y la novedad queda registrada | N/A |
| Faltante y novedad a la vez | Falta uno y sobra otro | El Ciclo se detiene por el faltante; la novedad igual queda registrada | El faltante manda |
| Novedad repetida | La misma novedad ya registrada en un Ciclo anterior | No se duplica; se actualiza su última detección | N/A |
| Sin esquema esperado capturado | No existe archivo para ese dataset | Error que dice cómo capturarlo | El Ciclo no arranca |
| Metadatos inalcanzables | La consulta de esquema responde 500 | El Ciclo se detiene nombrando dataset y estado HTTP | Nada se ingirió |
| Captura de esquema | `python -m vigia.schema --capturar --dataset contratos` | Escribe el archivo con los campos y la fecha de captura | N/A |

</frozen-after-approval>

## Code Map

Se apoya en lo construido por la 1.1 y añade el módulo `schema/` que la semilla estructural del spine reserva para la definición de columnas.

- `vigia/ingest/socrata.py` — añadir `columnas(dataset)`: consulta `/api/views/{id}.json` y devuelve los `fieldName` declarados. Es la segunda —y única otra— frontera con la red.
- `vigia/schema/definiciones.py` — `EsquemaEsperado` (dataset, campos, fecha de captura, procedencia) y su lectura/escritura en JSON. El esquema es dato, no código.
- `vigia/schema/esperado/contratos.json` — captura verificada del 2026-09-02: 85 campos de `jbjy-vk9h`.
- `vigia/schema/validacion.py` — `validar_esquema(...) -> ResultadoValidacion(faltantes, novedades)`; levanta `EsquemaCambiado` cuando hay faltantes, después de registrar las novedades.
- `vigia/schema/novedades.py` — `RepositorioNovedades` (Protocol), `Novedad`, e implementación en memoria.
- `vigia/schema/postgres.py` — implementación psycopg con `ON CONFLICT ... DO UPDATE` sobre la última detección.
- `vigia/ingest/ciclo.py` — `ingerir(...)` acepta un `validador` opcional y lo corre antes de recorrer páginas.
- `vigia/schema/__main__.py` — captura de esquema por línea de comandos.
- `migraciones/002_esquema_novedad.sql` — tabla `esquema_novedad`.
- `vigia/__main__.py` — cablear la validación en la corrida real y en `--dry-run`.
- `tests/test_esquema.py`, `tests/conftest.py` — el doble de la fuente debe servir también los metadatos.

## Tasks & Acceptance

**Execution:**

- [x] `vigia/schema/definiciones.py` — `EsquemaEsperado` y su serialización; el conjunto de campos esperados como dato con procedencia y fecha.
- [x] `vigia/schema/esperado/contratos.json` — captura verificada de los 85 campos de Contratos.
- [x] `vigia/ingest/socrata.py` — `columnas(dataset)` contra el endpoint de metadatos, con los mismos errores de dominio que el resto del cliente.
- [x] `vigia/schema/novedades.py` — `Novedad`, el Protocol y la implementación en memoria.
- [x] `migraciones/002_esquema_novedad.sql` — `esquema_novedad` con llave `(dataset, campo)` y primera/última detección.
- [x] `vigia/schema/postgres.py` — implementación psycopg que conserva la primera detección y actualiza la última.
- [x] `vigia/schema/validacion.py` — comparar declarado contra esperado, registrar novedades y levantar `EsquemaCambiado` nombrando cada faltante.
- [x] `vigia/ingest/ciclo.py` — correr el validador antes de la primera página.
- [x] `vigia/schema/__main__.py` — capturar el esquema de un dataset a su archivo.
- [x] `vigia/__main__.py` — construir el validador y pasarlo al Ciclo.
- [x] `tests/` — cubrir cada fila de la matriz, más la persistencia de novedades contra Postgres real.
- [x] `README.md` — cómo capturar un esquema y qué hacer cuando la validación falla.

**Acceptance Criteria:**

- Dado un campo esperado que ya no aparece en el esquema declarado, cuando arranca el Ciclo, entonces se detiene con un error que nombra ese campo y no se escribe nada en la capa cruda.
- Dado un campo nuevo no esperado, cuando arranca el Ciclo, entonces el Ciclo continúa y la novedad queda consultable con su fecha de detección.
- Dado que la suite corre sin Postgres, entonces pasa completa y solo se omiten las pruebas de integración.

## Spec Change Log

## Design Notes

Por qué contra el esquema declarado y no contra los registros: en Socrata un campo nulo **no llega como `null`, llega ausente**. Un contrato real traído el 2026-09-02 no incluía la clave `ultima_actualizacion`. Validar fila a fila daría campos «faltantes» en casi todos los Ciclos y la alarma se volvería ruido que nadie mira — que es la forma más común de que una alarma deje de existir.

El esquema esperado se captura, no se escribe. Inventar una lista de campos a mano produce faltantes falsos el primer día. Capturarla de la fuente y versionarla hace que el `diff` de un cambio de esquema sea legible en el control de versiones, con fecha y procedencia, igual que la tabla territorial de la 1.6.

Las novedades se registran incluso cuando hay faltantes: si la fuente renombró un campo, el faltante y la novedad son las dos mitades del mismo hecho y el equipo necesita ver ambas para entenderlo.

## Verification

**Commands:**

- `pytest` — expected: toda la suite pasa; las de integración se omiten sin `VIGIA_DSN_PRUEBAS`.
- `VIGIA_DSN_PRUEBAS=... pytest -m postgres` — expected: idempotencia, durabilidad y persistencia de novedades contra el motor real.
- `python -m vigia.schema --capturar --dataset procesos` — expected: escribe `vigia/schema/esperado/procesos.json` con los campos declarados y la fecha de captura.

## Suggested Review Order

**Por qué se compara contra lo declarado y no contra las filas**

- La decisión que sostiene toda la historia: Socrata omite las claves nulas por fila.
  [`validacion.py:1`](../../vigia/schema/validacion.py#L1)

- La prueba que la fija: un registro con solo `:id` no produce ni un faltante.
  [`test_esquema.py:283`](../../tests/test_esquema.py#L283)

**Qué detiene el Ciclo y qué no**

- Un faltante levanta, y la excepción lleva dataset y campos como atributos.
  [`validacion.py:108`](../../vigia/schema/validacion.py#L108)

- Una novedad no detiene nada, ni siquiera cuando no se puede anotar.
  [`validacion.py:123`](../../vigia/schema/validacion.py#L123)

- Se valida antes de la primera página, con el reloj ya corriendo.
  [`ciclo.py:130`](../../vigia/ingest/ciclo.py#L130)

**Que la novedad llegue a ojos de alguien**

- Sube al resumen del Ciclo en vez de morir en el valor de retorno.
  [`ciclo.py:66`](../../vigia/ingest/ciclo.py#L66)

- Y el `dry-run` avisa de que no la está guardando.
  [`__main__.py:198`](../../vigia/__main__.py#L198)

**El esquema esperado como dato**

- Se rechaza un esperado vacío: no reportaría faltantes nunca.
  [`definiciones.py:44`](../../vigia/schema/definiciones.py#L44)

- Un archivo ilegible o de otro dataset se trata como ausente, no como traza.
  [`definiciones.py:54`](../../vigia/schema/definiciones.py#L54)

- Escritura atómica: una captura interrumpida no puede truncar la referencia.
  [`definiciones.py:90`](../../vigia/schema/definiciones.py#L90)

- La recaptura dice en voz alta qué campos SALEN, que es como se apaga la alarma sin querer.
  [`vigia/schema/__main__.py:99`](../../vigia/schema/__main__.py#L99)

**Periféricos**

- `LEAST`/`GREATEST`: el orden de llegada de los Ciclos no altera el registro.
  [`002_esquema_novedad.sql:8`](../../migraciones/002_esquema_novedad.sql#L8)

- Las columnas internas de la plataforma no cuentan como novedad.
  [`socrata.py:117`](../../vigia/ingest/socrata.py#L117)
