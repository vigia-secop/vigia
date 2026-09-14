# El servidor

Aquí está todo lo que hace falta para que Vigía corra sola en una máquina
Linux y tú no vuelvas a abrir la carpeta por las mañanas.

**Léelo antes de pagar nada.** Esa fue la idea: que veas exactamente qué se
instala y qué hace antes de poner un peso.

---

## Lo que hay en esta carpeta

| Archivo | Qué es |
|---|---|
| `instalar.sh` | Deja el servidor montado. Se corre una vez. |
| `vigia-dia.sh` | El ciclo de cada día. Lo dispara systemd. |
| `vigia-historia.sh` | Trae el histórico hacia atrás. Se corre una vez. |
| `vigia.service` · `vigia.timer` | El temporizador de systemd. |

---

## Qué máquina

**Hetzner CX22, unos €4,35 al mes** — 2 vCPU, 4 GB de RAM, 40 GB NVMe, con
Ubuntu 24.04. Es lo más barato que aguanta Postgres con este histórico.

AWS Lightsail también sirve, pero el plan equivalente cuesta $12 al mes por la
mitad de la memoria. No necesitamos nada del ecosistema de Amazon: necesitamos
una máquina Linux prendida.

**El disco es lo único que hay que vigilar.** La capa cruda guarda el JSON de
SECOP tal como llega, y eso pesa: con un año de contratos y procesos calculo
entre 10 y 20 GB, más índices. En 40 GB cabe. Si se queda corto, Hetzner deja
pegarle un volumen sin reinstalar nada.

---

## Lo que yo no puedo hacer por ti

Tres cosas, y son las únicas:

1. **Crear la cuenta del servidor y pagarla.** No creo cuentas ni meto datos de
   pago, ni con tu permiso. Esa línea no la cruzo.
2. **Crear la cuenta anónima de GitHub**, y configurar la identidad de git
   **antes del primer push** — está en `ANONIMATO.md`. Un commit con tu correo
   personal no se borra del historial.
3. **Crear el bot de Telegram** con `@BotFather`. El token va al `.env` del
   servidor, nunca a un chat.

---

## Los pasos

### 1. La máquina

Crea el servidor con **Ubuntu 24.04** y entra por SSH. Anota la dirección IP.

### 2. El código

```bash
sudo VIGIA_REPO=https://github.com/TUCUENTA/vigia.git \
  bash /ruta/al/proyecto/servidor/instalar.sh
```

Si todavía no tienes el repositorio en GitHub, copia la carpeta del proyecto a
`/opt/vigia` con `scp` y corre el instalador sin `VIGIA_REPO`.

**El instalador es idempotente**: correrlo dos veces no rompe nada. Si algo
falla a la mitad, se arregla y se vuelve a correr.

Deja montado, y nada más que esto:

- PostgreSQL 16 **escuchando solo en localhost** — y si viene configurado de
  otra forma, **aborta** en vez de seguir
- un usuario `vigia` **sin shell de login y sin sudo**
- el proyecto en `/opt/vigia` con su propio entorno de Python
- un temporizador que corre el ciclo a las **05:40, hora de Bogotá**

**No abre ningún puerto al mundo.** Este servidor no sirve páginas: las
construye y las empuja a GitHub Pages, que es quien las sirve. Un puerto
abierto sería superficie de ataque a cambio de nada.

### 3. Los tokens

```bash
sudo nano /opt/vigia/.env
```

La contraseña de la base ya está puesta: la generó el instalador y no hace
falta que la recuerdes. Lo que falta es:

- `SOCRATA_TOKEN` y `SOCRATA_SECRET` — de datos.gov.co.
  **La Key Secret equivale a tu contraseña de esa cuenta.** Si alguna vez la
  escribes en un chat o un correo, revócala y genera otra.
- `TELEGRAM_TOKEN` y `TELEGRAM_CHAT` — el bot y tu conversación con él.
- `VIGIA_SITIO` — la dirección pública, solo para el aviso.

El archivo queda con permisos `600` y dueño `vigia`: ningún otro usuario del
sistema lo puede leer.

### 4. El histórico — **y esto es lo que desbloquea la 4.3**

```bash
sudo -u vigia /opt/vigia/servidor/vigia-historia.sh 12
```

Unas cinco horas. Déjalo y vete.

La concentración por proveedor es la única medición del proyecto que sobrevivió
al fondo: con mínimo de cinco contratos por entidad, la mediana de lo que se
lleva el mayor proveedor es **29,3 %** y solo el **2,1 %** de las entidades
pasa del 90 %. Minoría medida, no norma.

Lo único que la bloquea es la ventana. Y **no hay que esperar un año para tener
un año**: los datos de SECOP son históricos, y la concentración se mide sobre
contratos *firmados*, que están todos ahí mirando hacia atrás. Eso no vale para
todo —las visualizaciones de un proceso solo valen si las viste el día que
estaban— pero para la 4.3 vale entero.

Cuando termine:

```bash
sudo -u vigia psql -h localhost -U vigia -d vigia -f /opt/vigia/medir-concentracion.sql
```

### 5. La primera corrida

```bash
sudo systemctl start vigia.service
journalctl -u vigia.service -f
```

Y para ver cuándo toca la siguiente: `systemctl list-timers vigia.timer`.

---

## Lo que hace cada día

Siete pasos, y el séptimo es el que importa.

1. Migraciones — todas idempotentes, se reaplican siempre.
2. Ingesta de contratos.
3. Ingesta de procesos.
4. Normalizar.
5. Panel y lista de revisión.
6. La portada del día, y el boletín de la semana **si falta**.
7. **El semáforo.**

Una ingesta fallida **no mata el ciclo**: lo que ya está en la base sigue
siendo válido. Pero la puerta 1 lo ve y no se publica, porque publicar cifras
de ayer con fecha de hoy sí sería mentir.

Del paso 6: la pregunta no es «¿qué día es hoy?» sino **«¿ya existe el resumen
de la última semana completa?»**. Un disparador que pasa no vuelve; esa
pregunta se puede hacer cualquier día y da la misma respuesta correcta.

---

## El semáforo

Seis puertas. Cada una responde a la misma pregunta: **¿hay algo que haga que
lo que estamos a punto de publicar esté mal?** Si alguna dice que sí, **no se
publica nada** y te llega el motivo por Telegram.

| | Puerta | Se pone en rojo cuando |
|---|---|---|
| 1 | Ingesta | falló bajar datos, y lo que hay es de antes |
| 2 | Valores imposibles | la exclusión de los valores fuera de escala dejó de aplicarse |
| 3 | **Erratas ×10ⁿ** | apareció una que **nadie ha mirado todavía** |
| 4 | Comparabilidad | el período anterior está incompleto y la comparación sería una caída inventada |
| 5 | Barrera de publicación | un post se pasa de 280, o lleva vocabulario que imputa |
| 6 | Documentos en el sitio | alguna página de `docs/` lleva un documento de persona natural escrito entero |

**La puerta 3 es la que aprendimos a golpes.** El 11 de septiembre la Alcaldía
de Tipacoque —unos 3.000 habitantes— encabezaba el ranking con
$431.340.000.000. El presupuesto de ese proceso era $431.340.000: el mismo
número con tres ceros de más. La guarda de valores imposibles no lo atajó y
**nunca pudo**, porque 431 mil millones es un contrato perfectamente posible.

Y esa puerta **no tiene umbral inventado**. No pregunta «¿las erratas mueven
más del X % del valor?» —ese X habría que sacárselo de la manga, y así
murieron tres banderas de este proyecto—. Pregunta:

> ¿apareció una errata que nadie ha mirado?

Las revisadas viven en `erratas-revisadas.txt`, con el identificador del
contrato y la fecha. **Ese archivo sí se versiona**: es el rastro de que una
persona miró antes de publicar, y ese rastro es la respuesta el día que alguien
reclame.

Para revisarlas desde Windows: `EJECUTAR-REVISAR-ERRATAS.bat`. Te enseña cada
una con su enlace al SECOP y anota lo que respondas. Treinta segundos.

Y se puede responder **«es real»**, no solo «es errata»: si algún día un
contrato de verdad cuesta mil veces su presupuesto, la puerta no puede obligar
a llamarlo errata para poder publicar.

---

## Lo que el servidor NO hace, y no va a hacer

**No publica en X.** El hilo te llega escrito al teléfono, lo lees, lo
publicas tú. El día que alguien reclame, la respuesta tiene que ser «una
persona lo leyó», y no «lo publicó un proceso».

Tampoco guarda tu cuenta de X ni tu identidad personal de git. Lo único que
tiene para escribir afuera es la llave de despliegue de la cuenta anónima de
GitHub.

---

## Si algo sale mal

```bash
journalctl -u vigia.service -n 200        # la última corrida
ls -lt /opt/vigia/bitacora/ | head        # el registro de cada día
sudo systemctl start vigia.service        # correr a mano
```

El registro de cada corrida queda en `/opt/vigia/bitacora/ciclo-AAAA-MM-DD.txt`
con todo: qué se bajó, qué se insertó, qué falló y en qué paso.
