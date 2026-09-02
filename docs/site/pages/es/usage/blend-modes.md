# Modos de fusión

Cada capa (y grupo) se compone usando un **modo de fusión** elegido en el
desplegable por capa. PixelArt Creator incluye **doce** modos — **Normal** más
los once modos no normales **separables** de la especificación W3C
*Compositing and Blending Level 1* (el mismo conjunto y los mismos resultados
que Photoshop / Krita / SVG).

La fusión se realiza sobre **alfa recto (no premultiplicado)** en un espacio
de trabajo normalizado de coma flotante, y luego se escribe de vuelta a RGBA
de 8 bits. **Normal** es composición alfa recta *source-over*.

## Los doce modos

| Modo | Efecto |
| --- | --- |
| **Normal** | Alfa recto *source-over*. Una capa totalmente opaca reemplaza lo que hay debajo; una capa totalmente transparente lo deja sin cambios. |
| **Multiplicar** | Multiplica la capa con lo que hay debajo — siempre oscurece. El blanco es neutro; el negro produce negro. |
| **Trama** | Inversa de multiplicar — siempre aclara. El negro es neutro; el blanco produce blanco. |
| **Superponer** | Multiplica en los tonos oscuros, trama en los tonos claros — aumenta el contraste (relativo a lo que hay debajo). |
| **Oscurecer** | Conserva el valor más oscuro de los dos canales. |
| **Aclarar** | Conserva el valor más claro de los dos canales. |
| **Sobreexponer color** | Aclara lo que hay debajo para reflejar la capa; aclarado intenso. |
| **Subexponer color** | Oscurece lo que hay debajo para reflejar la capa; oscurecimiento intenso. |
| **Luz fuerte** | Superponer con los roles de capa y fondo intercambiados — un foco de luz duro. |
| **Luz suave** | Una luz fuerte más suave — sobreexposición/subexposición suave según el valor de la capa. |
| **Diferencia** | Diferencia absoluta entre los dos valores — colores iguales se cancelan a negro. |
| **Exclusión** | Como diferencia pero con menor contraste en los tonos medios. |

!!! note "La opacidad y el modo de fusión se combinan"
    La opacidad de una capa escala su contribución **en todos** los modos de
    fusión, no solo en Normal. Una capa oculta no aporta nada, sea cual sea el
    modo.

## Cómo se compone la pila

Las capas se componen de **abajo hacia arriba** sobre un resultado acumulado:
los píxeles de cada capa visible se funden sobre lo que hay debajo usando el
modo de fusión y la opacidad de esa capa (y su máscara, si tiene una). Una
pila de capas Normal es exactamente lo mismo que aplicar alfa recto
*source-over* de abajo hacia arriba. La composición nunca muta los búferes de
la capa de origen — es no destructiva.

Una sola edición recompone solo la **región afectada**, así que pintar en un
lienzo grande se mantiene fluido (consulta las
[notas de rendimiento](#rendimiento) más abajo).

## Rendimiento

En un lienzo de 8K (7680 × 4320), pintar un solo píxel recompone su pequeña
región sucia en aproximadamente **1 ms**, dentro del presupuesto de 16 ms /
60 fps con holgura. Algunas interacciones más pesadas con poco zoom —
arrastrar el deslizador de opacidad, o un cambio de atributo que repinta un
viewport grande a través de muchas capas — están actualmente limitadas por la
CPU y pueden superar el presupuesto; la composición completa por shader de
GPU es una mejora planificada para más adelante.

<!-- surface-only: site — la referencia al changelog asume un lector fuera de la app; la página equivalente del bundle termina el párrafo sin ella, por diseño -->

Consulta las **Limitaciones conocidas** del changelog para más detalles.
