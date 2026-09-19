"""Lee catalogo.csv y lo mete en la base de datos SQLite (carretes.db).

Crea el esquema si no existe (ver esquema.sql) y luego, por cada fila del
CSV, asegura que exista la "pelicula" correspondiente (una por cada
combinación única de marca+nombre) y añade el "producto" (pelicula +
formato + exposiciones) si todavía no está.

Se puede ejecutar varias veces sin miedo: si un producto ya está en la
base de datos, no lo vuelve a insertar.
"""

import csv
from pathlib import Path

import db

RAIZ = Path(__file__).parent
CATALOGO = RAIZ / "catalogo.csv"


def obtener_o_crear_pelicula(conexion, marca, nombre, iso, proceso):
    """Devuelve (id_de_la_pelicula, se_creo_una_nueva)."""
    fila = conexion.execute(
        "SELECT id FROM pelicula WHERE marca = ? AND nombre = ?",
        (marca, nombre),
    ).fetchone()
    if fila is not None:
        return fila[0], False

    cursor = conexion.execute(
        "INSERT INTO pelicula (marca, nombre, iso, proceso) VALUES (?, ?, ?, ?)",
        (marca, nombre, iso, proceso),
    )
    return cursor.lastrowid, True


def producto_ya_existe(conexion, pelicula_id, formato, exposiciones):
    # No basta con la restricción UNIQUE de la tabla: SQLite trata cada NULL
    # como distinto de los demás, así que dos filas de un mismo carrete en
    # 120 (que no tiene exposiciones) no chocarían entre sí ahí. Por eso
    # comprobamos a mano aquí, con "IS ?" en vez de "= ?" porque en SQL
    # "NULL = NULL" no es verdadero.
    fila = conexion.execute(
        """
        SELECT id FROM producto
        WHERE pelicula_id = ? AND formato = ? AND exposiciones IS ?
        """,
        (pelicula_id, formato, exposiciones),
    ).fetchone()
    return fila is not None


def cargar_catalogo():
    conexion = db.conectar()

    peliculas_nuevas = 0
    productos_nuevos = 0
    productos_repetidos = 0

    with CATALOGO.open(encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            marca = fila["marca"].strip()
            nombre = fila["nombre"].strip()
            iso = int(fila["iso"])
            proceso = fila["proceso"].strip()
            formato = fila["formato"].strip()
            exposiciones_texto = fila["exposiciones"].strip()
            exposiciones = int(exposiciones_texto) if exposiciones_texto else None

            pelicula_id, es_nueva = obtener_o_crear_pelicula(
                conexion, marca, nombre, iso, proceso
            )
            if es_nueva:
                peliculas_nuevas += 1

            if producto_ya_existe(conexion, pelicula_id, formato, exposiciones):
                productos_repetidos += 1
                continue

            conexion.execute(
                "INSERT INTO producto (pelicula_id, formato, exposiciones) VALUES (?, ?, ?)",
                (pelicula_id, formato, exposiciones),
            )
            productos_nuevos += 1

    conexion.commit()
    conexion.close()

    print(f"Películas nuevas insertadas: {peliculas_nuevas}")
    print(f"Productos nuevos insertados: {productos_nuevos}")
    print(f"Productos que ya existían (no se tocan): {productos_repetidos}")


if __name__ == "__main__":
    cargar_catalogo()
