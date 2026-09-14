-- ¿SE PUEDE MEDIR EL FRACCIONAMIENTO? SOLO LECTURA.
--
--     psql -f medir-fraccionamiento.sql
--
-- QUÉ ES EL FRACCIONAMIENTO. Partir una compra en varios contratos pequeños
-- para no pasar del tope que obligaría a un proceso competitivo. Si una
-- entidad necesita cien millones en papelería y hace diez contratos de diez
-- millones al mismo proveedor en el mismo mes, cada uno cabe en mínima cuantía
-- y ninguno tuvo que competir.
--
-- POR QUÉ ESTA HISTORIA Y NO OTRA DE LAS SEIS QUE FALTAN. Las tres banderas
-- muertas cayeron por lo mismo: el umbral había que inventarlo. Esta tiene un
-- tope que **existe en el mundo** —el de la mínima cuantía, que fija la ley
-- según el presupuesto de cada entidad— y que además **no hace falta que yo lo
-- sepa**:
--
--     El tope de cada entidad se puede leer en su propio comportamiento:
--     es el contrato de mínima cuantía más caro que esa entidad firma.
--
-- Eso es mejor que buscar el número en la ley y equivocarme con el salario
-- mínimo del año: sale de los datos, se recalcula solo cada año, y es distinto
-- para cada entidad, como lo es de verdad.
--
-- EL ORDEN, QUE ES LO QUE SALVA O MATA LA HISTORIA. Primero se cuenta el
-- fondo: **cuántas mínimas cuantías caen en un grupo de dos o más del mismo
-- proveedor**. Si eso es la mayoría, entonces contratar dos veces al mismo
-- proveedor en un mes es lo normal, la bandera describe el país y se descarta
-- como las otras tres. Solo si es minoría tiene sentido seguir.
--
-- ESTO NO ACUSA A NADIE. Fraccionar puede ser una decisión administrativa
-- perfectamente legítima —compras repetidas, entregas por tramos, urgencias— y
-- esta consulta no distingue una cosa de la otra. Mide una FORMA en los datos.

\pset border 2
\pset numericlocale on

-- Contratos de mínima cuantía con identidad de proveedor real y valor útil.
-- La modalidad vive en `proceso`, así que solo entran los que cruzaron.
CREATE TEMP TABLE m AS
SELECT c.id_contrato, c.nit_entidad, c.nombre_entidad,
       c.proveedor_tipo, c.proveedor_numero,
       c.fecha_de_firma, c.valor
FROM contrato c
JOIN proceso p USING (id_del_proceso)
WHERE p.modalidad ILIKE '%m_nima cuant_a%'
  AND c.proveedor_tipo IS NOT NULL
  AND c.proveedor_provisional IS FALSE
  AND c.valor_fuera_de_escala IS NOT TRUE
  AND c.valor > 0
  AND c.fecha_de_firma IS NOT NULL;

-- 0. SOBRE CUÁNTO ESTAMOS HABLANDO. Si las mínimas cuantías que cruzaron con
--    su proceso son una fracción pequeña de las que hay, esta medición no
--    representa al país y hay que decirlo antes que nada.
SELECT (SELECT count(*) FROM m)                                   AS minimas_medibles,
       (SELECT count(*) FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE)
                                                                  AS contratos_en_total,
       (SELECT count(DISTINCT nit_entidad) FROM m)                AS entidades,
       (SELECT sum(valor)::numeric(24,0) FROM m)                  AS valor;

-- 1. EL FONDO. Grupos de (entidad, proveedor) con dos o más mínimas cuantías
--    dentro de 30 días. ¿Es raro o es lo normal?
CREATE TEMP TABLE g AS
SELECT nit_entidad, max(nombre_entidad) AS entidad,
       proveedor_tipo, proveedor_numero,
       date_trunc('month', fecha_de_firma)::date AS mes,
       count(*)                AS contratos,
       sum(valor)              AS suma,
       min(fecha_de_firma)     AS primero,
       max(fecha_de_firma)     AS ultimo
FROM m
GROUP BY 1, 3, 4, 5;

SELECT CASE WHEN contratos = 1 THEN 'a. 1 contrato'
            WHEN contratos <= 3 THEN 'b. 2 a 3'
            WHEN contratos <= 5 THEN 'c. 4 a 5'
            WHEN contratos <= 10 THEN 'd. 6 a 10'
            ELSE                     'e. 11 o mas' END      AS contratos_del_grupo,
       count(*)                                             AS grupos,
       sum(contratos)                                       AS contratos,
       round(100.0 * sum(contratos)
             / nullif((SELECT count(*) FROM m), 0), 1)      AS pct_de_las_minimas,
       sum(suma)::numeric(24,0)                             AS valor
FROM g GROUP BY 1 ORDER BY 1;

-- 2. EL TECHO DE CADA ENTIDAD, leído de su propia conducta: la mínima cuantía
--    más cara que firma. No hace falta el salario mínimo ni la tabla de la
--    ley: cada entidad declara su tope cada vez que contrata.
CREATE TEMP TABLE techo AS
SELECT nit_entidad,
       max(valor)                                                  AS tope,
       round((percentile_cont(0.95) WITHIN GROUP (ORDER BY valor))::numeric, 0) AS p95,
       count(*)                                                    AS minimas
FROM m GROUP BY 1;

SELECT count(*)                                          AS entidades,
       round((percentile_cont(0.50) WITHIN GROUP (ORDER BY tope))::numeric, 0) AS tope_mediano,
       round((percentile_cont(0.90) WITHIN GROUP (ORDER BY tope))::numeric, 0) AS tope_p90,
       max(tope)::numeric(24,0)                          AS tope_mayor
FROM techo WHERE minimas >= 5;

-- 3. LOS CANDIDATOS: grupos cuya SUMA pasa el techo de su propia entidad.
--    Solo se miran entidades con al menos cinco mínimas cuantías, porque con
--    dos el «techo» es el único contrato que hay y no significa nada — es la
--    misma trampa aritmética que la concentración por proveedor.
SELECT count(*)                                                AS grupos_candidatos,
       count(DISTINCT g.nit_entidad)                           AS entidades,
       sum(g.contratos)                                        AS contratos,
       sum(g.suma)::numeric(24,0)                              AS valor,
       round(100.0 * count(*) / nullif((SELECT count(*) FROM g WHERE contratos > 1), 0), 1)
                                                               AS pct_de_los_grupos
FROM g JOIN techo t USING (nit_entidad)
WHERE g.contratos > 1 AND t.minimas >= 5 AND g.suma > t.tope;

-- 4. POR CUÁNTO SE PASAN. Si casi todos se pasan por un pelo, es ruido de
--    redondeo; si se pasan por varias veces el tope, es otra cosa.
WITH c AS (
    SELECT g.*, t.tope, g.suma / t.tope AS veces
    FROM g JOIN techo t USING (nit_entidad)
    WHERE g.contratos > 1 AND t.minimas >= 5 AND g.suma > t.tope
)
SELECT CASE WHEN veces > 10 THEN 'e. mas de 10 veces el tope'
            WHEN veces > 5  THEN 'd. 5 a 10 veces'
            WHEN veces > 2  THEN 'c. 2 a 5 veces'
            WHEN veces > 1.2 THEN 'b. 1,2 a 2 veces'
            ELSE                 'a. hasta 1,2 veces' END  AS cuanto_se_pasa,
       count(*)                                            AS grupos,
       sum(contratos)                                      AS contratos,
       sum(suma)::numeric(24,0)                            AS valor
FROM c GROUP BY 1 ORDER BY 1;

-- 5. LOS VEINTE MAYORES, con nombre, para mirarlos con los ojos antes de
--    escribir una sola línea de Regla. **Esta lista no sale de este
--    computador**: es material de trabajo, no de publicación.
WITH c AS (
    SELECT g.*, t.tope, g.suma / t.tope AS veces
    FROM g JOIN techo t USING (nit_entidad)
    WHERE g.contratos > 1 AND t.minimas >= 5 AND g.suma > t.tope
)
SELECT left(entidad, 38) AS entidad, proveedor_numero AS proveedor,
       mes, contratos, suma::numeric(24,0) AS suma,
       tope::numeric(24,0) AS tope_de_la_entidad,
       round(veces, 1) AS veces
FROM c ORDER BY suma DESC LIMIT 20;

DROP TABLE m; DROP TABLE g; DROP TABLE techo;
