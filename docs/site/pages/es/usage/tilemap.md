# Mapa de tiles y diseño de niveles

El **sistema de mapa de tiles** convierte una imagen de origen en un
**tileset** reutilizable y te permite pintar niveles grandes con esos tiles en
un **mapa infinito y multicapa**: divide una imagen en tiles indexados,
estampa / borra / rellena celdas, deja que el **auto-tile** resuelva los
bordes por ti, voltea y rota tiles mientras los colocas, y
**exporta / importa** el mapa completo como JSON compatible con Tiled. Cada
edición del mapa es un único paso de deshacer.

!!! note "Tiles lógicos frente a tiles mostrados"
    El auto-tile separa el tile que *colocas* (el tile **lógico**) del tile
    que se *muestra* (el tile de **visualización**). Pintas un tile de
    "muro" y el mapa elige la variante correcta de borde/esquina según sus
    vecinos; la colocación lógica es lo que se almacena y lo que se persiste
    en el ciclo de ida y vuelta, así que el resultado es **determinista y
    reversible**. Desactivar el auto-tile muestra el tile lógico
    directamente.

## Tilesets

Un **tileset** es una imagen de origen dividida en una cuadrícula de tiles
del mismo tamaño. Abre el panel de **Tileset** y añade un tileset desde una
imagen; el divisor lee la imagen con tu **tamaño de tile**, un **margen**
exterior opcional y un **espaciado** entre tiles, e indexa los tiles
resultantes de izquierda a derecha, de arriba a abajo, empezando en `0`.

- Cada tile es una región del búfer de origen, así que un tileset está
  **respaldado por una única imagen** en lugar de por muchas copias.
- **Editar un tile de origen se propaga** a cada instancia colocada de ese
  tile en todas las capas — repinta el tile una vez y todo el nivel se
  actualiza.
- El panel muestra los tiles divididos como una cuadrícula de selección; el
  tile seleccionado es el que pinta la herramienta de sello.

!!! tip "Margen y espaciado"
    `margin` es el borde que se omite alrededor de toda la imagen;
    `spacing` es el hueco que se omite **entre** tiles. Las hojas exportadas
    con un margen de 1 px suelen necesitar `spacing = 1` (y `margin = 1` si el
    margen también envuelve el borde) para que el divisor caiga exactamente
    sobre cada tile.

## Pintar un mapa de tiles

El **lienzo de mapa de tiles** pinta celdas sobre una cuadrícula, un tile por
celda. Elige un tile en el panel de tileset y luego usa las herramientas del
mapa:

| Herramienta | Qué hace |
| --- | --- |
| **Sello** | Coloca el tile seleccionado en la celda bajo el cursor (arrastra para pintar una tirada). |
| **Borrar** | Vacía la celda de vuelta a vacío. |
| **Rellenar** | Rellena por inundación la región contigua de celdas similares bajo el cursor con el tile seleccionado. |

Cada estampado / borrado / relleno es **exactamente un paso de deshacer**, y
deshacer restaura las celdas exactas anteriores. Pintar cerca de tiles
existentes vuelve a resolver el vecindario de **auto-tile** para que los
bordes se mantengan correctos mientras dibujas (ver más abajo).

### Voltear y rotar

Antes de estampar, puedes transformar el tile: **volteo H** y **volteo V** lo
reflejan, y **rotar** lo hace avanzar por las cuatro orientaciones en ángulo
recto (las rotaciones D4). La transformación se almacena por celda colocada
como un indicador compacto en el tile, así que voltear o rotar un tile no
cuesta **entradas adicionales de tileset** y se persiste sin pérdidas en el
ciclo de ida y vuelta. Las transformaciones se componen en un orden fijo
(diagonal, luego horizontal, luego vertical), así que una combinación dada
siempre se renderiza de forma idéntica.

## Auto-tile

El **auto-tile** resuelve el tile de *visualización* de cada celda a partir
de sus **ocho vecinos** (el esquema Blob-47: una máscara de bits de 8
vecinos con activación de esquina implicada por el borde, dando 47 tiles
distintos). Pinta un único tile de "terreno" y el mapa completa
automáticamente los bordes rectos y las esquinas interiores y exteriores
correctas.

- **Alterna** el auto-tile con su control. Cuando está **activado**, pintar,
  borrar o rellenar una celda también vuelve a resolver la celda afectada **y
  sus vecinos** para que el borde sea siempre coherente — todo dentro del
  mismo paso de deshacer.
- La resolución es una **función pura y determinista** de la colocación
  lógica y los vecinos, así que el mismo mapa siempre renderiza los mismos
  tiles de visualización.
- Desactivar el auto-tile muestra directamente el tile lógico que colocaste,
  sin resolución de bordes.

## Capas y mapas infinitos

Un mapa de tiles es **multicapa** — apila una capa de fondo, de terreno y de
detalle, cada una pintada de forma independiente — usando el mismo modelo de
capas que el resto del editor (añadir / eliminar / reordenar /
mostrar-ocultar). El panel de **Capas de mapa de tiles** gestiona la pila;
las capas visibles se componen juntas para su visualización.

El mapa en sí es **infinito**: las celdas se almacenan como una **cuadrícula
dispersa de chunks de 16×16**, así que solo las regiones que realmente pintas
consumen memoria. Puedes estampar lejos del origen (en cualquier dirección)
sin predimensionar el mapa, y las regiones vacías no cuestan nada. Cada celda
es un id de tile (GID) de 32 bits que lleva el índice del tile más sus
indicadores de volteo/rotación.

!!! note "Renderizado de mapas grandes"
    Cada chunk visible se renderiza una vez y se almacena en caché;
    desplazarse reutiliza los chunks en caché en lugar de repintarlos, así
    que desplazarse por un mapa grande se mantiene fluido. La **primera**
    pintura de una región recién visible se precalienta en segundo plano
    (fuera del hilo de la interfaz) para que la ventana permanezca receptiva
    mientras se pone al día; un chunk precalentado es un blit rápido a partir
    de entonces, y la caché se mantiene dentro de un presupuesto de memoria
    acotado.

## Exportación/importación de JSON de Tiled

El mapa se exporta a **JSON compatible con Tiled** y se reimporta **sin
pérdidas** — un ciclo completo conserva las capas, cada celda y sus
indicadores de volteo/rotación, y cualquier campo que el editor no use él
mismo (los campos desconocidos se pasan literalmente).

- **Exportar** escribe un mapa Tiled válido. Los datos de capa se emiten
  como **CSV por defecto**; también se admite **base64** (crudo/comprimido
  con gzip/zlib).
- **Importar** lee mapas Tiled escritos con datos de capa en CSV o base64
  (vacío/gzip/zlib), y acepta una referencia externa de tileset **`.tsj`**.
- Importar es una carga **defensiva y validada**: un mapa malformado, una
  capa comprimida con **zstd** no soportada, o una referencia externa de
  tileset **`.tsx`** se rechazan con un error claro en lugar de un fallo o
  una corrupción silenciosa.

!!! tip "Fidelidad de ida y vuelta"
    Como los campos desconocidos sobreviven al ciclo completo y los
    indicadores de volteo/rotación se conservan bit a bit, puedes mover un
    mapa entre PixelArt Creator y Tiled sin perder los datos que la otra
    herramienta haya añadido.

## Persistencia

Los tilesets y mapas de tiles se persisten a través de `.pixproj`
(esquema **versión 4**). Guardar y luego reabrir un proyecto restaura cada
tileset (su origen y su configuración de división) y cada mapa de tiles (sus
capas, celdas e indicadores de volteo/rotación por celda) de forma idéntica.
Los proyectos guardados por versiones anteriores (**v1 / v2 / v3**, antes de
que existieran los mapas de tiles) se siguen abriendo — simplemente cargan
sin tilesets ni mapas de tiles.

## Deshacer, rehacer y lo que *no* es deshacible

- **Deshacible (un paso cada uno):** estampar / borrar / rellenar una celda
  (incluyendo cualquier nueva resolución de vecinos de auto-tile), y
  añadir / eliminar / reordenar / mostrar-ocultar una capa de mapa de tiles.
- **No deshacible (estado de vista):** seleccionar un tile en el panel de
  tileset, alternar el auto-tile, elegir un volteo/rotación para el
  siguiente estampado, y desplazarse por el mapa.

## Lo que no se cubre

- Los datos de capa Tiled comprimidos con **zstd** y los tilesets externos
  **`.tsx`** en la importación — rechazados por diseño (la importación
  acepta CSV / base64 gzip/zlib y `.tsj` externo); usa una de las
  codificaciones admitidas.
- Los conjuntos de tiles **Wang de esquina/borde** más allá del esquema
  Blob-47 de 8 vecinos — el auto-tile está diseñado para extenderse a ellos
  en una fase posterior.
- **Tiles animados** y **capas de objetos** — una fase posterior; esta
  versión cubre las capas de tiles.
