# La línea de tiempo de animación

El **sistema de animación** convierte la lista de fotogramas de un documento en una
*línea de tiempo*: añade, elimina, reordena y duplica fotogramas; da a cada fotograma
su propia duración en pantalla; reproduce la secuencia en uno de cuatro modos; ve los
fotogramas adyacentes con el papel cebolla; y agrupa rangos de fotogramas en
**animaciones con nombre** mediante etiquetas de fotograma. Cada edición de fotograma
y de etiqueta es un único paso de deshacer.

Esto alcanza la paridad con **Aseprite** en línea de tiempo, reproducción, papel
cebolla y etiquetas, y va más allá con **varias animaciones con nombre independientes
en un solo archivo** (caminar, correr, quieto) mediante etiquetas de fotograma.

> **Capas independientes por fotograma.** Cada fotograma tiene su **propia** pila de
> capas, compuesta con el mismo [motor de capas](layers.md) (se respetan
> visibilidad/opacidad/modo de fusión/grupos/máscaras en cada fotograma). En un
> documento **indexado**, un fotograma es una única capa indexada, y el papel cebolla
> no se muestra (el compositor es solo RGBA).

## La tira de fotogramas

El panel de **Línea de tiempo** muestra el documento como una tira horizontal de
fotogramas en orden de reproducción (de izquierda a derecha); cada celda lleva una
miniatura, su número de fotograma y cualquier marcador de etiqueta que lo abarque. El
panel de capas refleja las capas del fotograma que está actualmente activo.

- **Seleccionar un fotograma** — haz clic en él (o usa las teclas de flecha). El
  lienzo muestra la pila de capas compuesta de ese fotograma. Seleccionar es una
  acción de vista, así que **no** es deshacible.
- **Recorrer (scrub)** — presiona y arrastra a lo largo de la tira; el lienzo muestra
  continuamente el fotograma bajo el cursor. Recorrer tampoco es deshacible.

## Gestionar fotogramas

La barra de herramientas de la línea de tiempo edita la secuencia. Cada acción es
**exactamente un paso de deshacer**:

| Acción | Qué hace |
| --- | --- |
| **Añadir fotograma** | Inserta un nuevo fotograma de capa vacía después del fotograma activo. |
| **Eliminar fotograma** | Borra el fotograma activo. **Desactivado cuando solo queda un fotograma** — un documento siempre conserva al menos un fotograma. |
| **Duplicar fotograma** | Inserta una **copia profunda e independiente** después del origen (se copian sus capas y duración). Editar la copia nunca cambia el original. |
| **Arrastrar un fotograma** | Arrastra una celda a una nueva posición para **reordenarla**. La reproducción y el recorrido siguen el nuevo orden. |

Deshacer restaura la secuencia exacta anterior — contenido, orden y duraciones.

## Duración por fotograma

Cada fotograma tiene su propia **duración** en milisegundos, mostrada en el editor de
duración de la tira (los fotogramas nuevos usan por defecto la duración de fotograma
estándar). Escribe un valor nuevo y confírmalo (Enter/pérdida de foco) para
establecer el tiempo de permanencia de ese fotograma como un paso de deshacer. Las
duraciones deben ser **positivas** — un valor no positivo se rechaza. Un fotograma de
500 ms permanece aproximadamente cinco veces más que uno de 100 ms durante la
reproducción.

> **Tasa de fotogramas uniforme.** Un FPS uniforme es simplemente la misma duración
> en cada fotograma (`duration_ms = round(1000 / fps)`). Los milisegundos por
> fotograma siguen siendo siempre la única fuente de la temporización de
> reproducción.

## Reproducción

Los **controles de reproducción** manejan el fotograma mostrado a lo largo del
tiempo:

- **Reproducir** inicia (o reanuda desde una pausa) sobre todo el documento.
- **Pausar** congela en el fotograma actual.
- **Detener** para la reproducción y vuelve al fotograma que estaba activo cuando
  pulsaste Reproducir.
- **Espacio** alterna reproducir/pausar.

El **selector de modo** elige cómo avanza la secuencia (por defecto **Bucle**):

| Modo | Comportamiento sobre un rango de 4 fotogramas |
| --- | --- |
| **Bucle** | `0,1,2,3,0,1,2,3,…` — se repite para siempre. |
| **Una vez** | `0,1,2,3` y luego **se detiene** en el último fotograma. |
| **Inverso** | `3,2,1,0,3,2,1,0,…` — se repite hacia atrás. |
| **Ping-pong** | `0,1,2,3,2,1,0,1,2,3,…` — rebota; **los extremos no se duplican**. |

La reproducción respeta la duración propia de cada fotograma, así que cambiar una
duración cambia el tiempo en pantalla de ese fotograma en el siguiente pase.

> **La primera reproducción de una animación grande se prepara fuera del hilo
> principal.** La primera vez que reproduces un rango en un documento grande (por
> ejemplo, 8K) y multicapa, la composición aplanada de cada fotograma tiene que
> construirse una vez. Esto ocurre **fuera del hilo de la interfaz** con una tira de
> progreso pequeña y **cancelable** en la barra de estado — la ventana permanece
> receptiva, y la reproducción **transmite** los fotogramas a medida que están listos
> en lugar de congelarse. Una vez preparados, los fotogramas quedan en caché, así que
> la repetición y el recorrido se ejecutan a 60 fps.

## Papel cebolla

El papel cebolla muestra los **fotogramas adyacentes** detrás del que estás editando,
así puedes alinear el movimiento.

- **Actívalo** con el alternador de papel cebolla. Los fotogramas fantasma se
  renderizan detrás del fotograma activo; el fotograma activo en sí no cambia.
- Establece cuántos fotogramas **anteriores** y **siguientes** mostrar (cada `0`
  desactiva ese lado; el valor por defecto es **1 anterior / 1 siguiente**).
- Establece el **tinte** para cada lado — **rojo** para el anterior, **azul** para el
  siguiente por defecto. Los fotogramas más lejanos se desvanecen.

Los recuentos y tintes del papel cebolla son **ajustes de vista** — cambiarlos
actualiza la superposición en vivo y no crea **ningún** paso de deshacer. El papel
cebolla se **suprime durante la reproducción** (es una ayuda de edición, no una vista
previa) y durante un recorrido.

## Etiquetas de fotograma (animaciones con nombre)

Una **etiqueta de fotograma** nombra un rango de fotogramas como su propia
animación. Un archivo puede tener varias etiquetas — por ejemplo `caminar` sobre los
fotogramas 1–4, `quieto` sobre el fotograma 0 — y pueden solaparse.

Desde el panel de **Etiquetas de fotograma**:

- **Añadir/editar/eliminar** una etiqueta — cada una abre un diálogo para el
  **nombre** de la etiqueta, el rango **desde/hasta** inclusivo, el **modo de
  reproducción**, el número de **repeticiones** (`0` = infinito para los modos en
  bucle) y un **color**. Cada cambio es **un paso de deshacer**. Una etiqueta se
  muestra como un tramo a través de los fotogramas que abarca.
- **Reproducir etiqueta** reproduce la etiqueta seleccionada como su propia animación
  con nombre: ejecuta el rango de la etiqueta bajo el **modo de reproducción y
  repetición propios** de la etiqueta, independientemente del modo de reproducción
  global. Una etiqueta **Una vez** con repetición 3 reproduce su rango tres veces y
  luego se detiene.

Cuando añades o eliminas fotogramas, los rangos de las etiquetas se mantienen válidos
automáticamente (se ajustan al nuevo número de fotogramas); deshacer restaura tanto
el cambio de fotogramas como los rangos de etiquetas originales juntos.

## Vista de cuadrícula (la cuadrícula de celdas)

El alternador **Grid View** (aún sin traducir al español en esta versión) de la
barra de herramientas de la línea de tiempo cambia de la tira horizontal a una
**cuadrícula de celdas**: fotogramas como columnas, pistas de capa como filas, al
estilo de la cuadrícula de celdas de Aseprite. Muestra el mismo documento que la
tira — alternar entre ambas vistas nunca pierde tu posición.

- **Mover/copiar una celda** — presiona y arrastra una celda que contenga contenido
  para moverlo a un fotograma/pista nuevo; mantén pulsado **Ctrl** mientras arrastras
  para copiarlo en su lugar, dejando el origen intacto. Ambas acciones son un único
  paso de deshacer.
- **Confirmación de sobrescritura** — soltar sobre una celda que ya tiene contenido
  abre el diálogo **Overwrite Existing Cel?** pidiéndote confirmación antes de
  reemplazarlo. Marca su casilla **"Don't ask again for this project"** (también
  pendiente de traducción) para dejar de recibir esa pregunta el resto de este
  proyecto; consulta [Confirmaciones del proyecto](#confirmaciones-del-proyecto)
  más abajo para volver a activarla.
- **Alternar visibilidad por celda** — haz clic en el indicador de visibilidad de una
  celda para mostrar/ocultar la capa de ese fotograma; es un paso de deshacer, igual
  que el alternador de visibilidad en cualquier otro lugar.
- **Crear una celda aquí** — clic derecho (o la tecla de menú contextual del teclado)
  sobre una celda vacía para la acción **"Create Cel Here"** (sin traducir). No se
  ofrece en absoluto cuando la celda ya está ocupada, ni cuando el fotograma ya está
  en el número máximo de capas — el menú nunca ofrece una acción que solo se
  rechazaría.
- **Recorrer (scrub)** — arrastra por las celdas vacías de la cuadrícula para
  recorrer el fotograma mostrado, igual que arrastrar por la tira.
- **Reordenar columnas** — arrastra el encabezado de una columna para reordenar
  fotogramas, el equivalente en la cuadrícula de arrastrar una celda de la tira.

> **Nota de idioma.** "Grid View", "Overwrite Existing Cel?", "Don't ask again for
> this project" y "Create Cel Here" aparecen todavía en inglés en la interfaz en
> español: el catálogo de traducción (`i18n/pixelart_es.ts`) aún no incluye estas
> cadenas. Esto es un hueco de localización, no un error de esta guía.

### Confirmaciones del proyecto

La confirmación de sobrescritura de la vista de cuadrícula es una de las
preferencias por proyecto de la aplicación: una vez suprimida con "Don't ask again
for this project," permanece desactivada para ese proyecto hasta que la restaures
desde el menú **Project confirmations** (bajo Editar; también pendiente de
traducción), que lista todas las confirmaciones suprimidas y reactiva cada una
individualmente.

## Persistencia

Los fotogramas, las duraciones por fotograma y las etiquetas de fotograma se
persisten completamente a través de `.pixproj`. Guardar y luego reabrir una animación
etiquetada restaura el orden de los fotogramas, la duración de cada fotograma y la
colección completa de etiquetas de forma idéntica. Los proyectos guardados por
versiones anteriores (antes de que existieran las etiquetas) se siguen abriendo —
cargan con una colección de etiquetas vacía.

## Deshacer, rehacer y lo que *no* es deshacible

- **Deshacible (un paso cada uno):** añadir/eliminar/reordenar/duplicar fotograma,
  establecer la duración de un fotograma, crear/editar/eliminar una etiqueta, y — en
  la vista de cuadrícula — mover/copiar una celda, alternar la visibilidad de una
  celda, y crear una celda.
- **No deshacible (estado de vista):** seleccionar o recorrer un fotograma,
  reproducir/pausar/detener, cambiar los recuentos o tintes del papel cebolla, y
  alternar entre la tira y la vista de cuadrícula.

## Temas relacionados

- Exporta tu animación como GIF, hoja de sprites o atlas en
  [Exportación y canalización](export-and-pipeline.md).
- Graba una sesión mientras animas con la herramienta de timelapse en
  [Ayudas visuales](visual-aids.md).
