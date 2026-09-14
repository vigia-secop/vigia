-- Llave de negocio para la capa cruda (propuesta de cambio 2026-09-04).
--
-- POR QUÉ. `crudo_registro` identificaba cada fila por el `:id` de Socrata, un
-- identificador de la PLATAFORMA que la fuente reasigna entre publicaciones.
-- Medido el 2026-09-03: tres Ciclos sobre el rango idéntico dejaron 50 434
-- filas crudas con 50 434 `:id` distintos para 25 749 contratos. La llave
-- primaria no impedía nada y `duplicados` marcaba cero para siempre.
--
-- QUÉ HACE ESTA MIGRACIÓN. Solo crea la tabla de destino, vacía. El traslado
-- lo hace `python -m vigia.crudo.rellave`, y no por gusto: el hash se calcula
-- con la MISMA función que usa la ingesta, así que reproducirlo en SQL sería
-- escribir por segunda vez algo que ya existe y que tiene que dar idéntico.
-- Dos implementaciones del mismo hash es una de más.
--
-- LA TABLA VIEJA NO SE BORRA. `rellave` la renombra a
-- `crudo_registro_antes_de_005` y ahí se queda. Nada de esto pierde datos y
-- volver atrás es un `ALTER TABLE ... RENAME`.

CREATE TABLE IF NOT EXISTS crudo_registro_rellave (
    dataset        text        NOT NULL,
    id_fila_fuente text        NOT NULL,
    hash_contenido text        NOT NULL,
    contenido      jsonb       NOT NULL,
    consultado_en  timestamptz NOT NULL,
    PRIMARY KEY (dataset, id_fila_fuente, hash_contenido)
);

COMMENT ON TABLE crudo_registro_rellave IS
    'Destino temporal de la migración 005. `rellave` la convierte en crudo_registro.';
COMMENT ON COLUMN crudo_registro_rellave.id_fila_fuente IS
    'Identidad de NEGOCIO de la fila: los campos que el dataset declara en campos_identidad, unidos por "|". Nunca el :id de Socrata, que la fuente reasigna.';
COMMENT ON COLUMN crudo_registro_rellave.hash_contenido IS
    'SHA-256 del contenido DE NEGOCIO en JSON canónico: se excluyen las claves que empiezan por ":", que son campos de sistema de Socrata y cambian sin que cambie el dato.';

CREATE INDEX IF NOT EXISTS crudo_registro_rellave_dataset_consultado_en_idx
    ON crudo_registro_rellave (dataset, consultado_en DESC);
