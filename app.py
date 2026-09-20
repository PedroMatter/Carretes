import streamlit as st

import comparador

st.title("correcarrete")
st.caption("Comparador de precios de carretes fotográficos en España.")

texto = st.text_input("Busca una película", placeholder="Ej. Portra 400, HP5, Gold 200...")

if not texto:
    st.caption(f"{len(comparador.buscar_peliculas(''))} películas en el catálogo. Escribe arriba para buscar.")

peliculas = comparador.buscar_peliculas(texto) if texto else []

if texto and not peliculas:
    st.write("No hay ninguna película en el catálogo que coincida exactamente con eso. ¿Quizás una de estas?")
    for sugerida in comparador.sugerir_peliculas(texto):
        st.markdown(f"- {sugerida['marca']} {sugerida['nombre']}")

for pelicula in peliculas:
    productos = comparador.productos_de_pelicula(pelicula["id"])

    st.subheader(f"{pelicula['marca']} {pelicula['nombre']}")
    st.caption(f"ISO {pelicula['iso']} · {pelicula['proceso']}")

    for producto in productos:
        etiqueta = producto["formato"]
        if producto["exposiciones"] is not None:
            etiqueta += f" · {producto['exposiciones']} exp"

        ofertas = comparador.ofertas_de_producto(producto["id"])

        st.markdown(f"**{etiqueta}**")

        if not ofertas:
            st.write("Sin precios capturados todavía.")
            continue

        for oferta in ofertas:
            precio_euros = oferta["precio_centimos"] / 100
            precio_unidad_euros = oferta["precio_por_unidad_centimos"] / 100

            if oferta["unidades_por_pack"] > 1:
                precio_texto = (
                    f"{precio_euros:.2f} € (pack de {oferta['unidades_por_pack']}, "
                    f"{precio_unidad_euros:.2f} €/ud)"
                )
            else:
                precio_texto = f"{precio_euros:.2f} €"

            if oferta["disponible"]:
                st.markdown(
                    f"- **{precio_texto}** — {oferta['tienda']} · "
                    f"[ver anuncio]({oferta['url']}) · visto {oferta['visto']}"
                )
            else:
                st.markdown(
                    f"- ~~{precio_texto}~~ — {oferta['tienda']} · agotado · "
                    f"[ver anuncio]({oferta['url']}) · visto {oferta['visto']}"
                )

    st.divider()
