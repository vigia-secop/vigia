# Poner Vigía en línea, paso por paso

Todo lo que hay que hacer, en el orden en que hay que hacerlo.

**El orden importa y no es casual: la página queda funcionando ANTES de que
pagues un peso.** Primero GitHub, que es gratis y te deja el sitio en internet
publicando desde tu computador. Solo después el servidor, que lo único que
añade es que no tengas que abrir la carpeta por las mañanas.

Si a mitad de camino decides que no quieres servidor, te quedas con un sitio
público funcionando y no perdiste nada.

| Fase | Cuesta | Tarda |
|---|---|---|
| 1 · GitHub y la página | **$0** | ~40 min |
| 2 · Telegram | **$0** | ~10 min |
| 3 · El servidor | **~€4,35/mes** | ~30 min |
| 4 · Subir el proyecto | — | ~20 min |
| 5 · El histórico | — | ~5 h sin ti |

---

## Antes de empezar

Necesitas tres cosas a mano:

1. **Un correo que no uses en ninguna otra parte.** Para la cuenta anónima de
   GitHub. Sirve cualquiera gratuito; lo importante es que no sea el tuyo de
   siempre ni tenga tu nombre.
2. **Una tarjeta** para el servidor. Solo en la fase 3.
3. **Git instalado en Windows.** Comprueba abriendo PowerShell y escribiendo
   `git --version`. Si no está, se baja de `git-scm.com`.

---

# FASE 1 · GitHub y la página · gratis

Al final de esta fase tienes el sitio en internet, publicando desde tu
computador. Sin pagar nada.

## 1.1 · Crea la cuenta anónima

En `github.com`, **Sign up**, con el correo que no usas en otra parte.

- Usuario: algo neutro. Va a quedar en la dirección del sitio
  (`https://USUARIO.github.io/...`), así que no pongas tu nombre.
- No llenes el perfil: ni foto, ni nombre real, ni ubicación, ni sitio web.

## 1.2 · Esconde el correo — **esto antes que nada**

`Settings → Emails → Keep my email addresses private`

Esa misma página te da un correo con esta forma:

```
12345678+usuario@users.noreply.github.com
```

**Cópialo.** Es el que va en cada commit en vez del tuyo.

> **Por qué va primero.** Cada commit de git lleva grabado un nombre y un
> correo, para siempre, y en un repositorio público cualquiera los lee con un
> clic. No se borran con `git commit --amend`: quedan en el historial y en
> cualquier copia que alguien haya clonado. Por eso `publicar.ps1` **aborta**
> si el correo no es de los que no identifican. No avisa: aborta.

## 1.3 · Configura git en tu computador

PowerShell, dentro de la carpeta del proyecto:

```powershell
cd C:\Users\User\Desktop\vigia-secop
git config user.name  "Vigia SECOP"
git config user.email "12345678+usuario@users.noreply.github.com"
```

Sin `--global`, a propósito: cambia solo este proyecto y no te toca el resto de
tu trabajo.

**Comprueba que quedó:**

```powershell
git config user.email
```

## 1.4 · Crea el repositorio

En GitHub, botón **New repository**:

- Nombre: `vigia`
- **Public** — y esto no es opcional: GitHub Pages solo funciona en
  repositorios públicos con una cuenta gratuita.
- **No** marques «Add a README», ni `.gitignore`, ni licencia. La carpeta ya
  tiene lo suyo.

> **Que el repositorio sea público es correcto, y es parte del método.**
> Cualquiera puede rehacer las cuentas — eso es lo que hace a Vigía creíble.
> Lo único que nunca entra ahí es `.env`, que lleva el token de Socrata, y
> `.gitignore` ya lo excluye. `publicar.ps1` lo comprueba y aborta si no.

## 1.5 · Conecta la carpeta con el repositorio

```powershell
cd C:\Users\User\Desktop\vigia-secop
git remote add origin https://github.com/USUARIO/vigia.git
git branch -M main
```

Si te dice que `origin` ya existe:

```powershell
git remote set-url origin https://github.com/USUARIO/vigia.git
```

## 1.6 · Construye el sitio y míralo antes de subirlo

Doble clic en **`EJECUTAR-VER-SITIO.bat`**.

Arma `docs\` y lo abre en el navegador. **No sube nada.** Míralo entero antes
de soltarlo a internet.

Si te detiene por la **puerta 3** —erratas ×10ⁿ— corre
**`EJECUTAR-REVISAR-ERRATAS.bat`**, mira cada una en SECOP, responde, y vuelve.
Treinta segundos.

## 1.7 · Súbelo

Doble clic en **`EJECUTAR-PUBLICAR.bat`**.

La primera vez git abre el navegador para que te autentiques en GitHub. **La
contraseña se escribe en la página de GitHub, nunca en la consola.**

Antes de subir comprueba, y cualquiera de las tres aborta:

1. Que `.env` esté ignorado.
2. Que el correo de git no te identifique.
3. Que ningún archivo de `docs/` lleve el documento de una persona natural
   escrito entero.

## 1.8 · Enciende GitHub Pages

En el repositorio: `Settings → Pages`

- **Source**: `Deploy from a branch`
- **Branch**: `main`
- **Folder**: `/docs`
- **Save**

A los dos o tres minutos el sitio está en:

```
https://USUARIO.github.io/vigia/
```

**Ábrelo. Ya está en internet.** Hasta aquí no has pagado nada.

## 1.9 · El hilo de arranque

`PRIMER-HILO.md` tiene los siete posts que explican qué es Vigía. Léelos,
cámbialos si quieres —son tuyos—, publícalos en X y **fija el hilo en el
perfil**. Quien llegue en enero tiene que poder leer qué es esto sin buscar.

---

# FASE 2 · Telegram · gratis

Para que el servidor te avise. Se puede hacer ahora o después.

## 2.1 · Crea el bot

En Telegram, busca **@BotFather** y escríbele:

```
/newbot
```

Te pide un nombre y un usuario que termine en `bot`. Al final te da un token
así:

```
7123456789:AAHxyz...
```

**Ese token va al archivo `.env` del servidor y a ningún otro sitio.** No lo
pegues en un chat, ni en un correo, ni me lo mandes a mí.

## 2.2 · Averigua tu chat

Escríbele **cualquier cosa** a tu bot —«hola» sirve— y luego abre en el
navegador:

```
https://api.telegram.org/bot<TU-TOKEN>/getUpdates
```

Busca `"chat":{"id":123456789` — ese número es tu `TELEGRAM_CHAT`.

---

# FASE 3 · El servidor · aquí se paga

## 3.1 · Crea la cuenta en Hetzner

En `hetzner.com` → **Cloud** → **Sign up**.

**Sobre el pago:** Hetzner acepta tarjeta de crédito (VISA, Mastercard, AMEX,
UnionPay) con cobro automático, y PayPal para pagos manuales. No todas las
opciones están disponibles en todos los países, así que mira cuáles te ofrece a
ti al registrarte. **No se puede pagar por adelantado**: se factura lo
consumido.

Es posible que te pidan una verificación de identidad la primera vez — es
normal en proveedores de nube y puede tardar unas horas. Si la cuenta se queda
trabada, **DigitalOcean, Vultr o Contabo** hacen exactamente lo mismo por un
precio parecido, y el instalador funciona igual en cualquiera de ellos con
Ubuntu 24.04.

## 3.2 · Prepara tu llave SSH — en tu computador, antes de crear el servidor

PowerShell:

```powershell
ssh-keygen -t ed25519 -C "vigia"
```

Enter a todo. Deja la frase de paso vacía o ponle una; las dos cosas sirven.

Luego copia la llave **pública**:

```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

Eso empieza por `ssh-ed25519 AAAA...`. **Esa es la pública y es la que se
comparte.** La otra, `id_ed25519` sin `.pub`, es la privada y no sale nunca de
tu computador.

## 3.3 · Crea el servidor

En la consola de Hetzner Cloud: **New project** → **Add server**.

- **Location**: Nuremberg o Helsinki. Da igual: el servidor no sirve páginas,
  solo baja datos y hace un push.
- **Image**: **Ubuntu 24.04**
- **Type**: **CX22** — 2 vCPU, 4 GB de RAM, 40 GB NVMe, ~€4,35/mes
- **SSH keys**: **Add SSH key** y pega la pública de arriba. Hazlo aquí; si
  creas el servidor sin llave, la contraseña de root llega por correo y eso es
  peor.
- **Name**: `vigia`
- **Create & Buy now**

Anota la **IP** que te da.

## 3.4 · Entra

```powershell
ssh root@LA-IP
```

La primera vez pregunta si confías en la máquina: `yes`.

Y actualiza el sistema antes de nada:

```bash
apt update && apt upgrade -y
```

---

# FASE 4 · Subir el proyecto y arrancar

## 4.1 · Una llave para que el servidor pueda publicar

El servidor tiene que poder hacer `push` al repositorio **sin tu contraseña de
GitHub**. Eso se hace con una llave de despliegue.

En el servidor:

```bash
mkdir -p /opt/vigia/.ssh
ssh-keygen -t ed25519 -f /opt/vigia/.ssh/id_ed25519 -N "" -C "vigia-servidor"
cat /opt/vigia/.ssh/id_ed25519.pub
```

Copia lo que salga. En GitHub, en tu repositorio:

`Settings → Deploy keys → Add deploy key`

- Title: `servidor vigia`
- Key: lo que copiaste
- **Marca «Allow write access»** — sin eso el servidor puede leer pero no
  publicar.

## 4.2 · Trae el proyecto y corre el instalador

En el servidor:

```bash
apt install -y git
git clone git@github.com:USUARIO/vigia.git /opt/vigia-tmp
mv /opt/vigia-tmp/* /opt/vigia-tmp/.[!.]* /opt/vigia/ 2>/dev/null
rmdir /opt/vigia-tmp
cd /opt/vigia
bash servidor/instalar.sh
```

El instalador deja montado Postgres —**escuchando solo en localhost**—, un
usuario `vigia` sin shell ni sudo, el entorno de Python, y el temporizador que
corre a las 05:40 hora de Bogotá.

**No abre ningún puerto al mundo.** Este servidor no sirve páginas: las
construye y las empuja a GitHub Pages, que es quien las sirve.

Es idempotente: si algo falla a la mitad, se arregla y se vuelve a correr.

## 4.3 · Los tokens

```bash
nano /opt/vigia/.env
```

La contraseña de la base ya está puesta: la generó el instalador. Falta:

```
SOCRATA_TOKEN=tu-token-de-datos.gov.co
SOCRATA_SECRET=tu-key-secret
TELEGRAM_TOKEN=el-que-te-dio-BotFather
TELEGRAM_CHAT=tu-numero-de-chat
VIGIA_SITIO=https://USUARIO.github.io/vigia/
```

`Ctrl+O`, Enter, `Ctrl+X` para guardar y salir.

> **La Key Secret de datos.gov.co equivale a tu contraseña de esa cuenta.** Si
> alguna vez la escribes en un chat, un correo o cualquier archivo que no sea
> este, revócala y genera otra.

## 4.4 · Que el servidor firme como anónimo

```bash
cd /opt/vigia
sudo -u vigia git config user.name  "Vigia SECOP"
sudo -u vigia git config user.email "12345678+usuario@users.noreply.github.com"
sudo -u vigia git remote set-url origin git@github.com:USUARIO/vigia.git
```

## 4.5 · Prueba

```bash
systemctl start vigia.service
journalctl -u vigia.service -f
```

`Ctrl+C` para dejar de mirar el registro; el ciclo sigue solo.

Si todo va bien, te llega un mensaje por Telegram. Si una puerta se pone en
rojo, te llega el motivo — y eso también es que funciona.

---

# FASE 5 · El histórico, y la bandera 4.3

Esto es lo que convierte a Vigía de una página de cifras en algo que encontró
algo.

```bash
sudo -u vigia /opt/vigia/servidor/vigia-historia.sh 12
```

**Unas cinco horas.** Puedes cerrar la ventana: sigue corriendo. Te avisa por
Telegram cuando termine.

Cuando acabe:

```bash
sudo -u vigia psql -h localhost -U vigia -d vigia -f /opt/vigia/medir-concentracion.sql
```

Mándame lo que salga.

> **Por qué esto importa.** La concentración por proveedor es la única
> medición del proyecto que sobrevivió al fondo: con mínimo de cinco contratos
> por entidad, la mediana de lo que se lleva el mayor proveedor es **29,3 %** y
> solo el **2,1 %** de las entidades pasa del 90 %. Minoría medida, no norma.
> Lo único que la bloquea es la ventana — y no hay que esperar un año para
> tener un año, porque los contratos de 2025 están ahí para mirarlos hoy.

---

# Comprobar que quedó bien

| Qué | Cómo |
|---|---|
| El sitio está vivo | abre `https://USUARIO.github.io/vigia/` |
| La portada es de hoy | la fecha del encabezado |
| El ciclo corre solo | `systemctl list-timers vigia.timer` |
| Te avisa | te llegó el mensaje de Telegram |
| No hay puertos abiertos | `ss -tlnp` — solo debe salir SSH |
| La base no escucha afuera | `ss -tlnp \| grep 5432` — solo `127.0.0.1` |
| Los commits son anónimos | en GitHub, mira el autor de un commit |

---

# Lo que sigue costando trabajo tuyo, y va a seguir así

**El hilo de X lo publicas tú.** Te llega escrito al teléfono, lo lees, lo
publicas. Treinta segundos a la semana.

Vigía no publica solo en X y no va a hacerlo. El día que alguien reclame, la
respuesta tiene que ser «una persona lo leyó», y no «lo publicó un proceso».
