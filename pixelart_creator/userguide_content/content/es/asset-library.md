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

## Registrar un recurso

Antes de que algo aparezca en el catálogo, tiene que **registrarse**. Tres lugares de
la aplicación inician un registro, y los tres terminan en el mismo aviso compartido,
**Registrar recurso** (*Register Asset*):

- **Registrar documento activo** (*Register Active Document*), en el menú
  **Biblioteca**, registra el documento abierto en la pestaña activa. Registrar el
  mismo documento de nuevo más tarde añade una nueva revisión a su entrada de catálogo
  existente en lugar de crear un duplicado — consulta
  [Versionado de recursos y reutilización entre proyectos](asset-versioning.md).
- **Registrar selección** (*Register Selection*), también en el menú **Biblioteca**,
  registra solo los píxeles dentro de tu selección actual. Para una selección no
  rectangular, todo lo que queda fuera de los píxeles seleccionados es transparente en
  el recurso registrado. Sin ninguna selección, no hay nada que registrar.
- **También añadir a la biblioteca de recursos**, una casilla del diálogo de
  exportación (consulta [Exportación y canalización](export-and-pipeline.md)), registra
  el artefacto exportado en el mismo paso que la exportación.

Los tres abren el mismo diálogo **Registrar recurso**, que pide:

| Campo | Qué pide |
| --- | --- |
| **Nombre** | Un nombre de visualización para la nueva entrada de catálogo. |
| **Tipo** | Uno de los cinco tipos de recurso — Sprite, Animación, Tileset, Mapa de tiles, Paleta. |
| **Etiquetas** | Un conjunto opcional de etiquetas separadas por comas, comprobado contra los mismos límites de longitud y cantidad que el panel de etiquetado más abajo. |

El diálogo valida mientras escribes: un nombre vacío, o un conjunto de etiquetas que
supere los límites de longitud/cantidad, deshabilita el botón **Registrar** con un
motivo claro mostrado hasta que lo corrijas. Cancelar el diálogo no registra nada.

## Mover un recurso individual

Otros dos comandos del menú **Biblioteca** mueven un único archivo de artefacto, a
diferencia de un proyecto completo:

- **Exportar recurso** (*Export Asset*) exporta la entrada de catálogo seleccionada
  actualmente — o, sin ninguna selección, todas las entradas del catálogo abierto —
  como un único archivo de artefacto importable.
- **Importar recurso** (*Import Asset*) lee de vuelta uno de esos artefactos en la
  biblioteca abierta, fusionándolo con el catálogo.

Estos son distintos de **Exportar paquete de proyecto** / **Importar paquete de
proyecto** (*Export Project Bundle* / *Import Project Bundle*), que mueven un proyecto
completo junto con todo lo que referencia — consulta
[Versionado de recursos y reutilización entre proyectos](asset-versioning.md).

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

## El resto de la biblioteca de recursos

La biblioteca de recursos se entregó en fases; el hito completo ya está
disponible. Más allá del catálogo, el etiquetado y la búsqueda/filtro anteriores:

- **[Dependencias de recursos y detección de roturas](asset-dependencies.md)** —
  un grafo consultable de cómo se referencian los recursos entre sí
  (`sprite -> animación -> conjunto de tiles -> mapa de tiles`) y una advertencia
  pasiva cuando cambiar un recurso rompe otro que lo referencia.
- **[Versionado de recursos y reutilización entre proyectos](asset-versioning.md)**
  — un historial de revisiones de solo adición por recurso (inspeccionar y
  restaurar), reutilización por referencia (sin copiar) de un recurso compartido
  entre proyectos, exportación/importación de los recursos que un proyecto
  referencia como un paquete autónomo, y respaldo opcional en la nube de los
  blobs compartidos.
