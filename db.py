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
    conexion.executescript(ESQUEMA.read_text(encoding="utf-8"))
    return conexion
