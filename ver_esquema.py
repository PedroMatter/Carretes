"""Imprime cada tabla de carretes.db con sus columnas e índices.

Uso: python ver_esquema.py
"""

import sqlite3
from pathlib import Path

BASE_DE_DATOS = Path(__file__).parent / "carretes.db"


def ver_esquema():
    conexion = sqlite3.connect(BASE_DE_DATOS)

    tablas = conexion.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    for (tabla,) in tablas:
        print(f"== {tabla} ==")

        for _, nombre, tipo, no_nulo, _, es_clave in conexion.execute(
            f"PRAGMA table_info({tabla})"
        ):
            etiquetas = []
            if es_clave:
                etiquetas.append("PRIMARY KEY")
            elif no_nulo:
                etiquetas.append("NOT NULL")
            print(f"    {nombre:<20} {tipo:<10} {' '.join(etiquetas)}")

        for _, nombre_indice, es_unico, *_ in conexion.execute(
            f"PRAGMA index_list({tabla})"
        ):
            # fila[2] es None cuando la columna del índice es una expresión
            # (como el COALESCE de producto_unico) en vez de un nombre simple.
            columnas = [
                fila[2] if fila[2] is not None else "<expresión>"
                for fila in conexion.execute(f"PRAGMA index_info({nombre_indice})")
            ]
            tipo_indice = "UNIQUE" if es_unico else "INDEX"
            print(f"    [{tipo_indice}] {nombre_indice} ({', '.join(columnas)})")

        print()

    conexion.close()


if __name__ == "__main__":
    ver_esquema()
