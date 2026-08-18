# El centro de color al clic derecho

El **centro de color** es un menú contextual que invocas **justo donde estás
trabajando**: haz **clic derecho** en el lienzo y se abre en el cursor. Te ofrece dos
formas rápidas de elegir un color — una lista de **Favoritos** seleccionada y una
**rueda de color** completa con **armonías de teoría del color** en vivo — y aplica tu
elección de inmediato.

## Abrir el centro

Haz clic derecho en cualquier parte del [lienzo](canvas-and-view.md). El centro de
color aparece anclado en el cursor, así que nunca tienes que ir a un panel lejano
para cambiar de color. Elige un color y se convierte de inmediato en el **color
activo**; la muestra activa se actualiza para reflejarlo.

## Favoritos

**Favoritos** es tu lista personal y persistente de colores de referencia.

- **Añade** el color actual a Favoritos para tenerlo a un clic la próxima vez.
- **Elimina** un color que ya no necesites.
- **Reordena** los favoritos para que los colores que más usas estén primero.

Tu lista de Favoritos **persiste** entre sesiones, así que tu paleta de trabajo
siempre está ahí cuando vuelves a abrir la aplicación. Hacer clic en un favorito lo
aplica de inmediato.

## La rueda de color

La **rueda de color** es una rueda RGB estilo Canva para elegir cualquier color por
tono y saturación, con un control de valor (brillo). A medida que te mueves por la
rueda, el color activo se actualiza en vivo.

## Armonías de teoría del color en vivo

Mientras eliges en la rueda, el centro muestra **muestras de armonía** derivadas de tu
color actual usando la teoría del color estándar, así puedes construir una paleta
coherente sin adivinar:

| Armonía | Relación con tu color |
| --- | --- |
| **Complementario** | El tono opuesto (+180°) — contraste máximo. |
| **Análogo** | Los vecinos (±30°) — esquemas tranquilos y cohesivos. |
| **Triádico** | Dos tonos a 120° de distancia (±120°) — equilibrado y vibrante. |
| **Complementario dividido** | Los dos tonos a cada lado del complementario (±150°). |
| **Rampas de sombra / tinte** | Pasos más oscuros (sombra) y más claros (tinte) de tu color. |

Haz clic en cualquier muestra de armonía para convertirla en el color activo, o
añádela a Favoritos. Las armonías se recalculan en vivo mientras te mueves por la
rueda.

## Aplicar y guardar

- **Aplicar** — el color elegido se activa de inmediato y la muestra activa lo
  refleja, así que tu próximo trazo lo usará.
- **Guardar en Favoritos** — conserva un color que te guste para más adelante.

## Paletas y documentos indexados

El centro de color funciona junto a la **paleta** de tu documento. En un documento
**indexado** la paleta es el conjunto fijo de colores que usa la obra; puedes cargar
paletas soltando un archivo `.gpl`, `.hex` o `.pal` sobre la ventana (consulta
[Importar arrastrando y soltando](drag-drop-import.md)). Reemplazar la paleta es un
único paso deshacible.

## Temas relacionados

- Pinta con el color elegido en [el lienzo](canvas-and-view.md).
- Gestiona el modo de color (RGBA frente a indexado) en
  [El panel de capas](layers.md).
