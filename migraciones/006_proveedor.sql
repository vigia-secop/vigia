-- Identidad canónica de Proveedor (historia 1.5).
--
-- POR QUÉ ESTA TABLA EXISTE. El mismo contratista aparece en el SECOP con el
-- documento escrito de varias formas y la razón social de varias más. Sin una
-- identidad, «concentración por proveedor» (4.3) cuenta a uno como tres y no
-- detecta nada.
--
-- LA LLAVE ES (tipo_documento, numero). El tipo forma parte de la identidad a
-- propósito: un NIT 900123456 y una cédula 900123456 son dos entidades
-- distintas del mundo, y fundirlas inventaría una concentración que no existe.
--
-- LO QUE NO ENTRA AQUÍ. Los contratos cuyo documento es un centinela de la
-- fuente -«No Definido», 175 836 en el histórico nacional- no tienen identidad
-- y NO se agrupan. Se conservan en `contrato` con `proveedor_tipo` y
-- `proveedor_numero` nulos y se cuentan aparte, igual que los huérfanos de la
-- 1.4. Agruparlos por el centinela habría creado un proveedor `NODEFINIDO` que
-- sería, de lejos, el contratista más concentrado de Colombia. Y falso entero.
--
-- AVISO: esta migración dice «no entra» de una población que la 007 partió en
-- dos. De esos 175 836, los 15 291 marcados `es_grupo = 'Si'` que ya son
-- contratos SÍ reciben identidad —provisional— desde la 007. Los otros
-- 160 543 son borradores y cancelados, y siguen sin identidad, que es lo
-- correcto: nunca adjudicaron a nadie. Ver `007_grupo_provisional.sql`.

CREATE TABLE IF NOT EXISTS proveedor (
    tipo_documento   text        NOT NULL,
    numero           text        NOT NULL,
    nombre_principal text,
    contratos        integer     NOT NULL DEFAULT 0,
    variantes        integer     NOT NULL DEFAULT 0,
    normalizado_en   timestamptz NOT NULL,
    PRIMARY KEY (tipo_documento, numero),
    CONSTRAINT proveedor_conteos_no_negativos CHECK (contratos >= 0 AND variantes >= 0)
);

COMMENT ON TABLE proveedor IS
    'Identidad canónica de proveedor. Llave (tipo_documento, numero): el tipo forma parte de la identidad.';
COMMENT ON COLUMN proveedor.nombre_principal IS
    'La forma más frecuente de escribir el nombre. En empate gana la primera alfabéticamente, para que dos corridas sobre los mismos datos den lo mismo.';
COMMENT ON COLUMN proveedor.variantes IS
    'Cuántas formas distintas de escribir el nombre se han visto. Mayor que 1 es en sí mismo una señal.';

-- Las variantes NO se descartan: el criterio de aceptación pide que queden
-- registradas y CONSULTABLES. Un mismo documento con tres razones sociales
-- puede ser un cambio de nombre legítimo o puede ser otra cosa, y el
-- Expediente de la épica 2 tendrá que mostrarlas.
CREATE TABLE IF NOT EXISTS proveedor_variante (
    tipo_documento text        NOT NULL,
    numero         text        NOT NULL,
    nombre         text        NOT NULL,
    contratos      integer     NOT NULL DEFAULT 0,
    normalizado_en timestamptz NOT NULL,
    PRIMARY KEY (tipo_documento, numero, nombre),
    FOREIGN KEY (tipo_documento, numero)
        REFERENCES proveedor (tipo_documento, numero) ON DELETE CASCADE
);

COMMENT ON TABLE proveedor_variante IS
    'Cada forma distinta de escribir el nombre de un proveedor, con cuántos contratos la usan.';

-- El enlace del contrato a su proveedor. Nulo cuando el documento no sirve
-- como identidad; el contrato se conserva igual.
ALTER TABLE contrato ADD COLUMN IF NOT EXISTS proveedor_tipo text;
ALTER TABLE contrato ADD COLUMN IF NOT EXISTS proveedor_numero text;
ALTER TABLE contrato ADD COLUMN IF NOT EXISTS proveedor_nombre text;

-- Misma barrera que el enlace a Proceso de la 1.4: media identidad no existe.
ALTER TABLE contrato DROP CONSTRAINT IF EXISTS contrato_proveedor_completo;
ALTER TABLE contrato ADD CONSTRAINT contrato_proveedor_completo CHECK (
    (proveedor_tipo IS NULL AND proveedor_numero IS NULL)
    OR (proveedor_tipo IS NOT NULL AND proveedor_numero IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS contrato_proveedor_idx
    ON contrato (proveedor_tipo, proveedor_numero)
    WHERE proveedor_tipo IS NOT NULL;

-- Los contratos SIN identidad de proveedor son la población que la 4.3 no
-- puede vigilar. Índice parcial para poder medirla barata.
CREATE INDEX IF NOT EXISTS contrato_sin_proveedor_idx
    ON contrato (id_contrato) WHERE proveedor_tipo IS NULL;

ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS proveedores integer;
ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS sin_documento_utilizable integer;
