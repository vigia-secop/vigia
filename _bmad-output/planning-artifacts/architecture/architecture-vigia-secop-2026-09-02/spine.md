---
title: "Architecture Spine — Vigía SECOP"
created: 2026-09-02
updated: 2026-09-02
status: draft
---

# Architecture Spine — Vigía SECOP

Deriva del PRD `prd-vigia-secop-2026-09-02` y de la investigación técnica de la API. Fija las decisiones que el código no puede contradecir.

## Paradigma de diseño

**Un pipeline por lotes con estado versionado, no un servicio en tiempo real.** El SECOP se actualiza por publicación, no por evento; el producto vive de la serie histórica, no de la latencia. Todo el sistema es una secuencia de transformaciones idempotentes sobre almacenamiento inmutable, con una capa delgada de revisión encima.

La consecuencia que importa: **cualquier Alerta debe poder recalcularse desde cero** con los datos y la versión de Regla registrados. Si una decisión de diseño impide eso, la decisión está mal.

## Invariantes heredadas del PRD

Vienen del producto, no de la ingeniería. No se negocian en implementación.

- **INV-1.** Ninguna Alerta existe sin Expediente completo (FR-8).
- **INV-2.** Ningún término acusatorio en superficies humanas; verificado por prueba automatizada (FR-9).
- **INV-3.** Ninguna Regla llega a `activa` sin haber corrido en `calibración` sobre un Recorte (FR-7).
- **INV-4.** Ninguna publicación sin aprobación humana explícita (FR-12).
- **INV-5.** Ningún nombre o identificación de persona natural sale en un Reporte publicado (FR-14).

## Invariantes y decisiones de arquitectura

### AD-1 — Almacenamiento por capas, crudo inmutable

Tres capas: **crudo** (respuesta de la API tal cual llegó, con fecha de consulta, nunca se modifica), **normalizado** (esquema unificado, DIVIPOLA resuelto, identidades agrupadas) y **derivado** (Alertas, Marcas, métricas, Reportes).

Reprocesar significa reconstruir normalizado y derivado desde crudo. El crudo es la única fuente de verdad y el seguro contra un cambio de esquema en la fuente: si CCE cambia un campo, el histórico ya ingerido sigue siendo reprocesable.

### AD-2 — Reglas como datos, no como código

Una Regla es un registro versionado: identificador de Bandera, versión, expresión evaluable, umbrales con vigencia, estado. Cambiar un umbral inserta una versión nueva; no actualiza en sitio.

Toda Alerta guarda el identificador de versión de Regla con que se emitió. Sin esto, la Tasa de confirmación por versión (FR-11) es incalculable y el Expediente miente.

### AD-3 — Identidad de Alerta determinista

La identidad de una Alerta es el hash de (registro fuente + versión de Regla + valores disparadores). Reejecutar un Ciclo sobre los mismos datos no crea Alertas duplicadas; un cambio de umbral sí crea Alertas nuevas, porque son otra afirmación.

Esto es lo que hace la ingesta segura de reintentar (FR-1) sin coordinación adicional.

### AD-4 — La marca de agua es por dataset, persistida y auditable

Cada dataset lleva su propio cursor de ingesta. Un Ciclo registra: cursor de entrada, cursor de salida, registros vistos, registros nuevos, huérfanos, errores. Un Ciclo vacío es un registro válido, distinguible de un fallo (FR-1).

### AD-5 — El mapeo territorial es una tabla versionada, no una función

El texto → DIVIPOLA vive en una tabla de correspondencias con versión y procedencia de cada entrada. Lo no resuelto va a una cola de no resueltos; nunca se resuelve por similitud automática (FR-3).

Razón: una asignación territorial equivocada contamina las comparaciones entre municipios y produce Alertas falsas indetectables. Prefiere el hueco visible al dato inventado.

### AD-6 — Los campos de persona natural se marcan en el esquema

Las columnas de personas naturales (`nombre_representante_legal`, `identificaci_n_representante_legal`, `nombre_ordenador_del_gasto`, `nombre_supervisor`, `nombre_ordenador_de_pago` y sus documentos) llevan una marca de sensibilidad en la definición del esquema.

Esa marca alimenta el filtro de publicación (INV-5): la verificación no busca nombres con heurística, compara contra los valores de las columnas marcadas del registro sustentador. Un filtro por lista de palabras sería evadible por accidente; este no.

### AD-7 — La compuerta de publicación es estructural

El componente que publica no tiene acceso a Alertas — solo a Reportes en estado `aprobado`. La transición a `aprobado` solo la produce una acción humana registrada.

No existe ruta de código desde el motor de reglas hasta la publicación. Es la traducción arquitectónica de INV-4: no se puede saltar por prisa porque no está conectado.

### AD-8 — Publicación manual asistida en v1

El sistema produce el borrador del Reporte (texto, cifras, enlaces, nota de indicador) y lo deja listo para copiar. No se integra la API de X en v1 (`ASSUMPTION-6`).

Evita costo, límites de tasa y credenciales, y mantiene un humano en el bucle de forma natural. Si la cadencia se vuelve cuello de botella, se automatiza el envío, nunca la aprobación.

## Convenciones de consistencia

- Los términos del glosario del PRD son los nombres de tablas, tipos y funciones. Sin sinónimos: si el glosario dice Marca, el código no dice `review` ni `flag`.
- Fechas en ISO 8601 y UTC en almacenamiento; presentación en hora local de Colombia.
- Todo valor monetario en pesos, entero, sin decimales; el dataset trae varios campos de valor y no se mezclan.
- Todo componente que consulta la API registra la fecha y hora de consulta junto al dato. Es requisito del Expediente, no telemetría.
- Un fallo de validación de esquema detiene el Ciclo y notifica. Nunca se degrada a nulos silenciosos.

## Stack propuesto

**Python** para todo el pipeline: es donde vive el ecosistema de datos, y Colombia Compra Eficiente publica sus propios ejemplos de consumo de Socrata en Python.

**PostgreSQL** como almacén único de las tres capas. El volumen nacional del SECOP es grande pero no exige nada exótico, y el motor de reglas se beneficia de SQL para las agregaciones comparativas (concentración por proveedor, percentiles por modalidad y sector). Crudo en JSONB, normalizado y derivado en tablas tipadas.

**Orquestación por cron sobre contenedor** en v1. Un Ciclo diario no justifica un orquestador de flujos; introducirlo ahora es complejidad prestada.

**Interfaz de revisión mínima**: la cola de Alertas, el Expediente y las Marcas. Es herramienta interna para una persona a la vez — no necesita framework de aplicación ni autenticación en v1, solo estar detrás de acceso restringido.

`[ASSUMPTION]` El stack asume que el equipo trabaja cómodo en Python y SQL. Si no, la decisión de lenguaje se revisa; las AD-1 a AD-8 no dependen de ella.

## Semilla estructural

```
vigia-secop/
├── ingest/          consulta a Socrata, marcas de agua, escritura a crudo
├── normalize/       esquema unificado, DIVIPOLA, identidad de proveedor
├── rules/
│   ├── catalog/     definiciones de Bandera y Regla (datos, versionadas)
│   └── engine/      evaluación, emisión de Alerta, construcción de Expediente
├── review/          cola, Marcas, Tasa de confirmación
├── publish/         armado de Reporte, filtro de sensibilidad, registro
├── schema/          definición de columnas y marcas de sensibilidad (AD-6)
└── tests/
    ├── territorial/ casos reales de variantes y homónimos (FR-3)
    ├── language/    prueba de vocabulario prohibido (INV-2)
    └── publication/ prueba de fuga de persona natural (INV-5)
```

## Mapa capacidad → arquitectura

| Requisito | Dónde vive | Invariante que lo protege |
|---|---|---|
| FR-1 Ingesta incremental | `ingest` | AD-4 marca de agua auditable |
| FR-2 Esquema unificado | `normalize` | AD-1 crudo reprocesable |
| FR-3 Territorial | `normalize` + `tests/territorial` | AD-5 tabla versionada, cola de no resueltos |
| FR-4 Identidad de proveedor | `normalize` | AD-1 |
| FR-5 Reglas versionadas | `rules/catalog` | AD-2 reglas como datos |
| FR-6 Catálogo v1 | `rules/catalog` | AD-2 |
| FR-7 Modo calibración | `rules/engine` | INV-3 |
| FR-8 Expediente | `rules/engine` | AD-3 identidad determinista |
| FR-9 Lenguaje | `tests/language` | INV-2 |
| FR-10 Marcas | `review` | — |
| FR-11 Tasa de confirmación | `review` | AD-2 versión en cada Alerta |
| FR-12 Compuerta humana | `publish` | AD-7 sin ruta de código |
| FR-13 Agregado por defecto | `publish` | — |
| FR-14 Sin personas naturales | `publish` + `schema` | AD-6 marca de sensibilidad |
| FR-15 Sustento visible | `publish` | AD-3 |
| FR-16 Registro y rectificación | `publish` | — |

## Aplazado

- **SECOP I y TVEC.** El esquema normalizado debe admitirlos sin rediseño; no se implementan en v1.
- **Escalamiento del Ciclo.** Si el Ciclo diario nacional no cabe en la ventana, se pasa a Recortes rotativos (`ASSUMPTION-5`). Se mide antes de optimizar.
- **API de X.** AD-8.
- **Cruces externos** (RUES, sanciones, societarios). El modelo de identidad de Proveedor debe dejar espacio para ellos.
- **Autenticación y multiusuario.** Cuando salga del equipo.

## Riesgo abierto

El concepto jurídico sigue siendo bloqueante para `publish`. El resto del sistema puede construirse en paralelo; el primer Reporte publicado no debe salir antes de tenerlo.
