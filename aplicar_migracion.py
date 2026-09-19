"""Aplica un fichero de migraciones/ contra carretes.db.

Uso: python aplicar_migracion.py migraciones/001_nombre.sql

Antes de tocar nada, copia carretes.db a respaldos/ con la fecha en el
nombre. Comprueba en migracion_aplicada si ese fichero ya se aplicó antes
(por nombre): si es así, avisa y no hace nada. Las claves foráneas se
desactivan mientras dura la migración (algunas borran y renombran tablas,
lo que con FK activas puede fallar) y se devuelven al estado que tenían.
"""

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import db


def hacer_respaldo():
    if not db.BASE_DE_DATOS.exists():
        return None
    carpeta = db.RAIZ / "respaldos"
    carpeta.mkdir(exist_ok=True)
    marca_de_tiempo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = carpeta / f"carretes_{marca_de_tiempo}.db"
    shutil.copy2(db.BASE_DE_DATOS, destino)
    return destino


def main():
    if len(sys.argv) != 2:
        print("Uso: python aplicar_migracion.py migraciones/NNN_nombre.sql")
        sys.exit(1)

    ruta = Path(sys.argv[1])

    conexion = db.conectar()

    ya_aplicada = conexion.execute(
        "SELECT aplicada_en FROM migracion_aplicada WHERE nombre = ?", (ruta.name,)
    ).fetchone()
    if ya_aplicada:
        print(f"'{ruta.name}' ya se aplicó el {ya_aplicada[0]}. No se hace nada.")
        conexion.close()
        return

    respaldo = hacer_respaldo()
    if respaldo:
        print(f"Copia de seguridad: {respaldo}")

    estado_fk_anterior = conexion.execute("PRAGMA foreign_keys").fetchone()[0]
    conexion.execute("PRAGMA foreign_keys = OFF")
    conexion.executescript(ruta.read_text(encoding="utf-8"))
    conexion.execute(f"PRAGMA foreign_keys = {'ON' if estado_fk_anterior else 'OFF'}")

    conexion.execute(
        "INSERT INTO migracion_aplicada (nombre, aplicada_en) VALUES (?, ?)",
        (ruta.name, datetime.now(timezone.utc).isoformat()),
    )
    conexion.commit()
    conexion.close()
    print(f"Migración aplicada: {ruta.name}")


if __name__ == "__main__":
    main()
