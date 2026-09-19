"""Lo común a cualquier tienda, sea cual sea la forma en la que trae los
datos (API o HTML): la forma de los datos que produce un adaptador, y las
reglas de buen comportamiento con la tienda (identificarse, respetar
robots.txt, no ir a toda pastilla). Ver CLAUDE.md, principio 5.
"""

from dataclasses import dataclass
from time import sleep
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = "CorrecarreteBot/0.1 (+https://correcarrete.streamlit.app)"
PAUSA_ENTRE_PETICIONES_SEGUNDOS = 2


@dataclass
class AnuncioCrudo:
    """Un anuncio tal como lo hemos leído de una tienda, sin decidir todavía
    a qué producto del catálogo corresponde (eso es cosa de emparejar.py).

    Sin marca/iso/exposiciones: nadie los usa todavía (no hay cruce
    automático) y son datos que sabemos poco fiables la mitad de las veces.
    En su lugar se guarda descripcion_cruda, tal como vino de la tienda,
    para que el humano que resuelva la cola tenga el detalle completo.
    """

    tienda: str
    id_externo: str
    url: str
    nombre_original: str
    formato: str | None
    unidades_por_pack: int | None  # None = hay señal de pack pero no se pudo leer el número
    precio_centimos: int
    disponible: bool
    descripcion_cruda: str


def sesion_educada() -> requests.Session:
    sesion = requests.Session()
    sesion.headers["User-Agent"] = USER_AGENT
    return sesion


def permitido_por_robots(url_base: str, ruta: str) -> bool:
    parser = RobotFileParser()
    parser.set_url(f"{url_base.rstrip('/')}/robots.txt")
    parser.read()
    return parser.can_fetch(USER_AGENT, f"{url_base.rstrip('/')}{ruta}")


def pausar():
    sleep(PAUSA_ENTRE_PETICIONES_SEGUNDOS)
