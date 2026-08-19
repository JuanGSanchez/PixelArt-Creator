# Panel de capas

El **panel de capas** lista las capas y grupos del documento activo para el
fotograma actual y expone todos los controles por capa. Es la superficie
principal para la edición no destructiva.

## Leer la lista

- Las capas se muestran **de arriba a abajo en orden z**: la fila en la **parte
  superior de la lista es la parte superior de la pila** (se dibuja al final /
  al frente).
- Exactamente una fila es la **capa activa** — es el objetivo de las
  herramientas de pintura.
- Los **grupos** aparecen como nodos expandibles/colapsables que contienen a
  sus hijos.

## Controles por capa

Cada fila de capa expone:

| Control | Qué hace |
| --- | --- |
| **Deslizador de opacidad** | Establece la opacidad de la capa del **0 al 100 %** (asignado a `Layer.opacity` 0.0–1.0). Se aplica a todos los modos de fusión, no solo a Normal. |
| **Alternador de visibilidad** | Muestra u oculta la capa. Una capa oculta no aporta nada a la composición. |
| **Alternador de bloqueo** | Protege la capa contra la mutación de **píxeles**. En una capa bloqueada, pintar/rellenar/borrar se convierten en operaciones nulas; su opacidad, visibilidad, modo de fusión y orden aún se pueden cambiar. |
| **Desplegable de modo de fusión** | Elige uno de los doce [modos de fusión](blend-modes.md). |

!!! tip "El bloqueo protege solo los píxeles"
    Aún puedes enfocar una capa bloqueada, cambiar su opacidad, mostrarla/
    ocultarla y reordenarla. Bloquear solo impide pintar sobre sus píxeles.

## Gestionar capas

- **Añadir** — inserta una nueva capa vacía encima de la capa activa.
- **Eliminar** — borra la capa activa. Eliminar la **última** capa de un
  fotograma se rechaza.
- **Duplicar** — inserta una copia píxel a píxel, con los atributos copiados,
  encima del origen.
- **Arrastrar para reordenar** — arrastra una fila a una nueva posición para
  cambiar el orden z; el lienzo se recompone en el nuevo orden. Arrastrar
  dentro o fuera de un grupo reasigna la capa a otro padre.

## Grupos

- **Agrupar** envuelve las capas de nivel superior seleccionadas en un nuevo
  nodo de grupo.
- **Desagrupar** disuelve un grupo, promoviendo a sus hijos al padre en la
  posición del grupo.

Un grupo **compone primero a sus hijos**, y luego funde ese único resultado
aplanado sobre la pila usando la opacidad y el modo de fusión **propios del
grupo**. Un grupo con atributos predeterminados (Normal, 100 %) se compone de
forma idéntica a sus hijos desagrupados. Ocultar un grupo oculta todo su
subárbol. El anidamiento de grupos está acotado por `MAX_GROUP_NESTING_DEPTH`.

## Máscaras

Adjunta una **máscara** a una capa para modular su alfa de forma no
destructiva:

1. Añade una máscara a la capa seleccionada.
2. Selecciona la máscara para convertirla en el objetivo de pintura — pintar
   ahora edita el búfer de la máscara, no los píxeles de la capa.
3. Donde la máscara es 0 la capa está oculta; donde está al máximo la capa se
   muestra por completo; los valores intermedios son proporcionales.

Una máscara totalmente al máximo equivale a no tener máscara, y editar una
máscara nunca altera los píxeles propios de la capa. Adjuntar/eliminar una
máscara es deshacible.

## Capas de referencia

Marca una capa como capa de **referencia** para calcarla: permanece visible en
la composición pero **rechaza pintar** (las herramientas de pintura no hacen
nada sobre ella), como un bloqueo permanente con un propósito declarado. El
indicador es reversible.

## Capas inteligentes

Crea una **capa inteligente** a partir de una capa de origen seleccionada. La
capa inteligente es una instancia no destructiva que **refleja los píxeles del
origen** (de solo lectura) mientras mantiene su propia opacidad, visibilidad y
modo de fusión. Editar el origen actualiza cada instancia inteligente en la
siguiente recomposición; la capa inteligente no tiene píxeles propios
editables. (El comportamiento avanzado de objetos inteligentes — filtros en
vivo, objetos procedurales/de transformación, enlaces externos — es una
función de una fase posterior.)

## Todo es un paso de deshacer

Cada operación de capa expuesta por el panel — establecer opacidad/
visibilidad/bloqueo/modo de fusión, añadir/eliminar/duplicar/reordenar,
agrupar/desagrupar, adjuntar/eliminar máscara, marcar como referencia/
inteligente — se apila como **exactamente un** comando de deshacer. Deshacer
restaura el estado exacto anterior del árbol de capas.

## Modo de color y documentos indexados

La pila de capas y los modos de fusión se aplican a documentos **RGBA**. Los
documentos **indexados** son de una sola capa por diseño — el compositor es
solo RGBA.

- Convertir un documento **RGBA multicapa** a indexado **aplana la composición
  en una única capa indexada** (por fotograma). Esto es deshacible: deshacer
  restaura el árbol RGBA multicapa completo — grupos, máscaras, opacidad,
  modos de fusión, referencias y enlaces inteligentes — con exactitud.
- Convertir de vuelta a RGBA convierte la única capa indexada en una capa
  RGBA.

El modo de color del documento es la única fuente de verdad, así que lo que
muestra el lienzo, lo que se guarda en `.pixproj` y el indicador de modo
siempre concuerdan.
