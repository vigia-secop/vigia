-- ¿SE PUEDE MEDIR CONCENTRACIÓN POR PROVEEDOR? SOLO LECTURA.
--
--     psql -f medir-concentracion.sql
--
-- LA LECCIÓN QUE ESTA CONSULTA APLICA. Tres banderas murieron el 2026-09-06
-- por el mismo motivo: describían la mayoría. «Un solo oferente» era el 52,8 %;
-- «pegado al presupuesto» era el 62,4 %. Los dos se veían como hallazgos hasta
-- que alguien contó el fondo.
--
-- Así que aquí el fondo se cuenta PRIMERO, y en concentración el fondo tiene
-- una trampa evidente que hay que atajar antes de mirar nada:
--
--     **Una entidad con dos contratos tiene, por fuerza, una concentración
--     altísima. No porque pase algo, sino porque tiene dos contratos.**
--
-- Si no se separa eso, el ranking de «entidades más concentradas» va a ser un
-- ranking de entidades pequeñas, y va a parecer un hallazgo. Por eso la
-- pregunta 1 no es sobre concentración: es sobre **cuántas entidades tienen
-- contratos suficientes para que la palabra signifique algo**.
--
-- Y HAY UN LÍMITE QUE VA EN CADA INFORME. 410 contratos de uniones temporales
-- sin documento —$1,91 billones, el 14,8 % del valor de la ventana— tienen
-- identidad propia y provisional: cada uno cuenta como un proveedor distinto.
-- **Ninguna medida de concentración los ve.** No es un detalle técnico: es una
-- séptima parte del dinero.

\pset border 2
\pset numericlocale on

-- Solo contratos con identidad de proveedor real y valor utilizable. Se
-- excluyen las uniones provisionales (cada una es su propia identidad, así que
-- inflarían la cuenta de proveedores distintos) y los valores imposibles.
CREATE TEMP TABLE c AS
SELECT nit_entidad, nombre_entidad, proveedor_tipo, proveedor_numero,
       proveedor_nombre, valor
FROM contrato
WHERE proveedor_tipo IS NOT NULL
  AND proveedor_provisional IS FALSE
  AND valor_fuera_de_escala IS NOT TRUE
  AND valor > 0;

-- 1. EL FONDO, ANTES QUE NADA: ¿cuántas entidades tienen contratos suficientes
--    para hablar de concentración? Si la mayoría tiene tres, cualquier ranking
--    de concentración es un ranking de entidades pequeñas disfrazado.
SELECT CASE
         WHEN n = 1        THEN 'a. 1 contrato'
         WHEN n <= 4       THEN 'b. 2 a 4'
         WHEN n <= 9       THEN 'c. 5 a 9'
         WHEN n <= 29      THEN 'd. 10 a 29'
         WHEN n <= 99      THEN 'e. 30 a 99'
         ELSE                   'f. 100 o mas'
       END                                          AS contratos_de_la_entidad,
       count(*)                                     AS entidades,
       sum(n)                                       AS contratos,
       sum(v)::numeric(24,0)                        AS valor
FROM (SELECT nit_entidad, count(*) AS n, sum(valor) AS v
      FROM c GROUP BY 1) t
GROUP BY 1 ORDER BY 1;

-- 2. LA CONCENTRACIÓN, y cómo cambia según dónde se ponga el mínimo. **Esta es
--    la tabla que decide si la historia se puede hacer.** Si la mediana de
--    «share del mayor proveedor» es alta en todos los cortes, entonces la
--    concentración es la norma y la 4.3 se cae como se cayeron las otras tres.
WITH e AS (
    SELECT nit_entidad, count(*) AS contratos, sum(valor) AS valor_total
    FROM c GROUP BY 1
), mayor AS (
    SELECT nit_entidad, max(v) AS valor_del_mayor
    FROM (SELECT nit_entidad, proveedor_tipo, proveedor_numero, sum(valor) AS v
          FROM c GROUP BY 1, 2, 3) p
    GROUP BY 1
), s AS (
    SELECT e.nit_entidad, e.contratos, mayor.valor_del_mayor / e.valor_total AS share
    FROM e JOIN mayor USING (nit_entidad) WHERE e.valor_total > 0
)
SELECT minimo AS minimo_de_contratos,
       count(*) FILTER (WHERE contratos >= minimo)                       AS entidades,
       round((percentile_cont(0.50) WITHIN GROUP (ORDER BY share)
             FILTER (WHERE contratos >= minimo))::numeric, 3)            AS mediana_share,
       round((percentile_cont(0.90) WITHIN GROUP (ORDER BY share)
             FILTER (WHERE contratos >= minimo))::numeric, 3)            AS p90_share,
       count(*) FILTER (WHERE contratos >= minimo AND share >= 0.90)     AS con_90_o_mas
FROM s, (VALUES (1), (5), (10), (30), (100)) AS m(minimo)
GROUP BY minimo ORDER BY minimo;

-- 3. LA OTRA CARA, y probablemente la más útil: proveedores que le facturan a
--    MUCHAS entidades distintas. Un proveedor con veinte entidades no es
--    sospechoso —puede ser una papelería nacional— pero es un hecho medible y
--    es el insumo de cualquier Regla de concentración que mire al proveedor y
--    no a la entidad.
SELECT CASE
         WHEN entidades = 1  THEN 'a. 1 entidad'
         WHEN entidades <= 3 THEN 'b. 2 a 3'
         WHEN entidades <= 9 THEN 'c. 4 a 9'
         WHEN entidades <= 29 THEN 'd. 10 a 29'
         ELSE                     'e. 30 o mas'
       END                                          AS entidades_del_proveedor,
       count(*)                                     AS proveedores,
       sum(contratos)                               AS contratos,
       sum(valor)::numeric(24,0)                    AS valor
FROM (SELECT proveedor_tipo, proveedor_numero,
             count(DISTINCT nit_entidad) AS entidades,
             count(*) AS contratos, sum(valor) AS valor
      FROM c GROUP BY 1, 2) p
GROUP BY 1 ORDER BY 1;

-- 4. LOS VEINTE DE MÁS ALCANCE, con nombre. Sin juicio: es una lista de
--    hechos, para poder mirarla con los ojos antes de escribir ninguna Regla.
SELECT left(coalesce(max(proveedor_nombre), '(sin razon social)'), 40) AS proveedor,
       proveedor_tipo AS tipo, proveedor_numero AS numero,
       count(DISTINCT nit_entidad)  AS entidades,
       count(*)                     AS contratos,
       sum(valor)::numeric(24,0)    AS valor
FROM c GROUP BY proveedor_tipo, proveedor_numero
ORDER BY count(DISTINCT nit_entidad) DESC, sum(valor) DESC
LIMIT 20;

-- 5. EL LÍMITE, dicho con número para que vaya en el informe y no se olvide.
SELECT count(*)                                            AS contratos_de_union_sin_documento,
       sum(valor)::numeric(24,0)                           AS valor_invisible,
       round(100.0 * sum(valor) / nullif((SELECT sum(valor) FROM contrato
              WHERE valor_fuera_de_escala IS NOT TRUE), 0), 1) AS pct_del_valor
FROM contrato WHERE proveedor_provisional;

DROP TABLE c;
