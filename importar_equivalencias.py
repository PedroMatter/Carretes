"""Importa equivalencias.csv a la tabla equivalencia.

Para vaciar la cola de golpe en una hoja de cálculo en vez de fila a fila
en resolver_cola.py. Busca cada producto por su identidad real (marca,
película, formato, exposiciones) porque el CSV no lleva producto_id — ver
exportar_equivalencias.py para el motivo.

Cada fila que se escribe (nueva, cambiada, o ya igual) cierra también su
fila de cola_revision si la tenía pendiente: si no, resolver_cola.py
volvería a preguntar por algo que este importador ya dejó resuelto.

Uso:
    python importar_equivalencias.py             # importa de verdad
    python importar_equivalencias.py --simular   # solo informa, no escribe

Falla a gritos y no importa NADA si alguna fila nombra un producto que no
existe en el catálogo, o si el propio CSV tiene dos filas para el mismo
(tienda, nombre_original). Nunca se salta una fila mala en silencio: sería
perder una decisión humana sin que nadie se entere.

Si alguna fila cambiaría una equivalencia ya existente (apuntando ahora a
un producto distinto), se enseña la lista completa de cambios y hace falta
confirmar antes de escribir nada.
"""

import argparse
import csv
import sys
from pathlib import Path

import db

RAIZ = Path(__file__).parent
EQUIVALENCIAS_CSV = RAIZ / "equivalencias.csv"


def leer_csv(ruta):
    with ruta.open(encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def buscar_producto_id(conexion, marca, nombre_pelicula, formato, exposiciones):
    fila = conexion.execute(
        """
        SELECT pr.id FROM producto pr JOIN pelicula p ON p.id = pr.pelicula_id
        WHERE p.marca = ? AND p.nombre = ? AND pr.formato = ? AND pr.exposiciones IS ?
        """,
        (marca, nombre_pelicula, formato, exposiciones),
    ).fetchone()
    return fila[0] if fila else None


def analizar(conexion, filas):
    """Devuelve (nuevas, iguales, cambios, errores). Solo lee, no escribe
    nada: todo lo que hace falta para decidir si se puede importar entero.
    """
    nuevas, iguales, cambios, errores = [], [], [], []
    vistas_en_csv = {}

    for numero_de_linea, fila in enumerate(filas, start=2):  # 1 = cabecera
        tienda = fila["tienda"].strip()
        nombre_original = fila["nombre_original"].strip()
        marca = fila["marca"].strip()
        nombre_pelicula = fila["nombre_pelicula"].strip()
        formato = fila["formato"].strip()
        exposiciones_texto = fila["exposiciones"].strip()

        clave = (tienda, nombre_original)
        if clave in vistas_en_csv:
            errores.append(
                f"línea {numero_de_linea}: (tienda, nombre_original) repetido, ya "
                f"apareció en la línea {vistas_en_csv[clave]}"
            )
            continue
        vistas_en_csv[clave] = numero_de_linea

        es_no_carrete = not (marca or nombre_pelicula or formato or exposiciones_texto)

        if es_no_carrete:
            producto_id = None
        else:
            try:
                exposiciones = int(exposiciones_texto) if exposiciones_texto else None
            except ValueError:
                errores.append(
                    f"línea {numero_de_linea}: exposiciones {exposiciones_texto!r} no es "
                    f"un número"
                )
                continue

            producto_id = buscar_producto_id(conexion, marca, nombre_pelicula, formato, exposiciones)
            if producto_id is None:
                errores.append(
                    f"línea {numero_de_linea}: no existe en el catálogo "
                    f"marca={marca!r} nombre_pelicula={nombre_pelicula!r} "
                    f"formato={formato!r} exposiciones={exposiciones_texto!r} "
                    f"(tienda={tienda!r}, nombre_original={nombre_original!r})"
                )
                continue

        actual = conexion.execute(
            "SELECT producto_id FROM equivalencia WHERE tienda = ? AND nombre_original = ?",
            (tienda, nombre_original),
        ).fetchone()

        registro = {"tienda": tienda, "nombre_original": nombre_original, "producto_id": producto_id}

        if actual is None:
            nuevas.append(registro)
        elif actual[0] == producto_id:
            iguales.append(registro)
        else:
            registro["producto_id_anterior"] = actual[0]
            cambios.append(registro)

    return nuevas, iguales, cambios, errores


def _describir_producto(conexion, producto_id):
    if producto_id is None:
        return "no es un carrete"
    fila = conexion.execute(
        """
        SELECT p.marca, p.nombre, pr.formato, pr.exposiciones
        FROM producto pr JOIN pelicula p ON p.id = pr.pelicula_id WHERE pr.id = ?
        """,
        (producto_id,),
    ).fetchone()
    if fila is None:
        return f"producto_id {producto_id} (ya no existe)"
    marca, nombre, formato, exposiciones = fila
    texto = f"{marca} {nombre} {formato}"
    if exposiciones is not None:
        texto += f" {exposiciones}exp"
    return texto


def escribir(conexion, registros):
    for r in registros:
        conexion.execute(
            """
            INSERT INTO equivalencia (tienda, nombre_original, producto_id) VALUES (?, ?, ?)
            ON CONFLICT (tienda, nombre_original) DO UPDATE SET producto_id = excluded.producto_id
            """,
            (r["tienda"], r["nombre_original"], r["producto_id"]),
        )
        # Si esta fila estaba en la cola, ciérrala: ya no hay nada pendiente
        # que preguntar sobre ella. Si no estaba en la cola, no toca nada.
        conexion.execute(
            "UPDATE cola_revision SET resuelto = 1 WHERE tienda = ? AND nombre_original = ?",
            (r["tienda"], r["nombre_original"]),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simular", action="store_true")
    parser.add_argument(
        "--archivo",
        default=str(EQUIVALENCIAS_CSV),
        help="CSV a importar (por defecto equivalencias.csv).",
    )
    args = parser.parse_args()

    filas = leer_csv(Path(args.archivo))
    conexion = db.conectar()
    nuevas, iguales, cambios, errores = analizar(conexion, filas)

    if errores:
        print(f"ERROR: {len(errores)} fila(s) con problemas. No se importa nada.")
        for error in errores:
            print(f"  - {error}")
        conexion.close()
        sys.exit(1)

    print(f"Nuevas equivalencias: {len(nuevas)}")
    print(f"Ya existían igual (sin cambio): {len(iguales)}")
    print(f"Cambiarían una decisión anterior: {len(cambios)}")

    if cambios:
        print()
        print("Estos cambios de decisión necesitan confirmación:")
        for c in cambios:
            print(f"  - {c['tienda']} / {c['nombre_original']}")
            print(f"      antes:  {_describir_producto(conexion, c['producto_id_anterior'])}")
            print(f"      ahora:  {_describir_producto(conexion, c['producto_id'])}")

    if args.simular:
        print()
        print("(--simular: no se ha escrito nada)")
        conexion.close()
        return

    if not nuevas and not cambios and not iguales:
        print("Nada que importar.")
        conexion.close()
        return

    if cambios:
        respuesta = input("\n¿Confirmas los cambios de decisión de arriba? [s/N] ").strip().lower()
        if respuesta != "s":
            print("Cancelado. No se ha escrito nada.")
            conexion.close()
            return

    try:
        # iguales también pasa por escribir(): la equivalencia no cambia,
        # pero puede que cola_revision siguiera sin marcar como resuelta.
        escribir(conexion, nuevas + cambios + iguales)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()

    print(f"Importadas {len(nuevas)} nuevas y {len(cambios)} cambios.")


if __name__ == "__main__":
    main()
