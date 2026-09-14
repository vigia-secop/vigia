-- ¿HAY NÓMINAS PARALELAS? UNA MISMA PERSONA CON VARIOS CONTRATOS A LA VEZ.
-- SOLO LECTURA.
--
--     psql -f medir-nominas-paralelas.sql
--
-- DE DÓNDE SALE ESTA PREGUNTA. Yo argumenté que las cédulas aportaban poco:
-- de 23 contratos, dos NIT movían el 99,7 % del dinero y veintiuna cédulas el
-- 0,3 %. El argumento era correcto **y estaba mirando la variable equivocada**.
--
-- En una nómina paralela el dinero de cada contrato es pequeño a propósito:
-- quince, veinte millones, prestación de servicios, por debajo de cualquier
-- umbral que mire valores. Lo que no es pequeño es el **patrón**: la misma
-- persona con cinco contratos abiertos al mismo tiempo, a veces en entidades
-- distintas. Eso no se ve sumando plata. Se ve contando solapamientos.
--
-- POR ESO LA CÉDULA SE GUARDA EN LA BASE. Esta consulta es exactamente la
-- razón por la que el número completo vive en `contrato` aunque no se escriba
-- en ninguna página: sin él, «la misma persona» no existe como concepto y
-- esta medición no se puede hacer.
--
-- LO QUE ESTA CONSULTA **NO** DICE, Y HAY QUE TENERLO CLARO ANTES DE LEERLA:
--
--   · Tener dos contratos a la vez **no es ilegal ni irregular**. Un contrato
--     de prestación de servicios con dos entidades distintas es legal, común y
--     a veces es simplemente cómo se gana la vida un profesional independiente.
--   · Las renovaciones consecutivas —enero a junio, julio a diciembre— no son
--     simultaneidad. Por eso aquí se miden **rangos que se traslapan**, no
--     contratos por año.
--   · La incompatibilidad depende del régimen de cada contrato y de la
--     dedicación pactada, que SECOP no publica. **Nosotros no podemos concluir
--     nada de eso.** Podemos contar, y contar bien.
--
-- Y LA REGLA DE LA CASA: el fondo primero. Si el 30 % de las personas tienen
-- tres contratos simultáneos, tres contratos simultáneos son la norma y no hay
-- historia. Tres banderas murieron el 2026-09-06 por saltarse este paso.

\pset border 2
\pset numericlocale on

-- ---------------------------------------------------------------------------
-- El universo: contratos de PERSONA NATURAL con fechas utilizables.
--
-- El tipo se reconoce por expresión regular y no por lista exacta porque la
-- fuente escribe «Cédula de Ciudadanía», «CEDULA DE CIUDADANIA» y «Cedula de
-- ciudadania» en el mismo dataset. El `~*` de Postgres no ignora las tildes,
-- así que las dos formas van escritas en el patrón.
--
-- Las fechas no están en la capa normalizada: se leen de la cruda, que las
-- trae como «2025-07-01T00:00:00.000». Se recorta a diez caracteres y se
-- comprueba la forma antes de castear.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE n AS
SELECT c.id_contrato,
       c.proveedor_numero                              AS documento,
       c.proveedor_tipo                                AS tipo,
       c.nit_entidad,
       c.nombre_entidad,
       c.departamento_nombre,
       c.valor,
       c.fecha_de_firma,
       f.inicio,
       f.fin
FROM contrato c
CROSS JOIN LATERAL (
    SELECT CASE WHEN left(rr.contenido->>'fecha_de_inicio_del_contrato', 10)
                     ~ '^\d{4}-\d{2}-\d{2}$'
                THEN left(rr.contenido->>'fecha_de_inicio_del_contrato', 10)::date END AS inicio,
           CASE WHEN left(rr.contenido->>'fecha_de_fin_del_contrato', 10)
                     ~ '^\d{4}-\d{2}-\d{2}$'
                THEN left(rr.contenido->>'fecha_de_fin_del_contrato', 10)::date END    AS fin
    FROM crudo_registro rr
    WHERE rr.dataset = 'contratos'
      AND rr.contenido->>'id_contrato' = c.id_contrato
    ORDER BY rr.consultado_en DESC
    LIMIT 1
) f
WHERE c.proveedor_numero IS NOT NULL
  AND c.proveedor_provisional IS FALSE
  AND c.proveedor_tipo ~* 'c[eé]dula|pasaporte|nuip|tarjeta de identidad|registro civil|permiso (especial|por)';

CREATE INDEX ON n (documento);


-- ---------------------------------------------------------------------------
-- 1. QUÉ VENTANA SE ESTÁ MIRANDO. Va primero y va en cualquier informe que
--    salga de aquí: «cinco contratos simultáneos» significa una cosa en un mes
--    de datos y otra muy distinta en tres años.
-- ---------------------------------------------------------------------------
SELECT count(*)                                    AS contratos_de_persona,
       count(DISTINCT documento)                   AS personas,
       min(fecha_de_firma)                         AS primera_firma,
       max(fecha_de_firma)                         AS ultima_firma,
       (max(fecha_de_firma) - min(fecha_de_firma)) AS dias_de_ventana,
       sum(valor)::numeric(28,0)                   AS valor
FROM n;

-- 2. ¿LLEGAN LAS FECHAS? Sin inicio y fin no hay simultaneidad que medir. Si
--    esta cobertura es baja, todo lo que sigue habla de una fracción del país
--    y hay que decirlo con ese nombre.
SELECT count(*)                                              AS contratos,
       count(*) FILTER (WHERE inicio IS NOT NULL)            AS con_inicio,
       count(*) FILTER (WHERE fin IS NOT NULL)               AS con_fin,
       count(*) FILTER (WHERE inicio IS NOT NULL AND fin IS NOT NULL
                          AND fin >= inicio)                 AS medibles,
       round(100.0 * count(*) FILTER (WHERE inicio IS NOT NULL AND fin IS NOT NULL
                          AND fin >= inicio) / nullif(count(*), 0), 1) AS pct_medible
FROM n;


-- ---------------------------------------------------------------------------
-- 3. EL FONDO, PRIMERA CAPA: cuántos contratos tiene cada persona en la
--    ventana, sin mirar fechas todavía. Esto solo por sí mismo no es un
--    hallazgo —seis contratos seguidos en un año son seis renovaciones— pero
--    dice el tamaño del terreno.
-- ---------------------------------------------------------------------------
SELECT CASE WHEN k = 1 THEN 'a. 1 contrato'
            WHEN k = 2 THEN 'b. 2'
            WHEN k <= 4 THEN 'c. 3 a 4'
            WHEN k <= 9 THEN 'd. 5 a 9'
            WHEN k <= 19 THEN 'e. 10 a 19'
            ELSE 'f. 20 o mas' END                       AS contratos_de_la_persona,
       count(*)                                          AS personas,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct,
       sum(v)::numeric(28,0)                             AS valor
FROM (SELECT documento, count(*) AS k, sum(valor) AS v FROM n GROUP BY 1) t
GROUP BY 1 ORDER BY 1;


-- ---------------------------------------------------------------------------
-- 4. LA MEDICIÓN DE VERDAD: SIMULTANEIDAD. Para cada persona, el mayor número
--    de contratos suyos que estaban abiertos **el mismo día**.
--
--    Se calcula por barrido de eventos: +1 el día que empieza un contrato, -1
--    el día siguiente al que termina; el máximo de la suma acumulada es el
--    pico. Es exacto y no depende de elegir fechas de corte.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE evento AS
SELECT documento, inicio AS dia, 1 AS delta FROM n
WHERE inicio IS NOT NULL AND fin IS NOT NULL AND fin >= inicio
UNION ALL
SELECT documento, fin + 1, -1 FROM n
WHERE inicio IS NOT NULL AND fin IS NOT NULL AND fin >= inicio;

CREATE TEMP TABLE pico AS
SELECT documento, max(abiertos) AS simultaneos
FROM (
    SELECT documento,
           sum(sum(delta)) OVER (PARTITION BY documento ORDER BY dia) AS abiertos
    FROM evento GROUP BY documento, dia
) t
GROUP BY documento;

SELECT CASE WHEN simultaneos <= 1 THEN 'a. nunca mas de 1 a la vez'
            WHEN simultaneos = 2  THEN 'b. 2 a la vez'
            WHEN simultaneos = 3  THEN 'c. 3'
            WHEN simultaneos = 4  THEN 'd. 4'
            WHEN simultaneos <= 6 THEN 'e. 5 a 6'
            WHEN simultaneos <= 9 THEN 'f. 7 a 9'
            ELSE                       'g. 10 o mas' END  AS pico_simultaneo,
       count(*)                                           AS personas,
       round(100.0 * count(*) / sum(count(*)) OVER (), 3) AS pct
FROM pico GROUP BY 1 ORDER BY 1;


-- ---------------------------------------------------------------------------
-- 5. SIMULTANEIDAD **ENTRE ENTIDADES DISTINTAS**. Esta es la forma que de
--    verdad interesa, y la diferencia no es cosmética:
--
--    · Dos contratos simultáneos con la MISMA entidad casi siempre son un
--      contrato y su adición, o dos objetos distintos del mismo convenio.
--    · Dos contratos simultáneos con entidades DISTINTAS son dos vínculos
--      independientes que existen a la vez.
--
--    Se cuenta como pareja: cuántas personas tienen al menos dos contratos que
--    se traslapan en el tiempo y pertenecen a entidades con NIT distinto.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE pareja AS
SELECT a.documento,
       a.id_contrato AS contrato_a, b.id_contrato AS contrato_b,
       a.nit_entidad AS nit_a,      b.nit_entidad AS nit_b,
       least(a.fin, b.fin) - greatest(a.inicio, b.inicio) + 1 AS dias
FROM n a JOIN n b
  ON a.documento = b.documento
 AND a.id_contrato < b.id_contrato
 AND a.nit_entidad IS DISTINCT FROM b.nit_entidad
 AND daterange(a.inicio, a.fin, '[]') && daterange(b.inicio, b.fin, '[]')
WHERE a.inicio IS NOT NULL AND a.fin IS NOT NULL AND a.fin >= a.inicio
  AND b.inicio IS NOT NULL AND b.fin IS NOT NULL AND b.fin >= b.inicio;

-- Las entidades se cuentan sobre LOS DOS LADOS de cada pareja. Contarlas solo
-- del lado `a` deja fuera a la entidad del contrato de id más alto, que nunca
-- aparece como `a`: con cuatro entidades reales el conteo decía tres. Es un
-- error silencioso, del peor tipo: da un número plausible.
CREATE TEMP TABLE entidad_de AS
SELECT documento, nit_a AS nit FROM pareja
UNION
SELECT documento, nit_b      FROM pareja;

CREATE TEMP TABLE cruce AS
SELECT p.documento,
       count(*)                                              AS parejas,
       (SELECT count(*) FROM entidad_de e
        WHERE e.documento = p.documento)                     AS entidades,
       max(p.dias)                                           AS dias_de_traslape_mayor
FROM pareja p GROUP BY p.documento;

SELECT (SELECT count(DISTINCT documento) FROM n)     AS personas_en_la_ventana,
       (SELECT count(*) FROM cruce)                  AS con_traslape_entre_entidades,
       round(100.0 * (SELECT count(*) FROM cruce)
             / nullif((SELECT count(DISTINCT documento) FROM n), 0), 3) AS pct,
       (SELECT count(*) FROM cruce WHERE entidades >= 3) AS con_tres_entidades_o_mas;


-- ---------------------------------------------------------------------------
-- 6. LA COLA, PARA MIRAR UNA POR UNA.
--
--    EL DOCUMENTO VA ENMASCARADO, y no es pudor: este archivo se guarda en
--    `nominas-paralelas-ultima-corrida.txt`, y un archivo se filtra por ser
--    legible —se pega en un chat, se manda por WhatsApp— mucho antes que por
--    publicarse. Los tres últimos dígitos bastan para distinguir dos filas, y
--    el `id_contrato` lleva a la ficha oficial del SECOP, donde está el nombre
--    completo, en la fuente, que es donde ese dato se puede defender.
--
--    Si de verdad hace falta el número entero para una denuncia formal, está
--    a una consulta de distancia y tiene que ser una decisión consciente:
--
--        SELECT proveedor_numero, proveedor_nombre FROM contrato
--        WHERE id_contrato = 'CO1.PCCNTR.XXXXXXX';
-- ---------------------------------------------------------------------------
SELECT repeat('•', greatest(length(c.documento) - 3, 0))
         || right(c.documento, 3)                    AS documento,
       p.simultaneos                                 AS pico_simultaneo,
       c.entidades                                   AS entidades_distintas,
       c.parejas                                     AS parejas_traslapadas,
       c.dias_de_traslape_mayor                      AS dias_traslape,
       (SELECT count(*) FROM n x WHERE x.documento = c.documento)        AS contratos,
       (SELECT sum(x.valor) FROM n x WHERE x.documento = c.documento)::numeric(28,0)
                                                                         AS valor_total,
       (SELECT string_agg(DISTINCT left(x.nombre_entidad, 22), ' | ')
        FROM n x WHERE x.documento = c.documento)    AS entidades_nombres
FROM cruce c LEFT JOIN pico p USING (documento)
ORDER BY c.entidades DESC, p.simultaneos DESC NULLS LAST, c.parejas DESC
LIMIT 30;


-- ---------------------------------------------------------------------------
-- 7. LOS CONTRATOS DE LOS CASOS DE ARRIBA, con su enlace al SECOP. Es lo que
--    permite comprobar sin que nosotros republiquemos nada: el enlace lleva a
--    la ficha oficial, con nombre, objeto y soportes.
-- ---------------------------------------------------------------------------
SELECT repeat('•', greatest(length(n.documento) - 3, 0))
         || right(n.documento, 3)                    AS documento,
       n.id_contrato,
       left(coalesce(n.nombre_entidad,'—'), 30)      AS entidad,
       left(coalesce(n.departamento_nombre,'—'), 14) AS departamento,
       n.valor::numeric(28,0)                        AS valor,
       n.inicio, n.fin,
       (SELECT rr.contenido->'urlproceso'->>'url'
        FROM crudo_registro rr
        WHERE rr.dataset = 'contratos'
          AND rr.contenido->>'id_contrato' = n.id_contrato
        ORDER BY rr.consultado_en DESC LIMIT 1)      AS enlace
FROM n
WHERE n.documento IN (SELECT documento FROM cruce
                      ORDER BY entidades DESC, parejas DESC LIMIT 8)
ORDER BY n.documento, n.inicio
LIMIT 80;


-- ---------------------------------------------------------------------------
-- 8. ¿SE PUEDE PUBLICAR ALGO DE ESTO? La respuesta sale de una sola cifra: el
--    porcentaje de la sección 5. Si es grueso, la simultaneidad entre
--    entidades es la norma y esta historia se cierra como se cerraron la 2.4 y
--    la 4.2. Si es delgado, hay una cifra publicable **sin nombrar a nadie**:
--    «N personas tuvieron contratos simultáneos con tres o más entidades».
--
--    Ese renglón no acusa a nadie, no republica ninguna cédula y es
--    exactamente el tipo de dato que hace que alguien con más herramientas que
--    nosotras vaya a mirar.
-- ---------------------------------------------------------------------------
--    El valor se suma sobre los CONTRATOS de esas personas, no sobre las
--    parejas: un contrato que se traslapa con otros tres aparece en tres
--    parejas, y sumar parejas lo contaría tres veces.
SELECT c.entidades                                   AS entidades_simultaneas,
       count(*)                                      AS personas,
       (SELECT sum(x.valor) FROM n x
        WHERE x.documento IN (SELECT d.documento FROM cruce d
                              WHERE d.entidades = c.entidades))::numeric(28,0)
                                                     AS valor_de_sus_contratos
FROM cruce c GROUP BY 1 ORDER BY 1 DESC;

DROP TABLE cruce;
DROP TABLE entidad_de;
DROP TABLE pareja;
DROP TABLE pico;
DROP TABLE evento;
DROP TABLE n;
