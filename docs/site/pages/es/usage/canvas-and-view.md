# Navegación del lienzo: zoom y ajuste

El menú **Ver** reúne un pequeño conjunto de comandos que cambian cómo estás
*mirando* un documento — nunca el documento en sí. Hacer zoom, desplazar la
vista y ajustarla son acciones de **vista**: ninguna de ellas es un paso de
deshacer, y ninguna toca un solo píxel.

## Acercar y alejar

**Ver ▸ Acercar** (*Zoom In* en el código fuente) y **Ver ▸ Alejar** (*Zoom Out*
en el código fuente) — también disponibles como **Ctrl++** y **Ctrl+-** —
saltan entre los mismos puntos fijos de zoom del lienzo (100 %, 200 %, 400 %,
800 %, 1600 %, 3200 %, 6400 %): **Acercar** salta al siguiente punto y
**Alejar** salta al anterior.

## Ajustar al contenido

**Ver ▸ Ajustar al contenido** (*Fit to Content* en el código fuente,
REQ-IS-UI-018) hace zoom y centra la pestaña
activa en el **rectángulo delimitador de los píxeles pintados** del fotograma
actual — el rectángulo más pequeño que contiene todos los píxeles no
transparentes — en lugar del rectángulo completo del documento. Es el
homólogo con nombre, alcanzable por teclado y por lector de pantalla, del
gesto **Mayús+clic central** ya disponible en el lienzo (consulta la propia
página **El lienzo: zoom, desplazamiento y la cuadrícula** de la guía
integrada para ese gesto).

- Si el fotograma activo aún no tiene ningún píxel no transparente, o si no
  hay ningún documento vinculado (por ejemplo justo después de crear un
  lienzo en blanco), el comando recurre a ajustar el rectángulo completo del
  documento en lugar de fallar o no hacer nada.
- El zoom resultante queda acotado por el mínimo y el máximo de zoom de la
  plataforma, los mismos límites que respeta cualquier otra acción de zoom.
- Como el resto de comandos de esta sección, es una acción de **vista**: no
  se envía nunca a la pila de deshacer.

Es la herramienta a la que recurrir después de desplazar o alejar el zoom de
una pieza pequeña de obra en un lienzo grande — un solo comando devuelve el
área pintada a la vista con un tamaño razonable, sin tener que buscarla ni
alejar el zoom hasta ver el documento completo.

## Temas relacionados

- El resto del comportamiento de zoom, desplazamiento y cuadrícula del
  lienzo se cubre en la propia página **El lienzo: zoom, desplazamiento y la
  cuadrícula** de la guía integrada de la aplicación, accesible desde el
  menú de Ayuda.
