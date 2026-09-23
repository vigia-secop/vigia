-- QUE PASO CON LA CUARTA ERRATA. SOLO LECTURA.
--
--     psql -f erratas-que-cambiaron.sql
--
-- EL HECHO. El 2026-09-16 la lista de revision decia «4 contrato(s) con valor
-- exactamente 10^n veces el presupuesto de su proceso ($653,5 mil millones)».
-- El 2026-09-19, con mas datos y ningun cambio en el detector, decia 3
-- ($653,3 mil millones). Uno dejo de cumplir el patron.
--
-- POR QUE ESTO NO ES UNA CURIOSIDAD. Vigia existe para mirar lo que se
-- publica. Que una cifra cambie despues de publicada es exactamente el tipo
-- de cosa que hay que poder ver: puede ser el SECOP corrigiendo una errata
-- -bien-, o puede ser un valor que se movio sin que nadie lo anunciara. Las
-- dos cosas se ven igual desde afuera si nadie guarda el antes.
--
-- Y SE PUEDE MIRAR PORQUE LA CAPA CRUDA GUARDA TODO. `crudo_registro` no
-- pisa: cada ingesta deja una fila nueva con su `consultado_en`. Esa decision
-- -tomada cuando el proyecto no tenia ni una pagina- es la que hace que hoy
-- se pueda responder esta pregunta. Sin ella solo habria un numero que bajo
-- de 4 a 3 y ninguna forma de saber cual ni por que.
--
-- NO ACUSA A NADIE. Dice que una cifra publicada cambio, con las dos cifras y
-- las dos fechas. Que significa eso lo dice quien abra el proceso en SECOP.

\set ON_ERROR_STOP on

-- MEMORIA PARA ORDENAR, Y ESTO NO ES UN CAPRICHO.
--
-- Esta consulta ordena casi medio millon de instantaneas DOS VECES: una para
-- quedarse con la primera de cada proceso y otra para quedarse con la ultima.
-- Con los 4 MB que trae PostgreSQL de fabrica, ese orden no cabe en memoria y
-- se hace escribiendo y releyendo archivos temporales en disco. El 2026-09-20
-- la primera corrida tardo DIECINUEVE MINUTOS por eso.
--
-- `SET` sin mas vale para esta sesion de psql y para nada mas: no cambia la
-- configuracion del servidor, no afecta al ciclo diario, y se va cuando psql
-- cierra. Es la forma barata de darle memoria a la consulta que la necesita
-- sin darsela a todas.
--
-- 256 MB sobre una maquina con 4 GB de cache efectiva. Si algun dia esto corre
-- en el servidor pequeno, bajalo.
SET work_mem = '256MB';

-- SE ORDENA SOBRE LO ESTRECHO Y SE VA A BUSCAR LO ANCHO DESPUES. La primera
-- version metia `entidad` y `enlace` -texto largo- dentro del orden, asi que
-- cada una de las 475.000 filas arrastraba media pagina de texto por el
-- ordenamiento. Aqui solo viajan numeros y una fecha; el nombre y el enlace se
-- buscan al final, para las ocho filas que se muestran.
WITH instantanea AS MATERIALIZED (
  SELECT contenido->>'id_del_proceso'                       AS id_del_proceso,
         consultado_en,
         (contenido->>'valor_total_adjudicacion')::numeric  AS adjudicado,
         (contenido->>'precio_base')::numeric               AS base
  FROM crudo_registro
  WHERE dataset = 'procesos'
    AND contenido->>'adjudicado' = 'Si'
    AND contenido->>'precio_base' ~ '^[0-9]+(\.[0-9]+)?$'
    AND contenido->>'valor_total_adjudicacion' ~ '^[0-9]+(\.[0-9]+)?$'
    AND (contenido->>'precio_base')::numeric > 0
),

-- La misma regla que usan `panel.sql`, `portada.sql`, `boletin.sql`,
-- `revision.sql` y `banderas.sql`, escrita una vez mas aqui a proposito: si
-- esta consulta importara la de alla y alla cambiara, esta mentiria en
-- silencio sobre lo que se detecto en su momento.
marcada AS (
  SELECT i.*,
         adjudicado / base AS razon,
         (adjudicado / base >= 100
          AND abs((adjudicado / base)
                  / power(10::numeric, round(log(adjudicado / base))) - 1) < 0.001
         ) AS es_errata
  FROM instantanea i
),

primera AS (
  SELECT DISTINCT ON (id_del_proceso) *
  FROM marcada ORDER BY id_del_proceso, consultado_en ASC
),
ultima AS (
  SELECT DISTINCT ON (id_del_proceso) *
  FROM marcada ORDER BY id_del_proceso, consultado_en DESC
)

SELECT
  CASE WHEN p.es_errata AND NOT u.es_errata THEN 'DEJO DE SERLO'
       WHEN NOT p.es_errata AND u.es_errata THEN 'EMPEZO A SERLO'
       ELSE 'sigue igual' END                            AS que_paso,
  p.id_del_proceso,
  left(pr.nombre_entidad, 40)                            AS entidad,
  to_char(p.consultado_en, 'YYYY-MM-DD')                 AS visto_primero,
  p.base                                                 AS base_antes,
  p.adjudicado                                           AS adjudicado_antes,
  round(p.razon, 1)                                      AS veces_antes,
  to_char(u.consultado_en, 'YYYY-MM-DD')                 AS visto_ultimo,
  u.base                                                 AS base_ahora,
  u.adjudicado                                           AS adjudicado_ahora,
  round(u.razon, 1)                                      AS veces_ahora,
  cr.contenido->'urlproceso'->>'url'                     AS enlace
FROM primera p JOIN ultima u USING (id_del_proceso)

-- EL NOMBRE Y EL ENLACE SE BUSCAN AQUI, NO ARRIBA, Y POR LA PUERTA BUENA.
--
-- Arriba habrian viajado por dos ordenamientos de 475.000 filas siendo texto
-- largo. Abajo ya solo quedan las pocas filas que importan.
--
-- Y no se buscan recorriendo `crudo_registro` por una expresion sobre JSON
-- -que es lo que costaba minutos en `banderas.sql`-, sino por las llaves que
-- la capa normalizada ya guardo: `proceso` tiene `id_del_proceso` de clave
-- primaria, y ademas apunta a la fila cruda EXACTA de la que salio con
-- (id_fila_fuente, hash_contenido), que es la clave primaria de
-- `crudo_registro`. Dos saltos, los dos directos, sin recorrer nada.
--
-- Esa columna `id_fila_fuente` se puso «para que la capa normalizada no sea
-- una afirmacion sin respaldo». Sirve tambien para esto.
LEFT JOIN proceso pr        ON pr.id_del_proceso = p.id_del_proceso
LEFT JOIN crudo_registro cr ON cr.dataset        = 'procesos'
                           AND cr.id_fila_fuente = pr.id_fila_fuente
                           AND cr.hash_contenido = pr.hash_contenido
WHERE p.es_errata <> u.es_errata
   OR u.es_errata
ORDER BY que_paso, u.adjudicado DESC;
