"""Adaptador de Cuarto Color Lab: misma API pública de WooCommerce Store que
La Peliculera, pero los datos vienen bastante más dispersos. No se comparte
ninguna suposición con tiendas/la_peliculera.py salvo lo que de verdad
coincide (paginación, forma de los precios, is_in_stock) — comprobado antes
de escribir esto, no asumido porque el motor de tienda sea el mismo.

Diferencias reales encontradas:
- Sí hay productos "variable" con carretes de verdad (packs como
  variaciones, no como productos sueltos). /products/{id}/variations no
  funciona en esta tienda: cada variación se pide por su propio id.
- Las categorías solo están en el producto padre; las variaciones traen
  categories vacío, así que se heredan del padre.
- No hay campo "Unidades" en ningún sitio. El tamaño del pack sale del
  nombre en productos simples, y del slug en variaciones.
- No hay categoría de "caducados": se detecta buscando "caduc" en la
  descripción (comprobado contra los datos reales: no es texto genérico,
  aparece solo en los productos que de verdad lo están).
"""

import html
import re

from tiendas.base import AnuncioCrudo, pausar, permitido_por_robots, sesion_educada

TIENDA = "Cuarto Color Lab"
URL_BASE = "https://cuartocolorlab.com"
RUTA_PRODUCTOS = "/wp-json/wc/store/v1/products"

CATEGORIA_CARRETES = "Carretes de fotos"
CATEGORIA_INSTANTANEA = "Instantánea"
CATEGORIA_110 = "110"
CATEGORIA_DESECHABLES = "Desechables"  # cámara con carrete de fábrica: es una cámara, no un carrete

FORMATOS_POR_CATEGORIA = {
    "35mm": "35mm",
    "Formato medio 120": "120",
}

# "Fomapan Classic 35mm 36exp" (id_externo 18309) está mal categorizado en
# la propia tienda: lleva la categoría "Formato medio 120" en vez de
# "35mm", aunque el nombre y la propia tabla de características de la
# ficha dicen "Formato: 35mm". Comprobado a mano el 20/09/2026 contra la
# API en vivo. Se revisaron los 67 candidatos de esa fecha buscando el
# mismo patrón (categoría de formato que contradice al nombre) y este es
# el único caso - no es sistemático, así que es una excepción puntual por
# nombre exacto, no una regla general.
EXCEPCIONES_FORMATO = {
    "Fomapan Classic 35mm 36exp": "35mm",
}


def _nombres_categorias(producto):
    return {c["name"] for c in producto.get("categories", [])}


def _es_caducado(producto):
    texto = html.unescape(
        (producto.get("description") or "") + " " + (producto.get("short_description") or "")
    )
    return "caduc" in texto.lower()


def _formato_de_categorias(categorias):
    for nombre_categoria, formato in FORMATOS_POR_CATEGORIA.items():
        if nombre_categoria in categorias:
            return formato
    return None


def _unidades_por_pack_desde_nombre(nombre):
    """Devuelve (unidades, motivo_incierto). motivo_incierto solo lleva
    valor cuando no se pudo determinar el número, para poder contar en el
    diagnóstico cuántas veces pasa cada patrón ("Double Pack", "tripack"...).
    """
    # "tripack 24×3": el número final tras x/× es el pack, no las
    # exposiciones que puedan venir justo antes. La x/× tiene que ir
    # pegada a un dígito ("24×3"), no a una letra: sin ese requisito,
    # "Cinestillfilm bw Double xx 120" (nombre real de un carrete, por la
    # película de cine Eastman Double-X) engancha la segunda "x" de "xx" y
    # confunde el 120 final -que es el formato- con un pack de 120.
    coincide_final = re.search(r"(?<=\d)[x×]\s*(\d+)\s*$", nombre, re.IGNORECASE)
    if coincide_final:
        return int(coincide_final.group(1)), None

    # "Pack 3", "Pack-2", "Pack 3x36exp": número pegado a "pack", rechazado
    # si lo que sigue son las exposiciones.
    coincide_pack = re.search(r"pack[\s-]*(\d+)\s*(\w*)", nombre, re.IGNORECASE)
    if coincide_pack and not coincide_pack.group(2).lower().startswith("exp"):
        return int(coincide_pack.group(1)), None

    # "3 pack": el número va antes de la palabra, no después.
    coincide_previo = re.search(r"(?:^|\s)(\d+)\s*pack\b", nombre, re.IGNORECASE)
    if coincide_previo:
        return int(coincide_previo.group(1)), None

    # Hay palabra de pack pero ningún número usable ("Double Pack", "tripack").
    coincide_palabra = re.search(r"\b(\w*\s?pack\w*)\b", nombre, re.IGNORECASE)
    if coincide_palabra:
        return None, coincide_palabra.group(1).strip().lower()

    return 1, None


def _unidades_por_pack_desde_slug(slug):
    coincide_pack = re.search(r"pack-(\d+)uds?", slug, re.IGNORECASE)
    if coincide_pack:
        return int(coincide_pack.group(1)), None

    coincide_ud = re.search(r"(\d+)\s*uds?", slug, re.IGNORECASE)
    if coincide_ud:
        return int(coincide_ud.group(1)), None

    if "pack" in slug.lower():
        return None, "pack (variación, sin número en el slug)"

    return 1, None


def _comprobar_moneda(precios, referencia):
    if precios["currency_minor_unit"] != 2:
        raise RuntimeError(
            f"currency_minor_unit inesperado ({precios['currency_minor_unit']}) "
            f"en {referencia}: no está previsto convertir eso, revisar a mano."
        )


def _traer_todas_las_paginas(sesion):
    productos = []
    pagina = 1
    total_paginas = None

    while True:
        respuesta = sesion.get(
            f"{URL_BASE}{RUTA_PRODUCTOS}",
            params={"per_page": 100, "page": pagina},
            timeout=30,
        )
        respuesta.raise_for_status()
        lote = respuesta.json()
        if not lote:
            break

        productos.extend(lote)
        if total_paginas is None:
            total_paginas = int(respuesta.headers.get("X-WP-TotalPages", pagina))

        if pagina >= total_paginas:
            break

        pausar()
        pagina += 1

    return productos, pagina


def _traer_variacion(sesion, variacion_id):
    respuesta = sesion.get(f"{URL_BASE}{RUTA_PRODUCTOS}/{variacion_id}", timeout=30)
    respuesta.raise_for_status()
    return respuesta.json()


def recolectar():
    """Devuelve (candidatos: list[AnuncioCrudo], diagnostico: dict)."""
    if not permitido_por_robots(URL_BASE, RUTA_PRODUCTOS):
        raise RuntimeError(f"robots.txt de {URL_BASE} prohíbe {RUTA_PRODUCTOS}")

    sesion = sesion_educada()
    productos, paginas_recorridas = _traer_todas_las_paginas(sesion)

    descartes = {
        "sin_categoria_carretes": 0,
        "instantanea": 0,
        "formato_110": 0,
        "desechables": 0,
        "caducado_por_texto": 0,
    }
    candidatos = []
    packs_sin_determinar_por_tipo = {}

    def _registrar_incierto(motivo):
        if motivo:
            packs_sin_determinar_por_tipo[motivo] = packs_sin_determinar_por_tipo.get(motivo, 0) + 1

    for producto in productos:
        categorias = _nombres_categorias(producto)
        nombre = html.unescape(producto["name"])

        if CATEGORIA_CARRETES not in categorias:
            descartes["sin_categoria_carretes"] += 1
            continue
        if CATEGORIA_INSTANTANEA in categorias:
            descartes["instantanea"] += 1
            continue
        if CATEGORIA_110 in categorias:
            descartes["formato_110"] += 1
            continue
        if CATEGORIA_DESECHABLES in categorias:
            descartes["desechables"] += 1
            continue
        if _es_caducado(producto):
            descartes["caducado_por_texto"] += 1
            continue

        descripcion_cruda = producto.get("description") or producto.get("short_description") or ""
        formato = EXCEPCIONES_FORMATO.get(nombre) or _formato_de_categorias(categorias)

        if producto["type"] == "simple":
            precios = producto["prices"]
            _comprobar_moneda(precios, f"producto {producto['id']}")

            unidades, motivo = _unidades_por_pack_desde_nombre(nombre)
            _registrar_incierto(motivo)

            candidatos.append(
                AnuncioCrudo(
                    tienda=TIENDA,
                    id_externo=str(producto["id"]),
                    url=producto["permalink"],
                    nombre_original=nombre,
                    formato=formato,
                    unidades_por_pack=unidades,
                    precio_centimos=int(precios["price"]),
                    disponible=bool(producto["is_in_stock"]),
                    descripcion_cruda=descripcion_cruda,
                )
            )

        elif producto["type"] == "variable":
            for referencia_variacion in producto.get("variations", []):
                pausar()
                variacion = _traer_variacion(sesion, referencia_variacion["id"])

                precios = variacion["prices"]
                _comprobar_moneda(precios, f"variación {variacion['id']}")

                unidades, motivo = _unidades_por_pack_desde_slug(variacion.get("slug", ""))
                _registrar_incierto(motivo)

                etiqueta_variacion = (variacion.get("variation") or "").strip()
                nombre_variacion = f"{nombre} ({etiqueta_variacion})" if etiqueta_variacion else nombre

                candidatos.append(
                    AnuncioCrudo(
                        tienda=TIENDA,
                        id_externo=str(variacion["id"]),
                        url=variacion.get("permalink") or producto["permalink"],
                        nombre_original=html.unescape(nombre_variacion),
                        formato=formato,
                        unidades_por_pack=unidades,
                        precio_centimos=int(precios["price"]),
                        disponible=bool(variacion["is_in_stock"]),
                        descripcion_cruda=descripcion_cruda,
                    )
                )

    diagnostico = {
        "total_productos": len(productos),
        "paginas_recorridas": paginas_recorridas,
        "descartes": descartes,
        "candidatos": len(candidatos),
        "packs_sin_determinar_por_tipo": packs_sin_determinar_por_tipo,
    }
    return candidatos, diagnostico
