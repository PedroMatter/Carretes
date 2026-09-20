"""
Caso de ejemplo: una lista de libros de texto de 1º de la ESO.

Los precios y las condiciones de envío son INVENTADOS, pero con la forma que
tienen de verdad: diferencias de precio por título entre tiendas, portes de
3 a 5 euros, y umbrales de envío gratis entre 19 y 50 euros.

El objetivo del ejemplo es enseñar la diferencia entre lo que hace un
comparador (cada libro donde esté más barato) y lo que hace el optimizador
(la combinación que minimiza el total puesto en casa).
"""

from optimizador import Tienda, Oferta, optimizar, ingenuo

TIENDAS = [
    Tienda("cdl",  "Casa del Libro",   porte=3.95, envio_gratis_desde=19.0),
    Tienda("eci",  "El Corte Inglés",  porte=4.90, envio_gratis_desde=50.0),
    Tienda("ama",  "Amazon",           porte=0.00, envio_gratis_desde=0.0),
    Tienda("imo",  "Imosver",          porte=3.50, envio_gratis_desde=45.0),
    Tienda("agp",  "Agapea",           porte=4.50, envio_gratis_desde=None),
]

# (artículo, tienda, precio). Un artículo que no aparece en una tienda es que
# esa tienda no lo tiene.
OFERTAS_BRUTAS = [
    # Lengua Castellana
    ("lengua",    "cdl", 36.10), ("lengua",    "eci", 34.20), ("lengua", "ama", 35.50),
    ("lengua",    "imo", 33.80), ("lengua",    "agp", 34.95),
    # Matemáticas
    ("matematicas", "cdl", 38.45), ("matematicas", "eci", 37.90),
    ("matematicas", "ama", 36.20), ("matematicas", "imo", 38.10),
    # Biología y Geología
    ("biologia",  "cdl", 35.60), ("biologia",  "eci", 33.95), ("biologia", "imo", 34.40),
    ("biologia",  "agp", 35.10),
    # Geografía e Historia
    ("historia",  "cdl", 37.20), ("historia",  "ama", 36.85), ("historia", "imo", 35.90),
    # Inglés (student's book)
    ("ingles",    "cdl", 32.40), ("ingles",    "eci", 31.75), ("ingles", "ama", 33.10),
    ("ingles",    "agp", 30.95),
    # Educación Plástica
    ("plastica",  "eci", 28.50), ("plastica",  "imo", 27.90), ("plastica", "agp", 29.20),
    # Tecnología
    ("tecnologia", "cdl", 31.15), ("tecnologia", "ama", 30.40), ("tecnologia", "imo", 31.80),
    # Religión / Valores
    ("valores",   "cdl", 24.30), ("valores",   "agp", 23.85),
]

ARTICULOS = sorted({a for a, _, _ in OFERTAS_BRUTAS})
OFERTAS = [Oferta(a, t, p) for a, t, p in OFERTAS_BRUTAS]
DEMANDA = {a: 1 for a in ARTICULOS}  # un libro de cada, no hay packs de libros

NOMBRES = {
    "lengua": "Lengua Castellana", "matematicas": "Matemáticas",
    "biologia": "Biología y Geología", "historia": "Geografía e Historia",
    "ingles": "Inglés", "plastica": "Educación Plástica",
    "tecnologia": "Tecnología", "valores": "Valores Éticos",
}


def main():
    print("=" * 66)
    print(f"LISTA: {len(ARTICULOS)} libros · {len(TIENDAS)} tiendas")
    print("=" * 66)

    base = ingenuo(DEMANDA, TIENDAS, OFERTAS)
    print("\n── Lo que hace un comparador (cada libro donde está más barato) ──\n")
    print(base.resumen())

    opt = optimizar(DEMANDA, TIENDAS, OFERTAS)
    print("\n── Lo que hace el optimizador (cesta completa con portes) ──\n")
    print(opt.resumen())

    ahorro = round(base.total - opt.total, 2)
    pct = (ahorro / base.total * 100) if base.total else 0
    print(f"\n>> Diferencia: {ahorro:.2f} €  ({pct:.1f} %)")
    print(f">> Paquetes: {len(base.pedidos)} → {len(opt.pedidos)}")

    # Muchas veces el óptimo puro reparte en más pedidos de los que uno quiere
    # recibir. Esta es la versión "quiero como mucho 2 paquetes".
    lim = optimizar(DEMANDA, TIENDAS, OFERTAS, max_tiendas=2)
    print("\n── Óptimo con un máximo de 2 pedidos ──\n")
    print(lim.resumen())
    print(f"\n>> Cuesta {lim.total - opt.total:+.2f} € frente al óptimo libre, "
          f"a cambio de {len(opt.pedidos) - len(lim.pedidos)} paquete(s) menos.")


if __name__ == "__main__":
    main()
