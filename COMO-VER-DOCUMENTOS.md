# Los documentos: cuándo se ven y cuándo no

## En tu escritorio: los ves si quieres

`revision.html` es tu herramienta de trabajo. Por defecto enmascara los
documentos de personas naturales, pero **el número completo está a una bandera
de distancia**:

```
py -3 -m vigia.revision --documentos-completos
```

Y si lo quieres siempre así, edita `ciclo-diario.ps1` y añade esa bandera en el
paso 5. Es tu computador y es tu decisión.

**Por qué el valor por defecto es enmascarado.** No por el riesgo de publicar
—esa puerta está cerrada por otro lado— sino porque la página se comparte: se
pega en un chat, se manda por correo, se le hace una captura. Eso pasó el
2026-09-11 con veintitrés cédulas, y ninguna barrera del proyecto podía
haberlo evitado. El valor por defecto protege del descuido, no de ti.

---

## En lo que se publica: el NIT sí, la cédula no

Y no es simetría por cautela. Es por lo que dicen los datos.

### El número que lo decide

De los veintitrés contratos sin razón social de esa misma captura:

| | Contratos | Valor | % del valor |
|---|---|---|---|
| **NIT** (empresas) | 2 | **$118.476 millones** | **99,7 %** |
| Cédula (personas) | 21 | $369 millones | 0,3 % |

La cédula más grande de la lista es de **$52,5 millones**. La mediana, de
**$15 millones**. Eso no son contratistas del Estado en el sentido que a Vigía
le interesa vigilar: **son personas con un contrato de prestación de
servicios**. Un ingeniero en una alcaldía, una enfermera en un hospital, un
profesional en una gobernación.

Publicar sus cédulas no le da control ciudadano a nadie sobre nada: **añade el
0,3 % del dinero y expone a veintiún trabajadores** por tener un contrato con
el Estado.

Y el 99,7 % que sí importa **va con NIT**, que se publica completo.

Lo mismo pasó en todas las mediciones: el contrato de $118 mil millones es un
NIT. Las uniones temporales que mueven $1,91 billones son grupos. Los
proveedores de más alcance —72 entidades, 61, 31— son aseguradoras e ICONTEC,
todos NIT. **Donde está el poder, está el NIT.**

### «Pero el SECOP es público»

Sí, y por eso Vigía enlaza al SECOP.

Que un dato esté disponible en una fuente oficial no es lo mismo que
republicarlo en bloque con un índice nuevo. La Ley 1581 de 2012 lo dice en su
principio de **finalidad** (art. 4, literal b): un dato personal se trata para
el fin que justificó recogerlo. SECOP publica la cédula para que se pueda
consultar **ese contrato**; una lista de cédulas ordenada por valor es otra
cosa, con otro uso, y la responsabilidad de ese uso es de quien la publica.

Esto no es un tecnicismo que nos frene: es la diferencia entre una herramienta
de control y un directorio.

### Y lo decisivo: no hace falta

**Para comprobar un contrato no se necesita la cédula. Se necesita el
contrato.** Por eso el identificador ahora va como enlace directo a la ficha
oficial:

```
CO1.PCCNTR.9790851  →  la ficha en SECOP
```

Ahí está todo: el nombre, el documento, el objeto, el valor, los soportes. En
la fuente, que es donde ese dato se puede defender y donde se puede corregir si
está mal.

**El enlace da más que la cédula y publica menos.** Republicar el número da un
dato suelto, sin contexto, que ya no se puede retirar. El enlace da el
expediente entero y no publica nada.

---

## Lo que esto NO limita

Vigía puede publicar —y publica— **el NIT de una empresa contratista, el nombre
de la entidad, el valor, la modalidad, el departamento y el enlace al
contrato**. Con eso, cualquiera hace control sobre el 99,7 % del dinero.

El día que una Regla calibrada señale algo, señalará con esos elementos. Y
seguirá sin hacer falta una sola cédula.
