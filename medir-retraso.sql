-- ¿LA VENTANA ESTA PERDIENDO CONTRATOS? SOLO LECTURA.
--
--     psql -f medir-retraso.sql
--
-- LA PREGUNTA. La ventana de solapamiento decide cuantos dias hacia atras
-- relee cada ingesta. Si un contrato se publica despues de que la ventana ya
-- paso por su fecha, no se baja nunca. No deja hueco: deja nada.
--
-- RESULTADO DE LA PRIMERA CORRIDA, 2026-09-21, sobre la ingesta del 20 con
-- ventana de 45 dias:
--
--     edad al entrar     nuevos de verdad    ya estaban y cambiaron
--     hasta 30 dias            6.097                  5.324
--     de 31 a 45                   0                  7.617
--     mas de 45                    0                  1.506
--
-- Cero contratos nuevos con mas de 30 dias. La alarma VENTANA CORTA habia
-- dicho 1.506 «registros nuevos» en el borde: eran, los 1.506, contratos que
-- ya teniamos y que el SECOP modifico. La alarma se corrigio para separarlos
-- (`cambiados_en_borde`, migracion 012).
--
-- LO QUE SE QUITO DE ESTE ARCHIVO, Y POR QUE. Tenia dos bloques mas que
-- median el retraso de publicacion con el campo de sistema `:created_at` de
-- Socrata. El primero de ellos era una comprobacion: si un solo dia
-- concentraba una tajada enorme de filas, `:created_at` no era la fecha de
-- publicacion sino la de una recarga. Salio asi:
--
--     2026-09-10   140.305 filas   50,00 %
--     2026-09-06    65.287 filas   23,27 %
--
-- La mitad de todos los contratos «creados» el mismo dia. `:created_at` no
-- mide cuando se publico un contrato; mide cuando Socrata recargo el
-- dataset. El bloque que dependia de el daba mediana de 58 dias y 0 % atrapado
-- con 30: basura con forma de dato. Se quito para que nadie lo lea como
-- verdad. La comprobacion hizo su trabajo: por eso estaba antes.

\set ON_ERROR_STOP on
SET work_mem = '256MB';

-- ---------------------------------------------------------------------------
-- LOS QUE ENTRARON EN LA ULTIMA CORRIDA: ¿ERAN NUEVOS O CAMBIARON?
-- ---------------------------------------------------------------------------
-- ESTE BLOQUE EXISTE PORQUE ME PRECIPITE. El 2026-09-20, al ver 1.506
-- «registros nuevos» en el borde de la ventana, le dije a Guillermo que la
-- ventana de 30 dias «llevaba perdiendo contratos desde el principio».
--
-- Pero la senal VENTANA CORTA cuenta FILAS nuevas en la capa cruda, y una
-- fila nueva sale de dos cosas distintas:
--
--   - un contrato que nunca habiamos visto          -> este SI se perdia
--   - un contrato que ya teniamos y que el SECOP     -> este NO se perdia:
--     modifico (estado, valor, una adicion)             ya estaba, solo cambio
--
-- Si la ventana llega por primera vez en semanas a un dia viejo, relee todos
-- sus contratos, y cada uno que haya cambiado desde entonces entra como fila
-- nueva. Eso daria 1.506 en el borde sin haber perdido ni uno.
--
-- Se separan mirando la PRIMERA vez que vimos cada contrato: si fue en esta
-- misma corrida, es nuevo de verdad; si fue antes, ya lo teniamos.
--
-- Y se agrupan por EDAD AL ENTRAR -cuantos dias tenia firmado cuando
-- aparecio-. La cifra que importa es la de «nuevos de verdad» con mas de 30
-- dias: esos son exactamente los que la ventana vieja habria perdido.
\echo
\echo '== Lo que entro en la ultima corrida: contratos nuevos, o que ya teniamos y cambiaron?'
\echo '   La fila que importa: NUEVOS DE VERDAD con mas de 30 dias. Esos se perdian.'

-- Las fechas se comparan como RANGO sobre `consultado_en` y no pasandola por
-- una funcion: asi entra por el indice (dataset, consultado_en) y lee solo lo
-- de la ultima corrida, en vez de recorrer las 883.444 filas para
-- preguntarle a cada una que dia es en Bogota.
WITH corrida AS (
  SELECT (max(consultado_en) AT TIME ZONE 'America/Bogota')::date AS dia
  FROM crudo_registro WHERE dataset = 'contratos'
),
entro AS (
  SELECT DISTINCT r.id_fila_fuente,
         (r.contenido->>'fecha_de_firma')::date AS firma
  FROM crudo_registro r CROSS JOIN corrida c
  WHERE r.dataset = 'contratos'
    AND r.consultado_en >= (c.dia::timestamp       AT TIME ZONE 'America/Bogota')
    AND r.consultado_en <  ((c.dia + 1)::timestamp AT TIME ZONE 'America/Bogota')
    AND r.contenido->>'fecha_de_firma' ~ '^\d{4}-\d{2}-\d{2}'
),
primera AS (
  SELECT id_fila_fuente,
         min((consultado_en AT TIME ZONE 'America/Bogota')::date) AS primera_vez
  FROM crudo_registro
  WHERE dataset = 'contratos'
    AND id_fila_fuente IN (SELECT id_fila_fuente FROM entro)
  GROUP BY id_fila_fuente
)
SELECT c.dia                                                     AS corrida,
       CASE WHEN c.dia - e.firma <= 30 THEN 'a) hasta 30 dias'
            WHEN c.dia - e.firma <= 45 THEN 'b) de 31 a 45'
            ELSE                            'c) mas de 45' END   AS edad_al_entrar,
       count(*) FILTER (WHERE p.primera_vez =  c.dia)            AS nuevos_de_verdad,
       count(*) FILTER (WHERE p.primera_vez <  c.dia)            AS ya_estaban_y_cambiaron
FROM entro e
JOIN primera p USING (id_fila_fuente)
CROSS JOIN corrida c
GROUP BY c.dia, 2
ORDER BY 2;
