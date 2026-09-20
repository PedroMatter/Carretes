"""Lógica del comparador de precios (v1).

No sabe nada de Streamlit ni de ninguna otra capa de presentación: solo
consulta la base de datos y devuelve datos ya listos para pintar. Así el
día que cambie la interfaz (o haya una API), este módulo no se toca.

Ordena siempre por precio POR UNIDAD, nunca por precio de pack. Confundir
las dos cosas es exactamente el error que este proyecto existe para
evitar (ver CLAUDE.md, "Lo que hace distinto a esto de un comparador
normal").
"""

from datetime import datetime, timezone

import db


def buscar_peliculas(texto):
    """Películas cuyo "marca nombre" contiene `texto`, sin distinguir
    mayúsculas. Con texto vacío, devuelve el catálogo entero (no son
    tantas películas como para que haga falta esconderlas).
    """
    conexion = db.conectar()
    patron = f"%{texto}%"
    filas = conexion.execute(
        """
        SELECT id, marca, nombre, iso, proceso FROM pelicula
        WHERE (marca || ' ' || nombre) LIKE ? COLLATE NOCASE
        ORDER BY marca, nombre
        """,
        (patron,),
    ).fetchall()
    conexion.close()
    return [
        {"id": id_, "marca": marca, "nombre": nombre, "iso": iso, "proceso": proceso}
        for id_, marca, nombre, iso, proceso in filas
    ]


def productos_de_pelicula(pelicula_id):
    conexion = db.conectar()
    filas = conexion.execute(
        """
        SELECT id, formato, exposiciones FROM producto
        WHERE pelicula_id = ? ORDER BY formato, exposiciones
        """,
        (pelicula_id,),
    ).fetchall()
    conexion.close()
    return [
        {"id": id_, "formato": formato, "exposiciones": exposiciones}
        for id_, formato, exposiciones in filas
    ]


def _hace_cuanto(capturado_en_iso):
    try:
        capturado_en = datetime.fromisoformat(capturado_en_iso)
    except ValueError:
        return capturado_en_iso

    ahora = datetime.now(timezone.utc)
    delta = ahora - capturado_en
    horas = delta.total_seconds() / 3600

    if horas < 1:
        return "hace menos de una hora"
    if horas < 24:
        return f"hace {int(horas)} h"
    dias = int(horas / 24)
    return f"hace {dias} día{'s' if dias != 1 else ''}"


def ofertas_de_producto(producto_id):
    """Para cada anuncio de este producto, su última observación
    (precio, disponibilidad, cuándo se vio). Ordenadas por precio POR
    UNIDAD, disponibles primero. Los "desaparecidos" (precio_centimos
    NULL, ver principio 1 y 3) no tienen precio que enseñar y se excluyen
    de la lista, no se inventan.
    """
    conexion = db.conectar()
    filas = conexion.execute(
        """
        SELECT a.tienda, a.unidades_por_pack, a.url,
               o.precio_centimos, o.disponible, o.capturado_en
        FROM anuncio a
        JOIN observacion o ON o.id = (
            SELECT id FROM observacion
            WHERE anuncio_id = a.id
            ORDER BY capturado_en DESC LIMIT 1
        )
        WHERE a.producto_id = ?
        """,
        (producto_id,),
    ).fetchall()
    conexion.close()

    ofertas = []
    for tienda, unidades_por_pack, url, precio_centimos, disponible, capturado_en in filas:
        if precio_centimos is None:
            continue
        precio_por_unidad = precio_centimos / unidades_por_pack
        ofertas.append(
            {
                "tienda": tienda,
                "unidades_por_pack": unidades_por_pack,
                "precio_centimos": precio_centimos,
                "precio_por_unidad_centimos": precio_por_unidad,
                "disponible": bool(disponible),
                "url": url,
                "visto": _hace_cuanto(capturado_en),
            }
        )

    ofertas.sort(key=lambda o: (not o["disponible"], o["precio_por_unidad_centimos"]))
    return ofertas
