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
from ejemplo import TIENDAS, OFERTAS, ARTICULOS


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
    print("── Caso de los libros de texto ──")
    bruto, n = fuerza_bruta(ARTICULOS, TIENDAS, OFERTAS)
    milp = optimizar(ARTICULOS, TIENDAS, OFERTAS)
    print(f"combinaciones evaluadas: {n}")
    print(f"fuerza bruta: {bruto/100:.2f} €")
    print(f"MILP:         {milp.total:.2f} €")
    assert abs(bruto / 100 - milp.total) < 0.005, "NO COINCIDE"
    print("coinciden ✓\n")

    print("── 40 instancias aleatorias ──")
    fallos = 0
    for s in range(40):
        arts, tis, ofs = caso_aleatorio(s)
        b, _ = fuerza_bruta(arts, tis, ofs)
        m = optimizar(arts, tis, ofs)
        if abs(b / 100 - m.total) >= 0.005:
            fallos += 1
            print(f"  semilla {s}: bruta {b/100:.2f} vs MILP {m.total:.2f}  ✗")
    if fallos == 0:
        print("40/40 coinciden ✓")
    else:
        print(f"{fallos} fallos ✗")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
