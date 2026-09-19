-- Esquema de carretes. Ver CLAUDE.md, sección "Modelo de datos", para el
-- razonamiento detrás de cada tabla.

CREATE TABLE IF NOT EXISTS pelicula (
    id      INTEGER PRIMARY KEY,
    marca   TEXT NOT NULL,
    nombre  TEXT NOT NULL,
    iso     INTEGER NOT NULL,
    proceso TEXT NOT NULL CHECK (proceso IN ('C-41', 'B&N', 'E-6', 'ECN-2')),
    UNIQUE (marca, nombre)
);

CREATE TABLE IF NOT EXISTS producto (
    id            INTEGER PRIMARY KEY,
    pelicula_id   INTEGER NOT NULL REFERENCES pelicula(id),
    formato       TEXT NOT NULL CHECK (formato IN ('35mm', '120')),
    exposiciones  INTEGER,
    UNIQUE (pelicula_id, formato, exposiciones)
);

CREATE TABLE IF NOT EXISTS anuncio (
    id                INTEGER PRIMARY KEY,
    producto_id       INTEGER NOT NULL REFERENCES producto(id),
    tienda            TEXT NOT NULL,
    unidades_por_pack INTEGER NOT NULL DEFAULT 1,
    url               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observacion (
    id           INTEGER PRIMARY KEY,
    anuncio_id   INTEGER NOT NULL REFERENCES anuncio(id),
    precio       REAL NOT NULL,
    disponible   INTEGER NOT NULL,
    capturado_en TEXT NOT NULL
);

-- Anónimas a propósito: ni usuario ni IP. Se guardan desde ya aunque no se
-- usen todavía, porque el histórico no se puede recuperar hacia atrás.

CREATE TABLE IF NOT EXISTS busqueda (
    id             INTEGER PRIMARY KEY,
    texto          TEXT NOT NULL,
    buscado_en     TEXT NOT NULL,
    hubo_resultado INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS clic_saliente (
    id          INTEGER PRIMARY KEY,
    anuncio_id  INTEGER NOT NULL REFERENCES anuncio(id),
    clicado_en  TEXT NOT NULL
);
