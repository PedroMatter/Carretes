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

-- id_externo es el identificador que da la propia tienda (id de producto,
-- o de variación si algún día una tienda las usa de verdad). Es lo que
-- identifica un anuncio de forma estable entre una pasada del recolector
-- y la siguiente, no la URL ni el nombre.
CREATE TABLE IF NOT EXISTS anuncio (
    id                INTEGER PRIMARY KEY,
    producto_id       INTEGER NOT NULL REFERENCES producto(id),
    tienda            TEXT NOT NULL,
    id_externo        TEXT NOT NULL,
    unidades_por_pack INTEGER NOT NULL,
    url               TEXT NOT NULL,
    UNIQUE (tienda, id_externo)
);

-- El precio se guarda en céntimos enteros, tal como lo da la tienda, para
-- no arrastrar errores de redondeo de coma flotante.
CREATE TABLE IF NOT EXISTS observacion (
    id              INTEGER PRIMARY KEY,
    anuncio_id      INTEGER NOT NULL REFERENCES anuncio(id),
    precio_centimos INTEGER NOT NULL,
    disponible      INTEGER NOT NULL,
    capturado_en    TEXT NOT NULL
);

-- Todavía no hay emparejamiento automático (ver CLAUDE.md, sección "El
-- emparejamiento"): todo anuncio nuevo de una tienda va aquí hasta que un
-- humano decida a qué producto corresponde, o que no es un carrete.
-- UNIQUE (tienda, nombre_original) para que un mismo anuncio sin resolver
-- no se repita en la cola cada vez que se ejecuta el recolector.
CREATE TABLE IF NOT EXISTS cola_revision (
    id                INTEGER PRIMARY KEY,
    tienda            TEXT NOT NULL,
    nombre_original   TEXT NOT NULL,
    url               TEXT NOT NULL,
    formato           TEXT,
    descripcion_cruda TEXT NOT NULL,
    motivo            TEXT NOT NULL,
    visto_en          TEXT NOT NULL,
    resuelto          INTEGER NOT NULL DEFAULT 0,
    UNIQUE (tienda, nombre_original)
);

-- La memoria permanente de lo que un humano ya decidió sobre un anuncio
-- concreto (por su nombre exacto en esa tienda). producto_id puede ser
-- NULL: significa "esto no es un carrete, no lo vuelvas a preguntar".
CREATE TABLE IF NOT EXISTS equivalencia (
    id              INTEGER PRIMARY KEY,
    tienda          TEXT NOT NULL,
    nombre_original TEXT NOT NULL,
    producto_id     INTEGER REFERENCES producto(id),
    UNIQUE (tienda, nombre_original)
);

-- Un registro por cada vez que se ejecuta un recolector, para poder
-- distinguir "no hay precios nuevos porque nada ha cambiado" de "el
-- recolector lleva tres semanas fallando en silencio".
CREATE TABLE IF NOT EXISTS ejecucion (
    id              INTEGER PRIMARY KEY,
    tienda          TEXT NOT NULL,
    iniciada_en     TEXT NOT NULL,
    finalizada_en   TEXT,
    anuncios_vistos INTEGER,
    error           TEXT
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
