---
story: 1.6 — Territorio (DIVIPOLA) y orden administrativo
status: review
implementada: 2026-09-05
migraciones: 008_territorio.sql
pruebas: 342 en verde contra PostgreSQL real
---

# Historia 1.6 — Territorio y orden administrativo

## 1. Por qué, y por qué ahora

Sin territorio no se puede comparar una alcaldía con otra, ni mirar un
departamento aparte, ni separar lo nacional de lo territorial.

Esa última separación dejó de ser un adorno el **7 de agosto de 2026**: el
cambio de gobierno movió lo **nacional** y no movió lo territorial —alcaldes y
gobernadores siguen en su periodo 2024-2027—. Una serie que mezcle los dos
órdenes le atribuye al cambio de gobierno lo que es otra cosa. Es el mismo tipo
de error del que ya nos salvó el calendario de festivos: una caída del 45,7 %
que resultó ser 1,0 % al normalizar por día hábil.

## 2. Lo que se midió antes de diseñar

`jbjy-vk9h` y el dataset oficial del DANE `vcjz-niiq`, el 2026-09-05.

### 2.1. `orden` no es binario: son tres valores

| `orden` | agosto 2026 | año 2019 |
|---|---|---|
| Territorial | 90 101 | 73 932 |
| Nacional | 19 967 | 66 860 |
| **Corporación Autónoma** | **2 224** | **1 800** |

Las Corporaciones Autónomas Regionales no son ni nacionales ni territoriales.
Aparecen en los dos cortes, con siete años entre ellos, así que no son ruido de
un mes. **Una bandera `es_nacional` booleana las habría metido en el cajón que
no es**, y son quienes manejan la plata ambiental.

### 2.2. Los nombres de departamento vienen limpios

33 valores distintos en un mes: los 32 departamentos más Bogotá, sin variantes
ni erratas, más 1 593 contratos (1,4 %) con «No Definido». **No hay que limpiar
nombres; hay que traducirlos.**

### 2.3. Pero no coinciden con DIVIPOLA, y fallan justo donde más duele

| DANE (DIVIPOLA) | SECOP |
|---|---|
| `BOGOTÁ, D.C.` | `Distrito Capital de Bogotá` |
| `ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA` | `San Andrés, Providencia y Santa Catalina` |

Los otros 31 cuadran al pasar a mayúsculas y quitar tildes. Es decir: **un
cruce por nombre deja sin código a Bogotá, que es el 16 % de los contratos del
país, y lo deja en silencio.** No hay excepción, no hay error, no hay fila
rechazada: simplemente un hueco.

### 2.4. El municipio no se identifica por su nombre

`Argelia` son **tres** municipios distintos: Antioquia (16 contratos), Cauca
(16) y Valle del Cauca (15). Los conteos son casi iguales, así que fundirlos no
se vería raro en ningún reporte. La llave del municipio es el **par**
(departamento, municipio).

## 3. Lo que se implementó

- `orden` es **texto con tres valores** y `NULL`, no un booleano. `NULL`
  significa «la fuente no lo declaró», que **no es lo mismo que territorial**:
  rellenarlo con el valor más común convertiría «no sé» en un dato.
- El **departamento se codifica en DIVIPOLA**, con la tabla de 33 filas
  versionada en el repositorio —misma decisión que la tabla de esquemas de la
  1.3, y por la misma razón: una tabla que cambia bajo los pies vuelve
  incomparable cualquier serie histórica—.
- Los **dos alias** del SECOP se declaran explícitos, con su código. Una prueba
  recorre los 33 nombres que el SECOP escribe y exige que **todos** resuelvan:
  si mañana alguien reescribe la tabla, se cae ahí y no en un reporte con un
  hueco silencioso.
- El **nombre que se guarda es el oficial** cuando se pudo resolver, para que
  dos contratos del mismo departamento se muestren igual. Cuando no resolvió,
  se guarda el que escribió la entidad: es lo único con lo que se podrá
  diagnosticar por qué.
- El **municipio va con nombre y sin código**, a propósito (§2.4). Son ~1 100
  entradas y, hasta tener la tabla oficial cargada y comprobada, un código
  adivinado es peor que ninguno.

La base pone tres barreras: `orden` solo admite los tres valores medidos, el
código de departamento tiene que ser dos dígitos, y un código sin nombre se
rechaza —media identidad no existe, igual que en la 1.4 y la 1.5—.

## 4. Lo que queda pendiente

1. **Códigos de municipio** (historia propia). Requiere cargar la tabla DIVIPOLA
   de municipios y comprobarla contra los 638 nombres que el SECOP escribe en un
   mes. Hasta entonces, cualquier corte municipal se hace por
   (departamento, nombre) y hay que decirlo.
2. **El corte del 7 de agosto**, ahora que se puede hacer bien: comparar
   nacional contra territorial, por día hábil, y ver qué se movió de verdad.
   Ese es el análisis que esta historia habilita y que sin ella habría dado un
   número falso.
