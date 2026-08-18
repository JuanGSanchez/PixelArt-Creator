# Múltiples lienzos (artboards)

Puedes tener abiertos varios documentos/artboards a la vez, cada uno en su propia
**pestaña**.

## Pestañas aisladas

Cada lienzo abierto está completamente **aislado en cuanto a estado**. Una pestaña
tiene su propio:

- árbol de capas (capas, grupos, máscaras, capas de referencia/inteligentes);
- paleta y modo de color;
- historial de deshacer/rehacer;
- vista compuesta y geometría del lienzo.

Cambiar a una pestaña convierte ese lienzo en el contexto activo — su árbol de capas,
paleta, pila de deshacer y composición pasan a ser los actuales, y el panel de capas
se repuebla para reflejarlo.

Como las pestañas están aisladas, una operación en un lienzo **nunca** afecta a otro:
pintar, cambiar atributos de capa, reordenar, agrupar o deshacer en la pestaña A deja
intactos el árbol, la composición y el historial de deshacer de la pestaña B.

## Trabajar entre artboards

- Cada artboard puede tener un tamaño de lienzo, paleta y modo de color diferentes.
- Deshacer es por pestaña: deshacer no alcanza a otros artboards.
- Guardar un documento escribe el árbol de capas propio de esa pestaña en su archivo
  `.pixproj`.

> **Consejo.** Usa artboards separados para variantes del mismo sprite (por ejemplo,
> cambios de color o poses) para que sus historiales de edición se mantengan
> independientes.

## Múltiples *lienzos* frente a múltiples *vistas*

Los múltiples lienzos son pestañas **aisladas** — cada una un documento *diferente*.
Eso es distinto de la **multivista**, que abre varias ventanas sobre **un** documento
compartido que se mantienen sincronizadas. Consulta
[Ayudas visuales y experiencia de usuario](visual-aids.md) para la edición multivista.
