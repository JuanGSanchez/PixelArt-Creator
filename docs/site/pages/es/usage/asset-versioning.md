# Versionado de recursos y reutilización entre proyectos

La biblioteca de recursos mantiene un **historial de versiones de solo
adición** para cada recurso, te permite **reutilizar un recurso compartido en
varios proyectos sin duplicar sus bytes**, **exportar e importar** los
recursos que un proyecto referencia como un paquete autocontenido, y — cuando
conectas un proveedor de nube — **respaldar los blobs compartidos en la
nube** sin dejar de funcionar completamente sin conexión. Se accede a todo
esto desde el menú **&Biblioteca**, junto a los paneles de
[biblioteca de recursos](asset-library.md) y
[dependencias](dependency-graph.md) sobre los que se construyen.

!!! note "Referencia, no copia"
    Todo esto se apoya en una idea que ya usa la biblioteca: los bytes de un
    recurso se almacenan **una sola vez**, indexados por su contenido, en un
    almacén direccionable por contenido, y un proyecto solo guarda una
    **referencia** (un id estable más el hash de contenido que espera). El
    versionado, la reutilización y la exportación mueven referencias y
    verifican el contenido — nunca hacen una segunda copia de tu obra.

## Historial de versiones

Cada vez que registras un nuevo estado de un recurso, la biblioteca añade
una **revisión** al historial de ese recurso:

- **De solo adición e inmutable.** Una revisión nunca se cambia ni se
  elimina en su lugar. Registrar un nuevo estado añade una nueva revisión a
  la cabeza; las revisiones anteriores permanecen exactamente como estaban,
  así que el historial es un registro fiel de cómo evolucionó el recurso.
- **Direccionada por contenido.** Cada revisión se identifica por el
  **hash de contenido** de sus bytes y se enlaza con la revisión que la
  precedió, así que el historial forma una cadena direccionada por
  contenido. Dos revisiones con bytes idénticos comparten un único blob
  almacenado (deduplicación).
- **Registrar el mismo contenido dos veces no hace nada.** Si registras un
  contenido cuyo hash coincide con la cabeza actual, es una **operación
  nula** — no se añade ninguna revisión ni ningún blob nuevos. Es la misma
  prueba de "¿este recurso realmente cambió?" que la biblioteca usa en otras
  partes.
- **Acotado.** Un recurso conserva hasta un número máximo fijo de
  revisiones; superarlo se reporta con un error claro en lugar de descartar
  el historial silenciosamente.

### Explorar y restaurar revisiones

El **explorador de versiones de recursos** lista las revisiones del recurso
seleccionado en orden. Selecciona una para **inspeccionarla**, o
**restaura** una revisión anterior para volverla la actual de nuevo.

!!! tip "Restaurar añade una nueva revisión — nunca reescribe el historial"
    Restaurar una revisión anterior **no** elimina las revisiones
    posteriores a ella. En su lugar, el explorador vuelve a registrar los
    bytes (verificados por hash de contenido) de la revisión elegida como
    una **nueva** revisión de cabeza. El historial solo crece, así que
    siempre puedes retroceder de nuevo — restaurar es en sí mismo un paso
    deshacible y recuperable dentro del registro.

Al restaurar, el explorador también verifica los bytes de la revisión
contra el hash que el registro espera; un blob que ya no coincide con su
hash registrado se **rechaza con un error claro** (defensa ante manipulación
/ corrupción) en lugar de cargarse.

## Reutilización entre proyectos (referenciar, no copiar)

El panel de **reutilización de recursos** te permite **referenciar un
recurso compartido existente en otro proyecto**. Como la biblioteca
referencia los recursos en lugar de copiarlos, la reutilización no cuesta
nada en almacenamiento:

- **Referenciar no copia bytes.** Añadir un recurso compartido a un
  proyecto registra la referencia (su id estable y el hash de contenido
  esperado); los bytes compartidos siguen viviendo **una sola vez** en el
  almacén direccionable por contenido. El número de blobs almacenados
  **no cambia** al referenciar.
- **Los recursos compartidos se marcan.** Cuando más de un proyecto
  referencia el mismo recurso, el panel lo muestra como **Compartido**, así
  que puedes ver de un vistazo qué recursos se usan en varios lugares (y
  pensarlo dos veces antes de cambiar uno).
- **La presencia se comprueba, nunca se escribe.** Antes de referenciar un
  recurso compartido, el panel confirma que los bytes compartidos están
  realmente presentes; si faltan, reporta un error claro en lugar de crear
  una referencia colgante. Solo lee — nunca escribe una copia nueva.

!!! note "Por qué esto es seguro"
    La reutilización y el [grafo de dependencias](dependency-graph.md)
    trabajan juntos: un recurso reutilizado es una referencia como
    cualquier otra, así que el indicador pasivo de roturas señalará una
    reutilización cuyo objetivo más tarde desaparece o cambia — conservas el
    beneficio de compartir una única copia sin perder de vista qué depende
    de qué.

## Exportar e importar los recursos de un proyecto

**Exportar** empaqueta exactamente los recursos que un proyecto referencia
en un **artefacto autocontenido y portable** para que el proyecto se abra
completo en otra máquina; **importar** trae de vuelta ese paquete.

- **Exactamente los recursos referenciados — ni más ni menos.** Exportar
  resuelve el conjunto de referencias del proyecto y empaqueta precisamente
  los blobs de esos recursos, cada uno almacenado una vez por contenido, más
  un índice de catálogo y complementos por recurso. No se incluye nada que
  el proyecto no referencie, y no se omite nada que sí referencie.
- **Reutiliza el formato de proyecto ya distribuido.** El paquete compone
  la maquinaria de catálogo y `.pixproj` existente — no hay un formato
  nuevo que aprender, y el paquete hereda la ruta de carga normal y
  defensiva de la aplicación.
- **Importar es defensivo.** Un paquete se trata como **entrada no
  confiable** al importar: se analiza sin ejecutar nada, se comprueban su
  tamaño y forma, y **se confirma que cada ruta permanece dentro del
  paquete** (defensa contra path-traversal). Cada blob se **verifica por
  hash de contenido** al leerse, así que un paquete manipulado o corrupto se
  rechaza con un error claro en lugar de cargarse.

## Respaldo opcional en la nube

Por defecto la biblioteca almacena cada blob **localmente** y funciona
**completamente sin conexión**. Si conectas un proveedor de nube (consulta
[Nube, versiones y recuperación](cloud.md)), la biblioteca también puede
**respaldar los blobs compartidos en la nube** — sin cambiar nada de cómo la
usas:

- **Local por defecto.** Cuando no hay ningún proveedor conectado, la
  biblioteca es puramente local; la nube se activa **solo cuando un
  proveedor está conectado**. Nada del versionado, la reutilización o la
  exportación requiere la nube.
- **La misma interfaz de almacenamiento.** El respaldo en la nube es
  simplemente otro backend de blobs detrás de la misma interfaz que usa el
  almacén local, así que el catálogo, las revisiones y la reutilización se
  comportan de forma idéntica, ya sea el respaldo local o compartido — nunca
  llegan a saber que hay un proveedor involucrado.
- **Los datos de la nube se verifican y se almacenan en caché.** Un blob
  obtenido de la nube se **verifica por hash de contenido** antes de
  usarse (la nube es entrada no confiable, exactamente igual que un archivo
  local), y luego se almacena en caché localmente para que las lecturas
  posteriores se mantengan sin conexión.
- **No se filtra ningún detalle del proveedor.** Ningún nombre de
  proveedor, credencial o tipo de SDK aparece en la biblioteca — el
  respaldo en la nube depende únicamente de la misma interfaz de nube
  agnóstica de proveedor que usa el resto de la aplicación.

## Accesibilidad, temas e idioma

Todo control del explorador de versiones y del panel de reutilización tiene
un nombre accesible y es alcanzable desde el teclado, todas las etiquetas
son completamente traducibles, y ambos paneles se renderizan correctamente
en los temas claro y oscuro.

## Fase 11 completa

Con el control de versiones, la reutilización entre proyectos, la
exportación/importación y el respaldo opcional en la nube, el hito de
**gestión de equipo y recursos** queda completamente entregado: catálogo,
etiquetas y búsqueda ([biblioteca de recursos](asset-library.md)); el grafo
de dependencias y la detección pasiva de roturas
([dependencias de recursos](dependency-graph.md)); y el versionado, la
reutilización y la portabilidad cubiertos aquí.
