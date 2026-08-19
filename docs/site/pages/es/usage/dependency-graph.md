# Dependencias de recursos y detección de roturas

El **grafo de dependencias** registra cómo tus recursos se referencian entre
sí — un sprite es un fotograma *de* una animación, un sprite es la imagen de
origen *de* un tileset, un tileset se usa *en* un mapa de tiles — y el
**indicador de rotura** advierte de forma pasiva cuando cambiar un recurso
rompería otro que apunta a él. Ambos se acceden desde el menú
**&Biblioteca**, junto a los paneles de la [biblioteca de recursos](asset-library.md)
sobre los que se construyen.

!!! note "Qué es una dependencia"
    Una dependencia es una **referencia dirigida** de un recurso del catálogo
    a otro: el recurso *referenciante* (el origen) apunta al recurso
    *referenciado* (el destino). La referencia también recuerda el contenido
    del destino en el momento en que se hizo, así que la biblioteca puede
    decir más adelante si el destino ha cambiado. Las dependencias forman un
    **grafo acíclico dirigido** — la biblioteca se niega a registrar una
    referencia que crearía un ciclo (un recurso no puede, directa o
    transitivamente, terminar dependiendo de sí mismo).

## Abrir el grafo de dependencias

El menú **&Biblioteca** gana un alternador de panel acoplable de **Grafo de
dependencias**. La vista del **Grafo de dependencias** visualiza las
referencias de todo el catálogo o del único recurso seleccionado actualmente
en el panel de [Biblioteca de recursos](asset-library.md), en dos
direcciones:

| Relación | Se lee como | Muestra |
| --- | --- | --- |
| **Depende de** | lo que este recurso *referencia* | los recursos a los que apunta el recurso seleccionado |
| **Referenciado por** | lo que *referencia* a este recurso | los recursos que apuntan al recurso seleccionado |

Ambas relaciones se muestran como listas estables y ordenadas
alfabéticamente. Por defecto, la vista muestra los vecinos **directos**; las
mismas relaciones se pueden leer de forma transitiva (la cadena completa —
por ejemplo, cada recurso del que depende en última instancia un mapa de
tiles, a través de sus tilesets y sus sprites de origen).

!!! tip "Por qué el grafo nunca se cuelga"
    Como el grafo almacenado es siempre acíclico, la vista solo lista los
    vecinos directos que devuelve el modelo — no realiza ningún recorrido
    recursivo propio. Incluso un conjunto de referencias deliberadamente
    enredado no puede hacer que la vista se quede colgada: un ciclo se
    detecta cuando se registra la referencia y se informa claramente, y una
    cadena muy profunda está acotada en lugar de seguirse indefinidamente.

## El indicador pasivo de rotura

Cuando cambias un recurso, cualquier cosa que lo referencie puede estar
apuntando ahora a contenido que ya no coincide. La biblioteca lo muestra de
forma **pasiva** — señala el problema, **no** bloquea tu edición:

- **Las roturas se señalan, nunca se bloquean.** Siempre puedes hacer el
  cambio; el indicador simplemente te dice que una referencia está ahora
  rota, para que decidas qué hacer. Nada se impide, y ningún diálogo modal te
  interrumpe.
- **Se actualiza con cada cambio del catálogo.** El indicador se reevalúa
  cada vez que cambia el catálogo o el grafo, así que siempre refleja el
  estado actual — nunca tienes que pedirle que vuelva a comprobar.
- **Se muestra en el lugar.** La vista del Grafo de dependencias muestra un
  resumen de roturas y un estado por referencia, y la lista de
  [Biblioteca de recursos](asset-library.md) lleva una columna de
  **Estado** para que un recurso roto sea visible justo donde lo exploras.

Una referencia se informa como rota por una de dos razones:

| Razón | Significado |
| --- | --- |
| **Falta** | el recurso referenciado ya no está en el catálogo (se eliminó). |
| **Desajuste de hash** | el recurso referenciado sigue presente, pero su contenido ha cambiado desde que se hizo la referencia. |

Un recurso cuyas referencias siguen siendo todas válidas no muestra ningún
indicador; solo se señala una referencia genuinamente rota, así que la
advertencia se mantiene significativa (sin falsos positivos).

## Accesibilidad, temas e idioma

Cada control de la vista del Grafo de dependencias tiene un nombre accesible
y es accesible desde el teclado, cada etiqueta es completamente traducible, y
la vista y la columna de Estado se renderizan correctamente en ambos temas,
claro y oscuro.

## Relacionado

El seguimiento de dependencias y la detección de roturas se construyen sobre
el catálogo de la [biblioteca de recursos](asset-library.md). La
capacidad complementaria — un **historial de versiones** de solo adición por
recurso, más **reutilización entre proyectos**, **exportación/importación** y
**respaldo opcional en la nube** — se documenta en
[Versionado de recursos y reutilización entre proyectos](asset-versioning.md).
Un recurso reutilizado es una referencia como cualquier otra, así que el
indicador de rotura descrito aquí señala una reutilización cuyo destino más
tarde falta o cambia.
