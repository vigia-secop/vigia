-- ¿QUÉ CIFRAS CAMBIARON DE VERDAD? SOLO LECTURA.
--
--     psql -f verificar-cifras.sql
--
-- `verificar-formato.sql` dejó una pregunta abierta: de los campos de plata que
-- cambiaron entre la penúltima y la última versión, 39.683 son el mismo número
-- escrito distinto («0» -> «0.000000») y 25.348 son números DISTINTOS. Eso
-- último puede ser una de dos cosas, y no dan igual:
--
--   a) La fuente actualizó la ejecución del contrato (pagos, facturación).
--      Normal: para eso se vuelve a leer todos los días.
--   b) La fuente cambió la ESCALA de las cifras. Catástrofe silenciosa: el
--      sitio publicaría totales equivocados sin un solo error en pantalla.
--
-- Se distinguen mirando la razón hoy/antes. Si el cambio es de escala, la razón
-- es la misma constante (1000, 0,001...) en casi todas las filas del campo. Si
-- es ejecución de verdad, las razones están desperdigadas y el campo de fondo
-- —`valor_del_contrato`— casi no se mueve.

\set ON_ERROR_STOP on
SET work_mem = '256MB';

WITH campos(campo) AS (VALUES
  ('valor_del_contrato'), ('valor_pagado'), ('valor_facturado'),
  ('valor_pendiente_de_pago'), ('valor_pendiente_de_ejecucion'),
  ('valor_pendiente_de'), ('valor_amortizado'), ('valor_de_pago_adelantado'),
  ('recursos_propios'), ('recursos_de_credito'),
  ('sistema_general_de_regal_as'), ('sistema_general_de_participaciones'),
  ('presupuesto_general_de_la_nacion_pgn'),
  ('recursos_propios_alcald_as_gobernaciones_y_resguardos_ind_genas_')
),
ultima_corrida AS (
  SELECT max(consultado_en)::date AS dia FROM crudo_registro WHERE dataset = 'contratos'
),
muestra AS (
  SELECT r.id_fila_fuente
  FROM crudo_registro r, ultima_corrida u
  WHERE r.dataset = 'contratos' AND r.consultado_en >= u.dia
  LIMIT 5000
),
versiones AS (
  SELECT r.id_fila_fuente, r.contenido, r.consultado_en,
         row_number() OVER (PARTITION BY r.id_fila_fuente ORDER BY r.consultado_en DESC) AS n
  FROM crudo_registro r
  WHERE r.dataset = 'contratos'
    AND r.id_fila_fuente IN (SELECT id_fila_fuente FROM muestra)
),
pares AS (
  SELECT a.id_fila_fuente, a.contenido AS hoy, b.contenido AS antes,
         a.consultado_en::date AS dia_hoy, b.consultado_en::date AS dia_antes
  FROM versiones a JOIN versiones b USING (id_fila_fuente)
  WHERE a.n = 1 AND b.n = 2
),
numeros AS (
  SELECT p.id_fila_fuente, c.campo, p.dia_antes,
         nullif(trim(p.antes ->> c.campo), '')::numeric AS antes,
         nullif(trim(p.hoy   ->> c.campo), '')::numeric AS ahora
  FROM pares p CROSS JOIN campos c
  WHERE trim(coalesce(p.antes ->> c.campo, '')) ~ '^-?[0-9]+(\.[0-9]+)?$'
    AND trim(coalesce(p.hoy   ->> c.campo, '')) ~ '^-?[0-9]+(\.[0-9]+)?$'
),
distintos AS (
  SELECT * FROM numeros WHERE antes <> ahora
)
SELECT campo,
       count(*)                                        AS cambios,
       count(*) FILTER (WHERE antes = 0)               AS desde_cero,
       count(*) FILTER (WHERE ahora = 0)               AS hasta_cero,
       count(*) FILTER (WHERE antes <> 0 AND ahora <> 0) AS ambos_con_plata,
       round(min(ahora / nullif(antes, 0)), 4)         AS razon_minima,
       round(max(ahora / nullif(antes, 0)), 4)         AS razon_maxima,
       round((percentile_cont(0.5) WITHIN GROUP (
                ORDER BY ahora / nullif(antes, 0)))::numeric, 4) AS razon_mediana
FROM distintos
GROUP BY campo
ORDER BY cambios DESC;

-- El campo que de verdad importa, visto de cerca: es el que alimenta los
-- totales del sitio. Diez ejemplos donde cambió y las dos versiones traen
-- plata, con el día de la versión anterior para saber si es cosa de hoy.
SELECT id_fila_fuente, dia_antes, antes, ahora,
       round(ahora / nullif(antes, 0), 4) AS razon
FROM (
  SELECT p.id_fila_fuente, p.dia_antes,
         nullif(trim(p.antes ->> 'valor_del_contrato'), '')::numeric AS antes,
         nullif(trim(p.hoy   ->> 'valor_del_contrato'), '')::numeric AS ahora
  FROM (
    SELECT a.id_fila_fuente, a.contenido AS hoy, b.contenido AS antes,
           b.consultado_en::date AS dia_antes
    FROM (
      SELECT r.id_fila_fuente, r.contenido, r.consultado_en,
             row_number() OVER (PARTITION BY r.id_fila_fuente ORDER BY r.consultado_en DESC) AS n
      FROM crudo_registro r
      WHERE r.dataset = 'contratos'
        AND r.id_fila_fuente IN (
          SELECT r2.id_fila_fuente FROM crudo_registro r2
          WHERE r2.dataset = 'contratos'
            AND r2.consultado_en >= (SELECT max(consultado_en)::date FROM crudo_registro WHERE dataset = 'contratos')
          LIMIT 5000)
    ) a
    JOIN (
      SELECT r.id_fila_fuente, r.contenido, r.consultado_en,
             row_number() OVER (PARTITION BY r.id_fila_fuente ORDER BY r.consultado_en DESC) AS n
      FROM crudo_registro r
      WHERE r.dataset = 'contratos'
        AND r.id_fila_fuente IN (
          SELECT r2.id_fila_fuente FROM crudo_registro r2
          WHERE r2.dataset = 'contratos'
            AND r2.consultado_en >= (SELECT max(consultado_en)::date FROM crudo_registro WHERE dataset = 'contratos')
          LIMIT 5000)
    ) b USING (id_fila_fuente)
    WHERE a.n = 1 AND b.n = 2
  ) p
  WHERE trim(coalesce(p.antes ->> 'valor_del_contrato', '')) ~ '^-?[0-9]+(\.[0-9]+)?$'
    AND trim(coalesce(p.hoy   ->> 'valor_del_contrato', '')) ~ '^-?[0-9]+(\.[0-9]+)?$'
) x
WHERE antes <> ahora AND antes <> 0 AND ahora <> 0
LIMIT 10;
