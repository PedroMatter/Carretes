-- Migración 003: reordena las columnas de ejecucion para que coincidan
-- con esquema.sql.
--
-- Motivo: la migración 002 añadió candidatos_vistos con ALTER TABLE ADD
-- COLUMN, que SQLite siempre pega al final. Eso dejó el orden físico real
-- (..., anuncios_vistos, error, candidatos_vistos) distinto del que
-- esquema.sql declara para una base de datos nueva (..., candidatos_vistos,
-- anuncios_vistos, error). El propio código no se equivoca porque siempre
-- nombra las columnas, pero un SELECT * leído por posición sí se
-- equivoca — y así se leyó mal un histórico real durante la investigación
-- del 20/09/2026 ("119 candidatos pasaron a 3"): candidatos_vistos y
-- anuncios_vistos estaban intercambiados a simple vista.
--
-- Se recrea la tabla con el orden correcto, copiando por nombre de
-- columna (no por posición), así que el mapeo es correcto pase lo que
-- pase con el orden físico de origen.

BEGIN;

CREATE TABLE ejecucion_nueva (
    id                INTEGER PRIMARY KEY,
    tienda            TEXT NOT NULL,
    iniciada_en       TEXT NOT NULL,
    finalizada_en     TEXT,
    candidatos_vistos INTEGER,
    anuncios_vistos   INTEGER,
    error             TEXT
);

INSERT INTO ejecucion_nueva
    (id, tienda, iniciada_en, finalizada_en, candidatos_vistos, anuncios_vistos, error)
    SELECT id, tienda, iniciada_en, finalizada_en, candidatos_vistos, anuncios_vistos, error
    FROM ejecucion;

DROP TABLE ejecucion;
ALTER TABLE ejecucion_nueva RENAME TO ejecucion;

COMMIT;
