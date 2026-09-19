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
        "SELECT id, unidades_por_pack FROM anuncio WHERE tienda = ? AND id_externo = ?",
        (tienda, candidato.id_externo),
    ).fetchone()

    if fila is not None:
        anuncio_id, unidades_anteriores = fila
        if unidades_anteriores != candidato.unidades_por_pack:
            # De momento solo avisar, no decidir nada: si esto no pasa nunca
            # en unos meses, se deja así; si pasa, se piensa con el caso
            # real delante (el histórico de precio-por-unidad de este
            # anuncio queda mezclado entre el valor viejo y el nuevo).
            print(
                f"AVISO: {tienda} {candidato.id_externo} ({candidato.nombre_original}) "
                f"cambia unidades_por_pack de {unidades_anteriores} a "
                f"{candidato.unidades_por_pack}"
            )
        conexion.execute(
            "UPDATE anuncio SET unidades_por_pack = ?, url = ? WHERE id = ?",
            (candidato.unidades_por_pack, candidato.url, anuncio_id),
        )
        return anuncio_id

    cursor = conexion.execute(
        """
        INSERT INTO anuncio (producto_id, tienda, id_externo, unidades_por_pack, url)
        VALUES (?, ?, ?, ?, ?)
        """,
        (producto_id, tienda, candidato.id_externo, candidato.unidades_por_pack, candidato.url),
    )
    return cursor.lastrowid


def _marcar_desaparecidos(conexion, tienda, vistos_id_externo, ahora):
    """Para cada anuncio de la tienda que no apareció en esta pasada, si su
    última observación conocida decía disponible=1, añade una observación
    con disponible=0 y precio_centimos=NULL — no se ha observado ningún
    precio, solo el hecho de que hoy no está.

    No repite la fila en cada pasada siguiente (solo escribe en la
    transición de "estaba" a "ya no está"), y un anuncio sin ninguna
    observación previa no genera nada: no hay "dejar de ver" que registrar.
    """
    marcados = 0
    for anuncio_id, id_externo in conexion.execute(
        "SELECT id, id_externo FROM anuncio WHERE tienda = ?", (tienda,)
    ):
        if id_externo in vistos_id_externo:
            continue

        ultima = conexion.execute(
            """
            SELECT disponible FROM observacion
            WHERE anuncio_id = ?
            ORDER BY capturado_en DESC LIMIT 1
            """,
            (anuncio_id,),
        ).fetchone()

        if ultima is None or ultima[0] == 0:
            continue

        conexion.execute(
            """
            INSERT INTO observacion (anuncio_id, precio_centimos, disponible, capturado_en)
            VALUES (?, NULL, 0, ?)
            """,
            (anuncio_id, ahora),
        )
        marcados += 1
    return marcados


def guardar(tienda_modulo):
    conexion = db.conectar()
    tienda = tienda_modulo.TIENDA
    ahora = datetime.now(timezone.utc).isoformat()

    id_ejecucion = conexion.execute(
        "INSERT INTO ejecucion (tienda, iniciada_en) VALUES (?, ?)",
        (tienda, ahora),
    ).lastrowid
    conexion.commit()

    candidatos_vistos = None
    anuncios_con_observacion = 0

    try:
        candidatos, diagnostico = tienda_modulo.recolectar()
        informar(candidatos, diagnostico)
        candidatos_vistos = diagnostico["candidatos"]

        vistos_id_externo = set()
        cola_creadas = 0

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
            UPDATE ejecucion
            SET finalizada_en = ?, candidatos_vistos = ?, anuncios_vistos = ?, error = NULL
            WHERE id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                candidatos_vistos,
                anuncios_con_observacion,
                id_ejecucion,
            ),
        )
        conexion.commit()

        print()
        print("=== GUARDADO ===")
        print(f"Filas nuevas en cola_revision: {cola_creadas}")
        print(f"Anuncios con observación nueva: {anuncios_con_observacion}")
        print(f"Marcados como no disponibles (desaparecidos): {desaparecidos}")

    except Exception as error:
        conexion.rollback()
        # anuncios_con_observacion no se guarda aquí: el rollback deshace
        # cualquier anuncio/observación de esta pasada, así que lo único
        # honesto es 0 (nada quedó guardado), aunque el bucle hubiera
        # llegado más lejos antes de fallar.
        conexion.execute(
            """
            UPDATE ejecucion
            SET finalizada_en = ?, candidatos_vistos = ?, anuncios_vistos = 0, error = ?
            WHERE id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                candidatos_vistos,
                str(error),
                id_ejecucion,
            ),
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
