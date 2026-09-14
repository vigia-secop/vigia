-- El número que fija el umbral de la 2.4. SOLO LECTURA.
--
-- Ya sabemos que el embudo llega poblado (99,92 % de los adjudicados) y que un
-- umbral global marcaría el 54,5 % del país. Falta lo único que convierte la
-- semilla en umbral: **entre los procesos COMPETITIVOS adjudicados, cuántos
-- terminan con un solo proveedor único**.
--
-- Si ese número es alto, el umbral de 1 sigue siendo demasiado ancho y la
-- bandera necesita una segunda condición. Si es bajo, la bandera tiene sujeto.
-- Las dos respuestas sirven; la que no sirve es no tenerlo.

\pset border 2
\pset numericlocale on

CREATE TEMP TABLE p AS
SELECT contenido->>'modalidad_de_contratacion'                        AS modalidad,
       contenido->>'adjudicado'                                       AS adjudicado,
       nullif(contenido->>'proveedores_invitados','')::numeric        AS invitados,
       nullif(contenido->>'visualizaciones_del','')::numeric          AS vistas,
       nullif(contenido->>'respuestas_al_procedimiento','')::numeric  AS respuestas,
       nullif(contenido->>'proveedores_unicos_con','')::numeric       AS unicos,
       nullif(contenido->>'numero_de_lotes','')::numeric              AS lotes,
       nullif(contenido->>'valor_total_adjudicacion','')::numeric     AS valor
FROM (
    SELECT DISTINCT ON (contenido->>'id_del_proceso', contenido->>'id_adjudicacion')
           contenido
    FROM crudo_registro
    WHERE dataset = 'procesos'
    ORDER BY contenido->>'id_del_proceso', contenido->>'id_adjudicacion',
             consultado_en DESC
) u
WHERE contenido->>'adjudicado' = 'Si';

-- Las ocho modalidades que la Regla considera competitivas, tal como las
-- escribe la fuente. Si esta lista y la del codigo se separan, la bandera
-- miraria un universo distinto del medido.
CREATE TEMP TABLE competitivas(nombre text);
INSERT INTO competitivas VALUES
 ('Licitación pública'), ('Licitación pública Obra Publica'),
 ('Selección Abreviada de Menor Cuantía'), ('Selección abreviada subasta inversa'),
 ('Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes'),
 ('Concurso de méritos abierto'),
 ('Enajenación de bienes con sobre cerrado'), ('Enajenación de bienes con subasta');

-- 1. EL NÚMERO QUE FIJA EL UMBRAL.
SELECT count(*)                                        AS competitivos_adjudicados,
       count(*) FILTER (WHERE unicos = 1)              AS con_un_solo_proveedor,
       round(100.0 * count(*) FILTER (WHERE unicos = 1) / nullif(count(*),0), 1) AS pct,
       count(*) FILTER (WHERE unicos = 1 AND vistas > 1) AS y_ademas_mas_de_una_vista,
       count(*) FILTER (WHERE unicos = 1 AND vistas > 5) AS y_mas_de_cinco_vistas,
       count(*) FILTER (WHERE unicos = 1 AND vistas > 20) AS y_mas_de_veinte_vistas
FROM p WHERE modalidad IN (SELECT nombre FROM competitivas);

-- 2. Por modalidad, para ver si la bandera enciende sobre una sola cosa.
SELECT left(modalidad, 42) AS modalidad, count(*) AS adjudicados,
       count(*) FILTER (WHERE unicos = 1) AS un_solo_proveedor,
       round(100.0 * count(*) FILTER (WHERE unicos = 1) / nullif(count(*),0), 1) AS pct
FROM p WHERE modalidad IN (SELECT nombre FROM competitivas)
GROUP BY 1 ORDER BY adjudicados DESC;

-- 3. Cuánta plata hay detrás, que es lo que decide si vale la pena mirarlos.
SELECT count(*) AS procesos,
       sum(valor)::numeric(20,0) AS valor_adjudicado,
       round(avg(vistas), 1) AS vistas_promedio,
       round(avg(invitados), 1) AS invitados_promedio
FROM p
WHERE modalidad IN (SELECT nombre FROM competitivas) AND unicos = 1;

-- 4. Los quince mayores, para mirarlos con los ojos antes de creer nada.
SELECT left(modalidad, 30) AS modalidad, invitados, vistas, respuestas, unicos,
       valor::numeric(20,0)
FROM p
WHERE modalidad IN (SELECT nombre FROM competitivas) AND unicos = 1
ORDER BY valor DESC NULLS LAST LIMIT 15;

DROP TABLE p; DROP TABLE competitivas;
