# Versionado de recursos y reutilización entre proyectos

La biblioteca de recursos mantiene un **historial de versiones de solo adición**
para cada recurso, te permite **reutilizar un recurso compartido en varios
proyectos sin duplicar sus bytes**, **exportar e importar** los recursos que un
proyecto referencia como un paquete autónomo, y — cuando conectas un proveedor de
nube — **respaldar los blobs compartidos en la nube** mientras sigues trabajando
totalmente sin conexión. Todo esto se accede desde el menú **Biblioteca**, junto a
los paneles de [biblioteca de recursos](asset-library.md) y
[dependencias](asset-dependencies.md) sobre los que se construyen.

> **Referencia, no copia.** Todo esto se apoya en una idea que la biblioteca ya
> usa: los bytes de un recurso se almacenan **una vez**, con clave según su
> contenido, en un almacén direccionable por contenido, y un proyecto solo
> mantiene una **referencia** (un id estable más el hash de contenido que espera).
> El versionado, la reutilización y la exportación mueven referencias y verifican
> contenido — nunca hacen una segunda copia de tu obra.

## Historial de versiones

Cada vez que registras un nuevo estado de un recurso, la biblioteca añade una
**revisión** al historial de ese recurso:

- **De solo adición e inmutable.** Una revisión nunca se cambia ni elimina en su
  sitio. Registrar un nuevo estado añade una nueva revisión a la cabeza; las
  revisiones anteriores permanecen exactamente como estaban, así que el historial
  es un registro fiel de cómo evolucionó el recurso.
- **Direccionado por contenido.** Cada revisión se identifica por el **hash de
  contenido** de sus bytes y se enlaza a la revisión que siguió, así que el
  historial forma una cadena direccionada por contenido. Dos revisiones con bytes
  idénticos comparten un único blob almacenado (deduplicación).
- **Registrar el mismo contenido dos veces no hace nada.** Si registras contenido
  cuyo hash coincide con la cabeza actual, es una **operación nula** — no se añade
  ninguna revisión ni blob nuevos.
- **Acotado.** Un recurso mantiene hasta un número máximo fijo de revisiones;
  superarlo se informa con un error claro en lugar de descartar el historial en
  silencio.

### Explorar y restaurar revisiones

El **Explorador de versiones de recursos** lista las revisiones del recurso
seleccionado en orden. Selecciona una para **inspeccionarla**, o **restaura** una
revisión anterior para volver a hacerla actual.

> **Restaurar añade una revisión nueva — nunca reescribe el historial.**
> Restaurar una revisión anterior **no** elimina las revisiones que llegaron
> después de ella. En su lugar, el explorador vuelve a registrar los bytes
> (verificados por hash de contenido) de la revisión elegida como una nueva
> revisión **cabeza**. El historial solo crece, así que siempre puedes retroceder
> de nuevo.

Al restaurar, el explorador también verifica los bytes de la revisión contra el
hash que espera el registro; un blob que ya no coincide con su hash registrado se
**rechaza con un error claro** (defensa contra manipulación/corrupción) en lugar
de cargarse.

## Reutilización entre proyectos (referenciar, no copiar)

El panel de **Reutilización de recursos** te permite **referenciar un recurso
compartido existente en otro proyecto**. Como la biblioteca referencia recursos en
lugar de copiarlos, la reutilización no cuesta nada en almacenamiento:

- **Referenciar no copia bytes.** Añadir un recurso compartido a un proyecto
  registra la referencia; los bytes compartidos siguen viviendo **una vez** en el
  almacén direccionable por contenido. El recuento de blobs almacenados
  **no cambia** al referenciar.
- **Los recursos compartidos están marcados.** Cuando más de un proyecto
  referencia el mismo recurso, el panel lo muestra como **Compartido**, así puedes
  ver qué recursos se usan en varios lugares.
- **La presencia se comprueba, nunca se escribe.** Antes de referenciar un recurso
  compartido, el panel confirma que los bytes compartidos están realmente
  presentes; si faltan, informa de un error claro en lugar de crear una referencia
  colgante. Solo lee — nunca escribe una copia nueva.

> **Por qué es seguro.** La reutilización y el
> [grafo de dependencias](asset-dependencies.md) trabajan juntos: un recurso
> reutilizado es una referencia como cualquier otra, así que el indicador pasivo de
> rotura señalará una reutilización cuyo destino desaparezca o cambie más
> adelante.

## Cuando cambia un recurso compartido

Abrir un proyecto que referencia un recurso de biblioteca que ha sido editado desde
entonces muestra el aviso **Recurso de biblioteca actualizado** (*Library Asset
Updated*), una vez por cada recurso cambiado:

- **Adoptar el cambio** (*Pick Up the Change*) resuelve a partir de ahora el
  contenido actual del recurso en la biblioteca; la referencia del proyecto pasa a
  la última revisión de la biblioteca.
- **Mantener la versión referenciada** (*Keep the Referenced Version*) sigue
  resolviendo exactamente el contenido que el proyecto ya referencia — nada de la
  referencia cambia.

Cancelar o cerrar el aviso se comporta igual que **Mantener la versión
referenciada**. Marcar **No volver a preguntar** al elegir cualquiera de las dos
opciones recuerda esa elección para futuras ediciones de este recurso, en este
proyecto; puedes restaurar el aviso más tarde desde **Editar → Confirmaciones del
proyecto → Cuando cambia un recurso de biblioteca referenciado**.

## Exportar e importar los recursos de un proyecto

**Exportar paquete de proyecto** (*Export Project Bundle*) empaqueta exactamente los
recursos que un proyecto referencia en un **artefacto autónomo y portable** para que el
proyecto se abra completo en otra máquina; **Importar paquete de proyecto** (*Import
Project Bundle*) trae de vuelta un paquete de esos. Ambos comandos se acceden desde el
menú **Biblioteca**.

- **Exactamente los recursos referenciados — ni más ni menos.** Exportar resuelve
  el conjunto de referencias del proyecto y empaqueta precisamente los blobs de
  esos recursos, cada uno almacenado una vez por contenido, más un índice de
  catálogo y complementos por recurso.
- **Reutiliza el formato de proyecto ya existente.** El paquete compone la
  maquinaria de catálogo y proyecto existente — no hay un formato nuevo que
  aprender.
- **La importación es defensiva.** Un paquete se trata como **entrada no
  confiable**: se analiza sin ejecutar nada, se comprueba por tamaño y forma, y
  **se confirma que cada ruta permanece dentro del paquete** (defensa contra
  traversal de rutas). Cada blob se **verifica por hash de contenido** al leerlo,
  así que un paquete manipulado o corrupto se rechaza con un error claro.

## Respaldo opcional en la nube

Por defecto, la biblioteca almacena cada blob **localmente** y funciona
**totalmente sin conexión**. Si conectas un proveedor de nube (consulta
[Nube, versiones y recuperación](cloud-and-collaboration.md)), la biblioteca también
puede **respaldar los blobs compartidos en la nube** — sin cambiar nada de cómo la
usas:

- **Local primero.** Cuando no hay ningún proveedor conectado, la biblioteca es
  puramente local; la nube se activa **solo cuando hay un proveedor conectado**.
- **La misma interfaz de almacenamiento.** El respaldo en la nube es solo otro
  backend de blobs detrás de la misma interfaz que usa el almacén local, así que
  el catálogo, las revisiones y la reutilización se comportan de forma idéntica,
  sea el respaldo local o compartido.
- **Los datos de la nube se verifican y se almacenan en caché.** Un blob obtenido
  de la nube se **verifica por hash de contenido** antes de usarse, y luego se
  guarda en caché localmente para que las lecturas posteriores sigan siendo sin
  conexión.
- **No se filtra ningún detalle de proveedor.** Ningún nombre de proveedor,
  credencial o tipo de SDK aparece en la biblioteca — el respaldo en la nube
  depende solo de la misma interfaz de nube agnóstica de proveedor que usa el
  resto de la aplicación.

## Accesibilidad, temas e idioma

Cada control del explorador de versiones y del panel de reutilización tiene un
nombre accesible y es accesible desde el teclado, todas las etiquetas son
completamente traducibles, y ambos paneles se renderizan correctamente en los
temas claro y oscuro.
