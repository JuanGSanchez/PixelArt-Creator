# Nube: guardado, versiones y guardado automático

En esta versión la **capa de nube** funciona con un adaptador integrado, en
memoria, así que el historial de versiones y la copia autoguardada duran solo
hasta que cierras la aplicación; no te protegen de un fallo ni de un corte de
energía. Guarda una copia local del proyecto para todo lo que quieras
conservar. Dentro de ese límite, la capa de nube te permite **conectar**,
**guardar** el proyecto actual, **abrirlo** de nuevo, explorar un **historial
de versiones** y **restaurar** un guardado anterior, y mantener una **copia de
trabajo autoguardada** mientras trabajas.

Todo en esta guía se maneja desde el menú **Nube** de la barra de menús.

!!! note "Un único puerto agnóstico de proveedor — sin dependencia de uno solo"
    La aplicación nunca habla directamente con un proveedor específico. Todo el
    trabajo en la nube pasa por **una única interfaz agnóstica de proveedor**
    (el *puerto de nube*): conectar, guardar, abrir, listar versiones,
    restaurar y la ranura de guardado automático/recuperación. La aplicación se
    comporta **de forma idéntica** sin importar qué proveedor la respalde, así
    que no estás atado a uno, y un proveedor nuevo es solo un nuevo adaptador
    detrás del mismo puerto. Consulta **ADR-0026** (diseño del puerto de nube)
    para la arquitectura.

!!! success "Lo que funciona en esta versión, y lo que no se conecta"
    Lo que funciona: el puerto agnóstico de proveedor, un adaptador integrado
    totalmente probado, el ciclo completo de `.pixproj` en la nube, historial de
    versiones + restauración y guardado automático (Fragmento A); los
    **proyectos compartidos, comentarios y presencia** (Fragmento B — consulta
    la guía de [Proyectos compartidos y comentarios](collaboration.md)), que se
    ejecutan en un adaptador en memoria dentro de una sola ventana de la
    aplicación, así que otra ventana o la copia de otra persona no pueden verlos;
    y la **ramificación de arte** local (Fragmento C). Lo que no se conecta: la
    **coedición en tiempo real y los cursores en vivo** no pueden conectarse, y
    los **proveedores reales de Google Drive / OneDrive / Dropbox** (Fragmento C)
    están implementados en la capa de almacenamiento, pero no se pueden elegir
    desde el menú Nube. Los proveedores se tratan en
    [Conectar un proveedor de nube real](#conectar-un-proveedor-de-nube-real)
    más abajo.

## Conectar un proveedor de nube

Las acciones de nube están desactivadas hasta que te conectas.

1. Abre el menú **Nube**.
2. Elige **Conectar…**. Esto conecta el adaptador integrado a través del
   puerto de nube y activa el resto del menú Nube (**Guardar en la nube…**,
   **Abrir desde la nube…**, **Historial de versiones…** y **Desconectar**).
3. Para cerrar sesión, elige **Nube ▸ Desconectar**. Esto libera la conexión y
   vuelve a desactivar las acciones de nube hasta que te conectes de nuevo.

!!! note "Tus credenciales nunca salen de la capa de almacenamiento"
    Cuando se usa un adaptador de proveedor real, el flujo de inicio de sesión
    (OAuth) se ejecuta **enteramente dentro de la capa de almacenamiento** — la
    aplicación solo abre tu navegador del sistema por ti. Los tokens **nunca**
    se muestran a la interfaz, **nunca** se escriben en un `.pixproj`, y
    **nunca** se escriben en logs. La interfaz solo ve un estado simple de
    *conectado / no conectado* (`REQ-P10-DATA-008`).

!!! tip "El adaptador integrado"
    La conexión de esta versión es un adaptador integrado, en memoria, que es
    determinista y no necesita red ni cuenta — hace que todo el flujo de
    guardado / versiones sea utilizable dentro de una sesión. Como vive en
    memoria, todo lo que contiene desaparece al cerrar la aplicación. Los
    proveedores reales en línea se describen en
    [Conectar un proveedor de nube real](#conectar-un-proveedor-de-nube-real),
    pero no se pueden elegir desde el menú Nube en esta versión.

## Conectar un proveedor de nube real

La capa de almacenamiento contiene proveedores **reales** de Google Drive,
OneDrive y Dropbox que se sitúan detrás del **mismo** puerto de nube que el
adaptador integrado. Cuando se usa uno de estos proveedores, los pasos de esta
guía (guardar, abrir, historial de versiones) funcionan igual sobre tu
almacenamiento en línea (`REQ-P10-DATA-001`, `-007`). Esta versión no tiene
ningún comando del menú Nube que seleccione uno: **Conectar…** conecta el
adaptador integrado.

!!! note "Función protegida por credenciales"
    Los proveedores reales están **protegidos por credenciales**: cada uno
    necesitaría un **id de cliente** OAuth para el servicio elegido y acceso a
    la red en vivo, así que no están activados por defecto, y esta versión no
    tiene ningún comando del menú Nube que active uno (se ejercen manualmente,
    fuera de la comprobación automática de CI). El adaptador integrado de arriba
    no necesita nada de esto.

### Cómo funciona el inicio de sesión

1. Al usar un proveedor de la capa de almacenamiento se inicia el flujo de
   acceso del proveedor. **Nube ▸ Conectar…** no lo hace en esta versión:
   conecta el adaptador integrado.
2. Ese flujo abre tu **navegador del sistema** en la página de inicio de
   sesión / consentimiento del proveedor. PixelArt Creator usa el flujo
   estándar de escritorio **código de autorización OAuth + PKCE sobre una
   redirección loopback** — no hay **ninguna vista web integrada** ni **ningún
   secreto de cliente** almacenado en la aplicación.
3. Aprueba el acceso en el navegador. El navegador redirige de vuelta a la
   aplicación, que completa la conexión. Las acciones de guardar / abrir /
   versiones del menú Nube se activan entonces igual que para el adaptador
   integrado.
4. Para cerrar sesión, elige **Nube ▸ Desconectar**.

!!! warning "Tus credenciales nunca salen de la capa de almacenamiento"
    Todo el inicio de sesión se ejecuta **enteramente dentro de la capa de
    almacenamiento**. Tu **token de actualización se almacena en el llavero
    del sistema operativo** (con clave por proveedor); el token de acceso de
    corta duración se mantiene solo en memoria y se renueva automáticamente.
    Los tokens **nunca** se muestran a la interfaz, **nunca** se escriben en un
    `.pixproj`, y **nunca** se escriben en logs (`REQ-P10-DATA-008`). El resto
    de la aplicación solo ve un estado simple de *conectado / no conectado*.

!!! note "Mismo comportamiento, cualquier proveedor"
    Como todos los proveedores están detrás del mismo puerto de nube, guardar y
    explorar versiones funcionan igual tanto si los respalda el adaptador
    integrado como Drive / OneDrive / Dropbox. Ese es el diseño sin dependencia
    de un solo proveedor (`REQ-P10-DATA-007`); elegir un proveedor desde el menú
    Nube no está disponible en esta versión.

## Guardar un proyecto en la nube

1. Con un proyecto abierto y un proveedor conectado, elige **Nube ▸ Guardar en
   la nube…**.
2. Introduce un **nombre de proyecto en la nube** cuando se te pida. Esta es
   la clave bajo la que se almacena tu proyecto; reutiliza el mismo nombre
   para seguir añadiendo versiones al mismo proyecto.
3. La aplicación serializa el proyecto a un `.pixproj` y lo almacena como una
   **versión nueva**. Cuando termina, la barra de estado muestra *"Guardado en
   la nube."*

Cada guardado se transporta como un `.pixproj` completo — el **mismo** formato
de guardado validado y versionado que se usa para archivos locales. La capa de
nube no añade ningún formato nuevo propio; simplemente transporta el
`.pixproj` como la *unidad de sincronización* atómica (`REQ-P10-DATA-002`).

!!! note "Guardar nunca congela la aplicación"
    La serialización + subida se ejecutan **fuera del hilo de la interfaz**,
    así que la ventana permanece receptiva incluso para un proyecto grande (de
    hasta 8K) — puedes seguir trabajando mientras se completa un guardado
    (`REQ-P10-UI-005`).

!!! warning "Cada guardado es una versión nueva"
    Guardar **no** sobrescribe el guardado anterior en la nube — añade una
    entrada nueva al historial de versiones (más abajo). El historial se
    limita a las **100** versiones más recientes por proyecto.

## Abrir un proyecto desde la nube

1. Elige **Nube ▸ Abrir desde la nube…**.
2. Introduce el **nombre del proyecto en la nube** a abrir.
3. La aplicación obtiene la última versión del proyecto y la abre en una
   **pestaña nueva**.

Abrir **no** reemplaza ni perturba lo que estés trabajando actualmente — el
proyecto de la nube llega como su propia pestaña.

!!! warning "Los archivos de la nube se tratan como no confiables"
    Un `.pixproj` obtenido de la nube se valida de forma defensiva exactamente
    igual que un archivo local: cada campo se comprueba por tipo y límites, la
    carga útil tiene un tope de tamaño, y un archivo malformado, demasiado
    grande o de versión desconocida se rechaza con un **error claro** — nunca
    con un fallo y **nunca** ejecutando código del archivo
    (`REQ-P10-DATA-006`). Si un proyecto obtenido no se puede validar, obtienes
    un diálogo de advertencia y tu trabajo actual queda intacto.

## Explorar el historial de versiones y restaurar una versión

Cada guardado crea una versión nueva y ordenada, y puedes volver a cualquiera
de ellas.
El historial de versiones dura solo la sesión actual: el adaptador integrado lo
mantiene en memoria y empieza vacío la próxima vez que inicies la aplicación.
Guarda una copia local del proyecto para todo lo que quieras conservar.

1. Elige **Nube ▸ Historial de versiones…** (si no has abierto ni guardado un
   proyecto en la nube en esta sesión, primero se te pedirá el nombre del
   proyecto en la nube).
2. El diálogo de **Historial de versiones en la nube** lista cada versión
   almacenada, de la más antigua a la más reciente, con estas columnas:
    - **Versión** — el ordinal / identificador de la versión.
    - **Marcador** — el marcador de orden de la versión.
    - **Tamaño (bytes)** — el tamaño del `.pixproj` almacenado.
    - **Fijada** — si la versión está fijada (conservada) — *Sí* / *No*.
    - **Padre** — la versión a la que siguió este guardado.
3. Selecciona una versión para ver sus detalles en el área de vista previa
   debajo de la lista.
4. Haz clic en **Restaurar** (o doble clic en la fila, o pulsa **Enter**) para
   traer de vuelta esa versión.

!!! note "Restaurar es seguro — abre una pestaña nueva"
    Restaurar una versión anterior la obtiene y valida, y luego la abre en una
    **pestaña nueva**. **No** sobrescribe tu trabajo actual ni tu último
    guardado en la nube — tú decides qué hacer con la copia restaurada
    (`REQ-P10-UI-002`).

La lista de versiones se obtiene fuera del hilo de la interfaz antes de que se
abra el diálogo, así que explorar el historial nunca congela la aplicación.

## Guardado automático y la ranura de recuperación

Mientras trabajas en un proyecto conectado, la aplicación **guarda
automáticamente** tu copia de trabajo en una **ranura de recuperación**
dedicada en segundo plano. En esta versión la ranura se mantiene solo en
memoria, así que protege tu trabajo dentro de la sesión, no ante un fallo.

- El guardado automático se ejecuta en un ciclo fijo (cada **2 minutos** por
  defecto) y **solo cuando el documento tiene cambios sin guardar** — un
  documento limpio nunca se guarda automáticamente.
- La ranura de recuperación está **separada de tu historial de versiones**. El
  guardado automático nunca crea una versión visible y **nunca sobrescribe tu
  último guardado explícito en la nube** (`REQ-P10-DATA-004`).
- El guardado automático se ejecuta fuera del hilo de la interfaz, así que
  nunca interrumpe tu dibujo.

### El aviso de recuperación al reiniciar

La recuperación tras un reinicio no está disponible en esta versión. El
adaptador integrado no conserva la ranura de recuperación de un reinicio a
otro, y el aviso de **Recuperar trabajo sin guardar** se comprueba una sola
vez, al iniciar la aplicación, antes de que puedas conectarte. Tras un fallo o
un corte de energía, no aparece ningún aviso la próxima vez que inicias la
aplicación. Hasta que se pueda elegir un proveedor persistente, confía en
guardar una copia local del proyecto.

El aviso en sí ofrece dos opciones (no lo verás en esta versión):

- **Recuperar** — obtiene y valida la copia autoguardada y la abre en una
  **pestaña nueva**. Tu último guardado explícito no se ve afectado.
- **Descartar** — descarta el aviso y deja todo como estaba.

!!! note "La recuperación también se descodifica de forma defensiva"
    La copia recuperada pasa por la misma validación de entrada no confiable
    que cualquier archivo de la nube, así que una ranura de recuperación
    malformada se rechaza con un error claro en lugar de abrirse.

!!! tip "El guardado automático necesita una conexión"
    El guardado automático opera a través del puerto de nube, así que se
    ejecuta solo mientras estás **conectado**. Protege tu trabajo dentro de la
    sesión, no ante un fallo.

## El resto del hito de nube y colaboración

Esta página cubre el trabajo en la nube de un solo usuario — guardado,
versiones, guardado automático — más los proveedores de la capa de
almacenamiento. Las funciones de colaboración están documentadas en la guía de
[Proyectos compartidos y comentarios](collaboration.md). En esta versión se
ejecutan en su propio adaptador en memoria, por ventana de la aplicación, y la
coedición en tiempo real no puede conectarse. Son estas:

- **Proyectos compartidos y membresía** — comparte un proyecto con miembros
  con nombre (roles propietario / editor / visualizador).
- **Comentarios** — encadena y resuelve comentarios en un proyecto compartido.
- **Presencia** — ve quién más está presente actualmente en un proyecto
  compartido.
- **Convergencia determinista** — las ediciones concurrentes se fusionan de
  forma determinista mediante un modelo híbrido de CRDT de árbol (estructura) +
  último-en-escribir-gana por mosaico (ráster).
- **Coedición en tiempo real y cursores en vivo** — edición multiusuario en
  vivo y convergente, con los cursores de otros editores mostrados en tu
  lienzo (la aplicación no puede conectarse a una sesión en tiempo real en esta
  versión).
- **Ramificación de arte** — ramifica un proyecto, edita de forma
  independiente y fusiona de vuelta sin conflictos.

La arquitectura detrás de todo esto se registra en **ADR-0026** (diseño del
puerto de nube), **ADR-0027** (ubicación del backend de sincronización +
tiempo real) y **ADR-0028** (modelo de convergencia híbrido + ramificación al
estilo git).
