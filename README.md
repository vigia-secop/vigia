# Vigía SECOP

Vigilancia de contratación pública colombiana. El sistema ingiere los datasets
del SECOP, los normaliza, corre reglas versionadas sobre ellos y publica
reportes con sustento verificable.

La planeación completa —brief, PRD, arquitectura y épicas— vive en
`_bmad-output/planning-artifacts/`. Léela antes de tocar código: hay
invariantes que el código no puede contradecir.

Estado: **1.1** (capa cruda), **1.2** (marca de agua e ingesta incremental),
**1.3** (validación de esquema) y **1.4** (esquema unificado y cruce
proceso–contrato) implementadas. Las tres primeras están **verificadas de punta
a punta contra la fuente real y PostgreSQL real** el 2026-09-03: 219 pruebas,
31 de ellas contra el motor, y una ingesta de 24 685 contratos del SECOP.

## Qué hay hoy

```
vigia/
├── ingest/       consulta a Socrata, marca de agua y orquestación del Ciclo
├── crudo/        capa cruda: identidad determinista y almacenamiento
├── normalizado/  Contratos y Procesos tipados, y el cruce entre ellos
└── schema/       campos esperados por dataset y validación de su forma
migraciones/      SQL de la base de datos
tests/            la suite; nada de aquí sale a la red
```

## Arrancar

Requiere Python 3.11 o superior y un PostgreSQL. Docker sirve, pero **no es el
camino recomendado ni es necesario**: Docker Desktop en Windows exige
virtualización por hardware (VT-x / SVM) habilitada en la BIOS, y este proyecto
no tiene por qué exigirte eso para correr sus pruebas. Un PostgreSQL instalado
en la máquina no pide nada de eso.

- Windows: <https://www.postgresql.org/download/windows/>
- Linux/macOS: el paquete de tu distribución, o `brew install postgresql`

**En Windows, la forma corta:** clic derecho sobre `probar.ps1` → *Ejecutar con
PowerShell*. Encuentra la base (nativa o Docker, en ese orden), crea el rol y
las bases si es la primera vez, aplica las migraciones, instala, corre la suite
completa y hace una consulta real al SECOP, diciendo en cada paso si pasó o
falló. Sin base de datos también corre: salta lo que la necesita y lo dice. Es
también la forma de comprobar que todo funciona después de un cambio.

A mano, con PostgreSQL instalado en la máquina. El rol y las bases se crean una
sola vez, como superusuario:

```bash
psql -U postgres -c "CREATE ROLE vigia LOGIN PASSWORD 'vigia';"
psql -U postgres -c "CREATE DATABASE vigia OWNER vigia;"
psql -U postgres -c "CREATE DATABASE vigia_pruebas OWNER vigia;"

cp .env.example .env
for m in migraciones/*.sql; do psql "$VIGIA_DSN" -f "$m"; done
pip install -e ".[dev]"
```

En PowerShell, los equivalentes son `Copy-Item .env.example .env` y
`py -3 -m pip install -e ".[dev]"`.

Con Docker, en cambio, `docker compose up -d postgres` aplica `migraciones/`
**solo al crear el volumen**. Si el tuyo ya existía, aplícalas a mano con el
mismo bucle de arriba.

Saltarse la 002 deja el proyecto sin la tabla `esquema_novedad`: los Ciclos
siguen corriendo, pero los campos nuevos que detecten no se guardan en ninguna
parte (queda el aviso en el log).

## Correr una ingesta

Carga el entorno. En bash, `set -a` hace que un DSN con espacios o caracteres
especiales sobreviva intacto:

```bash
set -a; source .env; set +a

# Primer Ciclo de un dataset: el rango se acota a mano.
python -m vigia --dataset contratos --desde 2026-08-01 --hasta 2026-09-02

# Ciclos siguientes: arrancan solos de la marca de agua.
python -m vigia --dataset contratos

# Ver qué traería, sin escribir nada (en seco no hay marca: exige --desde):
python -m vigia --dataset contratos --desde 2026-08-01 --hasta 2026-08-02 --dry-run
```

En PowerShell, en vez de `source .env`:

```powershell
Get-Content .env | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
    $nombre, $valor = $_ -split '=', 2
    Set-Item -Path "Env:$($nombre.Trim())" -Value $valor.Trim()
}
```

Instalado el paquete, `vigia ...` equivale a `python -m vigia ...`.

Datasets disponibles: `contratos` (`jbjy-vk9h`) y `procesos` (`p6dx-8zbt`).
El rango incluye ambos extremos y se interpreta en **hora de Colombia**, no en
UTC: las fechas de estos datasets son marcas de tiempo sin zona, que se leen en
la del publicador. `--limite-pagina` (o `VIGIA_LIMITE_PAGINA`) ajusta el tamaño
de página; el tope de Socrata es 50 000.

## Cuando la fuente tropieza

El SECOP se cae. Medido el 2026-09-03, en dos corridas consecutivas: un
**HTTP 500** en la página 6 de 25, y un **HTTP 503** en la página 1. Sin
reintento, cada uno abortaba el Ciclo entero.

El cliente reintenta hasta **5 veces** ante 202, 408, 425, 429, 500, 502, 503 y
504, y ante un fallo de red, con espera que se duplica (2 s, 4 s, 8 s… con tope
de 60) y dispersión aleatoria, para que varios Ciclos que tropiecen a la vez no
vuelvan a estrellarse juntos. Si la respuesta trae `Retry-After` en segundos,
se obedece, recortado al mismo tope: la fuente sabe mejor cuánto tarda en
volver, pero no se le deja colgar el Ciclo.

**Un 4xx no se reintenta.** Un 400 dice que la consulta está mal formada:
repetirla la repite mal, gasta cuota y esconde el error real. Solo se insiste
ante un «ahora no puedo», nunca ante un «lo que pediste está mal».

Agotados los intentos, el Ciclo aborta como siempre: queda `fallido` con su
causa, la marca no avanza, y el siguiente reanuda sin huecos.

Si los 503 son constantes, es la cuota por IP. Un token de aplicación de
Socrata es gratuito y da cuota propia: se pone en `VIGIA_TOKEN_SOCRATA`.

## La marca de agua y la ventana

Cada dataset lleva su propia marca en `ingesta_marca`: hasta qué **fecha del
hecho** —firma del contrato, publicación del proceso— se leyó. Cada Ciclo
retrocede una ventana de solapamiento antes de consultar (30 días por defecto,
`--ventana-dias` o `VIGIA_VENTANA_DIAS`), porque el SECOP publica con retraso: un
contrato firmado el día 1 puede aparecer el día 12. Volver a leerlo no cuesta
filas —la capa cruda lo deduplica— pero no leerlo lo pierde para siempre.

**La marca avanza solo si el Ciclo termina completo.** Si aborta, queda un Ciclo
`fallido` con su causa y la marca donde estaba, y el siguiente reanuda sin huecos.

**El retraso de publicación no es fijo.** Medido dos días seguidos, contra la
misma fuente y con la misma consulta:

| Día de la medición | Ventana pedida | Resultado |
|---|---|---|
| 2026-09-02 | últimos 7 días | **cero filas**; el contrato más reciente del dataset estaba firmado el 24 de agosto — nueve días de retraso |
| 2026-09-03 | 26-ago a 2-sep (8 días) | **24 685 contratos** en 25 páginas |

De un día para el otro aparecieron veinticuatro mil contratos con fecha de firma
dentro de la ventana que la víspera estaba vacía. La fuente no publica con un
retraso constante: publica **a saltos**, en recargas masivas.

Esto es exactamente el escenario para el que existe la ventana de solapamiento,
y la razón de que no se pueda estrechar mirando una sola medición. Un Ciclo
diario con ventana de 7 días habría visto cero el día 2 —sin ningún síntoma de
error— y se habría perdido esos contratos para siempre si la marca hubiera
avanzado. Los 30 días por defecto son los que absorben el salto.

Corolario para quien quiera optimizar: **el número que hay que mirar no es el
retraso promedio, sino el salto máximo entre recargas**, y ese solo se conoce
midiéndolo durante semanas. Es parte de `ASSUMPTION-5`.

### Cuánto cuesta un Ciclo, medido

Primera medición real, 2026-09-03, sin token de Socrata, desde una máquina
doméstica en Colombia:

| | |
|---|---|
| Ventana | 8 días (26-ago a 2-sep) |
| Contratos leídos | 24 685, en 25 páginas de 1000 |
| Tiempo | 56 segundos |
| Velocidad | ~444 contratos/s, 2,2 s por página |
| Volumen diario | ~3 100 contratos/día |

La misma ventana, **escribiendo de verdad en la capa cruda**, y una tercera vez
**repitiendo el mismo Ciclo** para probar la idempotencia sobre datos reales.
Mismo día, misma máquina, misma consulta:

| | Solo leer | Leer e insertar | Repetir (todo duplicado) |
|---|---|---|---|
| Tiempo | 53 s | **95,4 s** | **77,6 s** |
| Insertados | — | 24 685 | **0** |
| Duplicados | — | 0 | **24 685** |
| Filas en la tabla | — | 24 685 | 24 685, sin cambio |

Insertar cuesta 42 s sobre leer; **rechazar por duplicado cuesta 25 s**. Ese
segundo número es el precio de la ventana de solapamiento en régimen estable:
cada Ciclo vuelve a enviar treinta días de filas para que la llave primaria las
rechace. Extrapolado a la ventana de 30 días, un Ciclo en régimen estable son
**~4,8 minutos**; uno que trae todo nuevo, ~6.

**La idempotencia, verificada sobre 24 685 filas reales:** reingerir el mismo
rango insertó cero y no movió la tabla. No la garantiza una comprobación en
Python sino la llave primaria, y por eso vale igual ante un Ciclo repetido a
mano, uno reintentado tras un fallo, o dos corriendo a la vez.

Extrapolado a la ventana de 30 días que usa el Ciclo por defecto: **~92 500
contratos en ~6 minutos**, de punta a punta.

Con eso `ASSUMPTION-5` («un Ciclo diario nacional es viable en costo y tiempo»)
queda **sostenido con evidencia**, no supuesto: seis minutos diarios sobre el
universo nacional de Contratos no es un problema de costo ni de tiempo. Falta
sumarle el dataset de Procesos, que todavía no se puede ingerir.

Un dato del mismo Ciclo, para dimensionar: **24 685 contratos firmados en ocho
días**, unos 3 100 diarios. Ese es el volumen real que este sistema tiene que
vigilar.

Consecuencia de la que conviene estar consciente: como `--hasta` es hoy por
defecto y la marca queda en `hasta`, en régimen estable **cada Ciclo relee los
últimos 30 días**, no solo lo nuevo. Es correcto —la capa cruda deduplica— pero
el costo en peticiones es el de una ventana de 30 días diarios, no el de un
incremento. La marca gana su sueldo cuando un Ciclo falla: ahí no avanza y el
siguiente alcanza más atrás. Medir ese costo real es parte de `ASSUMPTION-5`.

Cada Ciclo queda en la tabla `ciclo` con sus cursores y sus conteos. Un Ciclo
vacío y uno fallido son ambos registros válidos y se distinguen por `estado`:

```sql
-- Hasta dónde va cada dataset y cuándo se confirmó por última vez.
SELECT dataset, fecha_hecho, actualizada_en FROM ingesta_marca;

-- Los últimos Ciclos, con sus señales.
SELECT inicio, estado, cursor_entrada, cursor_salida, vistos, insertados,
       recuperados_por_solapamiento, en_borde_de_ventana, ventana_dias, causa
FROM ciclo WHERE dataset = 'contratos' ORDER BY inicio DESC LIMIT 10;
```

`ciclo` guarda también `ventana_dias` y `desde_derivado`, para poder calibrar la
ventana leyendo el histórico en vez de a ojo.

### Cuando se enciende «VENTANA CORTA»

El Ciclo cuenta cuántos registros **nuevos** entraron con fecha de hecho en el
día más viejo de la ventana. Si ese número no es cero, la fuente todavía está
publicando cosas de esa fecha y la ventana se está quedando corta: ensánchala
con `--ventana-dias` antes de perder algo. Es la única forma de enterarse *antes*
y no después.

`Recuperados por el solapamiento` cuenta los que entraron con fecha anterior a la
marca previa: los que se habrían perdido sin ventana. Sirve para calibrarla.

La alarma solo se enciende cuando `desde` salió de la marca. En un histórico
pedido a mano con `--desde`, que haya registros nuevos el primer día del rango
es lo normal, no una señal. Tampoco puede encenderse en `--dry-run`: en seco no
hay con qué comparar, así que nada se cuenta como nuevo.

### Por qué el cursor no es `ultima_actualizacion`

El PRD fijaba en `ASSUMPTION-1` que la marca de agua usara `ultima_actualizacion`.
Medido contra la fuente el 2026-09-02, el supuesto no se sostiene:

1. **`ultima_actualizacion` viene vacío en ~40% de los contratos, y en los 20
   firmados más recientemente no venía en ninguno.** Socrata omite las claves
   nulas, así que un filtro `ultima_actualizacion > marca` no excluye esas filas
   una vez: las excluye para siempre, y justo las más nuevas.
2. **El dataset se recarga completo, no se actualiza fila por fila.** Contratos
   firmados en 2024, 2025 y 2026 comparten el mismo `:created_at` y `:updated_at`
   al milisegundo. El campo de sistema `:updated_at` tampoco sirve como cursor:
   cada recarga movería todas las filas.

`ASSUMPTION-1` quedó reescrito por `sprint-change-proposal-2026-09-02.md`. El
cursor va sobre la fecha del hecho, que la fuente sí llena siempre.

**Lo que este diseño no cubre**, y conviene tener escrito:

- Una corrección retroactiva a un registro viejo, fuera de la ventana, no se
  detecta. Para eso está la historia 1.7 (barrido completo periódico).
- Un contrato **sin `fecha_de_firma`** es invisible para todo Ciclo incremental,
  para siempre: la consulta filtra sobre ese mismo campo y SoQL descarta los
  nulos. El Ciclo cuenta `sin_fecha_de_hecho` como camino defensivo, pero en la
  práctica esos registros no llegan a volver. Falta medir qué proporción de la
  fuente carece del campo — la misma medición que refutó `ultima_actualizacion`.

El trabajo que la revisión de esta historia identificó y difirió está en
`_bmad-output/implementation-artifacts/deferred-work.md`.

## El esquema esperado

Antes de traer nada, el Ciclo compara el esquema que el dataset **declara**
contra un conjunto de campos esperados versionado en `vigia/schema/esperado/`.

- Un campo esperado que **desaparece** detiene el Ciclo nombrándolo. No se
  escribe una sola fila.
- Un campo **nuevo** no detiene nada: queda en `esquema_novedad` con la fecha
  en que se vio por primera vez, para que alguien lo mire.

El esquema esperado se captura, no se escribe a mano:

```bash
python -m vigia.schema --capturar --dataset contratos
```

Eso sobrescribe el archivo del dataset. **Revisa el `diff` y versiónalo.** Ese
paso es el control: recapturar sin mirar convierte la alarma en un sello de
goma. Cuando la validación falle, la pregunta correcta no es «cómo la callo»
sino «qué cambió en la fuente y qué se rompe aguas abajo».

Hoy está capturado `contratos` (85 campos, 2026-09-02). `procesos` falta.

## Pruebas

```bash
pytest              # las 219; las 31 de integración se omiten sin VIGIA_DSN_PRUEBAS
pytest -m postgres  # idempotencia y durabilidad contra PostgreSQL real
```

Las pruebas de integración **borran filas**, así que leen `VIGIA_DSN_PRUEBAS` y
nunca `VIGIA_DSN`. Apúntalas a una base desechable.

## Lo que conviene saber antes de extender esto

- **La capa cruda es de solo inserción.** Un registro que cambió en la fuente
  entra como fila nueva; la anterior no se toca. La serie histórica es el
  activo del producto, no un efecto secundario.
- **La idempotencia la garantiza la llave primaria**, no una comprobación en
  Python. Reingerir contenido idéntico no inserta nada.
- **Paginar sin `$order` es un error silencioso.** Socrata no ordena por
  defecto y saltar registros no produce ningún síntoma visible. Todo recorrido
  pide `$order=:id`.
- **Pedir un `$limit` mayor que el tope de Socrata también lo es**: la fuente
  recorta la página sin avisar y una página recortada parece la última. Por eso
  el límite se valida contra el tope antes de la primera petición.
- **Socrata omite las claves nulas**: un campo ausente en la respuesta no es
  evidencia de que la fuente cambió de esquema. Importa para la historia 1.3.
- **El vocabulario del glosario es obligatorio** en tablas, tipos y funciones:
  Proceso, Contrato, Entidad, Proveedor, Alerta, Ciclo. Sin sinónimos en inglés.
- **El crudo se guarda completo**, campos de persona natural incluidos. La
  protección de esos datos vive aguas abajo, en publicación, no aquí.

## Lo que todavía no está

Identidad de proveedor (1.5), mapeo territorial a DIVIPOLA (1.6) y barrido
completo periódico (1.7).
