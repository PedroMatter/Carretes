"""Decide a qué producto del catálogo corresponde un anuncio, o si hace
falta preguntarle a un humano.

Ver CLAUDE.md, sección "El emparejamiento: dos candidatos, sin decidir":
para las tiendas de momento no hay cruce automático por atributos, solo
lo que ya se resolvió a mano (equivalencia) y, si no está ahí, la cola.
"""

NO_ES_CARRETE = "no_es_carrete"
PENDIENTE = "pendiente"


def resolver(conexion, tienda, nombre_original):
    """Devuelve:
    - un producto_id (int), si ya hay una equivalencia que apunta a un producto.
    - NO_ES_CARRETE, si un humano ya decidió que esto no es un carrete.
    - PENDIENTE, si no hay ninguna decisión tomada todavía (va a cola_revision).
    """
    fila = conexion.execute(
        "SELECT producto_id FROM equivalencia WHERE tienda = ? AND nombre_original = ?",
        (tienda, nombre_original),
    ).fetchone()

    if fila is None:
        return PENDIENTE
    if fila[0] is None:
        return NO_ES_CARRETE
    return fila[0]
