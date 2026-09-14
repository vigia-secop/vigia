---
historias: 1.13 el día de un clic · 1.14 lista de revisión
status: review
implementada: 2026-09-06
pruebas: 416 en verde
---

# El día de un clic, y la lista de revisión

Estas dos historias no estaban en el plan. Nacen de una frase: *«ya quiero
tener algo para empezar a usar»*. Lo que había hasta ese momento era un motor
de Reglas correcto y ninguna Regla encendida, que desde afuera se ve igual que
no tener nada.

---

## 1.13 · El día

### El problema no era el antivirus

El diseño anterior eran tres tareas programadas: el ciclo a las 06:00, el
resumen semanal el lunes 07:30, el mensual el lunes 08:00. El instalador quedó
en cuarentena y eso se volvió el titular, pero **el diseño tenía un defecto
peor y anterior**:

> Un disparador que pasa no vuelve.

Si el equipo está apagado el lunes a las 07:30, el resumen de esa semana no se
saca nunca. Y nadie se entera, porque lo que falta es un archivo que no existe:
no hay error, no hay hueco visible, simplemente esa semana no está.

### La pregunta correcta

`dia.ps1` no pregunta *qué día es hoy*. Pregunta:

> ¿Existe ya el resumen de la última semana completa? ¿Y el del último mes
> completo?

Si no existe, lo saca — sea martes o sea jueves. Mira **cuatro semanas y dos
meses** hacia atrás, así que el equipo puede estar quince días apagado sin
perder nada. Y correrlo dos veces el mismo día no duplica ni reescribe nada,
porque la pregunta sigue teniendo la misma respuesta.

El corte en cuatro semanas es deliberado: más atrás que eso ya no es «me salté
unos días», es un reproceso, y un reproceso se pide a mano y a sabiendas.

**Efecto secundario que importa:** ya no hace falta ninguna tarea programada,
así que el antivirus deja de ser un bloqueante. No se rodeó: se dejó de
necesitar.

### Detalles que se ven pequeños y no lo son

- **No abre transcripción propia.** `ciclo-diario.ps1` abre la suya, y anidar
  `Start-Transcript` en PowerShell 5.1 hace que el `Stop-Transcript` del hijo
  cierre la del padre: el registro del día quedaría cortado a la mitad sin que
  nadie se entere.
- **La invocación del hijo lleva `| Out-Host`.** Sin eso, todo lo que el hijo
  escriba se suma al valor de retorno de la función y la ruta del archivo deja
  de ser una ruta para volverse un arreglo con media pantalla adentro.
- **`AddMonths` sobre día 1.** Sumar meses a un día 31 lo mueve al 28 o al 30 y
  el rango sale torcido. Aquí siempre se parte del día 1.

### Orden de los pasos

El ciclo pasó de cuatro pasos a cinco: la lista de revisión va **después** del
Panel, no antes. El Panel dice sobre qué parte del universo se está calculando,
y la lista solo se lee bien sabiendo eso. Es la misma razón por la que el
bloque de cobertura va primero dentro del Panel.

---

## 1.14 · La lista de revisión

### Qué es, y sobre todo qué no es

**No son alertas.** Ninguna fila afirma que haya un problema con un contrato,
una entidad o una persona. Cada fila está por un **hecho sobre el dato**,
medido y verificable:

| Sección | El hecho |
|---|---|
| Contratos grandes sin razón social | la fuente trae el documento y no el nombre |
| Uniones sin documento | tienen identidad propia, no integrantes |
| Huérfanos de alto valor | traen llave de cruce y no encontraron su Proceso |
| Un documento, varias razones sociales | el mismo número escrito de más de una forma |
| Competitivos de alto valor con un solo oferente | listado, y marcado como NO bandera |

Estar en esta lista significa **«esto todavía no lo sabemos»** o **«esto es
grande y conviene verlo»**. Nunca «esto está mal». La diferencia es todo el
proyecto, y va escrita en la propia página, no solo en este documento.

### Por qué existe esta página y no las Reglas de la épica 4

Porque las Reglas todavía no están calibradas, y encenderlas sin calibrar es
peor que no tenerlas: la primera que se midió —oferente único— resultó marcar
el **52,8 %** de su propio universo.

La quinta sección de esta página es esa misma medición, pero **presentada como
lo que es**: un listado por valor, con las visualizaciones al lado, y un aviso
en negrita de que no es una bandera. Se puede mirar sin que nadie quede
señalado, que era exactamente lo que no se podía hacer con una Regla encendida.

### La sección vacía dice que está vacía

Una tabla sin filas escribe «Ninguno en esta ventana». No se omite. Es la misma
distinción que sostiene el modo calibración (2.5): **«se miró y no había» no es
«no se miró»**, y una sección ausente no permite distinguirlas.

---

## Un defecto que estas historias destaparon

Las tres páginas del proyecto —Panel, resumen y lista— salían **sin
`<!doctype>` y sin `<meta charset="utf-8">`**. Abiertas con doble clic desde una
carpeta de Windows en español, el navegador adivina cp1252 y «Vigía» se lee
«VigÃ­a».

Llevaba días así y nadie lo reportó, porque un acento roto se lee como «así se
ve» y no como «esto está mal». **Los defectos que no fallan son los que más
duran.**

Lo encontró una prueba de la lista de revisión que comprobaba el `<!doctype>`;
al mirar por qué fallaba, resultó que las otras dos estaban igual desde que
existen. La prueba es ahora parametrizada sobre las tres, y carga la salida de
verdad de `panel.sql`, `resumen.sql` y `revision.sql` guardada en
`tests/datos/` — una carga inventada se quedaría vieja en silencio cuando la
consulta cambie de forma.
