# correcarrete

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

**Pendiente: ISO variable.** Algunas películas no tienen un ISO fijo, sino un
rango pensado para exponerse a distintas sensibilidades: Lomography Redscale
(50-200), Turquoise (100-400), Purple y LomoChrome Metropolis (100-400).
`pelicula.iso` guarda de momento solo el extremo bajo del rango, que no es
todo el dato. Antes de que la web muestre el ISO de estas películas hace
falta un `iso_max` opcional en el esquema (migración, no borrar y recrear).

---

## Alcance de la v1

**La v1 es un comparador de precios, no un optimizador de cesta.** Para
cada película: la lista de tiendas que la venden, ordenada de más barata a
más cara, con enlace directo a cada anuncio. Sin cesta, sin cálculo de
envío, sin optimización automática — eso es v2. `cesta/optimizador.py` ya
está escrito y verificado por fuerza bruta; se queda tal cual, en pausa,
hasta que haya coste de envío real de varias tiendas que optimizar de
verdad. Decidido el 20/09/2026, precisamente para que nadie —ni Pedro, ni
un asistente, ni una sesión futura— vuelva a asumir que el objetivo es el
optimizador.

**Dentro:** carretes frescos, de marcas conocidas, en 35mm y 120.

**Dentro también:** marcas propias de tienda y reenvasados (1hundred,
4hundred, 8hundred, CDX, Candido, las Eastman de La Peliculera). Si una
tienda lo vende fresco, entra. De ellas guardamos lo que publica la tienda y
nada más: nunca afirmamos qué emulsión llevan dentro, porque no lo sabemos.

**Fuera:** película caducada, bobina a granel, instantánea (Instax, Polaroid),
gran formato, cine (Super 8, 16mm).

**Fuera también, de momento:** revelado y escaneo. Y las tiendas físicas: no
publican precios, así que no hay dato que capturar. Si se mencionan, se dice
claramente que no tenemos sus precios, en vez de fingir que sí.

**Cámaras desechables, aunque lleven categoría de carrete.** Descubierto con
Cuarto Color Lab (20/09/2026): una cámara desechable con carrete de fábrica
cobra por la cámara entera, no por un carrete suelto, y comparar su precio
como si fuera un carrete induciría a error. Se excluyen aunque la tienda las
categorice junto a sus carretes.

**Dos reglas para las marcas propias y los reenvasados:**

- **Dos nombres se funden en un solo producto únicamente cuando lo dice el
  fabricante.** Un parecido que hemos deducido nosotros no basta nunca.
  Portra y Ektacolor Pro sí se funden, porque Eastman Kodak ha declarado que
  es la misma película renombrada. CDX y CineStill XX no se funden, aunque
  la ficha del CDX diga «250 Daylight / 200 Tungsteno», que son exactamente
  las características de la Double-X y hace muy probable que sean el mismo
  material: probable no es declarado.
- **Cada marca propia es su propia película**, aunque sospechemos que dos
  son el mismo material. No juntamos la 4hundred de una tienda con un
  genérico 400 de otra. Si algún día se confirma que son lo mismo, se junta
  entonces.
- **Los reenvasados nunca se funden en automático con el producto oficial
  del fabricante, aunque compartan la misma emulsión base.** "El Faro"
  reenvasa Kodak Vision3 sin tocar la emulsión, y aun así cada caso se le
  pregunta a Pedro antes de decidir fundir o catalogar aparte — no se
  codifica un criterio automático (del tipo "si no quita el remjet, es lo
  mismo"). La fusión de Vision3 250D/500T "El Faro" con los Kodak Vision3
  oficiales (20/09/2026) se decidió así, caso por caso, no por regla.

---

## Orden de construcción

0. **Despliegue mínimo.** Una app de Streamlit vacía, desplegada en Streamlit
   Community Cloud desde este repo. Treinta minutos, y hace que todo lo que
   venga después nazca ya publicado en vez de acumularse sin desplegar.
   *Hecho cuando la URL pública carga sin errores.*
1. **Esquema y catálogo canónico.** Sembrar a mano los 40-50 stocks que
   importan en España, en sus formatos. Se hace a mano y con cuidado.
2. **Una tienda de punta a punta.** Traer, parsear, emparejar, guardar
   observaciones. *Hecho cuando guarda observaciones sin intervención manual
   — no hay que esperar un plazo fijo para saberlo: cada tienda va aislada
   (principio 4), así que la señal es vigilar la tabla `ejecucion` por
   tienda de forma continua, no un cronómetro. Un fallo en una tienda no
   bloquea seguir avanzando con las demás.*
3. **La segunda tienda**, que es cuando aparecen los problemas de
   emparejamiento de verdad. *Hecho cuando añadir la tercera cuesta una hora.*
4. **La web de verdad: el comparador (v1).** Buscar una película, ver la
   lista de tiendas que la venden ordenada de más barata a más cara, con
   enlace directo a cada anuncio. Construida encima del despliegue mínimo
   del paso 0, con los datos que ya hay (producto + anuncio + pelicula).
5. **El optimizador de cesta con packs y umbrales (v2, en pausa).**
   `cesta/optimizador.py` ya está escrito y verificado por fuerza bruta;
   se retoma cuando haya coste de envío real de varias tiendas que
   optimizar de verdad.
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

## El emparejamiento: dos candidatos, sin decidir

La decisión se toma con números medidos sobre nuestros datos, no antes.

**Jev (TypeSafe AI).** No es un LLM: devuelve una opción de un conjunto
cerrado con probabilidad calibrada, en 70-500 ms y a unos 0,0004 $ por
decisión. Sus ventajas son el volumen, la latencia y que el número de
confianza es fiable de verdad — está entrenado para que sus probabilidades
cuadren con los resultados, cosa que en un LLM no ocurre. Sus inconvenientes:
en el banco de pruebas del propio fabricante saca 67,8% de acierto frente al
73,1% de Claude Opus 5 y el 74,1% del mejor GPT; admite un máximo de 255
opciones, y hoy hay 84 productos pero el catálogo crece; y salió en
septiembre de 2026, o sea que la API puede cambiar.

**Un LLM con calibración medida.** Más acierto hoy. La confianza no viene
calibrada de fábrica, pero se calibra midiendo contra los emparejamientos
hechos a mano.

A nuestra escala — unos 120 emparejamientos por tienda, una sola vez, que
quedan guardados en `equivalencia` y no se repiten — el precio y la latencia
de Jev no aportan nada. Lo que importa es el acierto, y ahí va por detrás.
Ese cálculo solo cambiaría con fuentes donde cada anuncio es único y no se
repite nunca.

**Lo que no cambia.** Ninguno de los dos deroga el principio 2. «No alucina»
significa que Jev siempre devolverá un producto del catálogo y nunca un
formato inválido. No significa que no se equivoque: el propio fabricante
reconoce que puede estar seguro y equivocado, y la calibración se mide sobre
grupos de respuestas, no sobre una respuesta concreta. La cola de revisión se
queda.

**Cómo se decide.** Emparejar a mano las dos primeras tiendas y usar esos
emparejamientos como patrón contra el que medir a los dos candidatos. El
umbral de confianza sale de esa medición y de ningún otro sitio.

**Cómo será el trabajo manual.** Vaciar la cola no es mirar nombres en
blanco: el script de resolución preparará una propuesta por fila, y el
humano firma o corrige. Se presenta con el nombre original de la tienda al
lado del producto propuesto, ordenado por riesgo — primero las dudosas y las
que no ha sabido emparejar, al final las obvias — y por bloques, no las 120
de una sentada. La fatiga de revisión es el riesgo real de este método.

**Pendiente: revisar y corregir equivalencias ya tomadas.** Primer caso real
(20/09/2026): se resolvió «Carrete Eastman Kodak Ektapan 400» como una
película nueva, creyendo que Ektapan era una marca propia — antes de saber
que es el T-Max renombrado. Quedó un producto duplicado hasta que alguien se
dio cuenta a mano. Hoy la única forma de corregir una equivalencia ya tomada
es SQL directo, y por diseño no vuelve a preguntarse sola: una decisión
tomada con información mala no se revisa nunca si nadie va a buscarla.
Hace falta una forma de repasar equivalencias existentes, no solo las
pendientes.

**Dónde sí encaja Jev con claridad.** En el filtro previo, «¿esto es un
carrete, sí o no?», sobre cientos de productos por tienda y pasada. Pregunta
binaria, repetida, a volumen, sobre un espacio cerrado. Ese es su perfil, y
no el emparejamiento.

**Un mismo producto con dos nombres distintos, a la vez.** En marzo de 2026,
Eastman Kodak renombró parte de su gama: Portra pasó a llamarse Ektacolor
Pro, y T-Max pasó a Ektapan — misma película, distinto nombre, porque Kodak
Alaris (quien fabricaba y vendía con los nombres antiguos) se quedó esos
nombres. Las tiendas venden las dos versiones a la vez, a precios distintos,
así que no es una migración de nombre limpia: son dos anuncios reales y
simultáneos del mismo producto. La tabla `equivalencia` ya lo resuelve sin
cambios: `(tienda, nombre_original)` admite tantos nombres como haga falta
apuntando al mismo `producto_id`, así que «Ektacolor Pro 400 35mm 36 exp» y
«Portra 400 35mm 36 exp» conviven señalando al mismo sitio.

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
