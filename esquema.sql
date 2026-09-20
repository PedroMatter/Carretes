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

-- UNIQUE (pelicula_id, formato, exposiciones) de arriba no basta: SQLite
-- trata cada NULL como distinto de los demás, así que dos filas del mismo
-- carrete en 120 (sin exposiciones) no chocarían. Este índice sí las
-- protege, tratando el NULL como un valor más (-1, que no es un número de
-- exposiciones real). Vive en la base de datos para que ningún script,
-- presente o futuro, pueda saltárselo por accidente.
CREATE UNIQUE INDEX IF NOT EXISTS producto_unico
    ON producto (pelicula_id, formato, COALESCE(exposiciones, -1));

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
-- no arrastrar errores de redondeo de coma flotante. precio_centimos admite
-- NULL: es lo que lleva la observación que registra que un anuncio dejó de
-- verse (disponible = 0) — ahí no hay ningún precio observado de verdad, y
-- rellenarlo con el último conocido sería inventar un dato.
CREATE TABLE IF NOT EXISTS observacion (
    id              INTEGER PRIMARY KEY,
    anuncio_id      INTEGER NOT NULL REFERENCES anuncio(id),
    precio_centimos INTEGER,
    disponible      INTEGER NOT NULL,
    capturado_en    TEXT NOT NULL
);

-- La consulta más habitual será "último precio de este anuncio": sin este
-- índice, cada consulta recorrería toda la tabla, y esta es la que más
-- crece de todas (una fila por anuncio en cada pasada de cada tienda).
CREATE INDEX IF NOT EXISTS observacion_anuncio_fecha
    ON observacion (anuncio_id, capturado_en);

-- Todavía no hay emparejamiento automático (ver CLAUDE.md, sección "El
-- emparejamiento"): todo anuncio nuevo de una tienda va aquí hasta que un
-- humano decida a qué producto corresponde, o que no es un carrete.
-- UNIQUE (tienda, nombre_original) para que un mismo anuncio sin resolver
-- no se repita en la cola cada vez que se ejecuta el recolector.
-- Lleva id_externo y unidades_por_pack porque hacen falta para dar de alta
-- el anuncio en el momento de resolver la fila, sin tener que volver a
-- pedirle el producto a la tienda. unidades_por_pack puede ser NULL: es el
-- caso en que ni siquiera eso se pudo determinar con seguridad.
CREATE TABLE IF NOT EXISTS cola_revision (
    id                INTEGER PRIMARY KEY,
    tienda            TEXT NOT NULL,
    id_externo        TEXT NOT NULL,
    nombre_original   TEXT NOT NULL,
    url               TEXT NOT NULL,
    formato           TEXT,
    unidades_por_pack INTEGER,
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
-- recolector lleva tres semanas fallando en silencio". candidatos_vistos
-- (cuántos trajo la tienda) y anuncios_vistos (cuántos acabaron con
-- observación guardada) van por separado: si se mezclaran, un recolector
-- que dejara de guardar nada seguiría pareciendo sano.
--
-- El orden de las columnas de abajo importa para quien lea con SELECT *:
-- una base de datos migrada desde antes de la migración 003 podía tener
-- este mismo orden físicamente distinto (candidatos_vistos se añadió al
-- final con ALTER TABLE ADD COLUMN). Si el orden vuelve a no coincidir
-- con lo de aquí, es señal de que hace falta otra migración de reordenar,
-- no de que el dato esté mal.
CREATE TABLE IF NOT EXISTS ejecucion (
    id                INTEGER PRIMARY KEY,
    tienda            TEXT NOT NULL,
    iniciada_en       TEXT NOT NULL,
    finalizada_en     TEXT,
    candidatos_vistos INTEGER,
    anuncios_vistos   INTEGER,
    error             TEXT
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

-- Registro de qué migraciones de migraciones/ se han aplicado ya a esta
-- base de datos concreta, para no aplicar la misma dos veces y para poder
-- saber, meses después, en qué punto está cada copia.
CREATE TABLE IF NOT EXISTS migracion_aplicada (
    id          INTEGER PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    aplicada_en TEXT NOT NULL
);
