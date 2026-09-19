-- Migración 001: observacion.precio_centimos pasa a admitir NULL.
--
-- Motivo: la observación que registra que un anuncio dejó de verse
-- (disponible = 0) no tiene ningún precio observado de verdad. Copiar ahí
-- el último precio conocido metía en la tabla una medición falsa, que
-- cualquier gráfico de histórico dibujaría como si fuera real. NULL es la
-- forma honesta de decir "esta observación no vio precio".
--
-- SQLite no permite quitar un NOT NULL con ALTER TABLE: se hace con el
-- patrón de tabla nueva + copiar + borrar + renombrar.

CREATE TABLE observacion_nueva (
    id              INTEGER PRIMARY KEY,
    anuncio_id      INTEGER NOT NULL REFERENCES anuncio(id),
    precio_centimos INTEGER,
    disponible      INTEGER NOT NULL,
    capturado_en    TEXT NOT NULL
);

INSERT INTO observacion_nueva (id, anuncio_id, precio_centimos, disponible, capturado_en)
    SELECT id, anuncio_id, precio_centimos, disponible, capturado_en FROM observacion;

DROP TABLE observacion;
ALTER TABLE observacion_nueva RENAME TO observacion;

CREATE INDEX IF NOT EXISTS observacion_anuncio_fecha
    ON observacion (anuncio_id, capturado_en);
