# Ayudas visuales y experiencia de usuario

La **capa de ayudas visuales** te ayuda a *ver y colocar* tu trabajo con precisión
sin cambiar nunca la obra en sí. Añade una **vista previa a tamaño real**,
**guías y reglas**, una **cuadrícula isométrica**, una **cuadrícula en perspectiva**,
un **panel de referencia** estilo PureRef, **edición multivista**, y
**grabación de timelapse**.

Cada ayuda es **no destructiva**: activar una cuadrícula, soltar una guía, añadir una
imagen de referencia, abrir una segunda vista, o grabar un timelapse no apila
**ningún** paso de deshacer y nunca toca tus píxeles. Solo las ediciones de dibujo
reales son deshacibles, y no se ven afectadas por esta capa.

> **Geometría probada, no un truco de interfaz.** Todo el ajuste (snapping), las
> marcas de las reglas y la escala a tamaño real proceden de un **motor de
> geometría puro y con pruebas unitarias**, con **cero Qt**. Las superposiciones
> solo *renderizan* lo que devuelve la geometría — las matemáticas de ajuste son el
> mismo código que ejercitan las pruebas, así que el ajuste es correcto y
> reproducible.

## Vista previa a tamaño real

La ventana de **Vista previa a tamaño real** muestra tu documento a su **tamaño
físico real**, para que puedas juzgar cómo se verá realmente un sprite o icono.

- La vista previa escala el documento exactamente por `DPI_pantalla / PPI_doc` — los
  píxeles por pulgada del documento (72 por defecto) frente al DPI físico del
  monitor. No se aplica nada más.
- Es una vista **de solo lectura** del documento **compartido**, así que **refleja
  tus ediciones en vivo** — dibuja en el lienzo y la vista previa se actualiza como
  parte de la misma edición, sin botón de actualizar.

> **Si el tamaño real se ve mal, calibra.** Algunos monitores informan un tamaño
> físico incorrecto (o ninguno), así que el DPI consultado está equivocado. Haz clic
> en **Calibrar…**, sostén una regla contra la barra en pantalla, e introduce su
> longitud medida; la vista previa entonces usará tu DPI medido. La escala también
> se recalcula automáticamente cuando mueves la ventana a un monitor de distinta
> resolución.

> **El HiDPI se gestiona por ti.** La escala es independiente del dispositivo y Qt
> aplica por sí mismo la relación de píxeles del dispositivo de la pantalla — la
> vista previa **no** multiplica por el DPR (hacerlo duplicaría la escala en
> pantallas HiDPI).

## Guías y reglas

Activa las **reglas** para obtener una regla horizontal y una vertical con una
**lectura de coordenadas** en vivo, y arrastra **guías** desde ellas para alinear
elementos.

- **Crear una guía** — arrastra desde la regla superior para una guía horizontal, o
  desde la regla izquierda para una guía vertical.
- **Ajuste (snap)** — tu cursor se ajusta a la guía más cercana dentro de una
  pequeña tolerancia. La tolerancia se expresa en **píxeles de pantalla** (8 px por
  defecto) y se convierte al espacio del documento según el zoom actual, así que la
  "adherencia" se siente igual en cualquier nivel de zoom.
- Las marcas de las reglas usan una escala de **números redondos** `1 / 2 / 5 × 10ⁿ`
  con etiquetas enteras simples, independientes de la configuración regional.

Las guías son estado de vista (hasta **256** de ellas). Añadir, mover o eliminar una
guía nunca es deshacible.

## Cuadrícula isométrica

Activa la **cuadrícula isométrica** (`Isometric Grid` en el código fuente) para
dibujar sobre una retícula de diamantes **dimétrica 2:1** (el estándar isométrico
del pixel art).

- La cuadrícula se dibuja proyectando celdas de la retícula a través de una
  transformación mundo↔pantalla **invertible**, y tu cursor **se ajusta al vértice
  de cuadrícula más cercano** (con un desempate determinista de redondeo hacia
  arriba en los empates, así que un punto exactamente entre dos vértices siempre se
  resuelve de la misma forma).
- El espaciado de la cuadrícula (ancho de tile) está acotado entre **2 y 1024 px**.
- La **isometría verdadera** (aproximadamente `1,732:1`) es configurable si la
  prefieres sobre la dimétrica 2:1.
- Abre **Configurar cuadrícula isométrica** desde el menú **Ayudas**, justo al lado
  del interruptor de la cuadrícula isométrica, para fijar valores exactos en lugar
  de calcularlos a ojo: el **ancho de tile**, la **relación de tile W:H** (2,0 para
  dimétrica, ~1,732 para isometría verdadera) y el **origen** de la retícula (X, Y).
  Pulsa **Aceptar** para aplicar la nueva configuración a la pestaña activa, o
  **Cancelar** para dejarla sin cambios.

> **Las cuadrículas muy alejadas se desvanecen por rendimiento.** Cuando el borde en
> pantalla de un tile se reduce por debajo de **32 px**, la retícula es demasiado
> densa para leerse, así que la superposición **deja de pintarse** en lugar de
> exceder el presupuesto de 16 ms de fotograma. Vuelve a acercar el zoom y
> reaparece.

## Cuadrícula en perspectiva

Activa la **cuadrícula en perspectiva** para dibujar con perspectiva de **1, 2 o 3
puntos**.

- Colocas los **puntos de fuga** (hasta **3**); la superposición dibuja un
  **abanico de líneas guía** determinista desde cada uno, más la línea del
  horizonte.
- Tu cursor **se bloquea en dirección a la línea de fuga más cercana** cuando está
  dentro de la tolerancia de ajuste; más allá de la tolerancia **no hay ajuste**, así
  que aún puedes dibujar con libertad.

## Panel de referencia

El **Panel de referencia** es un tablero estilo PureRef en su **propia** ventana
donde puedes reunir inspiración junto a tu lienzo.

- **Añade** imágenes, luego **mueve**, **escala** y ordena en **z** cada una;
  desplaza y haz zoom en todo el panel; y opcionalmente mantén la ventana **siempre
  encima**.
- El panel admite hasta **256** imágenes y está **completamente separado de tu
  obra** — las imágenes de referencia nunca se componen en el documento y nunca
  aparecen en una exportación.
- **Guarda/abre** un panel como un archivo `.pixboard`. El diseño se persiste con
  exactitud. Un archivo de panel malformado muestra un mensaje de error claro —
  nunca falla ni ejecuta nada del archivo.

## Edición multivista

Abre **varias vistas del mismo documento** a la vez — por ejemplo, una vista de
detalle con zoom junto a una vista general ajustada a la ventana.

- Cada vista adicional renderiza el **único documento compartido**, así que una
  edición en el lienzo principal aparece en **todas** las vistas (y en la vista
  previa a tamaño real) **de inmediato, sin actualización manual**.
- Cada vista mantiene su **propio** zoom y desplazamiento — esos son por vista y
  **no** se sincronizan.
- Hasta **8** vistas simultáneas (el lienzo principal cuenta como una). Las vistas
  adicionales son solo de navegación (desplazamiento/zoom); la pintura permanece en
  el lienzo principal.

> **Múltiples *vistas* frente a múltiples *lienzos*.** Esto es distinto de
> [múltiples lienzos](multi-canvas.md): esos son pestañas **aisladas**, cada una un
> documento *diferente* con sus propias capas e historial de deshacer. La multivista
> abre varias ventanas sobre **un** documento que se mantienen sincronizadas.

## Grabación de timelapse

Abre el panel **Timelapse** desde **Ayudas -> Timelapse** para grabar y reproducir
un timelapse de tu sesión de edición, y así compartir cómo se hizo una pieza.

- Pulsa **Grabar** para empezar a capturar; el grabador añade **un fotograma por
  cada edición confirmada** (cada comando deshacible). Púlsalo de nuevo para
  detenerlo.
- Grabar es **estado de vista/sesión** — nunca es deshacible y nunca cambia el
  documento.
- **Guardar timelapse / Abrir timelapse** la sesión como un archivo `.pixtimelapse`. La sesión almacena un
  manifiesto ordenado de **referencias de comandos, no de píxeles**, así que se
  mantiene pequeña y **se reproduce de forma determinista**: la misma sesión
  grabada, reproducida dos veces, produce la **misma** secuencia de fotogramas de
  forma idéntica. Las sesiones están acotadas a **4096** fotogramas; un archivo
  malformado muestra un error de cara al usuario.

### Reproducción

Una vez grabada o abierta una sesión, el mismo panel la reproduce:

- **Reproducir/Pausar** alterna la reproducción de la secuencia de fotogramas
  reconstruida; **Detener** la para. Un control de **búsqueda** absoluta salta
  directamente a cualquier fotograma, y un selector de **velocidad** (0.25x, 0.5x,
  1x, 2x, 4x) cambia la rapidez con la que avanzan los fotogramas — nada de esto
  toca tu documento, y mientras la reproducción está en curso (o en pausa a mitad
  de secuencia) las ediciones del documento se rechazan hasta que la detienes.
- Reproducir una sesión que **abriste** desde un archivo `.pixtimelapse` (en lugar
  de una que acabas de grabar) muestra un aviso **Grabación reabierta**,
  recordándote que estás reproduciendo la grabación guardada, no tu documento
  actual.
- La reproducción puede rechazar reconstruir un fotograma concreto en lugar de
  mostrar uno incorrecto. Puedes ver: la grabación no tiene contenido reconstruible;
  el contenido de un fotograma está incompleto; una posición solicitada está más
  allá del rango grabado; la grabación no coincide con el historial de deshacer
  actual del documento; o a un fotograma le falta la identidad estable que la
  reproducción necesita. Cada rechazo se comunica con un mensaje claro y
  específico — nunca un salto silencioso ni un error inesperado.

> **La exportación a vídeo/GIF es un traspaso posterior.** Esta versión produce la
> **secuencia de fotogramas** reproducible y su propia reproducción. Codificarla a
> un vídeo o GIF compartible reutiliza la
> [canalización de exportación](export-and-pipeline.md) como un seguimiento
> posterior — la secuencia grabada es la entrada de esa canalización.

## Accesibilidad, temas e idiomas

Cada control de ayudas visuales expone un nombre accesible (y una descripción donde
no es obvio), es accesible desde el teclado con un indicador de foco visible, se
renderiza correctamente en ambos temas, **claro y oscuro** (los colores de
superposición y guía se definen una sola vez por rol y permanecen legibles sobre la
obra), y tiene texto **completamente traducible** que se vuelve a establecer al
cambiar de idioma.

## Lo que no se cubre

- **Exportar un timelapse a vídeo/GIF** — aplazado a la canalización de
  exportación; esta versión entrega la secuencia reproducible.
- Una **biblioteca de imágenes de referencia alojada/en la nube** — el panel aquí es
  local.
- **Inferencia de perspectiva asistida por IA / detección automática de puntos de
  fuga** — una fase posterior.
