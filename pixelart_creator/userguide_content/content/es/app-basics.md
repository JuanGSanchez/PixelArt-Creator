# Primeros pasos y el espacio de trabajo

Bienvenido a **PixelArt Creator** — un estudio de pixel art de escritorio con un lienzo
de 8K, un sistema de capas no destructivo, una línea de tiempo de animación, un editor
de tileset/mapa de tiles, una canalización de exportación, automatización y scripting,
ayudas visuales y colaboración en la nube. Este tema te orienta en el espacio de
trabajo para que el resto de la guía tenga sentido.

## La ventana principal de un vistazo

- **Barra de menús** (arriba) — el punto de entrada a cada comando, agrupado en menús
  como **Archivo**, **Editar**, **Ver**, **Nube** y **Ayuda**. La Guía del usuario
  integrada que estás leyendo ahora se abre desde **Ayuda ▸ Guía del usuario** (o
  pulsando **F1**).
- **Lienzo** (centro) — la superficie de dibujo. Consulta
  [El lienzo: zoom, desplazamiento y la cuadrícula](canvas-and-view.md).
- **Paneles acoplables** (laterales) — el panel de capas, la línea de tiempo de
  animación, el panel de tileset y los paneles de nube/colaboración. La mayoría de los
  paneles se pueden activar o desactivar y organizar según tu flujo de trabajo.
- **Barra de estado** (abajo) — lecturas de coordenadas, indicadores de progreso para
  trabajo en segundo plano (exportación, preparación de reproducción, guardados en la
  nube) y avisos breves.

## Documentos y pestañas

Cada dibujo abierto es un **documento** que se muestra en su propia **pestaña**. Un
documento tiene un tamaño, un modo de color (**RGBA** o **Indexado**), una paleta, un
árbol de capas y — si lo animas — una lista de fotogramas. Puedes mantener varios
documentos abiertos a la vez; consulta
[Múltiples lienzos (artboards)](multi-canvas.md). Los documentos se guardan como
archivos de proyecto **`.pixproj`**, el formato de guardado validado y versionado que
usa toda la aplicación (y la capa de nube).

## Deshacer y rehacer

Casi cualquier edición — pintar, un cambio de capa, una transformación, una edición de
fotograma, una ejecución de automatización — se apila en la **pila de deshacer** del
documento como **exactamente un** paso. **Deshacer** revierte el último paso y
**Rehacer** vuelve a aplicarlo. El historial de deshacer es **por pestaña**, así que
deshacer en un documento nunca afecta a otro. Un puñado de acciones intencionalmente
**no** se pueden deshacer porque son estado de vista, no ediciones: seleccionar o
recorrer un fotograma, activar el papel cebolla, añadir una guía y abrir los paneles de
nube/colaboración.

## Temas (claro y oscuro)

La aplicación incluye temas **claro** y **oscuro** emparejados. Cambia entre ellos
desde el control de tema de la aplicación; todos los paneles, diálogos, superposiciones
y esta Guía del usuario se renderizan correctamente y siguen siendo legibles en ambos.
Los colores se definen una sola vez por rol, así que el tema es coherente en todas
partes.

## Idioma

La interfaz es completamente traducible. Cuando cambias el idioma activo, cada menú,
etiqueta y mensaje se retraduce en vivo — no necesitas reiniciar. El marco de esta Guía
del usuario (su título, las etiquetas de sección, el cuadro de búsqueda y la
navegación) sigue el idioma activo; el contenido de la guía se muestra en tu idioma
cuando hay una versión localizada incluida, y si no, recae en el texto predeterminado
(inglés).

## Atajos de teclado

Los comandos habituales tienen atajos de teclado, mostrados junto a sus entradas de
menú. Algunos que usarás constantemente:

| Atajo | Acción |
| --- | --- |
| **F1** | Abrir esta Guía del usuario |
| **Ctrl+Z** / **Ctrl+Y** | Deshacer / Rehacer |
| **Espacio** | Alternar reproducción/pausa de la animación |
| **Ctrl+Shift+E** | Abrir el diálogo de exportación |
| **Esc** | Cancelar la acción en curso (por ejemplo, un movimiento flotante) |
| **Enter** | Confirmar la acción en curso |

## Adónde ir a continuación

- Dibuja en el [lienzo](canvas-and-view.md) y elige colores desde el
  [centro de color](colour-hub.md).
- Organiza tu arte con [capas](layers.md) y [modos de fusión](blend-modes.md).
- [Selecciona y mueve](selection-and-transform.md) regiones de tu obra.
- Anima con la [línea de tiempo](animation-timeline.md), construye niveles con el
  [editor de tileset y mapa de tiles](tileset-and-tilemap.md), y envía recursos a
  través de la [exportación](export-and-pipeline.md).
- Acelera el trabajo repetitivo con
  [automatización y scripting](automation-and-scripting.md), dibuja con más precisión
  con las [ayudas visuales](visual-aids.md), y trabaja en equipo a través de la
  [nube](cloud-and-collaboration.md) y la [colaboración](collaboration.md).
