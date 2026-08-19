# Ayudas visuales y UX

La **capa de ayudas visuales** te ayuda a *ver y colocar* tu trabajo con
precisión sin cambiar nunca la obra en sí. Añade una **vista previa a tamaño
real**, **guías y reglas**, una **cuadrícula isométrica**, una **cuadrícula de
perspectiva**, un **tablero de referencia** de estilo PureRef, **edición
multivista**, y **grabación de timelapse**.

Toda ayuda es **no destructiva**: activar una cuadrícula, soltar una guía,
añadir una imagen de referencia, abrir una segunda vista o grabar un
timelapse no genera **ningún** paso de deshacer y nunca toca tus píxeles.
Solo las ediciones de dibujo reales son deshacibles, y no se ven alteradas
por esta capa.

!!! note "Geometría probada, no un truco de interfaz"
    Todo el ajuste (snapping), las marcas de regla y la escala a tamaño real
    provienen de un **motor de geometría puro y probado con tests**
    (`pixelart_creator.logic.grids` / `.guides` / `.preview` / `.timelapse`)
    con **cero Qt**. Las superposiciones solo *renderizan* lo que devuelve la
    geometría — la matemática de ajuste es el mismo código que ejercitan los
    tests, así que el ajuste es correcto y reproducible. Consulta la
    **ADR-0023** (modelo de geometría y ajuste) y la **ADR-0024**
    (arquitectura).

## Vista previa a tamaño real

La ventana de **vista previa a tamaño real** muestra tu documento en su
**tamaño físico real**, para que puedas juzgar cómo se verá realmente un
sprite o un icono.

- La vista previa escala el documento por exactamente `screen_DPI / doc_PPI`
  — los píxeles por pulgada del documento (`Document.ppi`, por defecto
  **72**) frente al DPI físico del monitor. No se aplica nada más.
- Es una vista **de solo lectura** del documento **compartido**, así que
  **refleja tus ediciones en vivo** — dibuja en el lienzo y la vista previa
  se actualiza como parte de la misma edición, sin botón de actualizar.

!!! tip "Si el tamaño real se ve mal, calibra"
    Algunos monitores informan un tamaño físico incorrecto (o ninguno), así
    que el DPI consultado es erróneo. Haz clic en **Calibrar…**, sostén una
    regla contra la barra en pantalla e introduce su longitud medida; la
    vista previa entonces usa tu DPI medido. La escala también se recalcula
    automáticamente cuando mueves la ventana a un monitor de distinta
    resolución.

!!! warning "El HiDPI se gestiona por ti"
    La escala es independiente del dispositivo y Qt aplica por sí mismo la
    relación de píxeles del dispositivo de la pantalla — la vista previa
    **no** multiplica por el DPR (hacerlo duplicaría la escala en pantallas
    HiDPI).

## Guías y reglas

Activa las **reglas** para obtener una regla horizontal y una vertical con
una **lectura de coordenadas** en vivo, y arrastra **guías** desde ellas para
alinear elementos.

- **Crear una guía** — arrastra desde la regla superior para una guía
  horizontal, o desde la regla izquierda para una guía vertical.
- **Ajuste (snap)** — tu cursor se ajusta a la guía más cercana dentro de
  una pequeña tolerancia. La tolerancia se expresa en **píxeles de
  pantalla** (por defecto **8 px**) y se convierte al espacio del documento
  según el zoom actual, así que la "adherencia" se siente igual en cualquier
  nivel de zoom.
- Las marcas de regla usan una escalera de **números redondos**
  `1 / 2 / 5 × 10ⁿ` con etiquetas enteras sencillas e independientes del
  idioma regional.

Las guías son estado de vista (hasta **256** de ellas). Añadir, mover o
eliminar una guía nunca es deshacible.

## Cuadrícula isométrica

Activa la **cuadrícula isométrica** para dibujar sobre una retícula de
diamantes **dimétrica 2:1** (el estándar isométrico del pixel art).

- La cuadrícula se dibuja proyectando las celdas de la retícula mediante una
  transformación mundo↔pantalla **invertible**, y tu cursor **se ajusta al
  vértice de cuadrícula más cercano** (con desempate determinista por
  redondeo hacia arriba en los .5, así que un punto exactamente entre dos
  vértices siempre se resuelve del mismo modo).
- El espaciado de la cuadrícula (ancho de tile) está acotado a **2–1024
  px**.
- La opción **verdaderamente isométrica** (aproximadamente `1,732:1`) es
  configurable si la prefieres sobre la dimétrica 2:1.

!!! note "Las cuadrículas alejadas se desvanecen por rendimiento"
    Cuando el borde en pantalla de un tile se reduce por debajo de **32 px**
    la retícula es demasiado densa para leerse, así que la superposición
    **omite el dibujo** en lugar de superar el presupuesto de fotograma de
    16 ms. Vuelve a acercar el zoom y reaparece. Solo se trazan las líneas
    de retícula visibles (el resto se descarta), y un paneo/zoom que deja la
    configuración sin cambios reutiliza la cuadrícula ya rasterizada.

## Cuadrícula de perspectiva

Activa la **cuadrícula de perspectiva** para dibujar con perspectiva de
**1, 2 o 3 puntos**.

- Colocas los **puntos de fuga** (hasta **3**); la superposición dibuja un
  **abanico de líneas guía** determinista desde cada uno, más la línea del
  horizonte.
- Tu cursor **se bloquea en dirección a la línea de fuga más cercana**
  cuando está dentro de la tolerancia de ajuste (píxeles del documento); más
  allá de la tolerancia **no hay ajuste**, así que aún puedes dibujar
  libremente.

## Tablero de referencia

El **tablero de referencia** es un tablero de estilo PureRef en su
**propia** ventana donde puedes reunir inspiración junto a tu lienzo.

- **Añade** imágenes, luego **muévelas**, **escálalas** y ajusta su **orden
  z**; desplaza y haz zoom sobre todo el tablero; y opcionalmente mantén la
  ventana **siempre visible**.
- El tablero admite hasta **256** imágenes y está **completamente separado
  de tu obra** — las imágenes de referencia nunca se componen en el
  documento y nunca aparecen en una exportación.
- **Guarda / abre** un tablero como un archivo `.pixboard`. El diseño (cada
  imagen más su transformación, recorte y orden de apilamiento) se conserva
  exactamente en el ciclo de ida y vuelta. Un archivo de tablero malformado
  muestra un mensaje de error claro — nunca se bloquea y nunca ejecuta nada
  del archivo.

## Edición multivista

Abre **varias vistas del mismo documento** a la vez — por ejemplo una vista
de detalle con zoom junto a una vista general ajustada a la ventana.

- Cada vista adicional renderiza el **único documento compartido**, así que
  una edición en el lienzo principal aparece en **todas** las vistas (y en
  la vista previa a tamaño real) **de inmediato, sin actualización manual**.
- Cada vista mantiene su **propio** zoom y paneo — son por vista y **no**
  se sincronizan.
- Hasta **8** vistas simultáneas (el lienzo principal cuenta como una). Las
  vistas adicionales son solo de navegación (desplazamiento/zoom); pintar se
  mantiene en el lienzo principal.

!!! note "Varias *vistas* frente a varios *lienzos*"
    Esto es diferente de [múltiples lienzos](multi-canvas.md): esos son
    pestañas **aisladas**, cada una un documento *distinto* con sus propias
    capas e historial de deshacer. La multivista abre varias ventanas sobre
    **un** documento que se mantienen sincronizadas.

## Grabación de timelapse

Graba un **timelapse** de tu sesión de edición para compartir cómo se hizo
una pieza.

- Pulsa **Grabar** para empezar a capturar; el grabador añade **un
  fotograma por cada edición confirmada** (cada comando deshacible). Púlsalo
  de nuevo para detener.
- Grabar es **estado de vista/sesión** — nunca es deshacible y nunca cambia
  el documento.
- **Guarda / abre** la sesión como un archivo `.pixtimelapse`. La sesión
  almacena un manifiesto ordenado de **referencias de comandos, no
  píxeles**, así que se mantiene pequeña y **se reproduce de forma
  determinista**: la misma sesión grabada reproducida dos veces produce la
  **misma** secuencia de fotogramas (los fotogramas se re-renderizan a
  partir del historial de edición del documento). Las sesiones están
  acotadas a **4096** fotogramas; un archivo malformado muestra un error
  visible para el usuario.

!!! note "La exportación a vídeo/GIF llega en un traspaso posterior"
    Esta versión produce la **secuencia de fotogramas** reproducible.
    Codificarla a un vídeo o GIF compartible reutiliza el pipeline de
    exportación como un seguimiento posterior — la secuencia grabada es la
    entrada de ese pipeline.

## Accesibilidad, temas e idiomas

Todo control de ayudas visuales expone un nombre accesible (y una
descripción cuando no es evidente), es alcanzable por teclado con un
indicador de foco visible, se renderiza correctamente en ambos temas
**claro y oscuro** (los colores de superposición y guía se definen una vez
por rol y se mantienen legibles sobre la obra), y tiene texto
**completamente traducible** que se vuelve a establecer al cambiar de
idioma.

## Lo que no se cubre

- **Exportar un timelapse a vídeo/GIF** — aplazado al pipeline de
  exportación; esta versión distribuye la secuencia reproducible.
- Una **biblioteca de imágenes de referencia alojada/en la nube** — una
  fase posterior de Nube y colaboración; el tablero de aquí es local.
- **Inferencia de perspectiva asistida por IA / detección automática de
  puntos de fuga** — una fase posterior.
