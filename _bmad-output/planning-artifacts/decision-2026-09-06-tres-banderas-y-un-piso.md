---
title: "Decisión — Tres banderas medidas, tres descartadas, y el piso que hay que arreglar antes"
created: 2026-09-06
decide: Claude (socio técnico), a petición explícita de Guillermo
alcance: mayor — cambia el orden del roadmap
---

# Tres banderas medidas, tres descartadas, y el piso que hay que arreglar antes

Guillermo pidió que la decisión la tomara yo. La tomo, y dejo escrito el
razonamiento completo para que se pueda discutir o revertir con los mismos
números delante.

---

## 1. Lo que se midió hoy, en orden

### 1.1. Oferente único (historia 2.4) — **DESCARTADA**

Dos mediciones, y la segunda es la que importa.

**Primera:** de 2 176 procesos competitivos adjudicados, 1 150 —el **52,8 %**—
terminan con un solo proveedor. Una Regla así marca la mayoría de su propio
universo.

**Segunda:** se buscó el criterio relativo que la salvara —«no importa que sea
uno, importa que lo miraran muchos y ofertara uno»— y los datos dijeron lo
contrario de la hipótesis:

| Grupo | Procesos | Mediana de visualizaciones |
|---|---|---|
| Un solo proveedor | 1 239 | **16** |
| Varios proveedores | 1 095 | **32** |

Un proceso que termina con una sola oferta es, por regla, **uno que nadie
miró**. Solo 30 de 1 239 (2,4 %) pasan el p90 de su modalidad, cuando por azar
serían ~124: están **infrarrepresentados** en la cola de atención. La Regla
propuesta habría marcado el grupo equivocado.

### 1.2. Adjudicación pegada al presupuesto (historia 4.2) — **DESCARTADA**

Se eligió esta historia precisamente porque su umbral no había que inventarlo:
la razón adjudicado/presupuesto tiene un punto que sale del mundo, el 1,00.

**El campo llega perfecto:** `precio_base` viene poblado en el **99,9 %** de
los 10 689 procesos adjudicados. Cobertura ideal, la mejor del proyecto.

**Y el resultado mata la Regla igual:**

| Franja | Procesos | % |
|---|---|---|
| por debajo del 95 % | 2 584 | 24,2 |
| 95 % a 99 % | 686 | 6,4 |
| 99,0 % a 99,9 % | 623 | 5,8 |
| **99,90 % a 100 %** | **6 660** | **62,4** |
| por encima del presupuesto | 119 | 1,1 |

Mediana exactamente **1,0000**. Adjudicar pegado al techo presupuestal es lo
que hace **casi dos tercios** del país. Otra vez la norma.

### 1.3. ¿Y si el presupuesto no fuera un presupuesto?

Antes de aceptar ese número había que descartar la explicación aburrida: que
`precio_base` se diligencie **con** el valor adjudicado, o se reescriba
después. Para eso existe la capa cruda, que guarda una foto por consulta.

De 371 062 pares proceso-adjudicación, 6 350 tienen más de una foto (1,7 %).
De esos, **56 cambiaron su `precio_base`** y **ninguno —cero— terminó igual al
valor adjudicado**. Los 15 mayores son revisiones al alza **antes** de
adjudicar, que es lo normal y lo legítimo.

**El presupuesto es un presupuesto.** La lectura aburrida queda descartada, con
la salvedad honesta de que solo se pudo comprobar sobre el 1,7 %.

### 1.4. Adjudicar POR ENCIMA del presupuesto — **NO ES LO QUE PARECÍA**

Quedaban los 119 del 1,1 %. Eran el candidato perfecto: minoría medida, y
criterio **categórico** —se pasa o no se pasa— sin ningún umbral que elegir.

Sobreviven todas las comprobaciones: los 119 están por encima de **la mayor
base que jamás se les vio**, no solo de la última foto. Cero se explican por
una foto vieja.

**Y al mirarlos uno por uno no son sobrecostos. Son erratas de la fuente.**

| Entidad | Presupuesto | Adjudicado | «Por encima» |
|---|---|---|---|
| ESE Hospital Local San José | $320 873 959 | **$8 054 481 856 630 300** | 2 510 169 900 % |
| Alcaldía de Tipacoque | $431 340 000 | $431 340 000 **000** | 99 900 % |
| Distrito de Medellín | $210 160 000 | $210 160 000 **000** | 99 900 % |
| CVC | $99 070 693 | $99 070 693 **000** | 99 900 % |
| CVC | $76 050 000 | $76 050 000 **000** | 99 900 % |

**El mismo número con tres ceros de más**, cinco veces, en entidades distintas.
Y un hospital con ocho mil billones de pesos: varias veces el PIB del país en
un solo renglón.

Hay una segunda familia, más discreta: **cuatro procesos con exactamente
42,9 % por encima** —Atlántico dos veces, la CAR del Cauca, una universidad—.
42,9 % es exactamente 10/7: el adjudicado es la base dividida por 0,7. Cuatro
entidades distintas no se equivocan en la misma fracción por azar; es una
convención de publicación (una base que es el 70 % de algo), no una anomalía.

Quitando erratas y convenciones, quedan unos 90 procesos con sobrecostos
plausibles que suman **$7 733 millones**. Es poco, es ruidoso, y no aguanta una
Regla.

---

## 2. La decisión

### 2.1. Las tres banderas se descartan

2.4 pasa a `descartada`. 4.2 pasa a `descartada`. La variante «por encima del
presupuesto» no se abre como historia.

### 2.2. El hallazgo real es otro, y es más grave

Buscando banderas encontramos que **la fuente publica valores imposibles**, y
eso no es un problema de las Reglas: es un problema de **todo lo que Vigía
publica hoy**.

El Panel dice «$12,91 billones en la ventana». Un solo contrato con tres ceros
de más convierte ese número en mentira, pone al que tuvo la errata en la cima
del ranking de contratistas, y **nadie se entera**, porque el número no falla:
sale, se lee, y está mal.

Es exactamente la clase de defecto que este proyecto no puede permitirse, y por
la misma razón por la que no puede permitirse una alerta inventada: **un número
falso publicado con la cara de Vigía le cuesta a alguien su reputación, y no
hay forma de devolvérsela.**

Y ya casi nos pasa. La lista de revisión de esta mañana lista, como huérfano
mayor, un contrato de **$1,37 billones** de TRANSMILENIO. Puede ser real —hay
contratos de ese tamaño en Colombia— o puede ser de esta familia. **Hoy no
sabemos distinguirlo, y lo estamos publicando.**

### 2.3. Lo que se hace en vez de la cuarta bandera

**Historia nueva 1.15 — Guarda de valores imposibles**, con prioridad por
encima de toda la épica 4:

1. Medir cuántos contratos de la capa normalizada tienen valores fuera de
   escala, y de qué tamaño es su efecto sobre los totales que ya publicamos.
   (`medir-valores-imposibles.sql`, escrito y listo — un doble clic en
   `EJECUTAR-valores.bat`.)
2. Con ese número, decidir la guarda. La forma probable: los contratos por
   encima de un techo se **excluyen de los totales y de los rankings, y se
   listan aparte con su valor tal cual**. No se corrigen —no somos la fuente—
   y no se esconden.
3. El Panel dice en su bloque de cobertura cuántos quedaron fuera y por qué.
   Es la misma regla que ya sigue con los huérfanos y las uniones sin
   documento: **lo que no se puede medir se declara, no se calla.**

### 2.4. Y después, qué bandera

Ninguna de las que dependen del embudo o del presupuesto. La siguiente
candidata es **4.3, concentración por proveedor**, por una razón concreta: es
la única cuya materia prima ya está medida y es buena —**109 215 identidades,
99,6 % de cobertura, 3,5 % de huérfanos**— y cuyo hallazgo no depende de un
umbral sino de una forma: la distribución de cuántas entidades le contratan a
un mismo proveedor.

Con la salvedad que ya está escrita y hay que repetir en cada informe: **410
contratos de uniones temporales sin documento, $1,91 billones —el 14,8 % del
valor de la ventana— son invisibles para cualquier medida de concentración**
hasta que se conozcan sus integrantes (historia 1.8).

---

## 3. Lo que cuesta esta decisión, dicho sin adornos

Se descartan tres banderas después de construir el motor entero para
sostenerlas. Es una épica de trabajo cuya Regla no se enciende.

A cambio quedan **cuatro hechos medidos sobre la contratación pública
colombiana** que antes no existían en ninguna parte de este proyecto:

1. Que un competitivo termine con un solo oferente es el desenlace mayoritario
   (52,8 %), **y está asociado a menos atención recibida, no a más**.
2. Adjudicar entre el 99,90 % y el 100 % del presupuesto es lo que hace el
   62,4 % del país.
3. El `precio_base` que publica la fuente es un presupuesto de verdad: no se
   reescribe con el resultado.
4. **La fuente publica valores imposibles**, y hasta hoy los estábamos sumando.

Y queda algo que vale más que las tres banderas juntas: **el motor de la
épica 2 se negó a activar una Regla sin calibrar, y funcionó a la primera
contra su propia autora.** La barrera que se construyó para no inventar alertas
acaba de impedir tres.

Una bandera descartada por medición vale más que una encendida por intuición.
Tres, más.
