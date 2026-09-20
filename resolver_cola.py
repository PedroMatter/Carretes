"""Resuelve filas de cola_revision a mano, una sesión a la vez.

No hay cruce automático (ver CLAUDE.md, "El emparejamiento"): las
sugerencias son solo parecido de texto (difflib), para que elijas más
rápido, nunca para decidir por su cuenta. Los números de parecido no se
enseñan a propósito: miden letras en común, no si es la película correcta,
y un porcentaje en pantalla invita a confiar en él más de lo que vale.

Uso:
    python resolver_cola.py               # hasta 20 filas
    python resolver_cola.py --limite 50   # hasta 50 filas

En cada fila:
    1-5  emparejar con esa sugerencia
    n    no es un carrete
    c    crear un producto nuevo en el catálogo y emparejar con él
    b    buscar en el catálogo a mano (por si ninguna sugerencia vale)
    s    saltar esta fila, seguir con la siguiente
    u    deshacer la última decisión (un solo nivel)
    q    salir de la sesión

Al terminar (o con q), vuelca equivalencia a equivalencias.csv.
"""

import argparse
import csv
import difflib
import re
from pathlib import Path

import db
import exportar_equivalencias
import recolectar

UMBRAL_SUGERENCIA = 0.5
MAX_SUGERENCIAS = 5
LIMITE_POR_DEFECTO = 20
PROCESOS_VALIDOS = ("C-41", "B&N", "E-6", "ECN-2")
FORMATOS_VALIDOS = ("35mm", "120")

RAIZ = Path(__file__).parent
CATALOGO_CSV = RAIZ / "catalogo.csv"


# --- catálogo y sugerencias -------------------------------------------------

def cargar_catalogo(conexion):
    """[(producto_id, texto_para_comparar, marca, nombre, formato, exposiciones), ...]"""
    filas = conexion.execute(
        """
        SELECT pr.id, p.marca, p.nombre, pr.formato, pr.exposiciones
        FROM producto pr JOIN pelicula p ON p.id = pr.pelicula_id
        """
    ).fetchall()
    catalogo = []
    for producto_id, marca, nombre, formato, exposiciones in filas:
        texto = f"{marca} {nombre} {formato}"
        if exposiciones is not None:
            texto += f" {exposiciones}exp"
        catalogo.append((producto_id, texto, marca, nombre, formato, exposiciones))
    return catalogo


def _parecido(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def sugerir(nombre_original, catalogo):
    puntuados = [(_parecido(nombre_original, item[1]), item) for item in catalogo]
    puntuados.sort(key=lambda par: par[0], reverse=True)
    return [item for puntuacion, item in puntuados if puntuacion >= UMBRAL_SUGERENCIA][
        :MAX_SUGERENCIAS
    ]


def ordenar_por_similitud(filas, clave_texto):
    """Reordena `filas` para que las que se parecen entre sí (por
    difflib, nunca mostrado) queden seguidas en pantalla. Es solo orden de
    presentación, no una decisión ni una puntuación que se enseñe.
    """
    if not filas:
        return []
    restantes = list(range(len(filas)))
    orden = [restantes.pop(0)]
    while restantes:
        actual = clave_texto(filas[orden[-1]])
        mejor_pos = max(
            range(len(restantes)),
            key=lambda i: _parecido(actual, clave_texto(filas[restantes[i]])),
        )
        orden.append(restantes.pop(mejor_pos))
    return [filas[i] for i in orden]


# --- carga de la cola --------------------------------------------------------

COLUMNAS_COLA = [
    "id",
    "tienda",
    "id_externo",
    "nombre_original",
    "url",
    "formato",
    "unidades_por_pack",
    "descripcion_cruda",
]


def cargar_pendientes(conexion):
    filas = conexion.execute(
        f"SELECT {', '.join(COLUMNAS_COLA)} FROM cola_revision WHERE resuelto = 0"
    ).fetchall()
    return [dict(zip(COLUMNAS_COLA, fila)) for fila in filas]


def preparar_orden(pendientes, catalogo):
    con_sugerencia = []
    sin_sugerencia = []
    for fila in pendientes:
        candidatos = sugerir(fila["nombre_original"], catalogo)
        if candidatos:
            con_sugerencia.append((fila, candidatos))
        else:
            sin_sugerencia.append((fila, []))

    con_sugerencia = ordenar_por_similitud(con_sugerencia, lambda par: par[0]["nombre_original"])
    sin_sugerencia = ordenar_por_similitud(sin_sugerencia, lambda par: par[0]["nombre_original"])
    return con_sugerencia + sin_sugerencia


# --- acciones sobre una fila --------------------------------------------------

def emparejar_y_dar_de_alta(conexion, fila, producto_id):
    # ON CONFLICT en vez de un INSERT plano: si ya hubiera una equivalencia
    # para este (tienda, nombre_original) - por ejemplo, si cola_revision se
    # desincronizó y la misma fila se intenta resolver dos veces - se
    # actualiza en vez de reventar.
    conexion.execute(
        """
        INSERT INTO equivalencia (tienda, nombre_original, producto_id) VALUES (?, ?, ?)
        ON CONFLICT (tienda, nombre_original) DO UPDATE SET producto_id = excluded.producto_id
        """,
        (fila["tienda"], fila["nombre_original"], producto_id),
    )
    recolectar.obtener_o_crear_anuncio(
        conexion,
        fila["tienda"],
        fila["id_externo"],
        fila["url"],
        fila["unidades_por_pack"],
        producto_id,
        fila["nombre_original"],
    )
    conexion.execute(
        "UPDATE cola_revision SET resuelto = 1 WHERE id = ?", (fila["id"],)
    )
    conexion.commit()


def marcar_no_es_carrete(conexion, fila):
    conexion.execute(
        """
        INSERT INTO equivalencia (tienda, nombre_original, producto_id) VALUES (?, ?, NULL)
        ON CONFLICT (tienda, nombre_original) DO UPDATE SET producto_id = NULL
        """,
        (fila["tienda"], fila["nombre_original"]),
    )
    conexion.execute(
        "UPDATE cola_revision SET resuelto = 1 WHERE id = ?", (fila["id"],)
    )
    conexion.commit()


def deshacer(conexion, ultima):
    """Revierte la última decisión: borra la equivalencia, borra el anuncio
    que se hubiera dado de alta con ella (si lo hubo) y vuelve a dejar la
    fila de la cola como pendiente. No toca el catálogo: si la decisión
    había creado una película/producto nuevos, esos se quedan.
    """
    tienda = ultima["tienda"]
    nombre_original = ultima["nombre_original"]
    conexion.execute(
        "DELETE FROM equivalencia WHERE tienda = ? AND nombre_original = ?",
        (tienda, nombre_original),
    )
    conexion.execute(
        "DELETE FROM anuncio WHERE tienda = ? AND id_externo = ?",
        (tienda, ultima["id_externo"]),
    )
    conexion.execute(
        "UPDATE cola_revision SET resuelto = 0 WHERE id = ?", (ultima["cola_id"],)
    )
    conexion.commit()


# --- crear un producto nuevo --------------------------------------------------

def _preguntar(mensaje, valores_validos=None):
    while True:
        respuesta = input(mensaje).strip()
        if valores_validos is None or respuesta in valores_validos:
            return respuesta
        print(f"  Valor no válido, tiene que ser uno de: {', '.join(valores_validos)}")


def _preguntar_entero(mensaje):
    while True:
        respuesta = input(mensaje).strip()
        if respuesta.isdigit():
            return int(respuesta)
        print("  Tiene que ser un número entero.")


def crear_producto_nuevo(conexion, nuevas_peliculas_sesion):
    marca = input("Marca: ").strip()

    existentes = conexion.execute(
        "SELECT nombre, iso, proceso FROM pelicula WHERE marca = ? ORDER BY nombre", (marca,)
    ).fetchall()
    if existentes:
        print(f"  Películas de {marca} que ya hay en el catálogo:")
        for nombre, iso, proceso in existentes:
            print(f"    - {nombre} (ISO {iso}, {proceso})")
    else:
        print(f"  No hay ninguna película de {marca} todavía en el catálogo.")

    nombre = input("Nombre de la película: ").strip()

    pelicula_existente = conexion.execute(
        "SELECT id, iso, proceso FROM pelicula WHERE marca = ? AND nombre = ?", (marca, nombre)
    ).fetchone()

    if pelicula_existente:
        pelicula_id, iso, proceso = pelicula_existente
        print(f"  Ya existe: {marca} {nombre} (ISO {iso}, {proceso}). Se reutiliza.")
        pelicula_es_nueva = False
    else:
        iso = _preguntar_entero("ISO: ")
        proceso = _preguntar(f"Proceso ({'/'.join(PROCESOS_VALIDOS)}): ", PROCESOS_VALIDOS)
        pelicula_id = None
        pelicula_es_nueva = True

    formato = _preguntar(f"Formato ({'/'.join(FORMATOS_VALIDOS)}): ", FORMATOS_VALIDOS)
    exposiciones = _preguntar_entero("Exposiciones: ") if formato == "35mm" else None

    resumen = f"{marca} {nombre}, {formato}"
    if exposiciones is not None:
        resumen += f", {exposiciones} exp"
    confirmacion = input(f"Crear: {resumen} - ¿confirmas? [s/N] ").strip().lower()
    if confirmacion != "s":
        print("  Cancelado.")
        return None

    if pelicula_id is not None:
        producto_existente = conexion.execute(
            """
            SELECT id FROM producto
            WHERE pelicula_id = ? AND formato = ? AND exposiciones IS ?
            """,
            (pelicula_id, formato, exposiciones),
        ).fetchone()
        if producto_existente:
            print("  Ese producto ya existía en el catálogo, se reutiliza.")
            return producto_existente[0]

    # DB sin confirmar todavía + CSV + solo entonces commit: si el CSV
    # falla, la transacción se deshace y no queda ni la mitad de las dos
    # cosas escrita. No es una garantía perfecta entre dos sistemas
    # distintos, pero cubre los fallos reales (dato inválido, disco lleno).
    try:
        if pelicula_es_nueva:
            pelicula_id = conexion.execute(
                "INSERT INTO pelicula (marca, nombre, iso, proceso) VALUES (?, ?, ?, ?)",
                (marca, nombre, iso, proceso),
            ).lastrowid

        producto_id = conexion.execute(
            "INSERT INTO producto (pelicula_id, formato, exposiciones) VALUES (?, ?, ?)",
            (pelicula_id, formato, exposiciones),
        ).lastrowid

        # Si el fichero no termina en salto de línea (por ejemplo, editado a
        # mano en un editor que lo recorta), un "a" pegaría la fila nueva al
        # final de la última línea existente en vez de en una línea propia.
        contenido_previo = CATALOGO_CSV.read_bytes()
        necesita_salto = contenido_previo and not contenido_previo.endswith(b"\n")

        with CATALOGO_CSV.open("a", newline="", encoding="utf-8") as archivo:
            if necesita_salto:
                archivo.write("\n")
            csv.writer(archivo).writerow(
                [marca, nombre, iso, proceso, formato, exposiciones if exposiciones is not None else ""]
            )
    except Exception:
        conexion.rollback()
        raise

    conexion.commit()

    if pelicula_es_nueva:
        nuevas_peliculas_sesion.append(f"{marca} {nombre} (ISO {iso}, {proceso})")

    return producto_id


# --- bucle principal -----------------------------------------------------

def _descripcion_legible(descripcion_html):
    texto = re.sub(r"<li>", "\n  - ", descripcion_html)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto)
    return texto.strip()


def mostrar_fila(indice, total, fila, candidatos):
    print()
    print("-" * 70)
    print(f"[{indice}/{total}] {fila['tienda']}")
    print(f"Nombre original: {fila['nombre_original']}")
    print(f"URL: {fila['url']}")
    pack = fila["unidades_por_pack"] if fila["unidades_por_pack"] is not None else "?"
    print(f"Formato detectado: {fila['formato'] or '?'}  |  Unidades por pack: {pack}")
    print(f"Descripción de la tienda:{_descripcion_legible(fila['descripcion_cruda'])}")

    if candidatos:
        print("Sugerencias:")
        for i, item in enumerate(candidatos, start=1):
            print(f"  {i}) {item[1]}")
    else:
        print("Sin sugerencias del catálogo.")


def buscar_manual(catalogo):
    consulta = input("Buscar en el catálogo: ").strip()
    if not consulta:
        return None
    puntuados = sorted(catalogo, key=lambda item: _parecido(consulta, item[1]), reverse=True)
    resultados = puntuados[:MAX_SUGERENCIAS]
    if not resultados:
        print("  Catálogo vacío.")
        return None
    for i, item in enumerate(resultados, start=1):
        print(f"  {i}) {item[1]}")
    eleccion = input("  Elige un número, o nada para cancelar: ").strip()
    if eleccion.isdigit() and 1 <= int(eleccion) <= len(resultados):
        return resultados[int(eleccion) - 1][0]
    return None


def resolver_sesion(limite):
    conexion = db.conectar()
    catalogo = cargar_catalogo(conexion)
    pendientes = cargar_pendientes(conexion)
    orden = preparar_orden(pendientes, catalogo)[:limite]

    print(f"{len(pendientes)} filas pendientes en total. Esta sesión procesa hasta {len(orden)}.")

    resueltas = 0
    nuevas_peliculas_sesion = []
    ultima_decision = None

    i = 0
    while i < len(orden):
        fila, _ = orden[i]
        candidatos = sugerir(fila["nombre_original"], catalogo)  # recalcular por si hay productos nuevos
        mostrar_fila(i + 1, len(orden), fila, candidatos)

        opciones = f"[1-{len(candidatos)}] emparejar" if candidatos else ""
        ayuda = ", ".join(
            filter(None, [opciones, "[n] no es carrete", "[c] crear nuevo", "[b] buscar",
                          "[s] saltar", "[u] deshacer" if ultima_decision else "", "[q] salir"])
        )
        respuesta = input(f"{ayuda}: ").strip().lower()

        if respuesta == "q":
            break

        if respuesta == "s":
            i += 1
            continue

        if respuesta == "u":
            if ultima_decision is None:
                print("  No hay nada que deshacer.")
                continue
            deshacer(conexion, ultima_decision)
            print(f"  Deshecho: {ultima_decision['nombre_original']}")
            ultima_decision = None
            resueltas -= 1
            i -= 1  # retrocede para volver a enseñar la fila que se acaba de deshacer
            continue

        if respuesta == "n":
            marcar_no_es_carrete(conexion, fila)
            ultima_decision = {**fila, "cola_id": fila["id"]}
            resueltas += 1
            i += 1
            continue

        if respuesta == "c":
            producto_id = crear_producto_nuevo(conexion, nuevas_peliculas_sesion)
            if producto_id is None:
                continue
            catalogo = cargar_catalogo(conexion)  # para que filas siguientes lo vean
            emparejar_y_dar_de_alta(conexion, fila, producto_id)
            ultima_decision = {**fila, "cola_id": fila["id"]}
            resueltas += 1
            i += 1
            continue

        if respuesta == "b":
            producto_id = buscar_manual(catalogo)
            if producto_id is None:
                continue
            emparejar_y_dar_de_alta(conexion, fila, producto_id)
            ultima_decision = {**fila, "cola_id": fila["id"]}
            resueltas += 1
            i += 1
            continue

        if respuesta.isdigit() and candidatos and 1 <= int(respuesta) <= len(candidatos):
            producto_id = candidatos[int(respuesta) - 1][0]
            emparejar_y_dar_de_alta(conexion, fila, producto_id)
            ultima_decision = {**fila, "cola_id": fila["id"]}
            resueltas += 1
            i += 1
            continue

        print("  No entendí esa opción.")

    conexion.close()

    print()
    print("=== FIN DE LA SESIÓN ===")
    print(f"Filas resueltas: {resueltas}")
    if nuevas_peliculas_sesion:
        print("Películas nuevas añadidas al catálogo en esta sesión:")
        for descripcion in nuevas_peliculas_sesion:
            print(f"  - {descripcion}")

    exportar_equivalencias.exportar()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=LIMITE_POR_DEFECTO)
    args = parser.parse_args()
    resolver_sesion(args.limite)


if __name__ == "__main__":
    main()
