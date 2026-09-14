# Empezar aquí

En esta carpeta hay treinta y un archivos que empiezan por `EJECUTAR`. **Tres
importan.** El resto son mediciones que se corren una vez y se olvidan, y están
al final de esta página para que no estorben.

Y hay una carpeta nueva: **`servidor\`**. Ahí está todo lo necesario para que
Vigía corra sola en una máquina Linux y no tengas que abrir esta carpeta por
las mañanas. Empieza por `servidor\LEEME.md` — está escrito para que lo leas
**antes** de pagar nada.

---

## Lo de todos los días

### `EJECUTAR-DIA.bat`

Doble clic. Trae los datos nuevos, los normaliza, dibuja las páginas y —si
falta— saca el resumen de la semana, el del mes y el hilo para publicar.

Tarda entre 20 y 40 minutos, casi todo en bajar datos. Déjalo corriendo.

Correrlo dos veces el mismo día no rompe ni duplica nada. Si el equipo estuvo
apagado, se da cuenta de qué falta y lo saca: no depende de estar encendido un
lunes a las siete.

### `EJECUTAR-VER-SITIO.bat`

Construye el sitio público en `docs/` y lo abre. **No sube nada.** Para mirarlo
antes de soltarlo.

### `EJECUTAR-PORTADA.bat`

Solo la portada del día — `docs/index.html` — y la abre. Tampoco sube nada.
Sirve para ver cómo quedó el día de hoy sin rehacer el sitio entero.

Usa **el último día con contratos**, no «hoy», porque SECOP publica con rezago:
una portada en blanco a las seis de la mañana no se lee como «todavía no hay
datos», se lee como «este sitio está roto».

### `EJECUTAR-PUBLICAR.bat`

Construye, revisa y sube a GitHub Pages. Aborta si algo huele mal — ver más
abajo.

### `EJECUTAR-REVISAR-ERRATAS.bat`

Solo cuando la publicación se detenga por la **puerta 3**. Te enseña, una por
una, las cifras que son exactamente mil o diez mil veces el presupuesto de su
propio proceso, con el enlace al SECOP. Miras, respondes, y queda anotado en
`erratas-revisadas.txt` con la fecha. Treinta segundos.

Se puede responder **«es real»**, no solo «es errata»: si algún día un contrato
de verdad cuesta mil veces su presupuesto, la guarda no puede obligarte a
llamarlo errata para poder publicar.

---

## Lo que produce, y para quién

| Archivo | Para quién | Sale de |
|---|---|---|
| `panel.html` | tú, en el escritorio | `panel.sql` |
| `revision.html` | tú, en el escritorio | `revision.sql` |
| `resumen-semanal-*.html` | tú | `resumen.sql` |
| `boletin-semana-*.txt` | el hilo para X | `boletin.sql` |
| `docs/index.html` | **internet**, todos los días | `portada.sql` |
| `docs/semana.html` | **internet**, cada semana | `boletin.sql` |
| `docs/semanas/*.html` | **internet**, URL permanente | `boletin.sql` |

**La línea que divide esa tabla es la más importante del proyecto.**

`panel.html` y `revision.html` llevan razones sociales y **cédulas de
contratistas personas naturales**. Ahí están bien: son herramientas de trabajo,
en tu escritorio, y el dato es público en SECOP.

Lo que se publica sale de dos consultas, y las dos tienen su regla escrita:

- **`boletin.sql`** —el resumen de la semana y el hilo de X— **no puede
  devolver el nombre de nadie.** Ni de una persona, ni de una empresa, ni de
  una entidad. Solo agregados.
- **`portada.sql`** —la página de cada día— **sí devuelve el nombre y el NIT de
  una empresa, y nunca el documento entero de una persona natural.** El
  enmascarado se hace **dentro de la consulta**, no al dibujar la página: así
  ningún error mío en una plantilla puede sacar una cédula a internet, porque
  el programa que dibuja nunca la recibe.

Y encima de eso, `EJECUTAR-PUBLICAR.bat` recorre **toda** la carpeta `docs/`
antes de subir y **aborta** si encuentra el documento de una persona natural
escrito entero.

---

## La portada, que es el registro

`docs/index.html` se rehace **todos los días**. No es el boletín de la semana:
es el día. Quien entre un miércoles tiene que ver el miércoles.

Lleva, en este orden y el orden es la posición del proyecto:

1. Las cifras del día, comparadas con **el mismo día de la semana anterior** —
   no con ayer, que un lunes contra un domingo no dice nada.
2. **Qué parte de eso no se puede ver.** Antes de cualquier ranking, siempre.
3. Los contratos más grandes, con el NIT de las empresas, el enlace a la ficha
   del SECOP, y la **marca de probable errata** donde corresponda.
4. Dónde, bajo qué modalidad, de qué tamaño.
5. Los últimos 28 días, con los días sin jornada hábil rayados.
6. **La calidad del dato**: cuántas erratas, cuántos valores imposibles,
   cuántos huérfanos. Publicado en la misma página que las cifras.

Un día sin jornada —un domingo, un festivo— **lo dice con palabras** en vez de
mostrar una caída del 99 %. Es la misma lección del 3 de septiembre, cuando los
conteos crudos decían −45,7 % y la diferencia real eran dos festivos: 1,0 %.

---

## Las tres páginas de escritorio

**`panel.html`** — la foto de la ventana. Lo primero que muestra, antes de
cualquier ranking, es cuánto queda fuera del alcance de cada medición.

**`revision.html`** — qué mirar primero, con el hecho concreto por el que cada
fila está listada. **No son alertas.** Estar ahí significa «esto todavía no lo
sabemos» o «esto es grande y conviene verlo». Nunca «esto está mal».

### Una cifra enorme no es un hallazgo

El 11 de septiembre el Panel encabezaba «Contratos mayores» con la **Alcaldía
de Tipacoque** —un municipio de unos 3.000 habitantes— firmando
**$431.340.000.000** con una fundación. El presupuesto oficial de ese proceso
era **$431.340.000**: el mismo número con **tres ceros de más**.

La guarda de valores imposibles no lo atajó **y nunca pudo**: el techo son 100
billones, y 431 mil millones es un contrato perfectamente posible. La errata de
tecleo no se detecta por tamaño; se detecta porque el valor es *exactamente*
mil o diez mil veces el presupuesto de su propio proceso. Un sobrecosto real da
una proporción cualquiera —2,3; 12,4—; solo una tecla cae justo sobre una
potencia de diez.

Desde hoy esas filas van **marcadas** en el Panel y **listadas arriba del todo**
en la lista de revisión, con el presupuesto del proceso al lado. No se quitan:
quitarlas sería corregir la fuente a ojo, y Vigía no corrige la fuente.

**Publicar una de estas como hallazgo acabaría con Vigía en un día**, y de paso
le haría un daño real a una fundación que probablemente no hizo nada. Antes de
creerle a una cifra grande, abre la ficha del SECOP: el identificador del
contrato es un enlace.

**`resumen-*.html`** — el período contra el anterior, siempre dividido por
días hábiles, con los festivos declarados. Sin esa división, el 3 de septiembre
los conteos crudos decían que la contratación había caído 45,7 %. Eran dos
festivos: la caída real era del 1,0 %.

---

## Publicar

1. Lee `ANONIMATO.md` y configura la identidad de git. **Antes del primer
   push**, porque un commit con tu correo personal no se borra del historial.
2. `EJECUTAR-VER-SITIO.bat` — mira el sitio.
3. `EJECUTAR-PUBLICAR.bat` — súbelo. La primera vez, en GitHub:
   **Settings → Pages → Deploy from a branch → main → /docs**.
4. `PRIMER-HILO.md` — el hilo que explica qué es Vigía. Publícalo y fíjalo.
5. Cada semana, `EJECUTAR-DIA.bat` te deja el hilo escrito en un `.txt`.
   Léelo y publícalo tú.

**Vigía no publica solo, y no va a hacerlo.** El generador escribe el archivo y
se detiene. Esa frontera es a propósito: el día que alguien reclame, la
respuesta es «una persona lo revisó», no «lo publicó un proceso».

---

## Las banderas

Ninguna encendida, y el sitio lo dice en su propia página.

| Historia | Estado |
|---|---|
| 2.4 Oferente único | **descartada** — 52,8 % es la norma |
| 4.2 Pegado al presupuesto | **descartada** — 62,4 % es la norma |
| 4.3 Concentración por proveedor | **viva** — 2,1 % de las entidades; falta historia |
| 4.6 Fraccionamiento | **en medición** |
| 4.1 · 4.4 · 4.5 · 4.7 · 4.8 | **por medir** — los campos existen |

Encender una regla sin calibrar es peor que no tenerla: una alerta inventada le
cuesta a alguien su reputación y no hay forma de devolvérsela.

---

## Si algo sale mal

El registro de cada corrida queda en **`bitacora\`**. Ahí está todo: qué se
bajó, qué se insertó, qué falló y en qué paso.

Si una ingesta falla, el ciclo **sigue** y vuelve a dibujar las páginas con lo
que ya hay en la base. Un panel de ayer es mejor que ningún panel, y el fallo
queda escrito.

---

## Lo demás (mediciones de una sola vez)

No hace falta correrlas para el día a día. Cada una responde una pregunta y
deja su respuesta en un `*-ultima-corrida.txt`.

| | |
|---|---|
| `EJECUTAR-HISTORIA-DESDE-JULIO.bat` | trae el histórico. **Una vez**, ~3 horas |
| `EJECUTAR-RESUMEN-DESDE-JULIO.bat` | el acumulado de julio a hoy |
| `EJECUTAR-campos.bat` | qué campos de SECOP llegan poblados |
| `EJECUTAR-fraccionamiento.bat` | ¿se puede construir la bandera 4.6? |
| `EJECUTAR-concentracion.bat` | ¿se puede construir la 4.3? |
| `EJECUTAR-valores.bat` | ¿hay valores imposibles? |
| `EJECUTAR-erratas.bat` | **la errata ×1000 que el techo de valores no ataja** |
| `EJECUTAR-nominas-paralelas.bat` | una persona con varios contratos a la vez |
| `EJECUTAR-fantasmas.bat` | identidades de proveedor sin contratos |
| `EJECUTAR-presupuesto.bat` | la razón adjudicado/presupuesto |
| `EJECUTAR-probar.bat` | corre las pruebas |
| `EJECUTAR-BOLETIN.bat` | rearma el hilo de la semana pasada |

Y estas catorce son de historias ya cerradas o de pasos que el ciclo diario
hace solo. Se quedan porque documentan cómo se llegó hasta aquí, no porque
haya que correrlas:

`HISTORIA` (la genérica; usa la de julio), `capturar-divipola`,
`capturar-procesos`, `estado-llave`, `exportar-reporte`, `guardar-en-git`,
`ingerir-procesos`, `ingerir-y-normalizar`, `instalar-tareas`,
`intercambiar-llave`, `migrar-llave`, `revisar-crudo`, `subir-a-github`,
`uniones`.

La única de esa lista que todavía sirve es **`EJECUTAR-subir-a-github.bat`**,
que te guía la primera vez para crear el repositorio. Después de eso,
`EJECUTAR-PUBLICAR.bat` hace el resto.
