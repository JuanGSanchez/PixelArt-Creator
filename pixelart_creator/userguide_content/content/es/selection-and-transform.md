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

**Duración de la selección.** Cambiar a una de las tres herramientas de
selección de arriba siempre **descarta** la selección actual y empieza de
cero — una selección nueva nunca hereda la forma de la anterior. Cambiar a
cualquier otra herramienta (Lápiz, Borrador, Relleno, …) en cambio **conserva**
la selección actual, así que el dibujo enmascarado sigue funcionando: tus
trazos siguen recortados a la selección mientras pintas con otra herramienta.

Mientras una de las tres herramientas de selección de arriba está activa,
**Shift** y **Alt** significan algo distinto que en el resto del lienzo —
consulta [Desplazar frente a construir una selección](#desplazar-frente-a-construir-una-seleccion)
más abajo:

| Modificador | Resultado con una herramienta de selección activa |
| --- | --- |
| Arrastre con **Shift** | **Añadir** a la selección actual. |
| Arrastre con **Alt** | **Restar** de la selección actual. |

### Desplazar frente a construir una selección

| Gesto | Resultado |
| --- | --- |
| **Shift+left-drag** | Desplaza el lienzo — **excepto** con una herramienta de selección activa, donde en cambio **añade** a la selección, exactamente como describe la tabla de arriba. |

### Seleccionar todo el lienzo, invertir y deseleccionar

| Atajo | Acción |
| --- | --- |
| **Ctrl+A** | Selecciona todo el lienzo. |
| **Ctrl+I** | Invierte la selección actual. |
| **Ctrl+Shift+A** | Deselecciona (borra la selección actual). |

Vaciar el **contenido** de la selección (en vez de la selección en sí) es una
acción distinta con sus propios atajos, **Shift+Q** y **Delete** — consulta la
tabla de [Primeros pasos](app-basics.md).

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
| **Shift** | **Añadir** a la selección (gesto de construcción) — fuera de una herramienta de selección activa, **Shift+left-drag** desplaza el lienzo en vez de añadir; consulta [Desplazar frente a construir una selección](#desplazar-frente-a-construir-una-seleccion) más arriba. |

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

Si el destino ya tiene píxeles, un diálogo **¿Sobrescribir píxeles existentes?**
pregunta antes: **Continuar** aplica la confirmación como de costumbre, **Cancelar**
no aplica nada y deja la selección flotante activa en su desplazamiento actual.
Marcar **"No volver a preguntar para este proyecto"** solo registra la supresión
cuando realmente aceptas — marcarla y cancelar no registra nada.

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

## Transformaciones de documento completo

**Imagen ▸ Escalar…**, los dos giros de un cuarto de vuelta y los dos volteos
(horizontal y vertical) actúan sobre **todo el documento** — cada capa y máscara, en
cada fotograma — siempre que no haya nada seleccionado. Con una selección activa,
esas mismas acciones siguen transformando solo la región enmascarada de la capa
activa, igual que antes.

| Atajo | Acción |
| --- | --- |
| **Shift+H** | Voltea la selección (o todo el documento) horizontalmente. |
| **Shift+V** | Voltea la selección (o todo el documento) verticalmente. |

RotSprite es la única excepción: siempre transforma solo la capa activa, haya o no
selección, porque su giro nunca cambia las dimensiones del búfer y nunca necesitó
el alcance más amplio.

> **Las transformaciones grandes preguntan antes.** Cuando el resultado
> remuestreado más los búferes conservados para deshacer superarían juntos los
> 506,25 MiB (el equivalente a cuatro lienzos completos de 8K en RGBA), el diálogo
> **Confirmar transformación grande** indica la memoria proyectada exacta antes de
> ejecutar nada. **Cancelar** es el botón predeterminado, así que pulsar Intro
> **no** inicia la transformación — tienes que pulsar **Continuar** deliberadamente.
> Rechazar deja el documento completamente intacto y no apila nada en el historial
> de deshacer. Por debajo de ese umbral, el diálogo no aparece en absoluto.

Mientras se ejecuta una transformación de documento completo, el diálogo de
progreso **Transformando documento** la sigue búfer a búfer y se puede cancelar en
cualquier momento — el botón Cancelar, Escape o el control de cierre de la propia
ventana funcionan igual. Cancelar es atómico: el documento queda exactamente como
estaba y nada llega al historial de deshacer, sin importar cuántos búferes se
hubieran remuestreado ya.

## Lo que no se cubre

- **Rotar o escalar** la selección *mientras flota* — confirma el movimiento primero,
  luego usa las herramientas de transformación.
- Una variante de **mover todas las capas** — la selección flotante es solo de la
  capa activa.
- Arrastre **entre documentos** de una selección flotante, o guardar una selección
  flotante en un `.pixproj` — una selección flotante es un estado de edición
  transitorio, siempre se confirma o se cancela primero.
