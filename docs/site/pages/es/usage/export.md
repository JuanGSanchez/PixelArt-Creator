# Exportación e integración de pipeline

El **sistema de exportación** convierte un proyecto en los recursos que consume un
pipeline de videojuego: un único **PNG**, un **GIF animado**, una **hoja de
sprites** o un **atlas de texturas** empaquetado, cada uno con metadatos **JSON al
estilo Aseprite** opcionales y **preajustes de motor** listos para usar en
**Unity** y **Godot**. Puedes exportar un objetivo desde el diálogo de
exportación, encolar varios con el panel de lotes, o ejecutar todo el proceso sin
interfaz gráfica desde la línea de comandos `pixelart-export` — y cada camino
produce los **mismos bytes**.

!!! note "Exportación reproducible byte a byte"
    La exportación es **determinista**: para un documento de entrada fijo y los
    mismos parámetros, los bytes de salida son idénticos siempre — los fotogramas
    se recorren en orden explícito, el GIF usa una paleta compartida fija con el
    dithering desactivado, y los codificadores están fijados (sin bloques de
    marca de tiempo, un nivel de compresión PNG fijado). La interfaz gráfica y la
    CLI usan el **mismo** motor, así que una exportación desde la interfaz y una
    exportación desde la CLI del mismo documento son **idénticas byte a byte**. La
    garantía es de *mismo entorno* (una cadena de herramientas fijada), no
    garantizada entre máquinas distintas.

## Exportación ráster (PNG / GIF)

- **PNG** exporta el **fotograma 0** como una única imagen RGBA — el objetivo de
  imagen fija.
- **GIF** exporta la animación: cada fotograma en orden, mostrado durante su
  propia **duración por fotograma** (las duraciones establecidas en la línea de
  tiempo de animación), con el número de bucles, la disposición de fotogramas y
  la transparencia escritos en el archivo. Todos los fotogramas comparten **una
  paleta fija** (una reducción por corte de mediana sobre la animación) y el
  dithering está **desactivado**, que es lo que mantiene el GIF reproducible byte
  a byte.

!!! tip "Número de bucles del GIF"
    El indicador `--loop` (CLI) / campo de bucle (diálogo) establece cuántas
    veces se repite el GIF; **`0` significa bucle infinito**. Déjalo en el valor
    por defecto salvo que necesites un número fijo de reproducciones.

## Hojas de sprites y atlas de texturas

- Una **hoja de sprites** dispone cada fotograma en una **cuadrícula uniforme**,
  por filas — el fotograma `k` se sitúa en la columna `k % columns`, fila
  `k // columns`, con un **relleno** configurable entre sprites y sin margen
  exterior. Establece el número de columnas para controlar la forma de la hoja.
- Un **atlas de texturas** empaqueta los fotogramas de forma compacta con el
  empaquetador compartido **MaxRects** (el mismo empaquetador que usa el resto
  del editor; **la rotación está desactivada**, así que los sprites siempre
  quedan alineados a los ejes). El atlas es la opción eficiente en espacio cuando
  los fotogramas varían en contenido.

!!! note "Límite de tamaño del atlas"
    El atlas está acotado al límite dimensional de **8K** de la plataforma. Si un
    conjunto de sprites no cabe dentro de ese límite, la exportación **falla de
    forma limpia** con un error de atlas claro (nunca un solapamiento silencioso,
    un truncamiento o un fallo no controlado) — reduce el relleno, el tamaño de
    fotograma o el número de fotogramas y vuelve a intentarlo.

## Metadatos JSON

Las exportaciones de hoja de sprites y atlas pueden emitir un **complemento de
metadatos JSON** en el formato **Aseprite *Array***: un array `frames[]` (el
rectángulo, tamaño de origen y duración de cada fotograma) más un bloque `meta{}`
que lleva las **etiquetas** de fotograma y las duraciones por fotograma. El JSON
es **determinista** — las claves están ordenadas, los separadores son fijos y las
coordenadas son enteros — así que se persiste y compara sin problemas. Actívalo
con la opción JSON en el diálogo, o `--json` / `--no-json` en la CLI (activado
por defecto).

## Preajustes de motor (Unity / Godot)

Junto a la imagen y el JSON, la exportación puede escribir un **preajuste listo
para el motor** para que el recurso caiga directamente en un proyecto:

| Preajuste | Qué escribe |
| --- | --- |
| **Unity** | Un complemento `.meta` de sprite — modo de sprite **Multiple**, `pixelsPerUnit`, pivote, y `filterMode = Point` (píxeles nítidos, sin suavizado bilineal). |
| **Godot** | Un recurso `.tres` de `SpriteFrames` (Godot 4.2) construido a partir de los fotogramas exportados. |

Elige el preajuste en el diálogo, o pasa `--preset unity` / `--preset godot` en
la CLI (`--preset none` — el valor por defecto — no escribe ningún preajuste).
Los archivos de preajuste se construyen de forma determinista a partir de los
mismos metadatos de disposición que la imagen.

## Exportación por lotes

El **panel de exportación por lotes** encola **varios objetivos a la vez** — por
ejemplo un PNG, un GIF y un atlas de Unity de un proyecto en una sola ejecución.
La exportación por lotes **continúa ante un fallo**: si un objetivo falla (por
ejemplo, un atlas que no cabe), los demás objetivos se siguen exportando y el
fallo se informa solo para ese objetivo, así que un objetivo defectuoso nunca
aborta el lote.

## Capacidad de respuesta

Todo el trabajo de exportación se ejecuta **fuera del hilo de la interfaz** en un
trabajador en segundo plano, detrás de un **indicador de progreso cancelable** —
así que exportar una animación o un atlas grande nunca congela la ventana. El
trabajador se detiene de forma determinista cuando la exportación termina o se
cancela.

!!! note "Cancelar un único objetivo grande"
    Cancelar surte efecto entre objetivos con prontitud; cancelar **a mitad de la
    codificación de un único objetivo grande** es más grueso — la codificación en
    curso termina antes de que se observe la cancelación. Cancelar un lote
    igualmente impide que empiece el siguiente objetivo.

## La línea de comandos `pixelart-export`

Para automatización y CI, `pixelart-export` ejecuta **exactamente el mismo**
camino de exportación sin interfaz gráfica (sin GUI) — su salida es idéntica
byte a byte a la exportación desde la interfaz del mismo documento y parámetros.
Carga el `.pixproj` a través del mismo cargador de proyecto defensivo y validado
que usa la aplicación.

```
pixelart-export --input PROJECT.pixproj --format FORMAT --output OUT [options]
```

| Indicador | Significado |
| --- | --- |
| `--input PATH` | **(obligatorio)** el proyecto `.pixproj` de origen a exportar. |
| `--format FORMAT` | **(obligatorio)** uno de `png`, `gif`, `sprite-sheet`, `atlas`. |
| `--output PATH` | **(obligatorio)** la ruta de la imagen de salida. |
| `--preset PRESET` | preajuste de motor: `none` (por defecto), `unity`, `godot`. |
| `--columns N` | número de columnas de la hoja de sprites. |
| `--padding N` | relleno entre sprites, en píxeles. |
| `--loop N` | número de bucles del GIF (`0` = bucle infinito). |
| `--tag NAME` | exporta solo el rango de una etiqueta de fotograma con nombre (por defecto: el documento completo). |
| `--json` / `--no-json` | emite el complemento JSON de la hoja de sprites/atlas (por defecto: activado). |

**Códigos de salida:** `0` éxito; `1` un error de exportación / empaquetado /
escritura (por ejemplo, un atlas que no cabe, o un fallo de escritura en el
sistema de archivos); `2` argumentos incorrectos o un proyecto de entrada
malformado / ilegible.

!!! tip "El mismo camino que la interfaz"
    Como la CLI y el diálogo llaman al mismo motor, puedes prototipar una
    exportación de forma interactiva y luego reproducirla exactamente en un
    script de compilación pasando los mismos parámetros como indicadores.

## Lo que no se cubre

- **APNG** (PNG animado) — **aplazado**; esta versión exporta PNG fijo
  (fotograma 0) y GIF animado.
- Salida **idéntica byte a byte entre máquinas** — la garantía de
  reproducibilidad byte a byte es de *mismo entorno* (una cadena de herramientas
  fijada); la cadena de herramientas de una máquina distinta puede producir
  bytes diferentes.
- Cancelación **de grano fino a mitad de codificación** de un único objetivo
  grande — la cancelación se observa entre objetivos, no a mitad de la
  codificación de uno (FU-1).
