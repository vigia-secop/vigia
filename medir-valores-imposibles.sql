-- ¿HAY VALORES IMPOSIBLES EN LOS CONTRATOS? SOLO LECTURA.
--
--     psql -f medir-valores-imposibles.sql
--
-- POR QUÉ ESTA ES AHORA LA PREGUNTA MÁS IMPORTANTE DEL PROYECTO.
--
-- Buscando la bandera 4.2 aparecieron 119 procesos que adjudican por encima de
-- su presupuesto. Ninguno se explica por una foto vieja. Pero al mirarlos uno
-- por uno **no son sobrecostos: son erratas de la fuente**, y de dos formas
-- que se reconocen a simple vista:
--
--   · `431.340.000` de presupuesto contra `431.340.000.000` adjudicado. El
--     mismo número con tres ceros de más. Aparece al menos cinco veces, en
--     entidades distintas, con un 99.900 % «por encima».
--   · Un proceso de un hospital con `$8.054.481.856.630.300` adjudicados.
--     Ocho mil billones: varias veces el PIB del país, en un solo renglón.
--
-- Eso deja de ser un asunto de banderas y pasa a ser un asunto de **todo lo
-- que publicamos**. El Panel dice «$12,91 billones en la ventana». Un solo
-- registro con tres ceros de más lo vuelve mentira, el mayor contratista del
-- ranking pasa a ser quien tuvo la errata, y nadie se entera porque el número
-- no falla: sale, se lee, y está mal.
--
-- Buscar una bandera más antes de tapar esto sería construir el piso doce
-- sobre un primer piso que no se ha revisado.
--
-- Esta consulta NO arregla nada. Pregunta si la capa de contratos —que es la
-- que el Panel suma— tiene el mismo problema, y de qué tamaño.

\pset border 2
\pset numericlocale on

-- 1. EL TECHO. Contra qué se compara: el contrato más grande que puede existir
--    de verdad en Colombia está en el orden de los billones (10^12). Cualquier
--    cosa por encima de 10^14 —cien billones— en UN contrato es imposible.
SELECT count(*)                                                  AS contratos,
       count(*) FILTER (WHERE valor >= 1e12)                     AS de_billones_o_mas,
       count(*) FILTER (WHERE valor >= 1e14)                     AS imposibles_10e14,
       count(*) FILTER (WHERE valor >= 1e15)                     AS imposibles_10e15,
       max(valor)::numeric(30,0)                                 AS el_mayor,
       sum(valor)::numeric(30,0)                                 AS suma_total,
       sum(valor) FILTER (WHERE valor < 1e14)::numeric(30,0)     AS suma_sin_los_imposibles
FROM contrato WHERE valor IS NOT NULL;

-- 2. LOS VEINTE MAYORES, para mirarlos con los ojos. Si el mayor de verdad es
--    un contrato de infraestructura conocido, bien. Si es una errata, se ve.
SELECT id_contrato, left(nombre_entidad, 38) AS entidad,
       left(coalesce(proveedor_numero,'—'), 14) AS documento,
       valor::numeric(30,0) AS valor, estado
FROM contrato WHERE valor IS NOT NULL
ORDER BY valor DESC LIMIT 20;

-- 3. LA ERRATA DE LOS TRES CEROS, buscada de frente. Un contrato cuyo valor es
--    exactamente mil veces el de otro contrato de la MISMA entidad con el
--    mismo proveedor es sospechoso de ser el mismo escrito dos veces, una bien
--    y otra mal. Se lista sin afirmar nada: es un patrón, no un veredicto.
SELECT a.id_contrato AS posible_errata, a.valor::numeric(30,0) AS valor_grande,
       b.id_contrato AS el_otro,        b.valor::numeric(30,0) AS valor_normal,
       left(a.nombre_entidad, 40) AS entidad
FROM contrato a
JOIN contrato b
  ON a.nit_entidad = b.nit_entidad
 AND a.proveedor_numero IS NOT DISTINCT FROM b.proveedor_numero
 AND a.id_contrato <> b.id_contrato
 AND a.valor = b.valor * 1000
WHERE a.valor IS NOT NULL AND b.valor > 0
ORDER BY a.valor DESC LIMIT 15;

-- 4. LA FORMA DE LA COLA ALTA. Cuántos contratos hay en cada orden de
--    magnitud. La contratación pública tiene una forma conocida: muchos
--    pequeños y pocos grandes. Un escalón que no encaja en esa forma es
--    justamente lo que hay que mirar.
SELECT CASE
         WHEN valor >= 1e15 THEN 'g. 10^15 o mas   IMPOSIBLE'
         WHEN valor >= 1e14 THEN 'f. 10^14 a 10^15 IMPOSIBLE'
         WHEN valor >= 1e13 THEN 'e. 10 a 100 billones'
         WHEN valor >= 1e12 THEN 'd. 1 a 10 billones'
         WHEN valor >= 1e11 THEN 'c. 100 a 1000 mil millones'
         WHEN valor >= 1e9  THEN 'b. 1 a 100 mil millones'
         ELSE                    'a. menos de mil millones'
       END                                    AS orden_de_magnitud,
       count(*)                               AS contratos,
       sum(valor)::numeric(30,0)              AS suma
FROM contrato WHERE valor IS NOT NULL
GROUP BY 1 ORDER BY 1 DESC;
