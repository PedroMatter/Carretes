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
    precio: float               # precio del pack entero, no por unidad
    unidades_por_pack: int = 1  # 1 = suelto; por defecto, para no romper código viejo


@dataclass
class LineaPlan:
    articulo_id: str
    tienda_id: str
    unidades_por_pack: int
    cantidad_packs: int
    precio_pack: float

    @property
    def unidades(self) -> int:
        return self.unidades_por_pack * self.cantidad_packs

    @property
    def subtotal(self) -> float:
        return round(self.precio_pack * self.cantidad_packs, 2)


@dataclass
class PedidoTienda:
    tienda_id: str
    nombre: str
    lineas: list[LineaPlan]
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
    sobras: dict[str, int] = field(default_factory=dict)  # producto -> unidades de más

    def resumen(self) -> str:
        if self.sin_stock:
            faltan = ", ".join(self.sin_stock)
            cabecera = f"Sin disponibilidad en ninguna tienda: {faltan}\n\n"
        else:
            cabecera = ""
        lineas = [cabecera.rstrip("\n")] if cabecera else []
        for p in self.pedidos:
            envio = "envío gratis" if p.envio_gratis else f"porte {p.porte:.2f} €"
            detalle = ", ".join(
                f"{l.cantidad_packs}×{l.articulo_id}"
                + (f" (pack de {l.unidades_por_pack})" if l.unidades_por_pack > 1 else "")
                for l in p.lineas
            )
            lineas.append(
                f"{p.nombre}: {detalle} · "
                f"{p.subtotal:.2f} € + {envio} = {p.total:.2f} €"
            )
        lineas.append(
            f"TOTAL {self.total:.2f} €  "
            f"(artículos {self.subtotal_articulos:.2f} € + portes {self.total_portes:.2f} €)"
        )
        if self.sobras:
            extra = ", ".join(f"{n} ud. de más de {a}" for a, n in self.sobras.items())
            lineas.append(f"Sobra: {extra}")
        return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# Núcleo: resolución exacta
# ─────────────────────────────────────────────────────────────────────────────

def _cent(x: float) -> int:
    """Euros a céntimos, redondeando al entero más cercano."""
    return int(round(x * 100))


def optimizar(
    demanda: dict[str, int],
    tiendas: list[Tienda],
    ofertas: list[Oferta],
    max_tiendas: Optional[int] = None,
) -> Plan:
    """
    Decide cuántos packs de cada oferta comprar, y en qué tiendas, para cubrir
    `demanda` (unidades pedidas de cada producto) al mínimo coste puesto en
    casa.

    Un mismo producto puede tener varias ofertas en la misma tienda (suelto,
    pack de 5, pack de 10...) y la demanda de un producto puede repartirse
    entre varias tiendas: no se fuerza a comprarlo entero en una sola. Contra
    eso ya está `max_tiendas`, que limita la fragmentación de la cesta
    completa - una restricción aparte solo para esto resolvería el mismo
    problema dos veces.

    Comprar de más está permitido (un pack de 5 cuando hacen falta 3, si sale
    más barato que 3 sueltas): la cobertura exige "como mínimo la demanda",
    no "exactamente". El plan resultante dice si sobra algo.

    `max_tiendas` limita de cuántas tiendas distintas se puede comprar. Es útil
    porque el óptimo puro a veces reparte en cinco pedidos para ahorrar 40
    céntimos, y recibir cinco paquetes en cinco días distintos no compensa.
    """
    por_tienda = {t.id: t for t in tiendas}
    productos = list(demanda.keys())

    # Un producto que nadie vende se aparta: no puede entrar en el modelo.
    disponibles, sin_stock = [], []
    for p in productos:
        if any(o.articulo_id == p for o in ofertas):
            disponibles.append(p)
        else:
            sin_stock.append(p)

    if not disponibles:
        return Plan(pedidos=[], total=0.0, subtotal_articulos=0.0,
                    total_portes=0.0, sin_stock=sin_stock)

    ofertas_disp = [o for o in ofertas if o.articulo_id in disponibles]
    precio_cent = {idx: _cent(o.precio) for idx, o in enumerate(ofertas_disp)}

    prob = pulp.LpProblem("cesta", pulp.LpMinimize)

    # x[idx] = cuántos packs de la oferta idx se compran. Cota superior
    # generosa: nunca hace falta más que demanda(producto) packs, incluso
    # comprándolo entero en packs de 1 unidad.
    x = {
        idx: pulp.LpVariable(f"x_{idx}", lowBound=0,
                              upBound=demanda[o.articulo_id], cat="Integer")
        for idx, o in enumerate(ofertas_disp)
    }
    # y[t] = 1 si se hace pedido a la tienda t (y por tanto se paga su porte)
    y = {t.id: pulp.LpVariable(f"y_{t.id}", cat="Binary") for t in tiendas}
    # f[t] = 1 si ese pedido alcanza el umbral de envío gratis
    f = {t.id: pulp.LpVariable(f"f_{t.id}", cat="Binary") for t in tiendas}

    # Objetivo: precio de los packs comprados + portes de las tiendas que no
    # llegan al umbral. Si f[t]=1 el porte se cancela.
    prob += (
        pulp.lpSum(precio_cent[idx] * v for idx, v in x.items())
        + pulp.lpSum(_cent(por_tienda[t].porte) * (y[t] - f[t]) for t in y)
    )

    # Cobertura: las unidades compradas de un producto (sumando todas sus
    # ofertas, de cualquier tienda) cubren como mínimo la demanda.
    for p in disponibles:
        prob += pulp.lpSum(
            o.unidades_por_pack * x[idx]
            for idx, o in enumerate(ofertas_disp) if o.articulo_id == p
        ) >= demanda[p]

    for t in tiendas:
        idx_tienda = [idx for idx, o in enumerate(ofertas_disp) if o.tienda_id == t.id]
        subtotal_t = pulp.lpSum(precio_cent[idx] * x[idx] for idx in idx_tienda)

        # Si compras algo en t, la tienda está "usada". La cota superior de
        # cada x[idx] (demanda del producto) hace de "M" en esta condición.
        for idx in idx_tienda:
            o = ofertas_disp[idx]
            prob += x[idx] <= demanda[o.articulo_id] * y[t.id]

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
    unidades_compradas = {p: 0 for p in disponibles}
    for idx, o in enumerate(ofertas_disp):
        cantidad = round(x[idx].value() or 0)
        if cantidad <= 0:
            continue
        compras.setdefault(o.tienda_id, []).append(
            LineaPlan(o.articulo_id, o.tienda_id, o.unidades_por_pack, cantidad, o.precio)
        )
        unidades_compradas[o.articulo_id] += o.unidades_por_pack * cantidad

    sobras = {
        p: unidades_compradas[p] - demanda[p]
        for p in disponibles if unidades_compradas[p] > demanda[p]
    }

    pedidos: list[PedidoTienda] = []
    for tid, lineas in compras.items():
        t = por_tienda[tid]
        subtotal = round(sum(l.subtotal for l in lineas), 2)
        gratis = (t.envio_gratis_desde is not None
                  and subtotal >= t.envio_gratis_desde - 1e-9)
        pedidos.append(PedidoTienda(
            tienda_id=tid,
            nombre=t.nombre,
            lineas=lineas,
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
        sobras=sobras,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Comparación: lo que haría un comparador normal
# ─────────────────────────────────────────────────────────────────────────────

def ingenuo(
    demanda: dict[str, int],
    tiendas: list[Tienda],
    ofertas: list[Oferta],
) -> Plan:
    """
    Lo que hace un comparador normal: para cada producto, la oferta con mejor
    precio por unidad, sin mirar portes ni umbrales, y sin repartir entre
    tiendas - todo lo que haga falta de ese producto sale de una sola oferta,
    aunque eso obligue a comprar de más si el pack no encaja justo. Sirve de
    línea base para medir cuánto aporta de verdad optimizar la cesta entera.
    """
    por_tienda = {t.id: t for t in tiendas}

    compras: dict[str, list[LineaPlan]] = {}
    sin_stock = []
    sobras: dict[str, int] = {}

    for p, cantidad in demanda.items():
        cands = [o for o in ofertas if o.articulo_id == p]
        if not cands:
            sin_stock.append(p)
            continue

        mejor = min(cands, key=lambda o: o.precio / o.unidades_por_pack)
        n_packs = -(-cantidad // mejor.unidades_por_pack)  # división hacia arriba
        compras.setdefault(mejor.tienda_id, []).append(
            LineaPlan(p, mejor.tienda_id, mejor.unidades_por_pack, n_packs, mejor.precio)
        )
        unidades = n_packs * mejor.unidades_por_pack
        if unidades > cantidad:
            sobras[p] = unidades - cantidad

    pedidos = []
    for tid, lineas in compras.items():
        t = por_tienda[tid]
        subtotal = round(sum(l.subtotal for l in lineas), 2)
        gratis = (t.envio_gratis_desde is not None
                  and subtotal >= t.envio_gratis_desde - 1e-9)
        pedidos.append(PedidoTienda(
            tienda_id=tid, nombre=t.nombre,
            lineas=lineas,
            subtotal=subtotal,
            porte=0.0 if gratis else t.porte,
            envio_gratis=gratis,
        ))

    pedidos.sort(key=lambda p: -p.total)
    subtotal_art = round(sum(p.subtotal for p in pedidos), 2)
    total_portes = round(sum(p.porte for p in pedidos), 2)
    return Plan(pedidos, round(subtotal_art + total_portes, 2),
                subtotal_art, total_portes, sin_stock, sobras)
