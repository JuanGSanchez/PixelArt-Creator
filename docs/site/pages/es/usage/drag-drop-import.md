# Importar arrastrando y soltando

Arrastra un archivo directamente desde el explorador de archivos de tu sistema
operativo (Explorador de Windows, Finder de macOS, Nautilus de Linux) **hacia**
la ventana de PixelArt Creator y hará lo obvio para ese tipo de archivo. No hay
que pasar por Archivo ▸ Abrir — suéltalo en cualquier parte de la ventana y la
aplicación lo enruta **por tipo de archivo**, no por dónde en la ventana lo
soltaste.

!!! note "El enrutamiento es por tipo, nunca por el lugar donde sueltas"
    Una imagen *siempre* se abre como un documento nuevo, un `.pixproj`
    *siempre* se abre como un proyecto, y un archivo de paleta *siempre* se
    carga en la paleta activa — sin importar dónde de la ventana lo sueltes.
    En una sola operación puedes mezclar tipos e incluso soltar varios
    archivos a la vez.

## Soltar una imagen → una nueva pestaña de documento

Suelta un **`.png`, `.jpg`, `.jpeg`, `.bmp` o `.gif`** y se abre como una
**nueva pestaña de lienzo/documento** que pasa a estar activa. Se importa como
un documento nuevo, **no** como una capa en el documento que estás editando —
tu documento actual permanece intacto.

- El documento nuevo es **RGBA** con el ancho y alto propios de la imagen. Un
  PNG o GIF paletizado (indexado) se expande a RGBA al importarlo.
- Para un **GIF animado**, se importa el **primer fotograma**.
- La importación es **de solo lectura en disco** — soltar un archivo nunca
  modifica el origen.

!!! warning "Límite de tamaño de imagen"
    Una imagen mayor que el máximo del lienzo (**7680 × 4320**) se **rechaza**
    con un aviso de error — nunca se recorta ni escala silenciosamente.
    Conviértela o redimensiónala fuera de la aplicación primero.

## Soltar un `.pixproj` → abrir el proyecto (con protección de guardado)

Suelta un **`.pixproj`** y se abre como un proyecto.

Si el documento que estás editando actualmente tiene **cambios sin guardar**,
la aplicación primero muestra un aviso de **Guardar / Descartar / Cancelar**
para que nunca pierdas trabajo por accidente:

| Opción | Resultado |
| --- | --- |
| **Guardar** | Guarda el documento actual y luego abre el proyecto soltado. |
| **Descartar** | Abre el proyecto soltado sin guardar. |
| **Cancelar** | Cancela la apertura — nada cambia. |

Si el documento actual **no** tiene cambios sin guardar (o no hay ninguno
abierto), el proyecto se abre inmediatamente sin aviso.

## Soltar una paleta → cargarla en la paleta activa (deshacible)

Suelta un archivo de paleta **`.gpl` (GIMP), `.hex` (lista hexadecimal plana)
o `.pal` (texto JASC-PAL)** y sus colores **reemplazan** la paleta de tu
documento activo.

- El reemplazo es **un único paso deshacible**: un **Deshacer** restaura tu
  paleta anterior exactamente.
- Si no hay ningún documento abierto, soltar el archivo es una operación
  inocua sin efecto, con un breve aviso.

!!! note "¿Qué formatos de paleta?"
    El conjunto de paletas de la v1 son los formatos de **texto** habituales
    en pixel art: `.gpl`, `.hex` y `.pal`. Los formatos binarios de Adobe
    **`.aco`** y **`.aseprite`** **aún no están soportados** — están
    planificados para una iteración posterior y se informan como un tipo no
    compatible por ahora.

## Soltar varios archivos a la vez

Una operación de soltar múltiples archivos procesa cada uno **de forma
independiente, según su tipo, en el orden en que se soltaron**:

- varias imágenes → varias pestañas nuevas;
- un `.pixproj` se abre (respetando su protección de cambios sin guardar);
- las paletas se cargan una tras otra — la **última** paleta soltada es la que
  queda activa (cada una es su propio paso de deshacer).

Un archivo desconocido o ilegible en el lote se omite con un aviso; el resto
se sigue procesando. Soltar cero archivos no hace nada.

## Cuando un archivo no se puede importar

Arrastrar y soltar nunca hace fallar la aplicación:

- un **tipo no compatible** (por ejemplo un `.txt`, o una paleta
  `.aco`/`.aseprite`) se **ignora** con un aviso de estado breve y no
  bloqueante;
- una imagen **corrupta, indescodificable o demasiado grande**, una paleta
  **malformada**, o un `.pixproj` **inválido** muestra un **aviso de error**
  que nombra el archivo y el problema, y deja tu trabajo **exactamente como
  estaba** — sin pestañas a medio crear ni paletas a medio cargar.

Todos los avisos y notificaciones son **traducibles**, accesibles desde el
teclado y legibles en ambos temas, claro y oscuro.

## Lo que no se cubre

- **Importar como capa** — una imagen siempre se abre como un documento
  nuevo, nunca como una capa en el actual (un futuro "importar como capa"
  queda aplazado).
- **Importación indexada** de una imagen de origen paletizada — las imágenes
  se descodifican a RGBA; aplica *Convertir a indexado* después si quieres un
  documento indexado.
- **Importación de GIF animado** — solo se importa el primer fotograma.
- El lado de **exportación / guardado** de la canalización, y arrastrar un
  archivo **fuera** de la aplicación.
