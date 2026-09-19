"""Adaptador de La Peliculera: trae sus productos vía la API pública de
WooCommerce Store (wp-json/wc/store/v1) y los convierte en AnuncioCrudo.

No hace ningún cruce automático con el catálogo — eso es cosa de
emparejar.py. Aquí solo se decide qué productos son candidatos a ser un
carrete (por categoría) y se extrae lo que la propia tienda ya da separado.
"""

import html
import re

from tiendas.base import AnuncioCrudo, pausar, permitido_por_robots, sesion_educada

TIENDA = "La Peliculera"
URL_BASE = "https://lapeliculera.com"
RUTA_PRODUCTOS = "/wp-json/wc/store/v1/products"

CATEGORIA_CARRETES = "Carretes"
CATEGORIA_INSTANTANEA = "Carretes para Cámaras Instantánea"
CATEGORIA_CADUCADOS = "Carretes Caducados"
CATEGORIA_110 = "110"


def _nombres_categorias(producto):
    return {c["name"] for c in producto.get("categories", [])}


def _extraer_campos_descripcion(descripcion_html):
    """{etiqueta_en_minusculas: valor} a partir de los <li>Etiqueta: valor</li>
    de la descripción. Tolera que falten etiquetas conocidas o que aparezcan
    otras nuevas: no fuerza ninguna forma fija, porque ya sabemos que la
    tienda no es consistente (Iso/ISO, Esposiciones/Exposiciones...).
    """
    campos = {}
    for etiqueta, valor in re.findall(r"<li>([^:<]+):\s*([^<]*)</li>", descripcion_html):
        campos[etiqueta.strip().lower()] = valor.strip()
    return campos


def _unidades_por_pack(nombre, descripcion_html, campos):
    valor = campos.get("unidades")
    if valor is not None:
        numero = re.search(r"\d+", valor)
        if numero:
            return int(numero.group())

    # Segunda opción: el número a veces está en el propio nombre ("Pack 5
    # Unidades", "Pack3"). Pero "Pack 36 exp" es un pack de algo con 36
    # exposiciones, no un pack de 36 unidades. Ojo: un "(?!...)" dentro de
    # la propia expresión no sirve aquí, porque el motor de regex recorta
    # el número (de "36" a "3") hasta que la condición se cumpla, en vez
    # de rendirse. Por eso la palabra siguiente se comprueba aparte, en
    # Python, sobre el número completo tal como vino.
    en_nombre = re.search(r"pack\s*(\d+)\s*(\w*)", nombre, re.IGNORECASE)
    if en_nombre and not en_nombre.group(2).lower().startswith("exp"):
        return int(en_nombre.group(1))

    texto = f"{nombre} {descripcion_html}".lower()
    if "pack" in texto or "unidades" in texto:
        return None  # hay señal de pack pero no se pudo leer el número: no adivinar

    return 1


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


def recolectar():
    """Devuelve (candidatos: list[AnuncioCrudo], diagnostico: dict)."""
    if not permitido_por_robots(URL_BASE, RUTA_PRODUCTOS):
        raise RuntimeError(f"robots.txt de {URL_BASE} prohíbe {RUTA_PRODUCTOS}")

    sesion = sesion_educada()
    productos, paginas_recorridas = _traer_todas_las_paginas(sesion)

    descartes = {
        "sin_categoria_carretes": 0,
        "instantanea": 0,
        "caducados": 0,
        "formato_110": 0,
        "nombre_caducado_sin_categoria": 0,
    }
    candidatos = []

    for producto in productos:
        categorias = _nombres_categorias(producto)
        nombre = html.unescape(producto["name"])

        if CATEGORIA_CARRETES not in categorias:
            descartes["sin_categoria_carretes"] += 1
            continue
        if CATEGORIA_INSTANTANEA in categorias:
            descartes["instantanea"] += 1
            continue
        if CATEGORIA_CADUCADOS in categorias:
            descartes["caducados"] += 1
            continue
        if CATEGORIA_110 in categorias:
            descartes["formato_110"] += 1
            continue
        if "caducad" in nombre.lower():
            # Red de seguridad: pasó los filtros de categoría pero el nombre
            # dice que está caducado. Si esto se dispara alguna vez, avisa:
            # significa que las categorías de la tienda no son de fiar.
            descartes["nombre_caducado_sin_categoria"] += 1
            continue

        descripcion = producto.get("description", "")
        campos = _extraer_campos_descripcion(descripcion)
        precios = producto["prices"]

        if precios["currency_minor_unit"] != 2:
            raise RuntimeError(
                f"currency_minor_unit inesperado ({precios['currency_minor_unit']}) "
                f"en producto {producto['id']}: no está previsto convertir eso, revisar a mano."
            )

        candidatos.append(
            AnuncioCrudo(
                tienda=TIENDA,
                id_externo=str(producto["id"]),
                url=producto["permalink"],
                nombre_original=nombre,
                formato=campos.get("formato"),
                unidades_por_pack=_unidades_por_pack(nombre, descripcion, campos),
                precio_centimos=int(precios["price"]),
                disponible=bool(producto["is_in_stock"]),
                descripcion_cruda=descripcion,
            )
        )

    diagnostico = {
        "total_productos": len(productos),
        "paginas_recorridas": paginas_recorridas,
        "descartes": descartes,
        "candidatos": len(candidatos),
    }
    return candidatos, diagnostico
