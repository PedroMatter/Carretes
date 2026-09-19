-- Migración 002: separa "cuántos candidatos trajo la tienda" de "cuántos
-- acabaron guardados con observación" en la tabla ejecucion.
--
-- Motivo: anuncios_vistos guardaba el número de candidatos de la tienda
-- (ej. 119), no el de anuncios realmente guardados (3, en la primera
-- prueba real). Esa columna es la señal de salud del recolector: un
-- recolector que dejara de guardar nada tenía que seguir pareciendo sano
-- con este error.

BEGIN;
ALTER TABLE ejecucion ADD COLUMN candidatos_vistos INTEGER;
COMMIT;
