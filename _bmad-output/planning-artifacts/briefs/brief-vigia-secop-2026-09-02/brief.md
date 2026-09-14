---
title: "Product Brief: Vigía SECOP"
status: draft
created: 2026-09-02
updated: 2026-09-02
---

# Product Brief: Vigía SECOP

## Resumen ejecutivo

Vigía SECOP es un sistema de detección de patrones atípicos en la contratación pública colombiana. Consume los datos abiertos del SECOP, los normaliza, les aplica un catálogo de reglas calibradas y emite alertas trazables: cada alerta señala un registro concreto, la regla que la disparó y el umbral usado.

El punto de partida es una observación simple: los datos ya son públicos y nadie los está mirando de forma sistemática. Colombia publica procesos, contratos, adiciones y contratistas en datos.gov.co con API abierta. Lo que no existe es la capa que cruza esos registros de manera continua y convierte el volumen en un puñado de casos que valen la pena revisar. Albania intentó resolverlo nombrando una IA ministra de contratación; Brasil explora caminos parecidos. La diferencia de enfoque aquí es deliberada: Vigía SECOP no decide ni adjudica. Señala.

La versión 1 se construye para uso interno del equipo, no para el mercado. La razón es de método: hasta que las reglas no estén calibradas contra datos reales y con una tasa de falsos positivos aceptable, sacarlo a usuarios externos destruye la confianza en el producto. El modelo comercial se define sobre reglas que ya demostraron funcionar. `[ASSUMPTION]`

## El problema

El SECOP es un archivo, no una herramienta de control. Está publicado, es consultable, y en la práctica es inabordable: millones de registros, campos heterogéneos entre SECOP I y II, y ninguna capa que diga dónde mirar. Quien quiere investigar una contratación específica puede hacerlo; quien quiere detectar dónde hay algo que investigar, no.

El resultado es que la detección hoy depende de una denuncia previa, de una filtración o de la intuición de alguien que ya sospechaba. Es decir: el control llega después del daño, y solo donde alguien estaba mirando. Los patrones que sí son detectables por cruce de datos — un contratista que concentra el gasto de una entidad, adiciones repetidas al límite, procesos competitivos que terminan con un solo oferente — pasan sin que nadie los vea, no por opacidad, sino por volumen.

## La solución

Un motor que corre de forma recurrente sobre los datasets del SECOP y produce un flujo de alertas priorizadas. Cada alerta responde tres cosas: qué se detectó, sobre qué registro, y con qué criterio.

Tres piezas:

**Ingesta y normalización.** Consulta incremental de los datasets del SECOP vía API, unificación de campos entre SECOP I y II, y llaves consistentes de contratista (NIT) y territorio (código DIVIPOLA del DANE).

**Motor de reglas.** Un catálogo de banderas rojas expresadas como reglas con umbrales configurables, no como modelos opacos. La configurabilidad no es un lujo: es lo que permite calibrar contra falsos positivos y lo que hace defendible cada alerta.

**Capa de alertas.** Priorización, agrupación por entidad y territorio, y un expediente por alerta con el registro fuente, la regla, el umbral y la fecha de consulta.

## Qué lo hace diferente

Conviene ser honesto sobre el foso, porque aquí no hay uno técnico. Los datos son públicos, la API es abierta y cualquiera con conocimiento de Python puede replicar la ingesta en un fin de semana. Lo que no se replica en un fin de semana es lo siguiente:

**El catálogo calibrado.** Una regla sin umbral validado contra datos reales produce ruido. El valor está en saber que la bandera de fraccionamiento dispara con este umbral y no con aquel, y qué proporción de esas alertas sobrevive a revisión humana. Eso solo se construye corriendo el sistema.

**La disciplina de trazabilidad.** Un producto que señala irregularidades en contratación pública y no puede sustentar cada señal es un pasivo legal, no un activo. Construir la trazabilidad desde el diseño es una decisión de arquitectura difícil de retrofitear.

**La continuidad.** El valor no está en una consulta puntual sino en la serie histórica: detectar que un patrón se repite requiere haber estado mirando antes.

Dicho eso, el diferenciador real en el corto plazo es la ejecución y la ventaja de haber empezado. No hay que fabricar más moat del que hay.

## A quién sirve

**Usuario de la v1 — el equipo.** Quienes construyen y calibran las reglas. Necesitan ver el detalle crudo, ajustar umbrales, marcar falsos positivos y medir qué tanto mejora el catálogo. Este es el único usuario de la primera versión.

**Compradores potenciales — a validar.** El brief no asume todavía a quién se le vende. Los candidatos plausibles: entes de control y oficinas de control interno; medios y unidades de investigación; firmas de auditoría y consultoría; y áreas de cumplimiento que necesitan verificar contrapartes antes de contratar. `[ASSUMPTION]` Cada uno de esos segmentos compra por razones distintas y con ciclos de venta muy distintos; elegir entre ellos es trabajo del PRD, no de este brief.

## Criterios de éxito

La métrica que gobierna todo es la **tasa de confirmación**: de cada cien alertas emitidas, cuántas un revisor humano clasifica como "efectivamente amerita revisión". Un sistema con tasa baja se ignora, y un sistema ignorado no tiene valor comercial ni cívico.

Alrededor de esa:

- Cobertura: qué proporción del universo de contratos evaluado sin errores de ingesta.
- Tiempo de verificación: cuánto tarda un humano en decidir si una alerta merece seguimiento. Si tarda más que buscar a mano, el producto falló.
- Estabilidad de la serie: la ingesta incremental corre sin intervención durante semanas.
- Reglas vivas: cuántas banderas del catálogo inicial sobreviven a la calibración. Es legítimo — y esperado — que varias se descarten.

## Alcance

**Dentro de la v1.** Ingesta de SECOP I y II con normalización por NIT y DIVIPOLA. Un catálogo inicial de banderas con umbrales configurables (detalle en el addendum). Expediente de trazabilidad por alerta. Segmentación por departamento, sector y modalidad sobre el universo nacional. Interfaz mínima para que el equipo revise, marque y calibre.

**Fuera de la v1.** Cuentas de usuario y permisos. Notificaciones a terceros. Publicación abierta de alertas. Cruces con fuentes fuera del SECOP — registro mercantil, sanciones, declaraciones de renta, parentescos. Modelos de aprendizaje automático: mientras las reglas explícitas no estén calibradas, un modelo solo agrega opacidad.

**Tensión conocida.** Se decidió trabajar sobre el universo nacional completo, con capacidad de segmentar por departamento, sector y modalidad, en vez de acotar el piloto a un recorte. Es más ambicioso y da más señal, pero multiplica el costo de ingesta y el ruido durante la calibración. La mitigación propuesta: procesar todo, pero **calibrar cada regla sobre un recorte controlado antes de activarla a nivel nacional**. `[ASSUMPTION]` Vale la pena confirmar esta decisión en el PRD.

## Restricciones de diseño

Dos reglas que no son preferencias sino condiciones de existencia del producto:

**Una alerta es un indicador, no una acusación.** El lenguaje del producto lo debe reflejar en toda la superficie: "patrón atípico que amerita revisión", nunca "contrato irregular". Es el debate que enfrentó Diella en Albania y es lo que separa una herramienta de control de un generador de escándalos.

**Todo hallazgo debe ser trazable.** Registro fuente, regla, umbral y fecha de consulta. Lo que no es verificable no es defendible, y en este dominio lo indefendible es un riesgo legal directo.

## Visión

Si funciona, Vigía SECOP deja de ser un detector y se vuelve infraestructura: la capa que cualquiera —periodista, veeduría, auditor, empresa— consulta antes de decidir dónde mirar. La serie histórica se vuelve el activo, porque permite responder no solo "esto es atípico" sino "esto viene siendo atípico desde hace tres años".

El horizonte natural es la expansión de fuentes: cruzar el SECOP con registro mercantil, sanciones e inhabilidades, y datos societarios, hasta que la pregunta que el sistema responde deje de ser "¿este contrato es raro?" y pase a ser "¿esta red de actores es rara?".

---

## Preguntas abiertas

1. ¿Qué campos entrega realmente la API del SECOP? Varias banderas del catálogo dependen de datos que aún no se ha confirmado que existan. Es lo primero que debe resolver la investigación técnica.
2. ¿Quién es el comprador de la v2 y por qué pagaría? Sin esto, "producto comercial" es una intención, no un plan.
3. ¿Cuál es el umbral de tasa de confirmación por debajo del cual una regla se descarta?
4. ¿Qué exposición legal existe al emitir alertas sobre entidades y contratistas identificados por nombre, incluso con lenguaje cauto?
