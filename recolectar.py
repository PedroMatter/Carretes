"""Recolector de anuncios.

En esta entrega SOLO IMPRIME: no guarda nada en la base de datos, ni
siquiera la fila de ejecucion. Sirve para ver con los propios ojos qué
trae y qué descarta cada tienda antes de dejar que toque el disco.
"""

from collections import Counter

from tiendas import la_peliculera


def informar(tienda_modulo):
    candidatos, diagnostico = tienda_modulo.recolectar()

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

    print()
    print("=== CANDIDATOS ===")
    for c in candidatos:
        pack = c.unidades_por_pack if c.unidades_por_pack is not None else "?"
        disponible = "sí" if c.disponible else "no"
        print(
            f"{c.id_externo}\t{c.nombre_original}\t"
            f"pack={pack}\t{c.precio_centimos}c\tdisponible={disponible}\t{c.url}"
        )


if __name__ == "__main__":
    informar(la_peliculera)
