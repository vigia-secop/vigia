---
story: 1.5 — Identidad canónica de Proveedor
status: review
implementada: 2026-09-04
incluye: 1.5b — Uniones Temporales y Consorcios sin documento
migraciones: 006_proveedor.sql, 007_grupo_provisional.sql
pruebas: 286 en verde contra PostgreSQL real
---

# Historia 1.5 — Identidad canónica de Proveedor

## 1. El problema

El mismo contratista aparece en el SECOP con el documento escrito de varias
formas —`900123456`, `900.123.456`, `900123456-5`— y con la razón social
escrita de varias más. Sin reducirlo a una identidad, «concentración por
proveedor» (4.3) cuenta a uno como tres y no detecta nada.

## 2. Lo que se midió antes de diseñar

Contra `jbjy-vk9h` el 2026-09-04, sobre los ~6,02 millones de contratos del
histórico nacional. **Ninguna decisión de este documento se tomó sin número
delante**, y la única que se tomó sin él resultó falsa (§6).

| Medición | Resultado |
|---|---|
| Contratos con Cédula de Ciudadanía | 4 929 133 (82,4 %) |
| Contratos con NIT | 900 513 |
| Documento literal «No Definido» | 175 836 |
| Documentos NIT de 9 caracteres | ~90 % |
| NIT de 10 dígitos que empiezan por 8 o 9 y verifican su DV | 16 de 16 |
| NIT de 10 dígitos que empiezan por 1 y verifican su DV | 1 de 9 |

**El proveedor típico del SECOP no es una empresa, es una persona.** Eso mueve
el peso de la 5.2 (filtro de persona natural) de detalle de privacidad a
decisión sobre cuatro de cada cinco contratos.

## 3. Las tres reglas de canonización

1. **Se quitan puntos, guiones y espacios**, y se pasa a mayúsculas sin tildes.
2. **Un documento sin un solo dígito no es un documento.** No es una lista de
   centinelas —«No Definido», «N/A», «SIN DOCUMENTO»—, porque una lista siempre
   se queda corta. Es la propiedad que todos comparten.
3. **Se quita el dígito de verificación solo si** el tipo es NIT **y** el número
   tiene diez dígitos **y** empieza por 8 o 9 **y** el décimo es el DV de los
   nueve anteriores.

La tercera regla es deliberadamente estrecha. La fuente etiqueta como «NIT»
muchas cédulas de diez dígitos que empiezan por 1, y a una de cada once le
cuadra el DV por azar: quitárselo la convertiría en otra persona. Queda sin
cubrir el NIT de persona natural cuya cédula empieza por 1, que contará como
dos proveedores si aparece con y sin DV.

> **El principio que decide todos los empates de este módulo:** separar de más
> subestima una concentración; unir de más la inventa, y una alerta inventada
> es exactamente lo que este proyecto no se puede permitir.

## 4. La identidad es (tipo, número)

El tipo forma parte de la llave a propósito: un NIT `900123456` y una cédula
`900123456` son dos entidades distintas del mundo.

Las variantes de nombre **no se descartan**: quedan en `proveedor_variante`,
consultables. Un mismo documento con tres razones sociales es en sí mismo una
señal, y el Expediente de la épica 2 tendrá que mostrarlas. El nombre principal
es el más frecuente, con desempate alfabético para que dos corridas sobre los
mismos datos den lo mismo.

## 5. El error que esto evita

Canonizar «a lo bruto» habría convertido los 175 836 contratos con «No
Definido» en un único proveedor `NODEFINIDO`: al instante, el contratista más
concentrado de Colombia. Una alerta de primera magnitud, y falsa entera.

# 1.5b — Uniones Temporales y Consorcios

## 6. Una afirmación mía que era falsa

Al cerrar la 1.5 escribí, en el código y en `deferred-work.md`, que esos
175 836 contratos eran «casi todos» Uniones Temporales y Consorcios. **No lo
había medido**: lo deduje de haber visto tres nombres de UT en una muestra
pequeña. Guillermo tomó la nota por buena y preguntó, con razón, cómo evitar
que esos contratos quedaran volando.

Medido el 2026-09-04, de los 175 836:

| Estado | Contratos |
|---|---|
| Borrador | 91 448 |
| Cancelado | 69 095 |
| **nunca adjudicaron a nadie** | **160 543 (91,3 %)** |
| contratos de verdad | **15 293 (8,7 %)** |

Y de los 15 293 reales, **15 291 —el 99,99 %— traen `es_grupo = 'Si'`**.

El universo de contratos de grupo son 39 767, y **25 866 ya traen NIT**: una
unión temporal en Colombia tiene NIT propio. El hueco nunca fueron «las uniones
temporales»: es la parte de ellas a la que la entidad no le diligenció el
documento. El error sobredimensionaba el problema por once y apuntaba a la
solución equivocada.

## 7. La regla

Un contrato cuyo documento no sirve **y** viene marcado `es_grupo = 'Si'`
recibe una identidad **provisional**, con el tipo reservado
`UNION TEMPORAL O CONSORCIO SIN DOCUMENTO` y, como número, **el identificador
de su propio contrato**.

Los demás —los borradores y cancelados— siguen sin identidad. No tienen
proveedor porque nunca lo tuvieron; inventárselo sería peor que dejarlos fuera.

## 8. Por qué una identidad por contrato y no por nombre

| Opción | Qué pasa |
|---|---|
| Fundirlas todas en un proveedor | Crea el contratista más concentrado del país. Falso. Es el error que la 1.5 existe para no cometer. |
| Agruparlas por el nombre | El nombre lo teclea cada entidad y no es único en Colombia. Dos «UNION TEMPORAL SALUD 2024» distintas se fundirían en una concentración inventada. |
| **Una identidad por contrato** | No funde nada y no deja nada fuera del conteo. Es el único que no puede equivocarse en ninguna de las dos direcciones. |

El nombre igual queda registrado como variante, así que la historia que sí
quiera juntarlas tendrá con qué, y con evidencia.

**Lo que una identidad provisional NO habilita:** medir concentración. Por
construcción hay exactamente una por contrato, así que jamás podrá encabezar un
ranking. La 4.3 tiene que excluirlas del ranking **y** reportar su total —que
es exactamente lo contrario de esconderlas.

## 9. Marca generada, no bandera escrita

`proveedor.provisional` y `contrato.proveedor_provisional` son columnas
`GENERATED ALWAYS AS ... STORED` derivadas del tipo de documento. Una bandera
que escribe Python puede quedar desincronizada del tipo, y entonces la base
diría una cosa y el reporte otra. Generada, no puede: es el tipo.

En `contrato` la columna tiene tres estados y los tres significan cosas
distintas: `true` (unión temporal contada pero no vigilable), `false`
(identidad real) y `NULL` (sin identidad ninguna).

## 10. Lo que queda pendiente

1. **La cifra en dinero** del hueco nacional. Las consultas están escritas en
   `medir_uniones.py`; la fuente dejó de responder agregados a mitad de sesión
   y **el número no se inventó**.
2. **Identidad real** de esas uniones (historia 1.8): los integrantes no están
   en `jbjy-vk9h`. Habría que mirar el dataset de procesos o la ficha de
   SECOP II. Hoy es una mejora, no un agujero: los contratos ya se cuentan, se
   suman y se listan uno a uno en `reporte.sql`.
