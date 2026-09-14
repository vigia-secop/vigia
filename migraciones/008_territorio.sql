-- Territorio y orden administrativo (historia 1.6).
--
-- POR QUÉ. Sin territorio no se puede comparar una alcaldía con otra, ni
-- mirar un departamento aparte, ni separar lo nacional de lo territorial. Esa
-- última separación dejó de ser un adorno el 7 de agosto de 2026: el cambio de
-- gobierno movió lo NACIONAL y no movió lo territorial —alcaldes y
-- gobernadores siguen en su periodo 2024-2027—, así que una serie que mezcle
-- los dos órdenes le atribuye al cambio de gobierno lo que es otra cosa.
--
-- TRES VALORES DE ORDEN, NO DOS. Medido el 2026-09-05 sobre `jbjy-vk9h`:
-- Territorial 90 101, Nacional 19 967 y **Corporación Autónoma 2 224** en
-- agosto de 2026; y 73 932 / 66 860 / 1 800 en todo 2019. Las CAR aparecen en
-- los dos cortes, con siete años de distancia. No caben en una bandera
-- booleana `es_nacional`, y por eso la columna es texto y no `boolean`.
--
-- EL CÓDIGO ES DIVIPOLA, NO EL NOMBRE. El DANE escribe «BOGOTÁ, D.C.» y el
-- SECOP «Distrito Capital de Bogotá». Cruzar por nombre deja sin territorio a
-- Bogotá —el 16 % de los contratos del país— y lo deja en silencio. La
-- traducción vive en `vigia/normalizado/territorio.py`, con los dos alias
-- declarados y una prueba que recorre los 33 nombres que el SECOP escribe.
--
-- EL MUNICIPIO VA SIN CÓDIGO, A PROPÓSITO. «Argelia» son tres municipios
-- distintos: Antioquia (16 contratos), Cauca (16) y Valle del Cauca (15). Con
-- conteos así de parecidos, fundirlos no se vería raro en ningún reporte. La
-- llave verdadera es el par (departamento, municipio) y son ~1 100 entradas;
-- hasta tener la tabla oficial cargada y comprobada, un código adivinado es
-- peor que ninguno.

ALTER TABLE contrato ADD COLUMN IF NOT EXISTS orden text;
ALTER TABLE contrato ADD COLUMN IF NOT EXISTS departamento_codigo text;
ALTER TABLE contrato ADD COLUMN IF NOT EXISTS departamento_nombre text;
ALTER TABLE contrato ADD COLUMN IF NOT EXISTS municipio_nombre text;

COMMENT ON COLUMN contrato.orden IS
    'NACIONAL, TERRITORIAL o CORPORACION AUTONOMA. NULL = la fuente no lo declaró, que NO es lo mismo que territorial.';
COMMENT ON COLUMN contrato.departamento_codigo IS
    'Código DIVIPOLA de dos dígitos (DANE, dataset vcjz-niiq). NULL cuando la fuente trae «No Definido» o un nombre que la tabla no conoce.';
COMMENT ON COLUMN contrato.departamento_nombre IS
    'El nombre OFICIAL DIVIPOLA cuando se pudo resolver; si no, el que escribió la entidad, para poder diagnosticar por qué no resolvió.';
COMMENT ON COLUMN contrato.municipio_nombre IS
    'Nombre del municipio, SIN código: el nombre solo no identifica a un municipio («Argelia» son tres). Ver la migración y territorio.py.';

-- Solo se admiten los tres órdenes medidos, o nada. Una cuarta cadena que
-- entre por descuido sería una categoría nueva sin que nadie se entere.
ALTER TABLE contrato DROP CONSTRAINT IF EXISTS contrato_orden_conocido;
ALTER TABLE contrato ADD CONSTRAINT contrato_orden_conocido CHECK (
    orden IS NULL OR orden IN ('NACIONAL', 'TERRITORIAL', 'CORPORACION AUTONOMA')
);

-- El código DIVIPOLA de departamento son exactamente dos dígitos.
ALTER TABLE contrato DROP CONSTRAINT IF EXISTS contrato_departamento_divipola;
ALTER TABLE contrato ADD CONSTRAINT contrato_departamento_divipola CHECK (
    departamento_codigo IS NULL OR departamento_codigo ~ '^[0-9]{2}$'
);

-- Un código sin nombre sería media identidad, como el enlace a Proceso de la
-- 1.4 y el proveedor de la 1.5.
ALTER TABLE contrato DROP CONSTRAINT IF EXISTS contrato_departamento_completo;
ALTER TABLE contrato ADD CONSTRAINT contrato_departamento_completo CHECK (
    departamento_codigo IS NULL OR departamento_nombre IS NOT NULL
);

CREATE INDEX IF NOT EXISTS contrato_departamento_idx
    ON contrato (departamento_codigo)
    WHERE departamento_codigo IS NOT NULL;

CREATE INDEX IF NOT EXISTS contrato_orden_idx
    ON contrato (orden) WHERE orden IS NOT NULL;

-- La población que ninguna Regla con corte territorial puede mirar. Índice
-- parcial para medirla barata, igual que con los huérfanos y los proveedores.
CREATE INDEX IF NOT EXISTS contrato_sin_departamento_idx
    ON contrato (id_contrato) WHERE departamento_codigo IS NULL;

ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS sin_departamento integer;
ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS sin_orden integer;
