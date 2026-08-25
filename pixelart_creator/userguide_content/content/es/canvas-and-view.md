<!-- surface-only: bundle — contenido de orientación en la app; sin página en el sitio, por diseño (WP-8 unidad 2d) -->
# El lienzo: zoom, desplazamiento y la cuadrícula

El **lienzo** es la superficie de dibujo principal — una escena grande que admite
documentos de hasta el máximo de la plataforma: **7680 × 4320 (8K)**. Renderiza tu obra
con escalado de **vecino más cercano** y **antialiasing desactivado**, así que los
píxeles se mantienen siempre nítidos y cuadrados a cualquier zoom, exactamente como
debe verse el pixel art.

## Navegar: zoom y desplazamiento

- **Zoom** — acerca para trabajar en píxeles individuales y aleja para ver la pieza
  completa. El zoom está centrado de forma que el punto bajo el cursor se mantiene
  fijo, lo que te mantiene orientado mientras escalas hacia arriba y hacia abajo. El
  zoom es una acción de **vista**; nunca cambia tu obra y no es un paso de deshacer.
- **El 100 % es el nivel de zoom mínimo.** Ya no puedes alejar el zoom más allá de
  1:1, ni siquiera en un documento más grande que la ventana. Por debajo del 100 % un
  único píxel del documento puede caer entre dos puntos de muestreo de pantalla y
  sencillamente no dibujarse — los trazos parecían desaparecer al alejar el zoom.
  Explora un documento grande **desplazándote (pan)** en su lugar: así puedes llevar
  cualquier esquina del lienzo al centro de la vista.
- **Desplazamiento (pan)** — desplaza la vista horizontal y verticalmente para
  alcanzar cualquier parte de un lienzo grande. Como la escena se prepara una sola vez
  para el tamaño completo del documento, desplazarse por un lienzo de 8K se mantiene
  fluido — solo se dibuja la parte del lienzo visible en el viewport, así que las
  regiones fuera de pantalla no cuestan nada al desplazarse.
- **Acercar / Alejar** (en inglés, **Zoom In** / **Zoom Out** en el código fuente) —
  estas dos acciones de vista saltan entre los mismos puntos fijos que usan los
  atajos de teclado (100 %, 200 %, 400 %, 800 %, 1600 %, 3200 %, 6400 %):
  **Acercar** salta al siguiente punto y **Alejar** salta al anterior. Es un salto
  discreto, a diferencia del zoom continuo anclado al cursor que obtienes al
  desplazar la rueda del ratón sobre el lienzo.

> **Los lienzos grandes se mantienen fluidos.** El renderizador dibuja solo la región
> actualmente expuesta en el viewport y repinta solo la pequeña área que una edición
> realmente cambia, así que pintar en un lienzo de 8K se mantiene dentro del
> presupuesto de fotogramas de 60 fps.

## El tablero de ajedrez es el límite de tu lienzo

El tablero de transparencia no es decoración detrás de la obra — **es la retícula de
píxeles**: cada cuadro alterno del tablero es exactamente un píxel del documento. El
tablero también está acotado: se detiene justo en el borde del lienzo, un color de
fondo de trabajo liso rellena el área que lo rodea, y un borde fino traza el límite
entre ambos, así que siempre puedes ver dónde termina la superficie de dibujo. Antes,
el tablero continuaba más allá del lienzo sin nada que marcara el borde, lo que hacía
fácil confundir un cuadro del tablero con un píxel.

## La cuadrícula de píxeles

La **cuadrícula de píxeles** te ayuda a colocar píxeles con precisión, y está
**activada de forma predeterminada** en un documento nuevo.

- **Alternar la cuadrícula** desde los controles de vista. Es una superposición
  dibujada encima de la obra — nunca pasa a formar parte de tus píxeles y nunca
  aparece en una exportación.
- La cuadrícula es legible en ambos temas, claro y oscuro, dibujada para que se lea
  con claridad sobre cualquier color de la obra.
- **Activada no significa dibujada.** La cuadrícula solo aparece cuando el borde en
  pantalla de un píxel mide al menos 8 píxeles de pantalla. Al 100 % de zoom un
  píxel del documento es más pequeño que eso, así que no verás líneas de cuadrícula
  aunque esté activada — acerca el zoom y aparecerán. Si activas la cuadrícula y no
  ves ningún cambio, esta es la razón; no es un error.
- Cuando estás muy alejado, una cuadrícula densa sería ilegible, así que la
  superposición deja de dibujarse con elegancia hasta que vuelvas a acercar el zoom.

## Ajuste (snapping)

Con el ajuste a la cuadrícula activado, las herramientas se alinean a la cuadrícula
para que un trazo caiga exactamente en los límites de los píxeles. Esto es
especialmente útil al colocar tiles o alinear formas. El ajuste es un ajuste de
vista/herramienta, no una edición.

## Pintar en el lienzo

- **Clic izquierdo** (y arrastre) pinta con la herramienta activa y el color activo.
  El color activo procede del [centro de color](colour-hub.md) o de la paleta. Cada
  trazo se apila como un paso de deshacer.
- **Clic derecho** abre el [centro de color](colour-hub.md) contextual en el cursor,
  así puedes elegir o cambiar tu color sin salir del lienzo.

## Cambiar el tamaño del lienzo

**Imagen ▸ Tamaño del lienzo…** cambia las dimensiones del lienzo en sí — no
remuestrea ni un solo píxel. Introduce un ancho y un alto nuevos (cada uno hasta el
máximo de la plataforma, **7680 × 4320**, es decir 8K) y pulsa **Aceptar**; cada capa
y máscara de cada fotograma se recorta o se rellena hasta el nuevo tamaño, anclada en
la esquina superior izquierda, así que la obra existente nunca se desplaza y
cualquier área recién expuesta queda transparente. Pulsa **Cancelar** para dejar el
documento exactamente como estaba. El cambio de tamaño se aplica como un único paso
deshacible.

Esta es una operación distinta de remuestrear la obra a un nuevo tamaño — Tamaño del
lienzo solo cambia cuánto lienzo hay; nunca estira ni encoge los píxeles que ya
tienes.

## Temas relacionados

- Elige y gestiona colores en [El centro de color al clic derecho](colour-hub.md).
- Apila y compón tu trabajo con [capas](layers.md).
- Selecciona y reposiciona regiones en
  [Selección y transformación flotante](selection-and-transform.md).
- Añade [cuadrículas, guías y otras ayudas visuales](visual-aids.md) no destructivas
  para una colocación precisa.
