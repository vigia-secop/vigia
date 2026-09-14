-- ¿CUÁNTAS DE LAS CIFRAS GRANDES SON ERRATAS DE TECLEO? SOLO LECTURA.
--
--     psql -f medir-erratas.sql
--
-- POR QUÉ EXISTE ESTA CONSULTA, Y TIENE NOMBRE PROPIO. El 2026-09-11 salió en
-- la lista de revisión este contrato:
--
--     FUNDACION MIL COLORES MAS · CO1.PCCNTR.9762242
--     ALCALDÍA MUNICIPAL DE TIPACOQUE (Boyacá, ~3.000 habitantes)
--     $431.340.000.000
--
-- Un municipio de tres mil habitantes contratando cuatrocientos treinta y un
-- mil millones de pesos con una fundación. Publicado tal cual, ese renglón es
-- una bomba. Y es falso: el proceso del que sale ese contrato tiene un
-- presupuesto oficial de **$431.340.000** — el mismo número con **tres ceros
-- de más**. No es un desfalco: es una tecla.
--
-- LO QUE ESTO DEMUESTRA. El techo de valores imposibles (1e14, migración 009)
-- **no ataja esto y nunca pudo**: 431 mil millones es un contrato
-- perfectamente posible en Colombia. Está escrito a propósito en
-- `tests/test_escala.py` para que nadie crea que esa guarda cubre más de lo
-- que cubre. La errata ×1000 no se detecta por tamaño. Se detecta por
-- **proporción**: contra el presupuesto del propio proceso, y contra lo que esa
-- misma entidad firma normalmente.
--
-- LA REGLA DE LA CASA SIGUE EN PIE: el fondo se cuenta PRIMERO. Si resulta que
-- el 40 % de los procesos adjudican por encima de diez veces su presupuesto,
-- entonces «×1000» no es una errata, es cómo funciona el campo, y esta
-- consulta se cierra igual que se cerraron la 2.4 y la 4.2.
--
-- QUÉ NO ES ESTO. No es una bandera de corrupción y no se publica como
-- hallazgo. Es un **filtro de calidad**: lo que caiga aquí no se puede usar en
-- ningún ranking por valor hasta que se mire una por una.

\pset border 2
\pset numericlocale on

-- Una sola fila por (proceso, adjudicación), la más reciente. Mismo destilado
-- que las otras mediciones. El casteo va con guarda de forma: `precio_base`
-- llega a veces con texto, y un error de casteo aquí mata la consulta entera.
CREATE TEMP TABLE p AS
SELECT contenido->>'id_del_proceso'                              AS id_del_proceso,
       contenido->>'entidad'                                     AS entidad_proceso,
       contenido->>'modalidad_de_contratacion'                   AS modalidad,
       CASE WHEN contenido->>'precio_base' ~ '^[0-9]+(\.[0-9]+)?$'
            THEN (contenido->>'precio_base')::numeric END        AS base,
       CASE WHEN contenido->>'valor_total_adjudicacion' ~ '^[0-9]+(\.[0-9]+)?$'
            THEN (contenido->>'valor_total_adjudicacion')::numeric END AS adjudicado
FROM (
    SELECT DISTINCT ON (contenido->>'id_del_proceso', contenido->>'id_adjudicacion')
           contenido
    FROM crudo_registro WHERE dataset = 'procesos'
    ORDER BY contenido->>'id_del_proceso', contenido->>'id_adjudicacion',
             consultado_en DESC
) u
WHERE contenido->>'adjudicado' = 'Si';

CREATE INDEX ON p (id_del_proceso);

-- Solo los que tienen los dos números. `razon` es adjudicado ÷ presupuesto.
CREATE TEMP TABLE r AS
SELECT id_del_proceso, entidad_proceso, modalidad, base, adjudicado,
       adjudicado / base                       AS razon,
       log(adjudicado / base)                  AS orden
FROM p
WHERE base > 0 AND adjudicado > 0;


-- ---------------------------------------------------------------------------
-- 1. EL FONDO. ¿Dónde vive la razón adjudicado ÷ presupuesto, por orden de
--    magnitud? La columna que decide si esta consulta sigue viva es la de
--    «×1000 o más»: si es gruesa, no es una errata, es el campo.
-- ---------------------------------------------------------------------------
SELECT CASE
         WHEN razon <  0.001 THEN 'a. menos de la milesima parte'
         WHEN razon <  0.1   THEN 'b. entre 0,1 % y 10 %'
         WHEN razon <= 1.0   THEN 'c. NORMAL: hasta el presupuesto'
         WHEN razon <  2     THEN 'd. hasta el doble'
         WHEN razon <  10    THEN 'e. de 2 a 10 veces'
         WHEN razon <  100   THEN 'f. de 10 a 100 veces'
         WHEN razon <  1000  THEN 'g. de 100 a 1.000 veces'
         ELSE                     'h. MIL VECES O MAS'
       END                                                 AS franja,
       count(*)                                            AS procesos,
       round(100.0 * count(*) / sum(count(*)) OVER (), 3)  AS pct,
       sum(adjudicado)::numeric(28,0)                      AS valor_adjudicado
FROM r GROUP BY 1 ORDER BY 1;


-- ---------------------------------------------------------------------------
-- 2. LA FIRMA DE LA TECLA. Un sobrecosto real da una razón cualquiera: 2,3;
--    7,8; 41,5. Una errata de tecleo da una razón que es **exactamente** una
--    potencia de diez, porque lo único que cambió fue la cantidad de ceros.
--
--    Esa diferencia es la que hace que esto sea medible y no una corazonada:
--    se pregunta cuántos de los que están por encima de ×10 caen a menos del
--    0,1 % de un 10, 100, 1.000 o 10.000 exacto. Si el mundo no tuviera
--    erratas, esa columna sería casi cero por pura aritmética.
-- ---------------------------------------------------------------------------
WITH alto AS (
    SELECT *,
           round(orden)                                   AS n,
           razon / power(10::numeric, round(orden))       AS cerca_de_uno
    FROM r WHERE razon >= 10
)
SELECT n                                                  AS ceros_de_mas,
       count(*)                                           AS procesos,
       count(*) FILTER (WHERE abs(cerca_de_uno - 1) < 0.001) AS potencia_exacta,
       round(100.0 * count(*) FILTER (WHERE abs(cerca_de_uno - 1) < 0.001)
             / count(*), 1)                               AS pct_exacta,
       sum(adjudicado) FILTER (WHERE abs(cerca_de_uno - 1) < 0.001)::numeric(28,0)
                                                          AS valor_de_las_exactas
FROM alto GROUP BY 1 ORDER BY 1;


-- ---------------------------------------------------------------------------
-- 3. LAS SOSPECHOSAS, UNA POR UNA. Potencia de diez exacta, de ×100 para
--    arriba. `valor_probable` es lo que diría el renglón si la errata es lo
--    que parece. **No se corrige nada en la base**: la capa cruda no se toca y
--    la normalizada guarda lo que la fuente publicó. Esto es una lista para
--    mirar, no un parche.
-- ---------------------------------------------------------------------------
WITH alto AS (
    SELECT *, round(orden) AS n, razon / power(10::numeric, round(orden)) AS u
    FROM r WHERE razon >= 100
)
SELECT id_del_proceso,
       left(coalesce(entidad_proceso,'—'), 38)    AS entidad,
       left(coalesce(modalidad,'—'), 26)          AS modalidad,
       base::numeric(28,0)                        AS presupuesto,
       adjudicado::numeric(28,0)                  AS adjudicado,
       n                                          AS ceros_de_mas,
       base::numeric(28,0)                        AS valor_probable
FROM alto
WHERE abs(u - 1) < 0.001
ORDER BY adjudicado DESC
LIMIT 40;


-- ---------------------------------------------------------------------------
-- 4. ¿LLEGA LA ERRATA HASTA EL CONTRATO? Esta es la pregunta que de verdad
--    importa, porque el Panel, la lista de revisión y el boletín leen
--    `contrato`, no `proceso`. Si la errata se queda en la capa de procesos,
--    molesta poco. Si cruza, contamina todos los rankings por valor.
--
--    Tipacoque cruzó.
-- ---------------------------------------------------------------------------
WITH alto AS (
    SELECT *, round(orden) AS n, razon / power(10::numeric, round(orden)) AS u
    FROM r WHERE razon >= 100
), sospechoso AS (
    SELECT id_del_proceso, base, adjudicado, n FROM alto WHERE abs(u - 1) < 0.001
)
SELECT count(*)                                        AS contratos_tocados,
       sum(c.valor)::numeric(28,0)                     AS valor_que_arrastran,
       round(100.0 * sum(c.valor) /
             nullif((SELECT sum(valor) FROM contrato
                     WHERE valor_fuera_de_escala IS NOT TRUE), 0), 2) AS pct_del_total
FROM contrato c JOIN sospechoso s USING (id_del_proceso);

WITH alto AS (
    SELECT *, round(orden) AS n, razon / power(10::numeric, round(orden)) AS u
    FROM r WHERE razon >= 100
), sospechoso AS (
    SELECT id_del_proceso, base, adjudicado, n FROM alto WHERE abs(u - 1) < 0.001
)
SELECT c.id_contrato,
       left(coalesce(c.nombre_entidad,'—'), 34)   AS entidad,
       left(coalesce(c.proveedor_nombre,'—'), 30) AS proveedor,
       c.valor::numeric(28,0)                     AS valor_publicado,
       s.base::numeric(28,0)                      AS valor_probable,
       s.n                                        AS ceros_de_mas,
       (SELECT rr.contenido->'urlproceso'->>'url'
        FROM crudo_registro rr
        WHERE rr.dataset = 'contratos'
          AND rr.contenido->>'id_contrato' = c.id_contrato
        ORDER BY rr.consultado_en DESC LIMIT 1)   AS enlace
FROM contrato c JOIN sospechoso s USING (id_del_proceso)
ORDER BY c.valor DESC NULLS LAST
LIMIT 40;


-- ---------------------------------------------------------------------------
-- 5. LA SEGUNDA PRUEBA: CONTRA LA PROPIA ENTIDAD. La prueba 2 necesita que el
--    contrato tenga proceso enlazado y presupuesto. Muchos no lo tienen, y
--    Tipacoque podría no haberlo tenido.
--
--    Esta prueba no necesita nada de eso. Pregunta: **¿cuántas veces el
--    contrato más grande de una entidad es más grande que la mediana de esa
--    misma entidad?** Una alcaldía de tres mil habitantes que firma casi todo
--    entre diez y cien millones y de pronto firma cuatrocientos mil millones
--    salta sin comparar con nada externo.
--
--    Y el fondo va primero, otra vez: el mínimo de 5 contratos no es un umbral
--    elegido para que dé bonito, es la cantidad por debajo de la cual la
--    palabra «mediana» no significa nada.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE e AS
SELECT nit_entidad,
       max(nombre_entidad)                          AS entidad,
       count(*)                                     AS contratos,
       -- El casteo no es adorno: `percentile_cont` devuelve `double
       -- precision`, y `round(double, int)` no existe en Postgres. Ya nos
       -- costó una consulta rota una vez.
       percentile_cont(0.5) WITHIN GROUP (ORDER BY valor)::numeric AS mediana,
       max(valor)                                   AS mayor
FROM contrato
WHERE valor > 0 AND valor_fuera_de_escala IS NOT TRUE
GROUP BY nit_entidad;

SELECT CASE
         WHEN contratos < 5   THEN 'a. menos de 5 contratos (no se mide)'
         WHEN salto < 10      THEN 'b. el mayor es menos de 10x la mediana'
         WHEN salto < 100     THEN 'c. de 10 a 100 veces'
         WHEN salto < 1000    THEN 'd. de 100 a 1.000 veces'
         WHEN salto < 10000   THEN 'e. de 1.000 a 10.000 veces'
         ELSE                      'f. mas de 10.000 veces'
       END                                                AS franja,
       count(*)                                           AS entidades,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
FROM (SELECT contratos, mayor / nullif(mediana, 0) AS salto FROM e) t
GROUP BY 1 ORDER BY 1;


-- ---------------------------------------------------------------------------
-- 6. EL CRUCE DE LAS DOS PRUEBAS. Un contrato que (a) salta mil veces por
--    encima de la mediana de su entidad y (b) esa entidad tiene historia
--    suficiente para que la mediana signifique algo.
--
--    Aquí no hay veredicto. Hay una lista corta para abrir en SECOP.
-- ---------------------------------------------------------------------------
SELECT c.id_contrato,
       left(coalesce(c.nombre_entidad,'—'), 34)       AS entidad,
       left(coalesce(c.departamento_nombre,'—'), 14)  AS departamento,
       left(coalesce(c.proveedor_nombre,'—'), 28)     AS proveedor,
       c.valor::numeric(28,0)                         AS valor,
       e.mediana::numeric(28,0)                       AS mediana_entidad,
       e.contratos                                    AS contratos_entidad,
       round(c.valor / nullif(e.mediana, 0), 0)       AS veces_la_mediana,
       (SELECT rr.contenido->'urlproceso'->>'url'
        FROM crudo_registro rr
        WHERE rr.dataset = 'contratos'
          AND rr.contenido->>'id_contrato' = c.id_contrato
        ORDER BY rr.consultado_en DESC LIMIT 1)       AS enlace
FROM contrato c JOIN e ON e.nit_entidad = c.nit_entidad
WHERE e.contratos >= 5
  AND c.valor > 0 AND c.valor_fuera_de_escala IS NOT TRUE
  AND c.valor / nullif(e.mediana, 0) >= 1000
ORDER BY c.valor DESC NULLS LAST
LIMIT 40;


-- ---------------------------------------------------------------------------
-- 7. LO QUE ESTO LE CUESTA AL BOLETÍN. Si las sospechosas mueven un pedazo
--    apreciable del valor de la ventana, entonces **ninguna cifra de total, ni
--    ningún ranking por valor, se puede publicar sin descontarlas**. Este
--    número es el que decide si hay que tocar `boletin.sql`.
-- ---------------------------------------------------------------------------
WITH alto AS (
    SELECT *, round(orden) AS n, razon / power(10::numeric, round(orden)) AS u
    FROM r WHERE razon >= 100
), sospechoso AS (
    SELECT id_del_proceso FROM alto WHERE abs(u - 1) < 0.001
), universo AS (
    SELECT sum(valor) AS todo FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE
), tocado AS (
    SELECT coalesce(sum(c.valor), 0) AS parte
    FROM contrato c JOIN sospechoso s USING (id_del_proceso)
    WHERE c.valor_fuera_de_escala IS NOT TRUE
)
SELECT (SELECT todo FROM universo)::numeric(28,0)   AS valor_total_ventana,
       (SELECT parte FROM tocado)::numeric(28,0)    AS valor_de_las_sospechosas,
       round(100.0 * (SELECT parte FROM tocado)
             / nullif((SELECT todo FROM universo), 0), 2) AS pct,
       ((SELECT todo FROM universo) - (SELECT parte FROM tocado))::numeric(28,0)
                                                    AS total_si_se_descuentan;

DROP TABLE r;
DROP TABLE p;
DROP TABLE e;
