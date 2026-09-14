# Publicar Vigía de forma anónima

Esto no es una guía de seguridad operacional completa y no pretende serlo. Son
los cuatro sitios concretos por donde este proyecto, tal como está construido,
filtraría quién lo hace — y qué se hizo con cada uno.

---

## 1. Git escribe tu nombre en cada commit, para siempre

**Es el más fácil de pasar por alto y el más difícil de deshacer.** Cada commit
lleva grabado un nombre y un correo. En un repositorio público, cualquiera los
lee con un clic, y no se borran con `git commit --amend`: quedan en el
historial y en cualquier copia que alguien haya clonado.

`publicar.ps1` **aborta** si el correo de git no es uno de los que no
identifican. No avisa: aborta. Un aviso se lee después.

Para arreglarlo, una sola vez:

1. En GitHub: **Settings → Emails → Keep my email addresses private**. Esa
   página te da un correo de la forma `12345678+usuario@users.noreply.github.com`.
2. En la carpeta del proyecto:

```
git config user.name  "Vigia SECOP"
git config user.email "12345678+usuario@users.noreply.github.com"
```

Se usa `git config` sin `--global` a propósito: cambia solo este proyecto, y no
te toca el resto de tu trabajo.

**Si ya hiciste commits con tu correo personal**, cambiar la configuración no
los arregla. Lo limpio es empezar el repositorio de nuevo: borrar la carpeta
`.git`, configurar la identidad, y hacer el primer commit otra vez. Se pierde
el historial; no se pierde nada más.

## 2. La cuenta de GitHub y la dirección del sitio

`https://TU-USUARIO.github.io/vigia-secop/` lleva tu usuario en la dirección.
Si ese usuario es el que usas para todo lo demás, el sitio te apunta.

Para anónimo hace falta **una cuenta aparte**, creada con un correo que no uses
en otra parte, y sin datos de perfil. Si más adelante quieres un dominio
propio, GitHub Pages acepta uno — y ahí conviene registrarlo con la privacidad
del WHOIS activada, que hoy es lo normal.

## 3. El sitio y el boletín no llevan nada tuyo

Esto ya está resuelto por construcción, no por cuidado. **Y la regla cambió el
14 de septiembre de 2026, así que conviene leerla otra vez aunque ya la
supieras:**

- `boletin.sql` —el resumen semanal y el hilo de X— **no puede** devolver el
  nombre de nadie. Ni de una persona, ni de una empresa, ni de una entidad.
- `portada.sql` —la página de cada día— **sí devuelve el nombre y el NIT de una
  empresa, y NUNCA el documento entero de una persona natural**. El
  enmascarado se hace **dentro de la consulta**, no al dibujar la página: el
  programa que arma el HTML nunca recibe una cédula completa, así que ningún
  error mío en una plantilla puede sacarla a internet.
- En la portada, además, **las personas naturales salen sin nombre** —«Persona
  natural» y el documento enmascarado—, porque la portada es la superficie más
  amplificada del proyecto. En `panel.html` y `revision.html`, que son páginas
  de detalle, sí van con nombre.
- `.gitignore` excluye las copias de trabajo de esas páginas y las bitácoras.
- `publicar.ps1` recorre **toda** la carpeta `docs/` antes de subir y **aborta**
  si encuentra el documento de una persona natural escrito entero. La
  comprobación es fina a propósito: deja pasar los NIT, que son justo lo que
  hay que publicar, y atrapa las cédulas.
- El semáforo del servidor repite esa misma comprobación en su **puerta 6**.

**Nada de esto te protege a ti**, que es de lo que trata este documento —
protege a los contratistas personas naturales que aparecen en los datos. Son
dos problemas distintos y los dos hay que resolverlos.

## 4. Lo que el anonimato NO te da

**No es blindaje, y conviene tenerlo claro antes que después.** Una parte
decidida —con orden judicial, o simplemente con paciencia— puede llegar a un
autor por el patrón de horarios, por metadatos, por el proveedor de internet, o
porque alguien lo comentó. El anonimato sube el costo de averiguarlo; no lo
vuelve imposible.

**Lo que de verdad protege a este proyecto es otra cosa: que Vigía no acusa a
nadie.** Publica agregados de datos públicos, con la fuente citada y la
cobertura declarada. Contra eso no hay demanda que prospere, porque no hay
afirmación que desmentir.

El día que Vigía empiece a señalar —si ese día llega, y solo con una Regla
calibrada detrás— el anonimato deja de ser suficiente y hace falta lo que la
épica 5 tiene escrito desde el principio: **un concepto jurídico**. Eso sigue
pendiente y ningún archivo de este repositorio lo reemplaza.
