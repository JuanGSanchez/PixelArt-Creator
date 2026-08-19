# PixelArt Creator — Guía de usuario

PixelArt Creator es un editor de arte pixel construido en torno a un lienzo con
capacidad para 8K, un modelo de capas no destructivo y un compositor rápido y
acotado por región.

Esta guía cubre los flujos de trabajo orientados al usuario entregados en la
**Fase 4 — Sistema de capas y lienzo**:

- **[Panel de capas](usage/layers.md)** — opacidad, visibilidad, bloqueo, modo de
  fusión, reordenación, añadir / eliminar / duplicar, grupos, máscaras, capas de
  referencia y capas inteligentes. Cada acción es un único paso de deshacer.
- **[Modos de fusión](usage/blend-modes.md)** — los doce miembros de `BlendMode` y
  qué hace cada uno.
- **[Múltiples lienzos](usage/multi-canvas.md)** — abrir varios
  documentos / mesas de trabajo como pestañas aisladas.
- **[Selección flotante](usage/floating-selection.md)** — levanta una selección y
  mueve (arrastrar) o copia (Ctrl+arrastrar) sus colores como una vista previa no
  destructiva, confirmando al soltar / Enter / cambiar de herramienta, Esc para
  cancelar.
- **[Importar por arrastrar y soltar](usage/drag-drop-import.md)** — arrastra un
  archivo desde el explorador de archivos de tu sistema operativo a la aplicación:
  una imagen se abre como un nuevo documento, un `.pixproj` se abre como un
  proyecto (con aviso de cambios sin guardar), y una paleta `.gpl`/`.hex`/`.pal`
  se carga en la paleta activa (deshacible).
- **[Línea de tiempo de animación](usage/animation.md)** — construye una línea de
  tiempo de fotogramas (añadir / eliminar / reordenar / duplicar, duración por
  fotograma), reprodúcela (bucle / una vez / ping-pong / inversa), usa el
  onion skinning, y agrupa rangos de fotogramas en animaciones con nombre
  mediante etiquetas de fotograma.
- **[Mapa de tiles y diseño de niveles](usage/tilemap.md)** — divide una imagen de
  origen en un tileset, pinta un mapa de tiles multicapa e infinito con
  estampar / borrar / rellenar, deja que el auto-tile resuelva los bordes,
  voltea / rota tiles mientras los colocas, y exporta / importa el mapa como
  JSON compatible con Tiled.
- **[Exportación e integración de pipeline](usage/export.md)** — exporta un
  proyecto como PNG, GIF animado, hoja de sprites o atlas de texturas empaquetado
  con metadatos JSON de estilo Aseprite y perfiles de motor Unity / Godot,
  encola varios objetivos con exportación por lotes, o ejecútalo sin interfaz
  gráfica con la línea de comandos `pixelart-export` — todo byte-reproducible.
- **[Automatización y extensibilidad](usage/automation.md)** — graba y reproduce
  macros (`.pixmacro`, deterministas), ejecuta scripts DSL acotados (sin
  `eval`/`exec`), amplía la aplicación con complementos de confianza y
  consentimiento explícito, recolorea por lotes muchos objetivos a la vez,
  genera contenido de forma procedural, y ejecuta cualquier automatización sin
  interfaz gráfica con la línea de comandos `pixelart-run`.
- **[Ayudas visuales y UX](usage/visual-aids.md)** — una vista previa en vivo a
  tamaño real, guías y reglas con ajuste, cuadrículas isométricas y de
  perspectiva, un tablero de referencia de estilo PureRef, varias vistas
  sincronizadas de un mismo documento, y grabación reproducible de timelapse —
  todo ayudas de vista no destructivas.
- **[Nube, versiones y recuperación](usage/cloud.md)** — conecta un proveedor de
  nube, guarda un proyecto en la nube y ábrelo de nuevo desde cualquier sesión,
  explora un historial de versiones completo y restaura un guardado anterior, y
  confía en el guardado automático en segundo plano con un aviso de recuperación
  ante fallos al reiniciar — todo tras una única interfaz agnóstica de proveedor.
- **[Proyectos compartidos y comentarios](usage/collaboration.md)** — comparte un
  proyecto con un listado de miembros con nombre (roles propietario / editor /
  espectador), deja y resuelve comentarios encadenados, y ve quién más está
  presente, con ediciones concurrentes fusionadas mediante un modelo determinista
  de convergencia híbrida (la co-edición en tiempo real, los cursores en vivo y
  el ramificado de arte llegan en una versión posterior).
- **[Biblioteca de recursos](usage/asset-library.md)** — cataloga tus sprites,
  animaciones, tilesets, mapas de tiles y paletas como recursos con nombre y
  etiquetados, y encuéntralos rápido con búsqueda y filtro por nombre, etiqueta y
  tipo, desde el menú **&Biblioteca**.
- **[Dependencias de recursos y detección de roturas](usage/dependency-graph.md)**
  — un grafo consultable de cómo se referencian los recursos entre sí
  (`sprite → animación → tileset → mapa de tiles`) y un indicador pasivo que
  señala — nunca bloquea — una referencia rota por un recurso que falta o ha
  cambiado.
- **[Versionado de recursos y reutilización entre proyectos](usage/asset-versioning.md)**
  — un historial de revisiones por recurso de solo adición (inspeccionar y
  restaurar, restaurar añade una nueva cabeza), reutilización por referencia (no
  por copia) de un recurso compartido entre proyectos, exportación/importación
  de los recursos referenciados de un proyecto como paquete autocontenido, y
  respaldo opcional en la nube de los blobs compartidos sin dejar de funcionar
  completamente sin conexión.

Para los flujos de trabajo de color, paleta y modo indexado, consulta el
material de la Fase 3; para el lienzo, las herramientas y el tematizado,
consulta el material de la Fase 1.

!!! note "Modo de color"
    El sistema de capas y los modos de fusión descritos aquí se aplican a
    documentos **RGBA**. Un documento **indexado** es de una sola capa por
    diseño (el compositor es solo RGBA). Convertir un documento RGBA multicapa
    a indexado aplana la pila en una única capa indexada, y la conversión es
    totalmente deshacible. Consulta la página del
    [panel de capas](usage/layers.md#modo-de-color-y-documentos-indexados).
