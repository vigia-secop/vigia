---
title: "Propuesta de cambio de sprint — La llave de la capa cruda se apoya en un identificador que la fuente reasigna"
created: 2026-09-04
status: propuesta
implementada: 2026-09-04, pendiente de correr la migración sobre la base real
disparador: "Revisión de los conteos del primer Ciclo real sobre datos nacionales, 2026-09-03"
alcance: mayor
decide: Guillermo
---

# Propuesta de cambio de sprint — La llave de la capa cruda se apoya en un identificador que la fuente reasigna

## 1. Resumen del problema

La capa cruda identifica cada fila por `(dataset, id_fila_fuente, hash_contenido)`,
donde `id_fila_fuente` es el campo de sistema `:id` de Socrata. La historia 1.1
lo eligió porque es el campo que la API exige para paginar sin saltos, y porque
el propio comentario del código dice que «sin identidad de fila no hay
idempotencia».

**El `:id` de Socrata no es estable entre publicaciones del dataset.** La fuente
se lo reasigna a la misma fila. Con eso, la llave primaria no impide nada: cada
Ciclo vuelve a insertar la ventana entera como si fuera nueva.

Y como el hash se calcula sobre el contenido **completo** —que incluye los
campos de plataforma `:id`, `:updated_at`, `:created_at` y `:version`—, tampoco
el hash frena el duplicado: cambian esos cuatro campos y el hash cambia con
ellos, aunque el contrato sea idéntico.

## 2. Qué se midió

Tres Ciclos sobre el rango **idéntico** 2026-08-26 a 2026-09-02, el 2026-09-03:

| Ciclo | Hora | vistos | insertados | duplicados |
|---|---|---|---|---|
| Primero | 12:29 | 24 685 | 24 685 | 0 |
| Segundo | 12:31 | 24 685 | **0** | **24 685** |
| Tercero | 17:31 | 25 749 | **25 749** | **0** |

El segundo Ciclo, dos minutos después del primero, se comportó como debía. El
tercero, cinco horas después, volvió a insertarlo todo.

**Estado de la capa cruda después de los tres** (`revisar-crudo.ps1`, 17:39):

| Medición | Resultado |
|---|---|
| Filas crudas de contratos | 50 434 |
| `id_fila_fuente` distintos | **50 434** |
| Contratos de negocio distintos (`id_contrato`) | **25 749** |
| Filas con más de una versión bajo la llave actual | **0** |
| Ocupación de la tabla | 149 MB |

Ni una sola fila tiene dos versiones bajo la llave actual, y sin embargo hay
casi el doble de filas que de contratos. La conclusión es inevitable: **24 685
contratos volvieron a entrar con un `:id` nuevo.**

## 3. Qué cambia entre las dos copias

La pregunta que decide el arreglo, sobre una muestra de 300 contratos
duplicados (`llave-rapido.sql`, 2026-09-03 21:20):

| Resultado | Contratos | Proporción |
|---|---|---|
| Difieren **solo** en campos de plataforma | **283** | 94,3 % |
| Traen un cambio de negocio real | **17** | 5,7 % |

Campos de plataforma encontrados: `:id`, `:updated_at`, `:created_at`,
`:version`.

Campos de negocio que sí cambiaron, en esos 17: `estado_contrato` (8),
`fecha_de_inicio_del_contrato` (8), `entidad_centralizada` (7),
`fecha_de_fin_del_contrato`, `valor_facturado`, `proveedor_adjudicado`,
`nombre_representante_legal`, `g_nero_representante_legal`.

**Este resultado es mejor que un 100 % de ruido.** Dice dos cosas a la vez:

1. El 94,3 % de la duplicación es basura pura y se puede eliminar sin perder
   nada.
2. El 5,7 % restante son **versiones de verdad**: contratos que cambiaron de
   estado o a los que les llenaron la fecha de inicio en cinco horas. Esas
   versiones hay que conservarlas, y el diseño de solo inserción de la 1.1
   existe precisamente para eso. El arreglo no puede colapsarlas.

## 4. Impacto

**Sobre las señales de salud.** `duplicados` en el resumen del Ciclo marcará
cero para siempre. Una duplicación real —el fallo que esa señal existe para
detectar— sería hoy indistinguible del funcionamiento normal. Es el impacto más
grave, porque anula un instrumento sin avisar.

**Sobre el costo.** La capa cruda crece por el tamaño de la **ventana**, no por
lo nuevo. Medido: 149 MB para ocho días de contratos ingeridos dos veces,
~3,1 KB por fila. Extrapolado a la ventana nacional de treinta días corriendo a
diario: ~300 MB por Ciclo, ~9 GB al mes, de los cuales el ~94 % es reinserción.

**Sobre la historia 1.7 (barrido completo).** Ampliar la ventana antes de
arreglar esto multiplica el problema por el factor que se amplíe. Por eso esta
propuesta va **antes** que la 1.7 en la secuencia.

**Sobre lo que NO se ve afectado.** La capa normalizada es correcta y la
historia 1.4 no cambia: se identifica por `id_contrato` y su `DISTINCT ON`
colapsó bien las 50 434 filas en 25 749 contratos. Que un error de la capa de
abajo saliera recuperable desde arriba es la primera vez que el diseño «el crudo
guarda todo y no interpreta nada» se paga solo.

## 5. Cambio propuesto

**5.1. La identidad de fila pasa a ser del negocio, no de la plataforma.**

`DatasetSecop` ya es el único sitio donde vive el conocimiento por dataset
(`id_socrata`, `campo_fecha_rango`). Se le añade `campos_identidad`, una tupla
ordenada:

| Dataset | `campos_identidad` | Por qué |
|---|---|---|
| `contratos` | `("id_contrato",)` | Un contrato por fila. |
| `procesos` | `("id_del_proceso", "id_adjudicacion")` | El dataset trae **una fila por adjudicación**, no por proceso (medido en la 1.4: 21 filas para `CO1.REQ.10772032`). Sin el segundo componente se perderían las adjudicaciones de un proceso multilote. |

El primer campo es obligatorio; los siguientes se concatenan si están
presentes. Un proceso sin adjudicar no trae `id_adjudicacion` y su identidad es
solo `id_del_proceso`, que es correcto: todavía no hay adjudicación que
distinguir.

**5.2. El hash pasa a calcularse sobre el contenido de negocio.**

Se excluyen del hash las claves que empiezan por `:`, que es la convención de
Socrata para sus campos de sistema. **El contenido almacenado no cambia: se
sigue guardando la fila entera tal como llegó**, porque el trabajo de la capa
cruda es conservar lo que llegó. Lo que cambia es sobre qué se hashea.

Consecuencia declarada: `hash_contenido` deja de ser una suma de verificación
del blob almacenado y pasa a ser la identidad de la versión de negocio. Hoy
nadie lo usa como suma de verificación, y el nombre sigue siendo correcto para
lo que pasa a significar.

**5.3. Migración 005.** Recalcula `id_fila_fuente` y `hash_contenido` de las
filas existentes desde su propio `contenido` —que las tiene todas—, colapsa las
que resulten iguales y vuelve a poner la llave primaria. No se pierde ninguna
versión real: las 17 de cada 300 que sí cambiaron siguen siendo dos filas.

**5.4. `ASSUMPTION` nueva en el PRD.** «El `:id` de Socrata es un identificador
de la plataforma, no del negocio, y la fuente lo reasigna. Ningún componente de
Vigía puede apoyar identidad en él.»

## 6. Alternativas descartadas

**Dejarlo y deduplicar al normalizar.** Ya funciona —la 1.4 lo demuestra— pero
deja el costo de almacenamiento intacto, deja `duplicados` muerto como señal, y
hace que el reproceso desde crudo de la 6.3 lea el triple de filas de las
necesarias. Arregla el síntoma visible y ninguna de las tres causas.

**Hashear el contenido completo pero con llave de negocio.** No sirve: los
campos de plataforma cambian, el hash cambia, y la llave `(dataset, negocio,
hash)` sigue admitiendo la fila. Medido arriba: es exactamente lo que pasa hoy.

**Guardar solo la última versión de cada fila.** Rompe la capa cruda. La serie
histórica es lo que hace posible el reproceso de la 6.3 y lo que permitió
recuperar este mismo error desde arriba.

**Un segundo hash, `hash_negocio`, junto al actual.** Más honesto sobre el
papel, pero añade una columna y un concepto para conservar una suma de
verificación que nadie consulta. Se descarta por no pagar lo que cuesta.

## 7. Qué hay que aprobar

1. Reabrir la historia **1.1**, hoy en `review`, para cambiar la definición de
   identidad de la capa cruda.
2. Aceptar la **migración 005** sobre una tabla con 407 000 filas. **Es
   reversible de verdad**: `rellave` escribe en una tabla nueva y, al
   intercambiar, deja la anterior como `crudo_registro_antes_de_005` sin
   borrarla. Volver atrás son dos `ALTER TABLE ... RENAME`. Además corre en dos
   tiempos: sin `--intercambiar` solo llena la tabla nueva y reporta los
   números, y `crudo_registro` sigue siendo la de antes hasta que se decida.
3. Confirmar la secuencia: esto **antes** de la 1.7.
