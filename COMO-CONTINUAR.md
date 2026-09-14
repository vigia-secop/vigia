# Cómo continuar Vigía SECOP en un chat nuevo

## Lo primero, una sola vez

Este proyecto vive ahora en tu computador, en la carpeta donde está este archivo. En cada chat nuevo, conecta esta carpeta desde la app de escritorio ("Add folder") antes de pedir nada. Sin eso, el chat nuevo no ve el proyecto.

Luego, una sola vez, instala BMAD dentro de esta carpeta. Requiere Node 20.12 o superior:

```
npx bmad-method install --modules bmm --tools claude-code \
  --communication-language Spanish \
  --document-output-language Spanish
```

Si prefieres, se lo pides al chat: *"instala BMAD en esta carpeta, módulo bmm, en español"*.

## El prompt de arranque de cualquier chat nuevo

Pégalo tal cual al abrir la sesión:

> Este es el proyecto Vigía SECOP. Lee `_bmad-output/planning-artifacts/` completo antes de hacer nada: el brief, la investigación de la API, el PRD, la arquitectura y las épicas. No repitas la planeación, ya está hecha.

## Una sola vez: planear el sprint

En la versión 6.11 el ciclo cambió. `bmad-create-story` y `bmad-dev-story` quedaron deprecados; el método oficial de implementación es ahora **`bmad-build`**.

Antes de la primera historia, en un chat con la carpeta conectada:

> Corre `bmad-sprint-planning` sobre `_bmad-output/planning-artifacts/epics.md`.

Genera el archivo de seguimiento del sprint y verifica que la planeación esté completa antes de dejarte escribir código.

## El ciclo por historia

**Cada paso va en un chat nuevo.** No es capricho: el contexto de implementar una historia contamina la revisión de la siguiente, y el modelo arrastra decisiones viejas.

**Paso 1 — Implementar.** Chat nuevo, después del prompt de arranque:

> Implementa la historia 1.1 con `bmad-build`.

`bmad-build` lee la historia desde las épicas, sigue la arquitectura y los patrones del proyecto, y produce el código.

**Paso 2 — Revisar.** Chat nuevo:

> Revisa la implementación de la historia 1.1 con `bmad-code-review`.

Es una revisión adversarial en capas paralelas con triage. No es un vistazo.

**Paso 3 — Tu control humano.** Chat nuevo, cuando el cambio sea grande o toque algo delicado:

> Hazme un `bmad-checkpoint-preview` de la historia 1.1.

Te explica qué cambió, dónde mirar y cómo probarlo. Este es tu punto de control real: el que decide si eso entra o no.

Y vuelves al paso 1 con la 1.2.

## Atajos útiles

| Lo que quieres | Lo que pides |
|---|---|
| Ver en qué vas | `bmad-sprint-planning` (vista de estado) |
| No sabes qué sigue | `bmad-help` |
| Cambió algo y hay que ajustar el plan | `bmad-correct-course` |
| Poner a prueba una decisión | `bmad-review` |
| Cerrar una épica y sacar aprendizajes | `bmad-retrospective` |
| Hablar con un rol específico | `bmad-agent-architect`, `bmad-agent-dev`, `bmad-agent-pm` |

No hace falta memorizar nombres ni escribir barras. Basta con decir qué quieres: *"implementa la 1.2"*, *"revisa la 1.2"*, *"en qué voy"*. El nombre del skill es por si quieres ser explícito.

## El orden de las historias

Van en orden numérico. La épica 1 completa antes de la épica 2, y así. Las excepciones:

- **Épica 5 (publicación):** se puede construir en paralelo, pero **no se publica nada** hasta tener el concepto jurídico.
- **Épica 4 (catálogo):** las historias 4.1 a 4.8 son independientes entre sí. Se pueden hacer en cualquier orden, o en paralelo si tienes con quién.

## Lo que no se negocia en implementación

Si en algún momento el desarrollador propone saltarse esto, la respuesta es no:

1. Ninguna alerta se emite sin expediente completo.
2. Ninguna regla pasa a nacional sin haber corrido antes en calibración sobre un recorte.
3. Ninguna publicación sin aprobación humana explícita.
4. Ningún nombre de persona natural en un reporte publicado.
5. Ningún término acusatorio en textos de cara al usuario.

Están en el PRD como requisitos y en la arquitectura como invariantes. Si una historia las contradice, la historia está mal.
