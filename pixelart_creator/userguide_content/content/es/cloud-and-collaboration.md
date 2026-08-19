# Nube: guardado, versiones, guardado automático y recuperación

La **capa de nube** permite que un proyecto viva en la nube en lugar de solo en una
máquina. Puedes **conectar un proveedor de nube**, **guardar** el proyecto actual en
la nube, **abrirlo** de nuevo desde cualquier sesión, explorar un **historial de
versiones** completo y **restaurar** un guardado anterior, y confiar en el
**guardado automático + recuperación tras fallos** para que un cierre no limpio
nunca pierda tu trabajo sin guardar.

Todo en esta guía se maneja desde el menú **Nube** de la barra de menús.

> **Un único puerto agnóstico de proveedor — sin dependencia de uno solo.** La
> aplicación nunca habla directamente con un proveedor específico. Todo el trabajo
> en la nube pasa por **una única interfaz agnóstica de proveedor** (el *puerto de
> nube*): conectar, guardar, abrir, listar versiones, restaurar y la ranura de
> guardado automático/recuperación. La aplicación se comporta **de forma idéntica**
> sin importar qué proveedor la respalde, así que no estás atado a uno, y un
> proveedor nuevo es solo un nuevo adaptador detrás del mismo puerto.

El hito completo de nube y colaboración se entrega en esta versión: el puerto
agnóstico de proveedor, un adaptador integrado totalmente probado, el ciclo completo
de `.pixproj` en la nube, historial de versiones + restauración, y guardado
automático/recuperación tras fallos; **proyectos compartidos, comentarios y
presencia**; y **coedición en tiempo real, cursores en vivo y ramificación de arte**
más los **proveedores reales de Google Drive / OneDrive / Dropbox**. Compartir,
comentarios, presencia, tiempo real y ramificación se tratan en
[Proyectos compartidos, comentarios, presencia y tiempo real](collaboration.md).

## Conectar un proveedor de nube

Las acciones de nube están desactivadas hasta que te conectas.

1. Abre el menú **Nube**.
2. Elige **Conectar…**. Esto establece una conexión agnóstica de proveedor a través
   del puerto de nube y activa el resto del menú Nube (**Guardar en la nube**,
   **Abrir desde la nube**, **Historial de versiones** y **Desconectar**).
3. Para cerrar sesión, elige **Nube → Desconectar**. Esto libera la conexión y
   vuelve a desactivar las acciones de nube hasta que te conectes de nuevo.

> **Tus credenciales nunca salen de la capa de almacenamiento.** Cuando se usa un
> adaptador de proveedor real, el flujo de inicio de sesión (OAuth) se ejecuta
> **enteramente dentro de la capa de almacenamiento** — la aplicación solo abre tu
> navegador del sistema por ti. Los tokens **nunca** se muestran a la interfaz,
> **nunca** se escriben en un `.pixproj`, y **nunca** se escriben en logs. La
> interfaz solo ve un estado simple de *conectado / no conectado*.

> **El adaptador integrado.** La conexión por defecto es un adaptador integrado, en
> memoria, que es determinista y no necesita red ni cuenta — existe para que todo el
> flujo de guardado/versiones/recuperación esté completo y sea utilizable de
> principio a fin. Para usar un proveedor real en línea en su lugar, consulta
> *Conectar un proveedor de nube real* a continuación.

## Conectar un proveedor de nube real

Puedes conectar una cuenta **real** de Google Drive, OneDrive o Dropbox detrás del
**mismo** flujo de Conectar, así que cada paso de esta guía (guardar, abrir,
historial de versiones, guardado automático/recuperación) funciona de forma idéntica
sobre tu almacenamiento en línea.

> **Función protegida por credenciales.** Los proveedores reales están
> **protegidos por credenciales**: cada uno necesita un **id de cliente** OAuth
> para el servicio elegido y acceso a la red en vivo, así que se configuran de
> forma deliberada en lugar de estar activados por defecto. El adaptador integrado
> anterior no necesita nada de esto.

### Cómo funciona el inicio de sesión

1. Elige **Nube → Conectar…** y selecciona el proveedor real que configuraste.
2. La aplicación abre tu **navegador del sistema** en la página de inicio de
   sesión/consentimiento del proveedor. PixelArt Creator usa el flujo estándar de
   escritorio **código de autorización OAuth + PKCE sobre una redirección
   loopback** — no hay **ninguna vista web integrada** y **ningún secreto de
   cliente** almacenado en la aplicación.
3. Aprueba el acceso en el navegador. El navegador redirige de vuelta a la
   aplicación, que completa la conexión. Las acciones de guardar/abrir/versiones
   del menú Nube se activan igual que para el adaptador integrado.
4. Para cerrar sesión, elige **Nube → Desconectar**.

> **Tus credenciales nunca salen de la capa de almacenamiento.** Todo el inicio de
> sesión se ejecuta **enteramente dentro de la capa de almacenamiento**. Tu
> **token de actualización se almacena en el llavero del sistema operativo**
> (con clave por proveedor); el token de acceso de corta duración se mantiene solo
> en memoria y se renueva automáticamente. Los tokens **nunca** se muestran a la
> interfaz, se escriben en un `.pixproj`, ni se escriben en logs.

> **Mismo comportamiento, cualquier proveedor.** Como todos los proveedores están
> detrás del mismo puerto de nube, cambiar del adaptador integrado a Drive /
> OneDrive / Dropbox — o entre ellos — no cambia **nada** en cómo guardas,
> exploras versiones o recuperas trabajo.

## Guardar un proyecto en la nube

1. Con un proyecto abierto y un proveedor conectado, elige **Nube → Guardar en la
   nube…**.
2. Introduce un **nombre de proyecto en la nube** cuando se te pida. Esta es la
   clave bajo la que se almacena tu proyecto; reutiliza el mismo nombre para seguir
   añadiendo versiones al mismo proyecto.
3. La aplicación serializa el proyecto a un `.pixproj` y lo almacena como una
   **versión nueva**. Cuando termina, la barra de estado muestra *"Guardado en la
   nube."*

Cada guardado se transporta como un `.pixproj` completo — el **mismo** formato de
guardado validado y versionado que se usa para archivos locales. La capa de nube no
añade ningún formato nuevo propio; simplemente transporta el `.pixproj` como la
*unidad de sincronización* atómica.

> **Guardar nunca congela la aplicación.** La serialización + subida se ejecutan
> **fuera del hilo de la interfaz**, así que la ventana permanece receptiva incluso
> para un proyecto grande (de hasta 8K) — puedes seguir trabajando mientras se
> completa un guardado.

> **Cada guardado es una versión nueva.** Guardar **no** sobrescribe el guardado
> anterior en la nube — añade una entrada nueva al historial de versiones. El
> historial se limita a las **100** versiones más recientes por proyecto.

## Abrir un proyecto desde la nube

1. Elige **Nube → Abrir desde la nube…**.
2. Introduce el **nombre del proyecto en la nube** a abrir.
3. La aplicación obtiene la última versión del proyecto y la abre en una **pestaña
   nueva**.

Abrir **no** reemplaza ni perturba lo que estés trabajando actualmente — el
proyecto de la nube llega como su propia pestaña.

> **Los archivos de la nube se tratan como no confiables.** Un `.pixproj` obtenido
> de la nube se valida de forma defensiva exactamente igual que un archivo local:
> cada campo se comprueba por tipo y límites, la carga útil tiene un tope de
> tamaño, y un archivo malformado, demasiado grande o de versión desconocida se
> rechaza con un **error claro** — nunca un fallo y **nunca** ejecutando código
> del archivo. Si un proyecto obtenido no se puede validar, obtienes un diálogo de
> advertencia y tu trabajo actual queda intacto.

## Explorar el historial de versiones y restaurar una versión

Cada guardado crea una versión nueva y ordenada, y puedes volver a cualquiera de
ellas.

1. Elige **Nube → Historial de versiones…** (si no has abierto ni guardado un
   proyecto en la nube en esta sesión, primero se te pedirá el nombre del proyecto
   en la nube).
2. El diálogo de **Historial de versiones en la nube** lista cada versión
   almacenada, de la más antigua a la más reciente, con estas columnas:
    - **Versión** — el ordinal/identificador de la versión.
    - **Marca** — el marcador de orden de la versión.
    - **Tamaño (bytes)** — el tamaño del `.pixproj` almacenado.
    - **Fijada** — si la versión está fijada (conservada) — *Sí* / *No*.
    - **Padre** — la versión a la que siguió este guardado.
3. Selecciona una versión para ver sus detalles en el área de vista previa debajo
   de la lista.
4. Haz clic en **Restaurar** (o doble clic en la fila, o pulsa **Enter**) para
   traer de vuelta esa versión.

> **Restaurar es seguro — abre una pestaña nueva.** Restaurar una versión anterior
> la obtiene y valida, y luego la abre en una **pestaña nueva**. **No**
> sobrescribe tu trabajo actual ni tu último guardado en la nube — tú decides qué
> hacer con la copia restaurada.

La lista de versiones se obtiene fuera del hilo de la interfaz antes de que se abra
el diálogo, así que explorar el historial nunca congela la aplicación.

## Guardado automático y recuperación tras fallos

Mientras trabajas en un proyecto conectado, la aplicación **guarda
automáticamente** tu copia de trabajo en una **ranura de recuperación** dedicada en
segundo plano.

- El guardado automático se ejecuta en un ciclo fijo (cada **2 minutos** por
  defecto) y **solo cuando el documento tiene cambios sin guardar** — un documento
  limpio nunca se guarda automáticamente.
- La ranura de recuperación está **separada de tu historial de versiones**. El
  guardado automático nunca crea una versión visible y **nunca sobrescribe tu
  último guardado explícito en la nube**.
- El guardado automático se ejecuta fuera del hilo de la interfaz, así que nunca
  interrumpe tu dibujo.

### El aviso de recuperación al reiniciar

Si la aplicación se cierra de forma no limpia (un fallo o un corte de energía)
mientras tenías trabajo sin guardar, la próxima vez que la inicies **y te
conectes**, detecta la ranura de recuperación sobrante y muestra un aviso de
**Recuperar trabajo sin guardar**:

- **Recuperar** — obtiene y valida la copia autoguardada y la abre en una
  **pestaña nueva**. Tu último guardado explícito no se ve afectado.
- **Descartar** — descarta el aviso y deja todo como estaba.

> **La recuperación también se descodifica de forma defensiva.** La copia
> recuperada pasa por la misma validación de entrada no confiable que cualquier
> archivo de la nube, así que una ranura de recuperación corrupta nunca puede hacer
> fallar la aplicación al iniciar — en el peor caso obtienes un error claro y
> puedes continuar.

> **El guardado automático necesita un proveedor conectado.** El guardado
> automático y el aviso de recuperación al reiniciar operan a través del puerto de
> nube, así que están activos mientras estás **conectado**. Conecta un proveedor
> al principio de una sesión para mantener una red de seguridad en funcionamiento.

## El resto del hito de nube y colaboración

Esta página cubre el trabajo en la nube de un solo usuario — guardado, versiones,
guardado automático/recuperación — más conectar un proveedor real. Las funciones de
colaboración que se construyen encima — **proyectos compartidos y membresía**,
**comentarios**, **presencia**, **convergencia determinista**, **coedición en tiempo
real y cursores en vivo**, y **ramificación de arte** — se cubren todas en
[Proyectos compartidos, comentarios, presencia y tiempo real](collaboration.md).
