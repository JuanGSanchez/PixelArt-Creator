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
- **Desplazamiento (pan)** — desplaza la vista horizontal y verticalmente para
  alcanzar cualquier parte de un lienzo grande. Como la escena se prepara una sola vez
  para el tamaño completo del documento, desplazarse por un lienzo de 8K se mantiene
  fluido — solo se dibuja la parte del lienzo visible en el viewport, así que las
  regiones fuera de pantalla no cuestan nada al desplazarse.

> **Los lienzos grandes se mantienen fluidos.** El renderizador dibuja solo la región
> actualmente expuesta en el viewport y repinta solo la pequeña área que una edición
> realmente cambia, así que pintar en un lienzo de 8K se mantiene dentro del
> presupuesto de fotogramas de 60 fps.

## La cuadrícula de píxeles

Con mucho zoom, una **cuadrícula de píxeles** te ayuda a colocar píxeles con
precisión.

- **Alternar la cuadrícula** desde los controles de vista. Es una superposición
  dibujada encima de la obra — nunca pasa a formar parte de tus píxeles y nunca
  aparece en una exportación.
- La cuadrícula es legible en ambos temas, claro y oscuro, dibujada para que se lea
  con claridad sobre cualquier color de la obra.
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

## Temas relacionados

- Elige y gestiona colores en [El centro de color al clic derecho](colour-hub.md).
- Apila y compón tu trabajo con [capas](layers.md).
- Selecciona y reposiciona regiones en
  [Selección y transformación flotante](selection-and-transform.md).
- Añade [cuadrículas, guías y otras ayudas visuales](visual-aids.md) no destructivas
  para una colocación precisa.
