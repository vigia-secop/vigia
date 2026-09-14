---
title: "Investigación técnica — Viabilidad de las banderas contra la API del SECOP"
status: complete
created: 2026-09-02
updated: 2026-09-02
---

# Investigación técnica — Viabilidad de las banderas contra la API del SECOP

Este documento resuelve la pregunta abierta #1 del brief: **qué campos entrega realmente la API y qué banderas son viables**. Se inspeccionó el esquema real de los dos datasets principales publicados por Colombia Compra Eficiente en datos.gov.co.

## Datasets inspeccionados

| Dataset | ID | Columnas | Grano |
|---|---|---|---|
| SECOP II — Contratos electrónicos | `jbjy-vk9h` | 85 | Un contrato firmado |
| SECOP II — Procesos de contratación | `p6dx-8zbt` | 50 | Un proceso, adjudicado o no |

Colombia Compra Eficiente confirma además una tercera fuente que el brief no contemplaba: **TVEC** (Tienda Virtual del Estado Colombiano), con compras por catálogo de acuerdo marco. Queda anotada para v2.

Ambos datasets se consultan por API Socrata sin credenciales, con filtros y paginación (`$where`, `$select`, `$limit`, `$offset`).

## Veredicto por bandera

### ✅ Viables con los campos actuales

**Oferente único.** El dataset de procesos trae la cadena completa de participación: `proveedores_invitados`, `proveedores_que_manifestaron`, `respuestas_al_procedimiento`, `proveedores_unicos_con` y `cantidad_de_ganadores`. Es la bandera mejor soportada de todo el catálogo, y además permite una versión más fina que la planteada: no solo "un solo proponente", sino el **embudo** — muchos invitados, muchas visualizaciones, una sola respuesta.

**Concentración por NIT.** `documento_proveedor` y `codigo_proveedor` en contratos, `nit_del_proveedor_ganador` en procesos, cruzados contra `nit_entidad` y `valor_del_contrato`. Directo.

**Plazo exprés.** Mejor de lo esperado: procesos trae `fecha_de_publicacion_del` y `fecha_de_adjudicacion` en el mismo registro, más `modalidad_de_contratacion` para comparar contra pares. No requiere cruzar datasets.

**Posible fraccionamiento.** `valor_del_contrato`, `documento_proveedor`, `fecha_de_firma`, `objeto_del_contrato`, `descripcion_del_proceso` y `modalidad_de_contratacion`. Viable, con la salvedad de que la similitud de objeto exige comparación de texto, no igualdad exacta.

### ⚠️ Viables con reformulación

**Adiciones al límite — reformular.** Hallazgo importante: **no existe un campo de valor de adición.** El único campo relacionado es `dias_adicionados` (número), que captura prórrogas en tiempo, no en dinero. La bandera tal como estaba escrita en el brief no es calculable con estos datasets.

Reformulación viable: detectar **prórrogas en tiempo** vía `dias_adicionados` contra `duraci_n_del_contrato`, y **desviación en dinero** comparando `valor_del_contrato` contra `valor_del_contrato_adjudicado` del proceso original. El delta entre lo adjudicado y lo contratado es la señal recuperable.

**Anomalía territorial — corregir el supuesto.** El brief y el addendum asumían que los datasets traen el código DIVIPOLA del DANE. **No lo traen.** Lo que hay es `departamento` y `ciudad` como **texto libre** en contratos, y `departamento_entidad` / `ciudad_entidad` en procesos. Hay `codigo_entidad`, que identifica la entidad, no el territorio.

Consecuencia: hace falta una tabla de mapeo texto → DIVIPOLA, con normalización de tildes, mayúsculas y variantes de escritura. Es trabajo real y una fuente probable de error silencioso. Debe ser una historia propia con pruebas.

### ❌ No viables en v1

**Contratista reciente.** Confirmado: no hay fecha de constitución ni antigüedad del proveedor en ninguno de los dos datasets. Requiere RUES o cámaras de comercio. Sale de la v1, como ya anticipaba el addendum.

## Banderas nuevas que los datos habilitan

La inspección reveló campos que no estaban en el catálogo original y que soportan señales más fuertes que varias de las planteadas.

**Representante legal compartido.** ⭐ Contratos trae `nombre_representante_legal` e `identificaci_n_representante_legal`. Esto permite detectar una misma persona natural como representante de múltiples proveedores adjudicados por la misma entidad — el patrón clásico de sociedades de fachada. Es probablemente la bandera más potente de todo el catálogo y no estaba contemplada.

**Adjudicación pegada al presupuesto oficial.** ⭐ Procesos trae `precio_base` y `valor_del_contrato_adjudicado`. La razón entre ambos permite detectar adjudicaciones sospechosamente cercanas al 100% del presupuesto estimado, señal reconocida de información filtrada.

**Concentración por ordenador del gasto.** Contratos trae `nombre_ordenador_del_gasto`, `nombre_supervisor` y sus documentos. Permite mover el análisis del nivel entidad al nivel funcionario: qué ordenador concentra adjudicaciones sobre los mismos proveedores.

**Ejecución anómala.** `valor_del_contrato`, `valor_facturado`, `valor_pagado`, `valor_amortizado`, `valor_pendiente_de_ejecucion` y `saldo_cdp` permiten detectar pagos que superan lo facturado o contratos pagados sin ejecución.

**Focalización por fuente de recursos.** `sistema_general_de_regal_as`, `sistema_general_de_participaciones`, `presupuesto_general_de_la_nacion_pgn`, `recursos_de_credito` y `origen_de_los_recursos` permiten priorizar alertas sobre regalías, históricamente el foco de mayor riesgo.

**Contratación directa sin justificación sólida.** `modalidad_de_contratacion` con `justificacion_modalidad_de` y `justificaci_n_modalidad_de` permite auditar el texto de justificación en directa.

## Regalo para la trazabilidad

Contratos trae **`urlproceso`** (tipo url): el enlace directo al expediente público del proceso. Esto resuelve el requisito de trazabilidad casi gratis — cada alerta puede enlazar al documento fuente sin construir nada. Debe ser campo obligatorio del expediente de alerta.

## Consecuencias para el PRD

1. La bandera de adiciones **cambia de definición**; no se puede escribir como estaba.
2. El mapeo territorial es **una historia con pruebas propias**, no un detalle de implementación.
3. Entran al catálogo **cinco banderas nuevas**, dos de ellas (representante legal compartido, adjudicación pegada al presupuesto) más fuertes que varias de las originales.
4. `urlproceso` es el ancla de trazabilidad.
5. TVEC queda registrado como fuente de v2.
