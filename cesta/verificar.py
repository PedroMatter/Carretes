"""
Comprobación de que el MILP no miente.

Para instancias pequeñas se puede enumerar TODAS las asignaciones posibles de
artículos a tiendas por fuerza bruta y quedarse con la mejor. Si el resultado
coincide con el del optimizador, el modelo está bien planteado.

Esto no es un test de rendimiento, es un test de corrección. Sirve para poder
confiar en el MILP cuando la instancia ya es demasiado grande para enumerarla.
"""

import itertools
import random

from optimizador import Tienda, Oferta, optimizar, _cent
from ejemplo import TIENDAS, OFERTAS, ARTICULOS, DEMANDA


def coste_total(asignacion: dict[str, str], tiendas: list[Tienda],
                precio: dict[tuple[str, str], int]) -> int:
    """Coste en céntimos de una asignación concreta artículo → tienda."""
    por_tienda = {t.id: t for t in tiendas}
    subtotales: dict[str, int] = {}
    for art, tid in asignacion.items():
        subtotales[tid] = subtotales.get(tid, 0) + precio[(art, tid)]

    total = 0
    for tid, sub in subtotales.items():
        t = por_tienda[tid]
        total += sub
        gratis = (t.envio_gratis_desde is not None
                  and sub >= _cent(t.envio_gratis_desde))
        if not gratis:
            total += _cent(t.porte)
    return total


def fuerza_bruta(articulos, tiendas, ofertas):
    precio = {(o.articulo_id, o.tienda_id): _cent(o.precio) for o in ofertas}
    opciones = {
        a: [t.id for t in tiendas if (a, t.id) in precio] for a in articulos
    }
    combos = itertools.product(*(opciones[a] for a in articulos))
    mejor, mejor_coste = None, None
    n = 0
    for combo in combos:
        n += 1
        asig = dict(zip(articulos, combo))
        c = coste_total(asig, tiendas, precio)
        if mejor_coste is None or c < mejor_coste:
            mejor, mejor_coste = asig, c
    return mejor_coste, n


# ─────────────────────────────────────────────────────────────────────────────
# Packs: fuerza bruta por cantidad de cada oferta, no por asignación 1-a-1
# ─────────────────────────────────────────────────────────────────────────────

def fuerza_bruta_packs(demanda, tiendas, ofertas):
    """Enumera cuántos packs de CADA oferta comprar (0, 1, 2...), se queda
    con las combinaciones que cubren la demanda de cada producto, y calcula
    el coste real (packs + portes) de la más barata.

    El rango de cada oferta va de 0 a demanda(producto)//pack + 2: nunca
    hace falta más que eso, ni comprando esa oferta sola, y el +2 es margen
    para no cortar por casos de redondeo en instancias tan pequeñas.
    """
    por_tienda = {t.id: t for t in tiendas}
    rangos = [
        range(0, demanda[o.articulo_id] // o.unidades_por_pack + 2) for o in ofertas
    ]

    mejor_coste = None
    n = 0
    for combo in itertools.product(*rangos):
        n += 1
        unidades = {p: 0 for p in demanda}
        for cantidad, o in zip(combo, ofertas):
            unidades[o.articulo_id] += cantidad * o.unidades_por_pack
        if any(unidades[p] < demanda[p] for p in demanda):
            continue

        subtotales: dict[str, int] = {}
        for cantidad, o in zip(combo, ofertas):
            if cantidad:
                subtotales[o.tienda_id] = (
                    subtotales.get(o.tienda_id, 0) + _cent(o.precio) * cantidad
                )

        total = 0
        for tid, sub in subtotales.items():
            t = por_tienda[tid]
            total += sub
            gratis = (t.envio_gratis_desde is not None
                      and sub >= _cent(t.envio_gratis_desde))
            if not gratis:
                total += _cent(t.porte)

        if mejor_coste is None or total < mejor_coste:
            mejor_coste = total
    return mejor_coste, n


def caso_aleatorio_packs(semilla: int):
    """Instancia pequeña al azar con productos, varias ofertas por (producto,
    tienda) con distinto tamaño de pack, y reparto libre entre tiendas.
    """
    rnd = random.Random(semilla)
    n_prod = rnd.randint(1, 2)
    n_tie = rnd.randint(2, 3)
    productos = [f"p{i}" for i in range(n_prod)]
    demanda = {p: rnd.randint(1, 4) for p in productos}

    tiendas = []
    for j in range(n_tie):
        umbral = rnd.choice([None, 10.0, 20.0])
        tiendas.append(Tienda(f"t{j}", f"Tienda {j}",
                              porte=rnd.choice([0.0, 2.5, 4.0]),
                              envio_gratis_desde=umbral))

    ofertas = []
    for p in productos:
        disp = rnd.sample(tiendas, rnd.randint(1, n_tie))
        for t in disp:
            pack = rnd.choice([1, 2, 3])
            precio_unidad = round(rnd.uniform(2, 10), 2)
            # el pack a veces sale más barato por unidad, a veces no - el
            # optimizador tiene que acertar en los dos casos
            precio_pack = round(precio_unidad * pack * rnd.uniform(0.8, 1.05), 2)
            ofertas.append(Oferta(p, t.id, precio_pack, pack))

    return demanda, tiendas, ofertas


def caso_aleatorio(semilla: int):
    """Genera una instancia pequeña al azar para castigar el modelo."""
    rnd = random.Random(semilla)
    n_art = rnd.randint(3, 6)
    n_tie = rnd.randint(2, 4)
    articulos = [f"a{i}" for i in range(n_art)]
    tiendas = []
    for j in range(n_tie):
        umbral = rnd.choice([None, 15.0, 25.0, 40.0])
        tiendas.append(Tienda(f"t{j}", f"Tienda {j}",
                              porte=rnd.choice([0.0, 2.95, 3.95, 5.5]),
                              envio_gratis_desde=umbral))
    ofertas = []
    for a in articulos:
        # cada artículo disponible en al menos una tienda
        disp = rnd.sample(tiendas, rnd.randint(1, n_tie))
        for t in disp:
            ofertas.append(Oferta(a, t.id, round(rnd.uniform(4, 45), 2)))
    return articulos, tiendas, ofertas


def main():
    print("── Caso de los libros de texto (sin packs, demanda 1 cada uno) ──")
    bruto, n = fuerza_bruta(ARTICULOS, TIENDAS, OFERTAS)
    milp = optimizar(DEMANDA, TIENDAS, OFERTAS)
    print(f"combinaciones evaluadas: {n}")
    print(f"fuerza bruta: {bruto/100:.2f} €")
    print(f"MILP:         {milp.total:.2f} €")
    assert abs(bruto / 100 - milp.total) < 0.005, "NO COINCIDE"
    print("coinciden ✓\n")

    print("── 40 instancias aleatorias (sin packs) ──")
    fallos = 0
    for s in range(40):
        arts, tis, ofs = caso_aleatorio(s)
        demanda = {a: 1 for a in arts}
        b, _ = fuerza_bruta(arts, tis, ofs)
        m = optimizar(demanda, tis, ofs)
        if abs(b / 100 - m.total) >= 0.005:
            fallos += 1
            print(f"  semilla {s}: bruta {b/100:.2f} vs MILP {m.total:.2f}  ✗")
    if fallos == 0:
        print("40/40 coinciden ✓")
    else:
        print(f"{fallos} fallos ✗")
        raise SystemExit(1)

    print("\n── 30 instancias aleatorias CON packs y reparto entre tiendas ──")
    fallos_packs = 0
    for s in range(30):
        demanda, tis, ofs = caso_aleatorio_packs(s)
        b, n = fuerza_bruta_packs(demanda, tis, ofs)
        m = optimizar(demanda, tis, ofs)
        if abs(b / 100 - m.total) >= 0.005:
            fallos_packs += 1
            print(
                f"  semilla {s}: bruta {b/100:.2f} vs MILP {m.total:.2f}  ✗  "
                f"(demanda={demanda})"
            )
    if fallos_packs == 0:
        print("30/30 coinciden ✓")
    else:
        print(f"{fallos_packs} fallos ✗")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
