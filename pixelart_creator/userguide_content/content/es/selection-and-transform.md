# Selección y movimiento/copia flotante

Seleccionar una región te permite trabajar solo en parte de tu obra — y una
**selección flotante** te permite tomar los colores dentro de una selección activa y
moverlos — o copiarlos — como una **vista previa en vivo y no destructiva**. Los
píxeles *debajo* de la selección flotante **no cambian** hasta que confirmas, así que
un movimiento siempre es seguro de reposicionar o abandonar.

Este es el comportamiento que conoces de Aseprite, Pro Motion NG, Pixelorama y Krita:
levantar, arrastrar, soltar.

> **Solo la capa activa.** Un movimiento/copia flotante opera sobre la **capa
> activa** (consulta [el panel de capas](layers.md)). En un documento indexado, esa
> es la única capa indexada. Las demás capas no se ven afectadas.

## Hacer una selección

Usa las herramientas de selección para definir la región en la que quieres trabajar:

| Herramienta | Qué selecciona |
| --- | --- |
| **Rectángulo** | Una región rectangular que arrastras. |
| **Lazo** | Una región a mano alzada que dibujas alrededor. |
| **Varita mágica** | Un área contigua de color similar bajo el clic. |

Puedes refinar una selección con gestos modificadores mientras la construyes:

| Gesto | Resultado |
| --- | --- |
| Arrastre con **Shift** | **Añadir** a la selección actual. |
| Arrastre con **Alt** | **Restar** de la selección actual. |

## Levantar y mover (arrastrar)

La selección flotante levanta la selección que ya está activa — **no** crea una
nueva forma de selección, reutiliza la máscara que ya tienes.

1. Con la herramienta de selección/movimiento activa, **presiona dentro** de la
   selección activa. Los píxeles enmascarados se levantan en una vista previa
   flotante.
2. **Arrastra.** Los colores flotantes siguen al cursor; la región de origen se lee
   como **borrada a transparente** (índice 0 en modo indexado) en la vista previa en
   vivo.
3. Los píxeles subyacentes **aún no se modifican** — solo cambia la vista previa.

Presionar **fuera** de la selección activa **no** levanta la selección; inicia una
nueva selección como de costumbre.

## Copiar en lugar de mover: mantén pulsado Ctrl

Mantén pulsado **Ctrl** mientras arrastras para cambiar la selección flotante a
**COPIAR**:

- el **origen permanece intacto** (no se vacía nada), y
- una **copia** de los colores flota hacia el cursor.

Un cursor/indicador de modo copia señala que estás copiando. Puedes alternar entre
mover y copiar **durante** el arrastre pulsando o soltando Ctrl.

> **Ctrl es el único modificador de copia — no Alt.** Copiar es **solo con Ctrl**.
> **Alt no es un modificador de copia**: un arrastre interior con Alt es el gesto de
> **restar** de la construcción de selección, y conserva ese significado. Mantener
> **Ctrl+Alt** en un arrastre interior se resuelve como restar con Alt, no como
> copiar — usa solo **Ctrl** para copiar.

| Arrastre interior | Resultado |
| --- | --- |
| *sin modificador* | Levantar/**mover** la selección (el origen se vacía al confirmar) |
| **Ctrl** | **Copiar** la selección (el origen se conserva) |
| **Alt** | **Restar** de la selección (gesto de construcción) |
| **Shift** | **Añadir** a la selección (gesto de construcción) |

## Confirmar o cancelar

La selección flotante se **confirma** con cualquiera de estos:

- **soltar** el botón del ratón,
- pulsar **Enter/Intro**, o
- **cambiar de herramienta** (o cambiar de pestaña de lienzo).

Al confirmar, el cambio se aplica como **exactamente un paso deshacible**:

- **Mover** — el origen se escribe como transparente (índice 0 en modo indexado) y
  los colores se estampan en el destino.
- **Copiar** — los colores se estampan en el destino y el origen queda sin cambios.

Después de confirmar, la máscara de selección **sigue hasta el destino**.

Pulsa **Esc** para **cancelar**. Como la selección flotante nunca escribió en el
búfer, cancelar restaura el lienzo previo al movimiento **exactamente** y no registra
**ninguna** entrada de deshacer; la máscara de selección vuelve a su posición previa
al levantamiento.

> **Un clic sin arrastre no cuesta nada.** Confirmar con un desplazamiento cero (un
> clic dentro de la selección sin mover) es una operación nula — no crea ningún paso
> de deshacer.

## Bordes fuera del lienzo

Puedes arrastrar una selección flotante **parcial o totalmente fuera del lienzo**. Al
confirmar, los píxeles fuera del lienzo se **descartan** (nunca se envuelven), así
que puedes empujar el arte hasta el borde sin errores. En un movimiento, todo el
origen dentro de los límites se vacía igualmente, sin importar cuánto hayas
arrastrado.

## Deshacer, rehacer y renderizado

- Un movimiento o copia confirmado es **un** paso de deshacer: **deshacer** restaura
  el búfer previo al movimiento exactamente; **rehacer** lo vuelve a aplicar.
- La vista previa flotante se renderiza con **vecino más cercano y antialiasing
  desactivado** a cualquier zoom, y es legible en ambos temas, claro y oscuro.
- La vista previa en vivo del arrastre actualiza solo la región que toca la
  selección flotante, así que se mantiene dentro del presupuesto de 16 ms / 60 fps
  incluso en un lienzo de 8K.

## Lo que no se cubre

- **Rotar o escalar** la selección *mientras flota* — confirma el movimiento primero,
  luego usa las herramientas de transformación.
- Una variante de **mover todas las capas** — la selección flotante es solo de la
  capa activa.
- Arrastre **entre documentos** de una selección flotante, o guardar una selección
  flotante en un `.pixproj` — una selección flotante es un estado de edición
  transitorio, siempre se confirma o se cancela primero.
