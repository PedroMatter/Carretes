# carretes.es

Comparador de precios de película fotográfica para España. Le dices qué
carretes quieres y cuántos, y te dice **en qué combinación de tiendas sale más
barato puesto en tu casa**, contando portes y umbrales de envío gratis.

No es un comparador de anuncios: es un optimizador de cesta.

---

## Lo que hace distinto a esto de un comparador normal

Un comparador te enseña, producto a producto, dónde está más barato. Eso **casi
nunca da el total más barato**, por dos motivos:

1. **Los packs.** Portra 400 en pack de 5 en FotoRuano sale a 24,00 €/carrete.
   Suelto en FotoCarrete, a 18,80 €. El pack es más caro por unidad. Comparar
   precios de anuncio te hace elegir mal.
2. **Los portes.** Comprar cada carrete donde está más barato son cinco tiendas
   y cinco portes. A veces sale mejor concentrar y cruzar un umbral de envío
   gratis.

Todo lo que se construya aquí tiene que preservar esas dos verdades.

---

## Principios que no se negocian

**1. Nunca presentar un dato sin verificar como si fuera cierto.**
Cada precio lleva cuándo se vio. Cada porte lleva si está confirmado en la web
de la tienda o es una estimación. La interfaz lo enseña. Si no sabemos el
porte, no es cero: es desconocido, y se dice.

**2. El emparejamiento va a mano, con cola de revisión.**
Nada de *fuzzy matching* automático. Un emparejado difuso equivocado muestra el
precio de un producto que no es, el usuario no se entera, y destruye la
confianza. Lo que no case con certeza va a una cola que se vacía a mano.

**3. Las observaciones se añaden, nunca se sobrescriben.**
Cada pasada del recolector escribe filas nuevas con su fecha. El precio actual
es la última observación. Así el histórico sale gratis, y el histórico no se
puede recuperar hacia atrás si no se guardó.

**4. Un adaptador roto no puede tumbar la web.**
Cada tienda va aislada, con sus propios tests. Si una cambia el HTML, esa
tienda se marca como obsoleta y las demás siguen funcionando. Y tiene que
avisar: acabar con datos de hace tres meses sin enterarse es el fracaso típico
de estos proyectos.

**5. No machacar a las tiendas.**
Son negocios pequeños de un mundillo donde todos se conocen. Respetar
robots.txt, identificar el bot, ir despacio. Antes de escribir un scraper,
mirar si ya hay JSON-LD en la ficha, feed de Google Shopping o sitemap con
datos: es más estable y no molesta.

---

## Modelo de datos: qué es un producto

Esta es la columna vertebral. Está decidido y no se cambia sin motivo fuerte.

```
pelicula      el stock/emulsión: marca, nombre, iso, proceso (C-41 / B&N / E-6 / ECN-2)
producto      lo que se compra: pelicula + formato + exposiciones      ← lo canónico
anuncio       lo que vende una tienda: producto + tienda + unidades_por_pack + url
observacion   un precio en un momento: anuncio + precio + disponible + capturado_en
```

**Decisiones cerradas:**

- **Las exposiciones forman parte de la identidad del producto.** Gold 200 de
  24 y Gold 200 de 36 son productos distintos. Motivo: el de 24 cuesta un 6%
  menos por un 33% menos de fotos (12,75 € → 0,53 €/foto frente a 13,50 € →
  0,38 €/foto). Si se unifican, la web diría «Gold 200 desde 12,75 €» y alguien
  compraría el peor creyendo que es el barato.
- **Pero van enlazados por stock**, para que la ficha pueda decir «también hay
  de 24 exp, a 0,53 €/foto frente a 0,38».
- **El 120 no tiene exposiciones** (depende del formato de la cámara: 12 en
  6x6, 10 en 6x7, 16 en 645). Campo nulo, y no se calcula precio por foto.
- **El tamaño del pack es del anuncio, no del producto.** Portra suelto y
  Portra en pack de 5 son el mismo producto en dos anuncios.

---

## Alcance de la v1

**Dentro:** carretes frescos, de marcas conocidas, en 35mm y 120.

**Fuera:** película caducada, bobina a granel, instantánea (Instax, Polaroid),
gran formato, cine (Super 8, 16mm), y marcas propias de tienda tipo 1Hundred o
4Hundred de Revelab — no sabemos con certeza qué emulsión llevan y afirmarlo
sería mentir.

**Fuera también, de momento:** revelado y escaneo. Y las tiendas físicas: no
publican precios, así que no hay dato que capturar. Si se mencionan, se dice
claramente que no tenemos sus precios, en vez de fingir que sí.

---

## Orden de construcción

1. **Esquema y catálogo canónico.** Sembrar a mano los 40-50 stocks que
   importan en España, en sus formatos. Se hace a mano y con cuidado.
2. **Una tienda de punta a punta.** Traer, parsear, emparejar, guardar
   observaciones. *Hecho cuando lleva siete días corriendo solo.*
3. **La segunda tienda**, que es cuando aparecen los problemas de
   emparejamiento de verdad. *Hecho cuando añadir la tercera cuesta una hora.*
4. **El optimizador** de cesta con packs y umbrales.
5. **La web.**
6. **Frescura y avisos** cuando un adaptador se rompe.
7. **Más tiendas.**

No adelantar pasos. Si el paso 2 no aguanta, lo demás da igual.

---

## Datos reales ya capturados (19/09/2026)

Precios vistos ese día. Sirven de semilla y de test.

| Tienda | Portra 400 35mm 36exp | Envío |
| --- | --- | --- |
| FotoRuano Pro | pack 5 a 120,00 € → 24,00 €/ud | gratis desde 199 € · **confirmado** |
| Revelab | 19,50 € suelto | sin publicar · **estimado** |
| FotoCarrete | 18,80 € suelto | sin publicar · **estimado** |
| Casanova Foto | no listado | sin publicar · **estimado** |

Otros precios vistos: HP5+ 120 a 9,57 € (FotoCarrete), 9,50 € (Casanova),
10,80 € (Revelab). Kentmere 200 35mm a 8,91 € (FotoRuano). Ultramax 400 35mm a
15,60 € (FotoCarrete) y 19,00 € (FotoRuano).

Los portes de tres de las cuatro **no están verificados**. Tratarlos como
desconocidos hasta confirmarlos.

---

## Stack

Todo gratis y todo desde GitHub:

- **Repo público en GitHub.** Público a propósito: los workflows programados de
  GitHub Actions no se disparan en repos privados con plan gratuito. Y aquí no
  hay nada secreto.
- **Streamlit Community Cloud** para la web. Despliega solo desde GitHub.
- **GitHub Actions** para ejecutar los recolectores en horario y guardar los
  precios en el propio repo.
- **SQLite** de entrada, con el esquema pensado para migrar a Postgres sin
  drama.

**La regla de arquitectura que no se rompe:** toda la lógica va en módulos de
Python normales que no saben nada de Streamlit. Streamlit es sólo una capa fina
que llama a esas funciones y pinta el resultado.

Motivo: Streamlit es el andamio, no la casa. El día que haya dominio propio,
diseño en condiciones y una API, se cambia la capa de arriba y el motor no se
toca. Sin esta regla, la lógica se mezcla con la interfaz y hay que reescribir
todo.

El optimizador ya está escrito y probado fuera de este repo: MILP con PuLP
sobre CBC, verificado contra fuerza bruta. Hay que portarlo y añadirle los
packs.

---

## Ideas para más adelante

Nada de esto está decidido. Son cosas a evaluar cuando toque el paso
correspondiente, no antes.

- **Jev, de TypeSafe AI**, para el paso 3 (emparejamiento automático de
  anuncios con productos canónicos). Devuelve decisiones sobre un conjunto
  cerrado de opciones con confianza calibrada, lo que encajaría bien con la
  cola de revisión del principio 2: confianza alta se empareja solo, confianza
  baja va a la cola. Pero no se usa antes de tener el emparejamiento manual
  funcionando — sin eso no hay con qué medir si sus decisiones son fiables.

---

## Cómo trabajar en este repo

**Quién hay al otro lado.** Pedro nunca ha programado. Está aprendiendo con
este proyecto y quiere aprender de verdad, no que le entreguen una caja negra.
Esto no es una limitación que haya que sortear: es el objetivo.

Lo que significa en la práctica:

- **Una cosa cada vez.** Nunca varios ficheros nuevos de golpe. Un paso, que
  funcione, que él lo vea funcionar, y entonces el siguiente.
- **Explicar antes de escribir.** Qué vas a hacer y por qué, en castellano
  llano, antes de tocar nada. Si un concepto es nuevo, explicarlo cuando
  aparece, no darlo por sabido.
- **Nada de jerga sin traducir.** La primera vez que salga un término
  (migración, endpoint, dependencia, entorno virtual), explicarlo en una línea.
- **Comentar el código de verdad**, pensando en alguien que lo lee para
  entenderlo, no para recordarlo.
- **Después de cada paso, decirle cómo comprobar que funciona.** El comando
  exacto y qué debería ver en pantalla.
- **Si algo falla, explicar por qué falló**, no sólo arreglarlo. El error es la
  clase.
- Es Windows, con PowerShell. Los comandos tienen que ser de Windows.

**No adelantar pasos.** Si pide el esquema, sólo el esquema. Si empiezas a
montar de más, te va a parar, y tiene razón.

Preferir aburrido y correcto sobre listo y frágil. El enemigo de este proyecto
es la complejidad acumulada, no la falta de funciones.
