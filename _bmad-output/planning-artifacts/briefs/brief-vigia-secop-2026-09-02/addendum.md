---
title: "Addendum — Vigía SECOP"
status: draft
created: 2026-09-02
updated: 2026-09-02
---

# Addendum — Vigía SECOP

Detalle que no cabe en el brief pero que el PRD y la arquitectura necesitan leer.

## Fuentes de datos

Todo el insumo primario es público y consultable por API (Socrata) sobre datos.gov.co. No se requiere scraping ni credenciales.

| Fuente | Aporta | Identificador |
|---|---|---|
| SECOP II — Procesos de contratación | Modalidad, objeto, valor estimado, fechas del proceso, proponentes | `p6dx-8zbt` |
| SECOP II — Contratos electrónicos | Contratos firmados, valor, adiciones, plazos, contratista, entidad | `jbjy-vk9h` |
| SECOP I (histórico) | Serie previa a SECOP II; necesaria para líneas base y detección de reincidencia | datos.gov.co |
| DIVIPOLA — DANE | Código de departamento y municipio; es la llave territorial correcta en Colombia | `cod_dane` |
| NIT | Llave para unir contratista con entidad; base de concentración y reincidencia | `nit` |

**Nota de vocabulario.** En Colombia la granularidad territorial no es el *ZIP code* sino el código DIVIPOLA del DANE, y viene en los datasets. Cualquier diseño que asuma códigos postales está mal planteado desde la raíz.

**Riesgo de ingesta.** SECOP I y SECOP II tienen esquemas distintos. La normalización entre ambos no es trivial y es la primera fuente probable de error silencioso. Debe tener pruebas propias.

## Catálogo inicial de banderas

Estas son **hipótesis a validar**, no reglas confirmadas. La fase de investigación técnica debe verificar, una por una, que los campos necesarios existen en la API antes de que entren al PRD como requisito.

| Bandera | Señal | Prioridad | Depende de |
|---|---|---|---|
| Oferente único | Procesos competitivos que terminan con un solo proponente habilitado | Alta | Número de proponentes en el proceso |
| Posible fraccionamiento | Varios contratos de objeto similar, mismo contratista, fechas cercanas, cada uno justo bajo el umbral de la siguiente modalidad | Alta | Objeto, valor, fecha, NIT, umbrales vigentes |
| Adiciones al límite | Adiciones que se acercan al tope legal frente al valor inicial | Alta | Valor inicial y adiciones registradas |
| Concentración por NIT | Un contratista concentra una porción atípica del gasto de una entidad frente a entidades comparables | Media | NIT contratista, NIT entidad, valores |
| Plazo exprés | Días entre publicación y adjudicación muy por debajo de lo habitual en esa modalidad y sector | Media | Fechas del proceso, modalidad |
| Contratista reciente | Adjudicación de monto alto a un NIT de registro mercantil muy nuevo | Media | Fuente externa (RUES) — **fuera de la v1** |
| Anomalía territorial | Gasto per cápita fuera de rango frente a municipios de categoría y población similares | Exploratoria | DIVIPOLA + proyecciones de población DANE |

**Advertencia sobre umbrales legales.** Los topes de modalidad y de adiciones dependen de normativa vigente y de la categoría de la entidad. No deben quemarse en código: van como configuración con fecha de vigencia, y su verificación normativa es una tarea explícita del PRD, no un supuesto del desarrollador.

## Decisiones tomadas en esta sesión

- **Alcance nacional con segmentación**, en vez de piloto acotado. Decisión del usuario. Mitigación propuesta: calibrar cada regla sobre un recorte controlado antes de activarla a nivel nacional.
- **Usuario de la v1 es el equipo interno.** El producto no se abre a terceros hasta que la tasa de confirmación sea aceptable.
- **Producto comercial como intención declarada**, con el comprador aún sin definir. Es una pregunta abierta, no un supuesto resuelto.
- **Sin modelos de machine learning en la v1.** Reglas explícitas primero; un modelo sobre reglas sin calibrar solo agrega opacidad.
- **Módulo BMB no instalado.** El instalador falló al resolverlo por un problema de credenciales de GitHub en el entorno. No bloquea nada: BMB sirve para construir agentes propios, no para este flujo.

## Referencia de inspiración

Albania nombró en 2025 a *Diella*, una IA encargada de la contratación pública, presentada como medida anticorrupción. El experimento recibió críticas centradas en rendición de cuentas y en la ausencia de responsabilidad humana clara. La lectura relevante para este proyecto: el error de diseño no fue automatizar el análisis, sino situar a la máquina en la posición de decidir. Vigía SECOP señala y sustenta; la decisión sigue siendo humana.
