"""Aplica un fichero de migraciones/ contra carretes.db.

Uso: python aplicar_migracion.py migraciones/001_nombre.sql

Las migraciones son el camino para cambiar el esquema cuando ya hay datos
dentro: en vez de borrar y recrear la base de datos (lo que perdería el
histórico, principio 3), se escribe un fichero .sql numerado en
migraciones/ con el cambio, y se aplica una vez con este script. esquema.sql
se actualiza a la vez, para que una base de datos nueva ya nazca con la
forma correcta sin tener que pasar por las migraciones antiguas.
"""

import sys
from pathlib import Path

import db


def main():
    if len(sys.argv) != 2:
        print("Uso: python aplicar_migracion.py migraciones/NNN_nombre.sql")
        sys.exit(1)

    ruta = Path(sys.argv[1])
    conexion = db.conectar()
    conexion.executescript(ruta.read_text(encoding="utf-8"))
    conexion.commit()
    conexion.close()
    print(f"Migración aplicada: {ruta.name}")


if __name__ == "__main__":
    main()
