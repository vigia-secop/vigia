-- ¿COMO SE LLAMA ESA ENTIDAD EN EL SECOP? SOLO LECTURA.
--
--     psql -f buscar-entidad.sql
--
-- POR QUE EXISTE. `perfil-entidad.sql` corrio con el patron
-- «%JURISDICCI_N ESPECIAL PARA LA PAZ%» y devolvio cero filas. Cero puede
-- significar dos cosas MUY distintas:
--
--   a) La entidad no contrata, o no publica en SECOP II.
--   b) Se llama de otra forma —una sigla, un nombre largo con «UNIDAD
--      ADMINISTRATIVA ESPECIAL», una tilde donde no la esperabamos—.
--
-- Confundir (b) con (a) es como se publica «la JEP no aparece» y al dia
-- siguiente alguien muestra sus contratos. Esto lista los nombres reales que
-- se parecen, para escoger a mano contra cual correr el perfil.

\set ON_ERROR_STOP on
SET work_mem = '256MB';

\echo '== Nombres de entidad que contienen PAZ, JEP o JURISDICC =='
SELECT nit_entidad,
       nombre_entidad,
       count(*)                  AS contratos,
       sum(valor)::numeric(24,0) AS valor_total,
       min(fecha_de_firma)       AS primera,
       max(fecha_de_firma)       AS ultima
FROM contrato
WHERE nombre_entidad ILIKE '%PAZ%'
   OR nombre_entidad ILIKE '%JURISDICC%'
   OR nombre_entidad ILIKE '%JEP%'
   OR nombre_entidad ILIKE '%TRANSICIONAL%'
   OR nombre_entidad ILIKE '%VERDAD%'
GROUP BY 1, 2
ORDER BY contratos DESC
LIMIT 40;

-- Lo mismo en Procesos: una entidad puede haber ABIERTO procesos sin que
-- todavia haya un contrato firmado dentro de la ventana que tenemos.
\echo ''
\echo '== Lo mismo en Procesos =='
SELECT nit_entidad, nombre_entidad, count(*) AS procesos,
       min(fecha_de_publicacion) AS primera, max(fecha_de_publicacion) AS ultima
FROM proceso
WHERE nombre_entidad ILIKE '%PAZ%'
   OR nombre_entidad ILIKE '%JURISDICC%'
   OR nombre_entidad ILIKE '%JEP%'
GROUP BY 1, 2
ORDER BY procesos DESC
LIMIT 40;

-- Y el recordatorio que hay que leer antes de concluir nada: QUE PERIODO
-- tenemos. La base no es «todo el SECOP»: es lo que se ha ingerido.
\echo ''
\echo '== Que periodo cubre la base =='
SELECT min(fecha_de_firma)        AS contrato_mas_viejo,
       max(fecha_de_firma)        AS contrato_mas_nuevo,
       count(*)                   AS contratos,
       count(DISTINCT nit_entidad) AS entidades
FROM contrato;
