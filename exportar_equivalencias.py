"""Vuelca la tabla equivalencia a equivalencias.csv.

Se guarda la identidad real del producto (marca, película, formato,
exposiciones), no producto_id: ese número lo asigna el orden en que
cargar_catalogo.py procesó catalogo.csv, y no es estable si el catálogo se
reconstruye en otro orden. Una fila con marca/nombre_pelicula/formato/
exposiciones en blanco significa "no es un carrete".

Se puede ejecutar en cualquier momento: siempre reescribe el fichero
entero, en el mismo orden (por id de equivalencia), así que git solo ve
líneas añadidas al final, no el fichero entero cambiando de sitio.

Pendiente para cuando se escriba el importador (la reconstrucción de la
base de datos desde los CSV del repo, para GitHub Actions): tiene que
fallar con un error claro si una fila nombra un producto que ya no existe
en el catálogo, nunca saltársela en silencio - eso sería perder una
decisión humana sin que nadie se entere.

Uso: python exportar_equivalencias.py
"""

import csv
from pathlib import Path

import db

RAIZ = Path(__file__).parent
EQUIVALENCIAS_CSV = RAIZ / "equivalencias.csv"

CABECERA = ["tienda", "nombre_original", "marca", "nombre_pelicula", "formato", "exposiciones"]


def exportar():
    conexion = db.conectar()
    filas = conexion.execute(
        """
        SELECT e.tienda, e.nombre_original, p.marca, p.nombre, pr.formato, pr.exposiciones
        FROM equivalencia e
        LEFT JOIN producto pr ON pr.id = e.producto_id
        LEFT JOIN pelicula p ON p.id = pr.pelicula_id
        ORDER BY e.id
        """
    ).fetchall()
    conexion.close()

    with EQUIVALENCIAS_CSV.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(CABECERA)
        for tienda, nombre_original, marca, nombre, formato, exposiciones in filas:
            escritor.writerow(
                [
                    tienda,
                    nombre_original,
                    marca or "",
                    nombre or "",
                    formato or "",
                    exposiciones if exposiciones is not None else "",
                ]
            )

    print(f"{len(filas)} equivalencias volcadas a {EQUIVALENCIAS_CSV.name}")
    return len(filas)


if __name__ == "__main__":
    exportar()
