"""Conexión a carretes.db, compartida por todos los scripts. Crea el
esquema si hace falta (CREATE TABLE/INDEX ... IF NOT EXISTS, así que no
pasa nada si ya existía).
"""

import sqlite3
from pathlib import Path

RAIZ = Path(__file__).parent
BASE_DE_DATOS = RAIZ / "carretes.db"
ESQUEMA = RAIZ / "esquema.sql"


def conectar():
    conexion = sqlite3.connect(BASE_DE_DATOS)
    # SQLite ignora las FOREIGN KEY por defecto: sin esto, los REFERENCES
    # del esquema son decorativos y nada impide, por ejemplo, una
    # observación que apunte a un anuncio que no existe. Es por conexión,
    # no queda guardado en el fichero: hay que activarlo siempre aquí.
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(ESQUEMA.read_text(encoding="utf-8"))
    return conexion
