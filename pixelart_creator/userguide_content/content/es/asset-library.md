# La biblioteca de recursos: explorar, etiquetar y buscar

La **biblioteca de recursos** es un catálogo a nivel de estudio de tus recursos
reutilizables — sprites, animaciones, tilesets, mapas de tiles y paletas — en un
solo lugar. Registra las entidades que ya has creado como **recursos con nombre**,
organízalos con **etiquetas** libres, y encuentra el correcto rápidamente con
**búsqueda y filtro**. La biblioteca y sus tres paneles se acceden desde el menú
**Biblioteca**.

> **Qué es un recurso.** Un recurso es una **entrada de catálogo** que *referencia*
> una de las entidades que ya has creado — no hace una segunda copia de tu obra.
> Cada entrada lleva un **id estable**, un **tipo** (sprite, animación, tileset,
> mapa de tiles o paleta), un **nombre** de visualización, sus **etiquetas**, y
> algunos metadatos. La entrada apunta a la forma guardada canónica de la entidad
> (el mismo contenido `.pixproj` que usa el resto de la aplicación) — la biblioteca
> no añade ningún formato de guardado nuevo para la obra en sí.

## Abrir la biblioteca

El menú **Biblioteca** tiene tres alternadores de panel acoplable, cada uno mostrando
u ocultando un panel:

| Entrada de menú | Panel | Para qué sirve |
| --- | --- | --- |
| **Biblioteca de recursos** | la lista de catálogo | Explora cada recurso por nombre, tipo y etiquetas. |
| **Búsqueda de recursos** | los controles de búsqueda/filtro | Reduce la lista por nombre, etiqueta y/o tipo. |
| **Etiquetado de recursos** | el editor de etiquetas | Añade y elimina etiquetas del recurso seleccionado. |

Cada entrada es un alternador de panel normal (coherente con los demás paneles de
flujo de trabajo de la aplicación), así que puedes organizar los tres paneles como
prefieras. Los paneles comparten **un** catálogo en memoria, así que un cambio hecho
en un panel se refleja de inmediato en los demás.

## Explorar el catálogo

El panel de **Biblioteca de recursos** lista el catálogo en tres columnas —
**nombre**, **tipo** y **etiquetas**. Siempre muestra exactamente lo que contiene el
catálogo: añadir, eliminar o etiquetar un recurso actualiza la lista de inmediato.
Seleccionar una fila elige ese recurso, que es lo que edita después el panel de
**Etiquetado de recursos**.

- La lista se maneja enteramente desde el catálogo compartido; el panel en sí no
  hace ningún filtrado ni ordenación propios.
- Cuando el panel de **Búsqueda de recursos** tiene una consulta activa, la lista de
  la biblioteca muestra solo las entradas coincidentes (ver abajo); limpiar la
  consulta restaura la lista completa.

## Etiquetar recursos

El panel de **Etiquetado de recursos** edita las etiquetas del recurso seleccionado
en la biblioteca. Escribe una etiqueta y añádela; selecciona una etiqueta y
elimínala. Las etiquetas son marcadores libres — por ejemplo `heroe`, `enemigo` o
`tileset-a` — que te permiten organizar recursos por significado.

- **Las ediciones de etiquetas son deshacibles.** Añadir o eliminar una etiqueta es
  un único paso en la pila de deshacer compartida, así que **Deshacer** restaura el
  conjunto exacto de etiquetas anterior y **Rehacer** vuelve a aplicar la edición —
  el mismo deshacer/rehacer que usas en cualquier otro sitio (consulta
  [Primeros pasos y el espacio de trabajo](app-basics.md)).
- **Añadir una etiqueta ya presente no hace nada** (es una operación nula), y
  eliminar una etiqueta que no está presente es igualmente inocuo.
- **Las etiquetas están acotadas.** Una sola etiqueta tiene una longitud máxima, y
  cada recurso tiene un número máximo de etiquetas. Una etiqueta demasiado larga, o
  una que empujaría al recurso más allá de su límite de etiquetas, se **rechaza con
  un mensaje claro** y no se añade — nada se trunca en silencio.

## Buscar y filtrar

El panel de **Búsqueda de recursos** reduce la lista de la biblioteca con tres
controles que funcionan juntos:

| Control | Coincide con |
| --- | --- |
| **Nombre** | Recursos cuyo nombre *contiene* el texto que escribes (coincidencia de subcadena). |
| **Etiquetas** | Recursos que llevan la(s) etiqueta(s) que introduces (separadas por comas para más de una). |
| **Tipo** | Recursos del tipo elegido; una entrada **Todos los tipos** borra el filtro de tipo. |

- Los tres filtros se **intersecan** — un resultado debe coincidir con el nombre
  *y* las etiquetas *y* el tipo que establezcas. Deja un control vacío para
  ignorar esa dimensión.
- **Los resultados son estables y deterministas:** el mismo catálogo y la misma
  consulta siempre producen la misma lista en el mismo orden.
- **Limpiar todos los controles restaura el catálogo completo**, en su orden
  normal.

> **Encuentra por significado, no por archivo.** Como los recursos están
> etiquetados y son buscables, puedes obtener "cada sprite `enemigo`" o "los
> tilesets etiquetados `mazmorra`" sin rebuscar en carpetas. Dale a tus recursos un
> vocabulario de etiquetas pequeño y coherente, y los filtros hacen el resto.

## Cómo se almacenan los recursos

Detrás de los paneles, la biblioteca mantiene un **catálogo** de entradas de
recursos y un **almacén direccionable por contenido** para sus bytes:

- **Almacenados una vez, por contenido.** Los bytes de cada recurso se almacenan
  con clave según el *contenido* mismo, así que registrar el mismo contenido dos
  veces no lo duplica — los bytes idénticos se conservan solo una vez
  (**deduplicación**).
- **Referenciados por un id estable, no por una ruta.** Un recurso se identifica
  por un id estable que viaja con él, así que **mover o renombrar** el archivo
  subyacente **no** rompe la entrada del catálogo.
- **La obra conserva su formato de guardado normal.** El catálogo reutiliza el
  formato de proyecto `.pixproj` existente para el contenido y almacena solo
  referencias y metadatos junto a él — no hay un segundo formato del que
  preocuparse para tu obra.
- **La carga es defensiva.** Un catálogo o sus metadatos se tratan como entrada no
  confiable al cargar: se comprueban por tamaño y forma, nunca ejecutan nada, y
  cada ruta referenciada se confirma que permanece dentro de la biblioteca — un
  catálogo malformado o fuera de límites se rechaza con un error claro en lugar de
  fallar o corromper algo.

## Lo que aún no se cubre

La biblioteca de recursos se entrega en fases. Esta versión entrega el
**catálogo, etiquetado y búsqueda/filtro**, más el **seguimiento de dependencias y
detección de roturas** (consulta
[Dependencias de recursos y detección de roturas](asset-dependencies.md) — un grafo
consultable de cómo se referencian los recursos entre sí, y una advertencia pasiva
cuando cambiar un recurso rompe otro que lo referencia). Llegando en fases
posteriores:

- **Historial de versiones** — un registro de solo adición de las revisiones de
  cada recurso, con la capacidad de inspeccionar y restaurar una revisión
  anterior.
- **Reutilización entre proyectos** — referenciar un recurso compartido desde
  varios proyectos sin duplicar sus bytes, y empaquetar los recursos
  referenciados en la exportación.
