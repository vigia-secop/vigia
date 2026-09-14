---
title: 'Historia 1.1 — Traer datos del SECOP y guardarlos crudos'
type: 'feature'
created: '2026-09-02'
status: 'done'
baseline_commit: 'NO_VCS'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** No existe capa cruda: hoy nada del SECOP entra al sistema, y sin una copia inmutable de lo que la fuente devolvió —con su fecha de consulta— ninguna Alerta posterior es reproducible ni defendible.

**Approach:** Un cliente Socrata que pagina hasta agotar el resultado y un repositorio de capa cruda que guarda cada registro verbatim, con fecha y hora de consulta, bajo una identidad determinista que hace la reingesta idempotente.

## Boundaries & Constraints

**Always:**

- El contenido guardado es el registro tal como lo devolvió la API: sin renombrar, sin coercionar tipos, sin descartar ni añadir campos.
- Todo registro crudo lleva `consultado_en` en UTC, capturado en el momento de la respuesta HTTP que lo trajo.
- La paginación siempre pide `$order=:id`. Socrata no garantiza orden implícito y paginar sin él salta o repite registros.
- La identidad de un registro crudo es `(dataset, id_fila_fuente, hash_contenido)`. Reingerir contenido idéntico no inserta fila.
- La capa cruda es de solo inserción. Nunca se hace `UPDATE` ni `DELETE` sobre ella; una versión nueva del mismo registro es una fila nueva.
- Vocabulario del glosario en tablas, tipos y funciones: Proceso, Contrato, Ciclo. Sin sinónimos en inglés para conceptos del dominio.
- El lote de una página entra completo o no entra: una página se guarda en una sola transacción.

**Ask First:**

- Cambiar la identidad del registro crudo o el algoritmo de hash.
- Añadir cualquier dataset distinto de Contratos (`jbjy-vk9h`) y Procesos (`p6dx-8zbt`).
- Introducir un ORM o una capa de migraciones con framework.

**Never:**

- Marca de agua, ingesta incremental o persistencia de cursor — es la historia 1.2.
- Validación de campos esperados o detección de campos nuevos — es la historia 1.3.
- Normalización, esquema unificado, territorio, identidad de proveedor — historias 1.4 a 1.6.
- Filtrar, enmascarar o excluir campos de persona natural en esta capa: el crudo se guarda completo y la protección vive aguas abajo, en publicación.
- Reintentos con espera exponencial, concurrencia o paralelismo. Un fallo de red aborta el Ciclo; reanudar es 1.2.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Ingesta simple | Dataset y rango de fechas con 3 registros | 3 filas crudas, cada una con el contenido verbatim y `consultado_en` en UTC | N/A |
| Reingesta sin cambios | Los mismos 3 registros ya guardados | 0 insertados, 3 duplicados; la capa cruda sigue con 3 filas | N/A |
| Registro modificado en la fuente | Mismo `:id`, contenido distinto | Fila nueva; la anterior se conserva sin modificar | N/A |
| Resultado mayor que la página | 2500 registros, página de 1000 | 3 peticiones (`$offset` 0, 1000, 2000), 2500 filas | N/A |
| Última página exacta | 2000 registros, página de 1000 | 3 peticiones; la tercera vuelve vacía y cierra el recorrido | N/A |
| Resultado vacío | Rango sin registros | 0 filas, resumen con `vistos=0` y sin error | N/A |
| Campo nulo en la fuente | Registro sin la clave `ultima_actualizacion` | Se guarda tal cual, sin inventar la clave ni un `null` | N/A |
| Fallo HTTP a mitad del recorrido | La página 2 devuelve 500 | El Ciclo aborta con error que nombra dataset, `$offset` y estado HTTP | Las páginas ya confirmadas quedan guardadas; no se avanza ningún cursor |
| Rango de fechas invertido | `desde` posterior a `hasta` | Error de validación antes de la primera petición | Mensaje que nombra ambas fechas |

</frozen-after-approval>

## Code Map

Repositorio vacío: no hay `pyproject.toml`, ni paquete, ni git, ni pruebas. Todo se crea en esta historia. La semilla estructural del spine (`ingest/`, `normalize/`, `rules/`, `review/`, `publish/`, `schema/`, `tests/`) es el destino de la épica completa; aquí solo nacen `ingest/` y el almacén crudo, más el andamiaje mínimo.

- `pyproject.toml` — paquete `vigia`, dependencias `httpx` y `psycopg[binary]`, `pytest` en el grupo de desarrollo. No existe.
- `vigia/ingest/datasets.py` — descriptor por dataset: id de Socrata, campo de fecha para el rango, nombre de dominio. Único lugar donde vive `jbjy-vk9h` / `p6dx-8zbt`.
- `vigia/ingest/socrata.py` — cliente HTTP: construcción de `$where`/`$order`/`$select`/`$limit`/`$offset` y recorrido de páginas. Frontera con la red; lo único que las pruebas sustituyen.
- `vigia/crudo/modelo.py` — `RegistroCrudo` y el cálculo de `hash_contenido` sobre JSON canónico. Define la identidad determinista.
- `vigia/crudo/repositorio.py` — `RepositorioCrudo` como Protocol: `guardar_pagina(registros) -> ResultadoGuardado`.
- `vigia/crudo/postgres.py` — implementación psycopg; `INSERT ... ON CONFLICT DO NOTHING` sobre la llave primaria, una transacción por página.
- `vigia/crudo/memoria.py` — implementación en memoria con la misma semántica de conflicto; es lo que usan las pruebas unitarias.
- `vigia/ingest/ciclo.py` — orquesta cliente y repositorio, devuelve `ResumenCiclo` (vistos, insertados, duplicados, páginas, inicio y fin en UTC).
- `migraciones/001_capa_cruda.sql` — tabla `crudo_registro` con `contenido jsonb`, `consultado_en timestamptz`, llave primaria compuesta e índice por dataset y fecha de consulta.
- `docker-compose.yml`, `.env.example`, `README.md`, `.gitignore` — arranque local de Postgres y cómo correr todo.
- `tests/` — dobles de la fuente, casos de la matriz, y la prueba de integración contra Postgres marcada para que se salte sin base de datos.

## Tasks & Acceptance

**Execution:**

- [x] `pyproject.toml` — crear el paquete `vigia` con dependencias, configuración de pytest y el marcador `postgres` — sin esto no hay nada ejecutable.
- [x] `.gitignore`, `.env.example`, `docker-compose.yml` — andamiaje mínimo para levantar Postgres local y no versionar secretos ni artefactos.
- [x] `migraciones/001_capa_cruda.sql` — crear `crudo_registro` con la llave primaria compuesta que hace la idempotencia una garantía del motor, no del código.
- [x] `vigia/crudo/modelo.py` — definir `RegistroCrudo` y `hash_contenido` sobre JSON canónico (claves ordenadas, UTF-8, sin espacios) — la identidad determinista de AD-3 empieza aquí.
- [x] `vigia/crudo/repositorio.py` — declarar el Protocol, `ResultadoGuardado` y `ErrorAlmacen` para que el Ciclo no dependa de Postgres ni vea sus excepciones.
- [x] `vigia/crudo/memoria.py` — implementación en memoria con idéntica semántica de conflicto, más `RepositorioNulo` para las corridas en seco.
- [x] `vigia/crudo/postgres.py` — implementación psycopg con `ON CONFLICT DO NOTHING` y una transacción por página.
- [x] `vigia/ingest/datasets.py` — descriptores de Contratos y Procesos; único punto donde viven los ids de Socrata.
- [x] `vigia/ingest/socrata.py` — cliente paginado con `$order=:id` y `$select=:*,*`, que sella `consultado_en` por respuesta.
- [x] `vigia/ingest/ciclo.py` — orquestación y `ResumenCiclo`; valida el rango antes de la primera petición y registra lo confirmado al abortar.
- [x] `vigia/__main__.py` — invocación por línea de comandos con dataset y rango, que imprime el resumen del Ciclo.
- [x] `tests/` — cubrir cada fila de la matriz de I/O con un doble de la fuente, más la integración contra Postgres bajo el marcador.
- [x] `README.md` — cómo levantar Postgres, aplicar la migración, correr una ingesta y correr las pruebas.

**Acceptance Criteria:**

- Dado un dataset y un rango de fechas, cuando se ejecuta el Ciclo, entonces cada registro devuelto queda en la capa cruda con su `consultado_en` y su contenido sin transformar.
- Dado un registro ya presente, cuando se reingiere sin cambios, entonces no se crea una fila nueva y el resumen lo cuenta como duplicado.
- Dado un resultado mayor que el límite de página, cuando se ejecuta el Ciclo, entonces se recorren todas las páginas hasta agotar el resultado.
- Dado el conjunto de pruebas, cuando se corre sin Postgres disponible, entonces la suite pasa y solo la prueba de integración queda marcada como omitida.

## Spec Change Log

## Design Notes

`hash_contenido` se calcula sobre `json.dumps(contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`. El orden de claves de la respuesta no es estable entre peticiones; canonizar antes de hashear es lo que hace que "mismo contenido" signifique lo mismo hoy y en seis meses. El contenido **almacenado** es el objeto tal cual, no la cadena canónica.

`id_fila_fuente` es el campo de sistema `:id` de Socrata, obtenido con `$select=:*,*`. Es estable por fila y es además la cláusula de orden que la documentación de Socrata exige para paginar sin saltos ni repeticiones.

El recorrido de páginas termina cuando una respuesta trae menos elementos que el límite. Con 2000 registros y páginas de 1000 eso implica una tercera petición vacía; es el precio de no confiar en un conteo que la fuente no garantiza.

```sql
CREATE TABLE crudo_registro (
    dataset          text        NOT NULL,
    id_fila_fuente   text        NOT NULL,
    hash_contenido   text        NOT NULL,
    contenido        jsonb       NOT NULL,
    consultado_en    timestamptz NOT NULL,
    PRIMARY KEY (dataset, id_fila_fuente, hash_contenido)
);
```

## Verification

**Commands:**

- `pytest` — expected: 70 pruebas pasan, 9 omitidas (las de integración) sin `VIGIA_DSN_PRUEBAS`.
- `VIGIA_DSN_PRUEBAS=... pytest -m postgres` — expected: 9 pruebas pasan; verifican idempotencia, durabilidad por página leída desde otra conexión, y que el hash recalculado sobre el JSONB recuperado coincide con el almacenado.
- `python -m vigia --dataset contratos --desde 2026-08-01 --hasta 2026-08-02 --dry-run` — expected: imprime el resumen del Ciclo sin escribir en la base.

Las pruebas de integración borran filas, por eso leen `VIGIA_DSN_PRUEBAS` y nunca `VIGIA_DSN`: apuntarlas a la base de trabajo destruiría la serie histórica que es el activo del producto.

## Suggested Review Order

**Identidad e idempotencia — el corazón de la historia**

- La terna que hace la reingesta idempotente y conserva el histórico.
  [`modelo.py:76`](../../vigia/crudo/modelo.py#L76)

- Canonizar antes de hashear: sin esto, «el mismo contenido» cambia de significado entre peticiones.
  [`modelo.py:40`](../../vigia/crudo/modelo.py#L40)

- La garantía la da la llave primaria, no el código.
  [`001_capa_cruda.sql:11`](../../migraciones/001_capa_cruda.sql#L11)

- Una transacción por página: lo confirmado sobrevive a un Ciclo que muere después.
  [`postgres.py:52`](../../vigia/crudo/postgres.py#L52)

**Paginación — donde vive el riesgo de pérdida silenciosa**

- `$order=:id` en toda petición; sin él Socrata salta y repite filas sin síntoma.
  [`socrata.py:87`](../../vigia/ingest/socrata.py#L87)

- Rechazar un `$limit` sobre el tope: la fuente recorta en silencio y la página recortada parece la última.
  [`socrata.py:78`](../../vigia/ingest/socrata.py#L78)

- Y rechazar una página más larga que el límite: el cursor avanza exacto y la diferencia se perdería.
  [`socrata.py:160`](../../vigia/ingest/socrata.py#L160)

- Sin redirecciones: httpx reenvía `X-App-Token` a otro host.
  [`socrata.py:181`](../../vigia/ingest/socrata.py#L181)

**Orquestación**

- El rango se valida antes de gastar una petición, y se interpreta en hora de Colombia.
  [`ciclo.py:79`](../../vigia/ingest/ciclo.py#L79)

- Al abortar, lo confirmado queda registrado antes de que suba la excepción.
  [`ciclo.py:148`](../../vigia/ingest/ciclo.py#L148)

**Periféricos**

- La corrida en seco no retiene nada ni finge saber qué sería nuevo.
  [`memoria.py:50`](../../vigia/crudo/memoria.py#L50)

- La durabilidad se verifica desde una conexión distinta de la que escribió.
  [`test_postgres.py:159`](../../tests/test_postgres.py#L159)

- El doble de la fuente exige `$order` y ordena como Socrata.
  [`conftest.py:50`](../../tests/conftest.py#L50)
