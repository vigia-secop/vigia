-- 009 · Marcar los valores que no pueden ser ciertos.
--
-- POR QUÉ ES UNA COLUMNA GENERADA Y NO UN CÁLCULO EN CADA CONSULTA. Es la
-- misma decisión de la migración 007 y por la misma razón: si el techo vive en
-- el código Python y además se repite escrito a mano en `panel.sql`,
-- `resumen.sql` y `revision.sql`, tarde o temprano uno de los cuatro se queda
-- viejo y nadie se entera. Con `GENERATED ALWAYS ... STORED`, **la base y el
-- código no se pueden separar**: el valor lo calcula PostgreSQL, siempre igual,
-- y cambiarlo exige una migración con su número y su fecha.
--
-- EL TECHO: 10^14 pesos = 100 billones. Sale del tamaño del Estado, no de
-- nuestros resultados: el Presupuesto General de la Nación está en el orden de
-- los 500 billones anuales, así que un contrato de 100 billones sería la
-- quinta parte de todo el gasto público del año en un solo renglón de SECOP.
-- Ver `vigia/normalizado/escala.py` para la fuente citable y la fecha de
-- vigencia, que la historia 2.1 exige para todo tope normativo.
--
-- ESTÁ DELIBERADAMENTE HOLGADO. El contrato público más grande de Colombia
-- vive en el orden de los billones (10^12), cien veces por debajo. Este techo
-- no separa «grande» de «muy grande»: ataja lo imposible. Un techo apretado
-- dejaría fuera contratos reales, que es el error contrario y peor.
--
-- LO QUE ESTA MIGRACIÓN NO HACE: no borra, no corrige, no adivina el valor
-- verdadero. Vigía no es la fuente. Solo marca, para que los totales puedan
-- dejarlos fuera **y declararlo**.

ALTER TABLE contrato
    ADD COLUMN IF NOT EXISTS valor_fuera_de_escala boolean
    GENERATED ALWAYS AS (valor >= 1e14) STORED;

COMMENT ON COLUMN contrato.valor_fuera_de_escala IS
    'El valor no puede ser cierto: >= 10^14 COP (100 billones), la quinta parte '
    'del presupuesto nacional anual en un solo contrato. NULL cuando no hay valor: '
    'un contrato sin cifra es «falta el dato», no «imposible», y se cuenta aparte. '
    'Techo vigente desde 2026-09-06; ver vigia/normalizado/escala.py.';

-- Los imposibles son poquísimos y se consultan siempre por sí mismos, así que
-- el índice va parcial: ocupa lo que ocupan ellos y no lo que ocupa la tabla.
CREATE INDEX IF NOT EXISTS contrato_fuera_de_escala_idx
    ON contrato (valor DESC)
    WHERE valor_fuera_de_escala;
