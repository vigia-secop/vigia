-- ¿QUÉ TRAE DE VERDAD LA FUENTE? Censo de cobertura, campo por campo. SOLO LECTURA.
--
--     psql -f medir-campos.sql
--
-- POR QUÉ EXISTE ESTA CONSULTA. El 2026-09-11 escribí que cuatro de las seis
-- banderas que faltan no se podían medir porque SECOP no publicaba los datos:
-- el ordenador del gasto, las prórrogas, la ejecución y el representante legal.
--
-- **Las cuatro estaban equivocadas.** El esquema que este mismo proyecto
-- captura y versiona —`vigia/schema/esperado/contratos.json`, 85 campos— trae
-- `nombre_ordenador_del_gasto`, `dias_adicionados`, `valor_pagado` y
-- `nombre_representante_legal`. Lo afirmé de memoria en vez de abrir el
-- archivo que teníamos delante.
--
-- PERO QUE EL CAMPO EXISTA NO ES QUE SIRVA, y esa lección ya la pagamos:
-- `proveedores_invitados` existe y llega poblado en el 25,7 % de los casos.
-- Una Regla montada sobre un cuarto del país presentada como si midiera el
-- país es otra forma de mentir.
--
-- Así que esta consulta no pregunta «¿está el campo?» sino **«¿en qué
-- porcentaje llega con algo utilizable?»**, que es la única pregunta cuya
-- respuesta decide si una historia se puede escribir.
--
-- CENTINELAS. La fuente escribe «No Definido», «No aplica», «0» y cadenas
-- vacías cuando no sabe. Contarlos como dato poblado inflaría la cobertura
-- justo en los campos donde más importa no engañarse.

\pset border 2
\pset numericlocale on

CREATE TEMP TABLE u AS
SELECT DISTINCT ON (contenido->>'id_contrato') contenido
FROM crudo_registro WHERE dataset = 'contratos'
ORDER BY contenido->>'id_contrato', consultado_en DESC;

-- Un campo «sirve» si trae algo que no es vacío, ni centinela, ni cero.
CREATE OR REPLACE FUNCTION pg_temp.util(v text) RETURNS boolean AS $$
  SELECT v IS NOT NULL
     AND btrim(v) <> ''
     AND upper(btrim(v)) NOT IN ('NO DEFINIDO','NO APLICA','NO DEFINIDA',
                                 'SIN DESCRIPCION','N/A','NA','NULL','NINGUNO')
     AND btrim(v) !~ '^0([.,]0+)?$';
$$ LANGUAGE sql IMMUTABLE;

SELECT historia, campo,
       count(*) FILTER (WHERE pg_temp.util(valor))                    AS con_dato,
       (SELECT count(*) FROM u)                                       AS de_un_total_de,
       round(100.0 * count(*) FILTER (WHERE pg_temp.util(valor))
             / nullif((SELECT count(*) FROM u), 0), 1)                AS pct,
       left(max(valor) FILTER (WHERE pg_temp.util(valor)), 28)        AS un_ejemplo
FROM (
  SELECT h.historia, h.campo, contenido->>h.campo AS valor
  FROM u, (VALUES
    -- 4.1 · Representante legal compartido entre proponentes.
    ('4.1 representante', 'nombre_representante_legal'),
    ('4.1 representante', 'identificaci_n_representante_legal'),
    ('4.1 representante', 'tipo_de_identificaci_n_representante_legal'),
    -- 4.4 · Concentración por ordenador del gasto.
    ('4.4 ordenador',     'nombre_ordenador_del_gasto'),
    ('4.4 ordenador',     'n_mero_de_documento_ordenador_del_gasto'),
    ('4.4 ordenador',     'nombre_ordenador_de_pago'),
    ('4.4 ordenador',     'nombre_supervisor'),
    -- 4.5 · Plazo exprés.
    ('4.5 plazo',         'duraci_n_del_contrato'),
    ('4.5 plazo',         'fecha_de_inicio_del_contrato'),
    ('4.5 plazo',         'fecha_de_fin_del_contrato'),
    -- 4.7 · Desviación y prórroga.
    ('4.7 prorroga',      'dias_adicionados'),
    ('4.7 prorroga',      'el_contrato_puede_ser_prorrogado'),
    ('4.7 prorroga',      'fecha_de_notificaci_n_de_prorrogaci_n'),
    ('4.7 prorroga',      'valor_del_contrato'),
    -- 4.8 · Ejecución anómala.
    ('4.8 ejecucion',     'valor_pagado'),
    ('4.8 ejecucion',     'valor_facturado'),
    ('4.8 ejecucion',     'valor_pendiente_de_ejecucion'),
    ('4.8 ejecucion',     'valor_pendiente_de_pago'),
    ('4.8 ejecucion',     'valor_amortizado'),
    ('4.8 ejecucion',     'valor_de_pago_adelantado'),
    ('4.8 ejecucion',     'estado_contrato'),
    -- Contexto que varias historias necesitan.
    ('contexto',          'objeto_del_contrato'),
    ('contexto',          'tipo_de_contrato'),
    ('contexto',          'sector'),
    ('contexto',          'es_pyme'),
    ('contexto',          'origen_de_los_recursos')
  ) AS h(historia, campo)
) t
GROUP BY historia, campo
ORDER BY historia, pct DESC;

-- 2. EL REPRESENTANTE LEGAL, MIRADO DE CERCA. Es el campo que abre la 4.1 y
--    también el más delicado del proyecto: es la cédula de una persona
--    natural. Si esto llega poblado, la historia se puede construir — y su
--    resultado NO se publica nunca, ni con la barrera de publicación puesta.
SELECT count(*) FILTER (WHERE pg_temp.util(contenido->>'identificaci_n_representante_legal'))
                                                             AS con_documento,
       count(DISTINCT contenido->>'identificaci_n_representante_legal')
         FILTER (WHERE pg_temp.util(contenido->>'identificaci_n_representante_legal'))
                                                             AS personas_distintas,
       count(DISTINCT contenido->>'documento_proveedor')
         FILTER (WHERE pg_temp.util(contenido->>'identificaci_n_representante_legal'))
                                                             AS proveedores_distintos
FROM u;

-- 3. ¿HAY REPRESENTANTES QUE FIRMAN POR VARIOS PROVEEDORES? El fondo de la
--    4.1, antes de escribir nada. Puede ser perfectamente normal —un abogado
--    que representa a varias empresas del mismo grupo— y por eso se cuenta
--    primero cuántos hay, no quiénes son.
WITH r AS (
  SELECT contenido->>'identificaci_n_representante_legal' AS doc,
         contenido->>'documento_proveedor'                AS proveedor
  FROM u
  WHERE pg_temp.util(contenido->>'identificaci_n_representante_legal')
    AND pg_temp.util(contenido->>'documento_proveedor')
), c AS (
  SELECT doc, count(DISTINCT proveedor) AS proveedores FROM r GROUP BY 1
)
SELECT CASE WHEN proveedores = 1 THEN 'a. 1 proveedor'
            WHEN proveedores = 2 THEN 'b. 2'
            WHEN proveedores <= 4 THEN 'c. 3 a 4'
            WHEN proveedores <= 9 THEN 'd. 5 a 9'
            ELSE                      'e. 10 o mas' END  AS proveedores_del_representante,
       count(*)                                          AS representantes,
       round(100.0 * count(*) / nullif(sum(count(*)) OVER (), 0), 1) AS pct
FROM c GROUP BY 1 ORDER BY 1;

DROP TABLE u;
