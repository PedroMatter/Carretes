"""
Optimizador de cesta multi-tienda.

El problema: tienes una lista de artículos y varias tiendas que los venden a
distintos precios. Los comparadores al uso te dicen, artículo por artículo,
dónde está cada uno más barato. Eso NO da el total más barato, porque cada
tienda de la que compras te cobra su porte, y muchas lo perdonan a partir de
cierto importe.

Comprar doce artículos en seis tiendas distintas son seis portes. A veces sale
mejor concentrar todo en dos tiendas y cruzar sus umbrales de envío gratis.

Decidir eso es un problema de optimización combinatoria, no una comparación.
Aquí se resuelve de forma exacta con programación lineal entera mixta (MILP).

Internamente todo se calcula en céntimos enteros para no arrastrar errores
de coma flotante en las restricciones.
"""

from dataclasses import dataclass, field
from typing import Optional
import pulp


# ─────────────────────────────────────────────────────────────────────────────
# Modelo de datos
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Tienda:
    id: str
    nombre: str
    porte: float                             # coste de envío en euros
    envio_gratis_desde: Optional[float] = None   # umbral en euros; None = nunca


@dataclass(frozen=True)
class Oferta:
    articulo_id: str
    tienda_id: str
    precio: float


@dataclass
class LineaPlan:
    articulo_id: str
    tienda_id: str
    precio: float


@dataclass
class PedidoTienda:
    tienda_id: str
    nombre: str
    articulos: list[str]
    subtotal: float
    porte: float
    envio_gratis: bool

    @property
    def total(self) -> float:
        return round(self.subtotal + self.porte, 2)


@dataclass
class Plan:
    pedidos: list[PedidoTienda]
    total: float
    subtotal_articulos: float
    total_portes: float
    sin_stock: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        if self.sin_stock:
            faltan = ", ".join(self.sin_stock)
            cabecera = f"Sin disponibilidad en ninguna tienda: {faltan}\n\n"
        else:
            cabecera = ""
        lineas = [cabecera.rstrip("\n")] if cabecera else []
        for p in self.pedidos:
            envio = "envío gratis" if p.envio_gratis else f"porte {p.porte:.2f} €"
            lineas.append(
                f"{p.nombre}: {len(p.articulos)} art. · "
                f"{p.subtotal:.2f} € + {envio} = {p.total:.2f} €"
            )
        lineas.append(
            f"TOTAL {self.total:.2f} €  "
            f"(artículos {self.subtotal_articulos:.2f} € + portes {self.total_portes:.2f} €)"
        )
        return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# Núcleo: resolución exacta
# ─────────────────────────────────────────────────────────────────────────────

def _cent(x: float) -> int:
    """Euros a céntimos, redondeando al entero más cercano."""
    return int(round(x * 100))


def optimizar(
    articulos: list[str],
    tiendas: list[Tienda],
    ofertas: list[Oferta],
    max_tiendas: Optional[int] = None,
) -> Plan:
    """
    Reparte `articulos` entre `tiendas` minimizando el total puesto en casa.

    `max_tiendas` limita de cuántas tiendas distintas se puede comprar. Es útil
    porque el óptimo puro a veces reparte en cinco pedidos para ahorrar 40
    céntimos, y recibir cinco paquetes en cinco días distintos no compensa.
    """
    precio = {(o.articulo_id, o.tienda_id): _cent(o.precio) for o in ofertas}
    por_tienda = {t.id: t for t in tiendas}

    # Un artículo que nadie vende se aparta: no puede entrar en el modelo.
    disponibles, sin_stock = [], []
    for a in articulos:
        if any((a, t.id) in precio for t in tiendas):
            disponibles.append(a)
        else:
            sin_stock.append(a)

    if not disponibles:
        return Plan(pedidos=[], total=0.0, subtotal_articulos=0.0,
                    total_portes=0.0, sin_stock=sin_stock)

    prob = pulp.LpProblem("cesta", pulp.LpMinimize)

    # x[a,t] = 1 si el artículo a se compra en la tienda t
    x = {
        (a, t.id): pulp.LpVariable(f"x_{a}_{t.id}", cat="Binary")
        for a in disponibles for t in tiendas if (a, t.id) in precio
    }
    # y[t] = 1 si se hace pedido a la tienda t (y por tanto se paga su porte)
    y = {t.id: pulp.LpVariable(f"y_{t.id}", cat="Binary") for t in tiendas}
    # f[t] = 1 si ese pedido alcanza el umbral de envío gratis
    f = {t.id: pulp.LpVariable(f"f_{t.id}", cat="Binary") for t in tiendas}

    # Objetivo: precio de los artículos + portes de las tiendas que no llegan
    # al umbral. Si f[t]=1 el porte se cancela.
    prob += (
        pulp.lpSum(precio[k] * v for k, v in x.items())
        + pulp.lpSum(_cent(por_tienda[t].porte) * (y[t] - f[t]) for t in y)
    )

    # Cada artículo se compra exactamente una vez.
    for a in disponibles:
        prob += pulp.lpSum(x[(a, t.id)] for t in tiendas if (a, t.id) in precio) == 1

    for t in tiendas:
        subtotal_t = pulp.lpSum(
            precio[(a, t.id)] * x[(a, t.id)]
            for a in disponibles if (a, t.id) in precio
        )
        # Si compras algo en t, la tienda está "usada".
        for a in disponibles:
            if (a, t.id) in x:
                prob += x[(a, t.id)] <= y[t.id]
        # Sólo puedes reclamar envío gratis si hay pedido...
        prob += f[t.id] <= y[t.id]
        # ...y si el subtotal alcanza el umbral. Sin umbral, nunca es gratis.
        if t.envio_gratis_desde is None:
            prob += f[t.id] == 0
        else:
            prob += subtotal_t >= _cent(t.envio_gratis_desde) * f[t.id]

    if max_tiendas is not None:
        prob += pulp.lpSum(y.values()) <= max_tiendas

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    if pulp.LpStatus[prob.status] != "Optimal":
        raise RuntimeError(f"No se encontró solución óptima: {pulp.LpStatus[prob.status]}")

    # ── Reconstruir el plan a partir de la solución ──────────────────────────
    compras: dict[str, list[LineaPlan]] = {}
    for (a, tid), var in x.items():
        if var.value() and var.value() > 0.5:
            compras.setdefault(tid, []).append(
                LineaPlan(a, tid, precio[(a, tid)] / 100)
            )

    pedidos: list[PedidoTienda] = []
    for tid, lineas in compras.items():
        t = por_tienda[tid]
        subtotal = round(sum(l.precio for l in lineas), 2)
        gratis = (t.envio_gratis_desde is not None
                  and subtotal >= t.envio_gratis_desde - 1e-9)
        pedidos.append(PedidoTienda(
            tienda_id=tid,
            nombre=t.nombre,
            articulos=[l.articulo_id for l in lineas],
            subtotal=subtotal,
            porte=0.0 if gratis else t.porte,
            envio_gratis=gratis,
        ))

    pedidos.sort(key=lambda p: -p.total)
    subtotal_art = round(sum(p.subtotal for p in pedidos), 2)
    total_portes = round(sum(p.porte for p in pedidos), 2)

    return Plan(
        pedidos=pedidos,
        total=round(subtotal_art + total_portes, 2),
        subtotal_articulos=subtotal_art,
        total_portes=total_portes,
        sin_stock=sin_stock,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Comparación: lo que haría un comparador normal
# ─────────────────────────────────────────────────────────────────────────────

def ingenuo(
    articulos: list[str],
    tiendas: list[Tienda],
    ofertas: list[Oferta],
) -> Plan:
    """
    Lo que hacen los comparadores: cada artículo en la tienda donde está más
    barato, sin mirar portes ni umbrales. Sirve de línea base para medir cuánto
    aporta de verdad optimizar la cesta entera.
    """
    precio = {(o.articulo_id, o.tienda_id): _cent(o.precio) for o in ofertas}
    por_tienda = {t.id: t for t in tiendas}

    compras: dict[str, list[tuple[str, int]]] = {}
    sin_stock = []
    for a in articulos:
        cands = [(precio[(a, t.id)], t.id) for t in tiendas if (a, t.id) in precio]
        if not cands:
            sin_stock.append(a)
            continue
        p, tid = min(cands)
        compras.setdefault(tid, []).append((a, p))

    pedidos = []
    for tid, lineas in compras.items():
        t = por_tienda[tid]
        subtotal = round(sum(p for _, p in lineas) / 100, 2)
        gratis = (t.envio_gratis_desde is not None
                  and subtotal >= t.envio_gratis_desde - 1e-9)
        pedidos.append(PedidoTienda(
            tienda_id=tid, nombre=t.nombre,
            articulos=[a for a, _ in lineas],
            subtotal=subtotal,
            porte=0.0 if gratis else t.porte,
            envio_gratis=gratis,
        ))

    pedidos.sort(key=lambda p: -p.total)
    subtotal_art = round(sum(p.subtotal for p in pedidos), 2)
    total_portes = round(sum(p.porte for p in pedidos), 2)
    return Plan(pedidos, round(subtotal_art + total_portes, 2),
                subtotal_art, total_portes, sin_stock)
