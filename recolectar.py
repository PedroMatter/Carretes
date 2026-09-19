"""Recolector de anuncios.

Uso:
    python recolectar.py             # trae, guarda anuncios/observaciones/cola
    python recolectar.py --simular   # trae, filtra e imprime; no toca la base de datos

En modo real, la fila de "ejecucion" se escribe siempre, tanto si la
pasada termina bien como si falla a medias - es la que permite ver, más
adelante, si el recolector lleva tiempo sin funcionar.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone

import db
import emparejar
from tiendas import la_peliculera


def informar(candidatos, diagnostico):
    print("=== RESUMEN ===")
    print(f"Productos totales vistos: {diagnostico['total_productos']}")
    print(f"Páginas recorridas: {diagnostico['paginas_recorridas']}")
    print("Descartados por regla:")
    for motivo, cantidad in diagnostico["descartes"].items():
        print(f"  {motivo}: {cantidad}")
    print(f"Candidatos: {diagnostico['candidatos']}")

    inciertos = sum(1 for c in candidatos if c.unidades_por_pack is None)
    print(f"Candidatos con unidades_por_pack sin determinar: {inciertos}")

    nombres = Counter(c.nombre_original for c in candidatos)
    repetidos = {nombre: n for nombre, n in nombres.items() if n > 1}
    print(f"Nombres originales repetidos entre candidatos: {len(repetidos)}")
    for nombre, n in repetidos.items():
        print(f"  x{n}  {nombre}")


def imprimir_candidatos(candidatos):
    print()
    print("=== CANDIDATOS ===")
    for c in candidatos:
        pack = c.unidades_por_pack if c.unidades_por_pack is not None else "?"
        disponible = "sí" if c.disponible else "no"
        print(
            f"{c.id_externo}\t{c.nombre_original}\t"
            f"pack={pack}\t{c.precio_centimos}c\tdisponible={disponible}\t{c.url}"
        )


def _obtener_o_crear_anuncio(conexion, tienda, candidato, producto_id):
    fila = conexion.execute(
        "SELECT id FROM anuncio WHERE tienda = ? AND id_externo = ?",
        (tienda, candidato.id_externo),
    ).fetchone()

    if fila is not None:
        conexion.execute(
            "UPDATE anuncio SET unidades_por_pack = ?, url = ? WHERE id = ?",
            (candidato.unidades_por_pack, candidato.url, fila[0]),
        )
        return fila[0]

    cursor = conexion.execute(
        """
        INSERT INTO anuncio (producto_id, tienda, id_externo, unidades_por_pack, url)
        VALUES (?, ?, ?, ?, ?)
        """,
        (producto_id, tienda, candidato.id_externo, candidato.unidades_por_pack, candidato.url),
    )
    return cursor.lastrowid


def _marcar_desaparecidos(conexion, tienda, vistos_id_externo, ahora):
    desaparecidos = 0
    for anuncio_id, id_externo in conexion.execute(
        "SELECT id, id_externo FROM anuncio WHERE tienda = ?", (tienda,)
    ):
        if id_externo in vistos_id_externo:
            continue
        conexion.execute(
            """
            INSERT INTO observacion (anuncio_id, precio_centimos, disponible, capturado_en)
            VALUES (
                ?,
                (SELECT precio_centimos FROM observacion
                 WHERE anuncio_id = ? ORDER BY capturado_en DESC LIMIT 1),
                0,
                ?
            )
            """,
            (anuncio_id, anuncio_id, ahora),
        )
        desaparecidos += 1
    return desaparecidos


def guardar(tienda_modulo):
    conexion = db.conectar()
    tienda = tienda_modulo.TIENDA
    ahora = datetime.now(timezone.utc).isoformat()

    id_ejecucion = conexion.execute(
        "INSERT INTO ejecucion (tienda, iniciada_en) VALUES (?, ?)",
        (tienda, ahora),
    ).lastrowid
    conexion.commit()

    try:
        candidatos, diagnostico = tienda_modulo.recolectar()
        informar(candidatos, diagnostico)

        vistos_id_externo = set()
        cola_creadas = 0
        anuncios_con_observacion = 0

        for candidato in candidatos:
            resultado = emparejar.resolver(conexion, tienda, candidato.nombre_original)

            if resultado == emparejar.NO_ES_CARRETE:
                continue

            if resultado == emparejar.PENDIENTE:
                cursor = conexion.execute(
                    """
                    INSERT OR IGNORE INTO cola_revision
                        (tienda, id_externo, nombre_original, url, formato,
                         unidades_por_pack, descripcion_cruda, motivo, visto_en)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente_revision', ?)
                    """,
                    (
                        tienda,
                        candidato.id_externo,
                        candidato.nombre_original,
                        candidato.url,
                        candidato.formato,
                        candidato.unidades_por_pack,
                        candidato.descripcion_cruda,
                        ahora,
                    ),
                )
                if cursor.rowcount:
                    cola_creadas += 1
                continue

            producto_id = resultado
            anuncio_id = _obtener_o_crear_anuncio(conexion, tienda, candidato, producto_id)
            vistos_id_externo.add(candidato.id_externo)
            conexion.execute(
                """
                INSERT INTO observacion (anuncio_id, precio_centimos, disponible, capturado_en)
                VALUES (?, ?, ?, ?)
                """,
                (anuncio_id, candidato.precio_centimos, int(candidato.disponible), ahora),
            )
            anuncios_con_observacion += 1

        desaparecidos = _marcar_desaparecidos(conexion, tienda, vistos_id_externo, ahora)

        conexion.commit()
        conexion.execute(
            """
            UPDATE ejecucion SET finalizada_en = ?, anuncios_vistos = ?, error = NULL
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), diagnostico["candidatos"], id_ejecucion),
        )
        conexion.commit()

        print()
        print("=== GUARDADO ===")
        print(f"Filas nuevas en cola_revision: {cola_creadas}")
        print(f"Anuncios con observación nueva: {anuncios_con_observacion}")
        print(f"Marcados como no disponibles (desaparecidos): {desaparecidos}")

    except Exception as error:
        conexion.rollback()
        conexion.execute(
            "UPDATE ejecucion SET finalizada_en = ?, error = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), str(error), id_ejecucion),
        )
        conexion.commit()
        raise
    finally:
        conexion.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--simular",
        action="store_true",
        help="Trae y filtra, imprime el resultado, no escribe nada en la base de datos.",
    )
    args = parser.parse_args()

    if args.simular:
        candidatos, diagnostico = la_peliculera.recolectar()
        informar(candidatos, diagnostico)
        imprimir_candidatos(candidatos)
    else:
        guardar(la_peliculera)


if __name__ == "__main__":
    main()
