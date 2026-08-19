# Múltiples lienzos (mesas de trabajo)

Puedes abrir varios documentos / mesas de trabajo a la vez, cada uno en su
propia **pestaña**.

## Pestañas aisladas

Cada lienzo abierto está totalmente **aislado en su estado**. Una pestaña
tiene su propio(a):

- árbol de capas (capas, grupos, máscaras, capas de referencia / inteligentes);
- paleta y modo de color;
- historial de deshacer / rehacer (`QUndoStack`);
- vista compuesta y geometría del lienzo.

Cambiar a una pestaña convierte ese lienzo en el contexto activo — su árbol de
capas, paleta, pila de deshacer y composición pasan a ser los actuales, y el
panel de capas se repuebla para coincidir con él.

Como las pestañas están aisladas, una operación en un lienzo **nunca** afecta
a otro: pintar, cambiar atributos de capa, reordenar, agrupar o deshacer en la
pestaña A deja intactos el árbol, la composición y el historial de deshacer de
la pestaña B.

## Trabajar entre mesas de trabajo

- Cada mesa de trabajo puede tener un tamaño de lienzo, una paleta y un modo
  de color distintos.
- Deshacer es por pestaña: deshacer no alcanza a otras mesas de trabajo.
- Guardar un documento escribe el árbol de capas propio de esa pestaña en su
  archivo `.pixproj`.

!!! tip
    Usa mesas de trabajo separadas para variantes del mismo sprite (por
    ejemplo, cambios de color o poses) para que sus historiales de edición se
    mantengan independientes.
