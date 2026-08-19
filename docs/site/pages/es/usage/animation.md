# Línea de tiempo de animación

El **sistema de animación** convierte la lista de fotogramas de un documento
en una *línea de tiempo*: añade, elimina, reordena y duplica fotogramas; da a
cada fotograma su propia duración en pantalla; reproduce la secuencia en uno
de cuatro modos; ve los fotogramas adyacentes con onion skinning; y agrupa
rangos de fotogramas en **animaciones con nombre** mediante etiquetas de
fotograma. Cada edición de fotograma y de etiqueta es un único paso de
deshacer.

Esto alcanza la paridad con **Aseprite** en línea de tiempo, reproducción,
onion skinning y etiquetas, y va más allá con **varias animaciones
independientes con nombre en un mismo archivo** (andar, correr, en reposo) a
través de las etiquetas de fotograma.

!!! note "Capas independientes por fotograma"
    Cada fotograma tiene su **propia** pila de capas, compuesta con el mismo
    motor de capas (visibilidad / opacidad / modo de fusión / grupos /
    máscaras se respetan todos por fotograma). Los *cels enlazados* — una
    capa compartida entre fotogramas — no forman parte de esta versión. En
    un documento **indexado** un fotograma es una única capa indexada, y el
    onion skinning no se muestra (el compositor es solo RGBA).

## La tira de fotogramas

El panel de **Línea de tiempo** muestra el documento como una tira horizontal
de fotogramas en orden de reproducción (de izquierda a derecha); cada celda
lleva una miniatura, su número de fotograma y cualquier marcador de etiqueta
que la abarque. El panel de capas refleja las capas del fotograma que está
activo en ese momento.

- **Seleccionar un fotograma** — haz clic en él (o usa las teclas de flecha).
  El lienzo muestra la pila de capas compuesta de ese fotograma. Seleccionar
  es una acción de vista, así que **no** es deshacible.
- **Explorar (scrub)** — pulsa y arrastra a lo largo de la tira; el lienzo
  muestra continuamente el fotograma bajo el cursor. El scrub tampoco es
  deshacible.

## Gestionar fotogramas

La barra de herramientas de la línea de tiempo edita la secuencia. Cada
acción es **exactamente un paso de deshacer**:

| Acción | Qué hace |
| --- | --- |
| **Añadir fotograma** | Inserta un nuevo fotograma de capa vacía después del fotograma activo. |
| **Eliminar fotograma** | Borra el fotograma activo. **Deshabilitado cuando solo queda un fotograma** — un documento siempre conserva al menos un fotograma. |
| **Duplicar fotograma** | Inserta una **copia profunda e independiente** después del origen (sus capas y duración copiadas). Editar la copia nunca cambia el original. |
| **Arrastrar un fotograma** | Arrastra una celda a una nueva posición para **reordenarlo**. La reproducción y el scrub siguen el nuevo orden. |

Deshacer restaura la secuencia exacta anterior — contenido, orden y
duraciones.

## Duración por fotograma

Cada fotograma tiene su propia **duración** en milisegundos, mostrada en el
editor de duración de la tira (los fotogramas nuevos usan por defecto la
duración estándar de fotograma). Escribe un valor nuevo y confírmalo (Enter /
perder el foco) para fijar el tiempo de permanencia de ese fotograma como un
paso de deshacer. Las duraciones deben ser **positivas** — un valor no
positivo se rechaza. Un fotograma de 500 ms permanece en pantalla unas cinco
veces más que uno de 100 ms durante la reproducción.

!!! tip "Tasa de fotogramas uniforme"
    Una tasa de FPS uniforme es simplemente la misma duración en cada
    fotograma (`duration_ms = round(1000 / fps)`). Los milisegundos por
    fotograma son siempre la única fuente de la temporización de
    reproducción.

## Reproducción

Los **controles de reproducción** gobiernan el fotograma mostrado a lo largo
del tiempo:

- **Reproducir** inicia (o reanuda desde una pausa) sobre todo el documento.
- **Pausar** se congela en el fotograma actual.
- **Detener** para y vuelve al fotograma que estaba activo cuando pulsaste
  Reproducir.
- **Espacio** alterna reproducir/pausar.

El **selector de modo** elige cómo avanza la secuencia (por defecto
**Bucle**):

| Modo | Comportamiento sobre un rango de 4 fotogramas |
| --- | --- |
| **Bucle** | `0,1,2,3,0,1,2,3,…` — envuelve para siempre. |
| **Una vez** | `0,1,2,3` y luego **se detiene** en el último fotograma. |
| **Inversa** | `3,2,1,0,3,2,1,0,…` — envuelve hacia atrás. |
| **Ping-pong** | `0,1,2,3,2,1,0,1,2,3,…` — rebota; los **extremos no se duplican**. |

La reproducción respeta el `duration_ms` propio de cada fotograma, así que
cambiar una duración cambia el tiempo en pantalla de ese fotograma en la
siguiente pasada.

!!! note "La primera reproducción de una animación grande se prepara fuera del hilo principal"
    La primera vez que reproduces un rango en un documento grande (por
    ejemplo 8K) y multicapa, el compuesto aplanado de cada fotograma debe
    construirse una vez. Esto ocurre **fuera del hilo de la interfaz** con
    una pequeña barra de progreso **cancelable** en la barra de estado — la
    ventana permanece receptiva, y la reproducción **transmite** los
    fotogramas a medida que están listos en lugar de congelarse. Una vez que
    los fotogramas están preparados se almacenan en caché, así que la
    repetición y el scrub se ejecutan a 60 fps (un acierto de caché es un
    blit rápido). Los fotogramas se almacenan en caché dentro de un
    presupuesto de memoria acotado; un fotograma expulsado de la caché
    simplemente se vuelve a preparar la próxima vez que se necesita.

## Onion skinning

El onion skinning muestra los **fotogramas adyacentes** detrás del que estás
editando, para que puedas alinear el movimiento.

- **Actívalo** con el interruptor de onion skinning. Los fotogramas fantasma
  se renderizan detrás del fotograma activo; el fotograma activo en sí no
  cambia.
- Define cuántos fotogramas **anteriores** y **siguientes** mostrar (cada
  `0` desactiva ese lado; el valor por defecto es **1 anterior / 1
  siguiente**).
- Define el **tinte** de cada lado — **rojo** para los anteriores, **azul**
  para los siguientes por defecto. Los fotogramas más lejanos se desvanecen.

Los recuentos y tintes del onion skinning son **ajustes de vista** — cambiarlos
actualiza la superposición en vivo y no crea **ningún** paso de deshacer. El
onion skinning se **suprime durante la reproducción** (es una ayuda de
edición, no una vista previa) y durante un scrub.

## Etiquetas de fotograma (animaciones con nombre)

Una **etiqueta de fotograma** nombra un rango de fotogramas como su propia
animación. Un mismo archivo puede contener varias etiquetas — por ejemplo
`andar` sobre los fotogramas 1–4, `reposo` sobre el fotograma 0 — y pueden
solaparse.

Desde el panel de **Etiquetas de fotograma**:

- **Añadir / editar / eliminar** una etiqueta — cada acción abre un diálogo
  para el **nombre** de la etiqueta, el rango inclusivo **desde / hasta**, el
  **modo de reproducción**, el número de **repeticiones** (`0` = infinito
  para los modos en bucle) y un **color**. Cada cambio es **un paso de
  deshacer**. Una etiqueta se muestra como un tramo a lo largo de los
  fotogramas que cubre.
- **Reproducir etiqueta** reproduce la etiqueta seleccionada como su propia
  animación con nombre: ejecuta el rango de la etiqueta bajo el **propio**
  modo de reproducción y las repeticiones de la etiqueta, con independencia
  del modo de reproducción global. Una etiqueta **Una vez** con 3
  repeticiones reproduce su rango tres veces y luego se detiene.

Cuando añades o eliminas fotogramas, los rangos de las etiquetas se mantienen
válidos automáticamente (recortados al nuevo número de fotogramas); deshacer
restaura tanto el cambio de fotogramas como los rangos de etiqueta originales
juntos.

## Persistencia

Los fotogramas, las duraciones por fotograma y las etiquetas de fotograma se
persisten todos a través de `.pixproj` (esquema **versión 3**). Guardar y
luego reabrir una animación etiquetada restaura el orden de los fotogramas,
la duración de cada fotograma y la colección completa de etiquetas (nombres,
rangos, modos, recuentos de repetición, orden) de forma idéntica. Los
proyectos guardados por versiones anteriores (v1 / v2, antes de que
existieran las etiquetas) se siguen abriendo — cargan con una colección de
etiquetas vacía.

## Deshacer, rehacer y lo que *no* es deshacible

- **Deshacible (un paso cada uno):** añadir / eliminar / reordenar /
  duplicar un fotograma, fijar la duración de un fotograma, y
  crear / editar / eliminar una etiqueta.
- **No deshacible (estado de vista):** seleccionar o explorar (scrub) un
  fotograma, reproducir / pausar / detener, y cambiar los recuentos o
  tintes del onion skinning.

## Lo que no se cubre

- Los **cels enlazados** (el contenido de una capa compartido entre
  fotogramas) — pospuesto; cada fotograma tiene una pila de capas
  independiente.
- Una **ventana de vista previa de movimiento a tamaño real dedicada** —
  planificada para una fase posterior; por ahora, previsualiza el movimiento
  **reproduciendo sobre el lienzo**.
- La **exportación a GIF / hoja de sprites** de la animación — una fase
  posterior; los compuestos por fotograma que produce este sistema son las
  entradas de esa exportación.
