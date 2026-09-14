---
title: "Propuesta de cambio de sprint — «Oferente único» describe la mayoría, no la excepción"
created: 2026-09-06
status: propuesta
disparador: "Medición del embudo de la historia 2.4 sobre 341 549 procesos reales, 2026-09-06"
alcance: mayor
decide: Guillermo
---

# Propuesta de cambio de sprint — «Oferente único» describe la mayoría, no la excepción

## 1. Resumen del problema

La historia 2.4 pide detectar «procesos competitivos que terminan con un solo
proponente», con la premisa implícita de que eso es notable.

**No lo es. Es el desenlace mayoritario.**

De los **2 176 procesos competitivos adjudicados** de la base, **1 150 —el
52,8 %— terminaron con un solo proveedor único.** Una Regla que marque eso
enciende sobre más de la mitad de su propio universo. No es una señal: es la
forma normal de contratar en Colombia.

## 2. Qué se midió

Sobre 341 549 procesos, 9 942 adjudicados (2,9 %). De esos, 2 176 en las ocho
modalidades competitivas.

### 2.1. El total

| Medición | Procesos |
|---|---|
| Competitivos adjudicados | 2 176 |
| **Con un solo proveedor único** | **1 150 (52,8 %)** |
| …y además con más de 1 visualización | 1 133 |
| …y además con más de 5 | 987 |
| …y además con más de 20 | **459** |

Valor adjudicado de esos 1 150: **$768 502 882 210**. Promedio de 20,3
visualizaciones y 3,8 invitados.

### 2.2. Por modalidad

| Modalidad | Adjudicados | Un solo proveedor | % |
|---|---|---|---|
| Selección Abreviada de Menor Cuantía | 1 176 | 677 | 57,6 |
| Selección abreviada subasta inversa | 648 | 299 | 46,1 |
| Concurso de méritos abierto | 165 | 85 | 51,5 |
| Licitación pública | 119 | 69 | **58,0** |
| Licitación pública Obra Pública | 41 | 10 | **24,4** |
| Enajenación de bienes con sobre cerrado | 15 | 3 | 20,0 |
| Enajenación de bienes con subasta | 5 | 3 | 60,0 |

**El oferente único es la norma en casi todas.** Las dos excepciones —Obra
Pública con 24,4 % y Enajenación con sobre cerrado con 20 %— son justamente
donde hay activo físico y pliego largo.

### 2.3. Los quince mayores

Todos son Licitación pública, con 14 a 77 visualizaciones y una sola respuesta.
El mayor: **$72 001 177 364**. En los quince, `proveedores_invitados = 0`, lo
que confirma que ese contador no sirve.

## 3. Por qué esto no se arregla subiendo el umbral

Se puede recortar con visualizaciones: exigir más de 20 baja de 1 150 a 459.
Pero **el 20 es inventado**. Nada en los datos dice que 20 sea el corte; se
elige porque da un número que cabe en una cola, que es exactamente la forma de
razonar que este proyecto no puede permitirse. Un umbral escogido para que el
resultado quepa no mide nada del mundo.

Y hay un problema más de fondo: **459 alertas siguen sin ser una señal si el
52,8 % es el fondo**. Marcar «uno de cada dos» con un filtro encima sigue
marcando lo normal, solo que menos veces.

## 4. Lo que sí distingue

La pregunta útil no es *«¿hubo un solo oferente?»* sino ***«¿este proceso se
comportó distinto de los comparables?»***

Es la misma forma que la historia 4.5 ya estableció para el plazo exprés —«por
debajo del percentil configurado de su modalidad y sector»— y que se adoptó
allí por la misma razón: medido, un umbral global marcaba el 64,7 % de los
contratos y el criterio por modalidad separaba limpio.

Aplicado aquí, el candidato es **el embudo estrecho relativo**: procesos con
una sola respuesta cuya atención recibida —visualizaciones— está en el extremo
alto **de su propia modalidad**. Un proceso que nadie miró y nadie ofertó no
dice nada; un proceso que miraron cuarenta y ofertó uno, sí.

## 5. Cambio propuesto

**5.1.** Renombrar la Regla de `oferente-unico` a **`embudo-estrecho`**, y
reescribir su criterio: se enciende cuando un proceso competitivo adjudicado
tiene proveedores únicos por debajo del umbral **y** visualizaciones por encima
del percentil configurado **de su modalidad**.

**5.2.** Los umbrales de la nueva versión son dos, y los dos son
configurables: `proveedores_unicos_maximos` y `percentil_de_visualizaciones`.
Ninguno se escribe en el código.

**5.3.** El Expediente no cambia: sigue llevando el embudo completo. Lo que
cambia es qué lo dispara.

**5.4.** La medición que falta para fijar el percentil, y que se puede correr
hoy: **la distribución de visualizaciones dentro de cada modalidad
competitiva, separando los procesos de un solo proveedor de los de varios.** Si
las dos distribuciones se parecen, ni siquiera el embudo relativo discrimina y
la bandera hay que descartarla. Si se separan, el punto donde se separan es el
percentil.

**5.5.** Añadir una `ASSUMPTION` al PRD: «En Colombia, que un proceso
competitivo termine con un solo proponente es el desenlace mayoritario
(52,8 %, medido). Ninguna Regla puede tratarlo como anomalía por sí solo.»

## 6. Alternativas descartadas

**Dejar la Regla como está y calibrar el umbral.** No hay umbral que arregle
que el fenómeno sea mayoritario. Se descarta.

**Subir el corte de visualizaciones hasta que quepa en la cola.** Es elegir el
umbral por el tamaño del resultado y no por el mundo. Es la forma de razonar
que produce alertas inventadas.

**Combinar con el valor del contrato.** Un solo oferente en una licitación de
$72 000 millones no es lo mismo que en una menor cuantía. La idea es buena y
probablemente entre después, pero mezclar dos criterios sin haber medido
ninguno hace imposible saber cuál está funcionando. Va a una historia propia.

**Descartar la bandera.** Prematuro: los 1 150 procesos mueven $768 502 882 210
y el embudo estrecho todavía no se ha medido de forma relativa. Descartarla
antes de esa medición sería tan poco fundado como activarla.

## 7. Qué hay que aprobar

1. Reabrir la historia **2.4**, hoy en `review`, para cambiar el criterio de la
   Regla de absoluto a relativo por modalidad.
2. Correr la medición de la §5.4 **antes** de escribir la versión nueva.
3. Aceptar que la Regla siga en `borrador` hasta que esa medición exista. Hoy
   no puede activarse, y el código ya lo impide.

---

# RESOLUCIÓN — 2026-09-06, después de correr la §5.4

**La bandera se descarta.** No se renombra, no se recalibra, no se aplaza.

## El número

Se midió la distribución de visualizaciones de los **2 334 procesos
competitivos adjudicados**, separando los de un solo proveedor de los de
varios. La §5.4 decía: «si las dos distribuciones se parecen, la bandera hay
que descartarla; si se separan, el punto donde se separan es el percentil».

**Se separan. Al revés.**

| Grupo | Procesos | p25 | Mediana | p75 | p90 | Promedio |
|---|---|---|---|---|---|---|
| Un solo proveedor | 1 239 | 8 | **16** | 27 | 41 | 20,1 |
| Varios proveedores | 1 095 | 18 | **32** | 53 | 78 | 41,5 |

La hipótesis del embudo estrecho era: *«un proceso que miraron cuarenta y
ofertó uno, sí dice algo»*. Los datos dicen que un proceso que termina con una
sola oferta es, por regla, **uno que nadie miró**. La atención no es alta y la
respuesta baja: las dos son bajas a la vez.

Y la cola confirma: solo **30 de 1 239 (2,4 %)** superan el p90 de su propia
modalidad. Si los de un oferente se repartieran como los demás, serían ~124.
Están **infrarrepresentados** en la cola de atención, no sobrerrepresentados.
La Regla propuesta habría marcado exactamente el grupo equivocado.

## Por modalidad

| Modalidad | Con uno | Mediana | Con varios | Mediana |
|---|---|---|---|---|
| Selección Abreviada de Menor Cuantía | 727 | 14 | 532 | 30 |
| Selección abreviada subasta inversa | 325 | 16 | 369 | 30 |
| Concurso de méritos abierto | 91 | 21 | 88 | 48 |
| **Licitación pública** | **76** | **28** | **53** | **29** |
| Licitación pública Obra Pública | 10 | 38 | 34 | 57 |
| Enajenación con sobre cerrado | 3 | 5 | 12 | 16 |

En todas la mediana con un oferente es la mitad, **menos en licitación
pública, donde 28 contra 29 es la misma**. Es el único sitio donde la atención
no predice cuántos se presentan.

Es tentador construir la bandera ahí. **No se hace, y por dos razones.** La
primera es que 76 contra 53 procesos no distingue «no hay diferencia» de «la
diferencia es más pequeña que lo que esta muestra puede ver»: con esos números
las dos frases son la misma. La segunda es la que importa más: elegir la única
celda de la tabla donde el efecto desaparece, después de haber mirado la tabla
entera, es exactamente el mismo error que elegir el umbral por el tamaño de la
cola. Se busca hasta encontrar, y se encuentra siempre.

## Qué se decide

1. **La historia 2.4 pasa a `descartada`**, no a `review`. La Regla no existe.
2. **El código del motor se queda entero.** Regla versionada, identidad de
   Alerta, Expediente obligatorio, modo calibración, vocabulario prohibido: son
   la épica 2 y siguen en pie. Lo que se cae es la primera inquilina, no la
   casa. La segunda Regla los estrena sin cambiar una línea.
3. **Los 30 procesos sobre el p90 de su modalidad** siguen visibles, pero en
   `revision.html` y con el percentil escrito al lado: son el caso raro dentro
   del caso raro, y mirarlos sale barato. **Como lista, no como Alerta.**
4. **`ASSUMPTION` al PRD**, ahora en su versión fuerte: «En Colombia, que un
   proceso competitivo termine con un solo proponente es el desenlace
   mayoritario (52,8 %) y está asociado a MENOS atención recibida, no a más
   (mediana de 16 visualizaciones contra 32). Ninguna Regla puede tratarlo como
   anomalía, ni sola ni cruzada con visualizaciones.»

## Lo que esto costó y lo que compró

Costó una épica de trabajo cuya Regla no se enciende. Compró **dos hechos
medidos sobre la contratación pública colombiana que antes no teníamos**, y un
motor probado que ya sabe negarse a activar una Regla sin calibrar — que fue,
literalmente, lo que acaba de pasar. La barrera funcionó a la primera y contra
su propia autora.

Una bandera descartada por medición vale más que una encendida por intuición.
