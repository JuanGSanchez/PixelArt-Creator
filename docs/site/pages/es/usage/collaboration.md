# Proyectos compartidos: miembros, comentarios y presencia

La **capa de colaboración** permite que varias personas trabajen alrededor de un
proyecto en la nube. Puedes **compartir un proyecto** con un conjunto de miembros
con nombre (cada uno con un rol), dejar y resolver **comentarios** en él, y ver
**quién más está presente**. Todo aquí se construye sobre la
[capa de nube](cloud.md) — un proyecto compartido sigue siendo un `.pixproj`
almacenado a través del mismo puerto de nube agnóstico de proveedor; compartir
añade una **lista de miembros**, un **hilo de comentarios** y un canal de
**presencia efímera** por encima.

Todo en esta guía se maneja desde el menú **Nube** de la barra de menús, que
lleva los paneles acoplables de colaboración y los controles de tiempo real
debajo de la entrada de historial de versiones:

- **Nube → Proyectos compartidos** — comparte el proyecto actual y gestiona sus
  miembros.
- **Nube → Comentarios** — añade, encadena y resuelve comentarios.
- **Nube → Presencia** — ve quién está presente y anúnciate.
- **Nube → Iniciar tiempo real… / Detener tiempo real** — únete o abandona una
  sesión de coedición en vivo en el documento activo.
- **Nube → Mostrar cursores en vivo** — alterna en tu lienzo los cursores en
  vivo de otros editores.
- **Nube → Ramificación** — abre el panel de ramificar / cambiar / fusionar.

Cada entrada de panel acoplable alterna el panel correspondiente, así que puedes
organizarlos junto a los paneles de capas, línea de tiempo y demás paneles de
trabajo.

!!! success "Lo que se entrega en esta versión — la Fase 10 está completa"
    Esta versión completa el hito de nube y colaboración. Además de proyectos
    compartidos, comentarios, presencia y convergencia determinista (Fragmento B),
    añade **coedición en tiempo real**, **cursores y selecciones en vivo de otros
    editores**, y **ramificación de arte al estilo git** (Fragmento C), servidos
    por un **backend de sincronización en tiempo real** dedicado. Conectar un
    proveedor **real** de Google Drive / OneDrive / Dropbox se cubre en la
    [guía de la nube](cloud.md).

!!! note "Un único puerto agnóstico de proveedor — sin dependencia de uno solo"
    Igual que los guardados en la nube de un solo usuario, la colaboración nunca
    habla directamente con un proveedor específico. Compartir, la membresía, los
    comentarios y la presencia pasan todos por la **misma interfaz agnóstica de
    proveedor** (la familia del *puerto de nube*), así que la aplicación se
    comporta de forma idéntica sin importar qué proveedor la respalde. En esta
    versión, esa interfaz la sirve un adaptador integrado, en memoria —
    determinista, sin red ni cuenta — así que todo el flujo de colaboración está
    completo y es utilizable de principio a fin. El respaldo con un proveedor real
    llegará detrás de la misma interfaz más adelante, sin cambio alguno en los
    pasos siguientes. Consulta **ADR-0026** (diseño del puerto de nube) y
    **ADR-0028** (convergencia híbrida) para la arquitectura.

## Compartir un proyecto y gestionar la lista de miembros

Compartir un proyecto se hace desde el panel de **Proyectos compartidos**. Ábrelo
con **Nube → Proyectos compartidos**.

### Crear (compartir) un proyecto

1. En el campo **Nombre del proyecto compartido**, escribe el nombre bajo el que
   se registrará tu proyecto compartido (por ejemplo, `team-sprite`). Reutiliza
   el mismo nombre más adelante para seguir trabajando en el mismo proyecto
   compartido.
2. Construye la **lista para compartir** usando la fila de añadir miembro:
    - Escribe un **id de miembro** (el identificador del colaborador) en el
      campo *Id de miembro a invitar*.
    - Elige un **rol** en el selector de rol — **Propietario**, **Editor** o
      **Visor**.
    - Haz clic en **Añadir miembro**. El miembro aparece en la lista editable
      *Lista para compartir* con su rol.
3. Repite el paso 2 para cada colaborador. Para quitar a alguien antes de
   compartir, selecciona la fila y haz clic en **Eliminar**.
4. Cuando la lista esté lista, haz clic en **Compartir / Actualizar**. El
   proyecto se comparte con exactamente esa lista, y los miembros confirmados
   aparecen en la lista de solo lectura *Miembros actuales* debajo.

!!! note "Roles"
    Un rol es un marcador de permiso agnóstico de proveedor asociado a cada
    miembro:

    - **Propietario** — control total del proyecto compartido.
    - **Editor** — puede editar la obra y comentar.
    - **Visor** — puede ver y comentar.

    Los roles se almacenan con la membresía y se muestran tanto en la lista
    editable como en la lista de miembros actuales.

!!! warning "El límite de miembros"
    Un proyecto compartido puede tener como máximo **32** miembros
    (`MAX_SHARED_MEMBERS`). El panel se niega a añadir un miembro por encima de
    ese límite con un mensaje claro, y la capa de almacenamiento aplica el mismo
    límite como segunda línea de defensa. Los id de miembro duplicados también
    se rechazan.

### Actualizar la lista

Para cambiar quién está en un proyecto compartido, ajusta la lista editable
(añade o elimina miembros) y haz clic en **Compartir / Actualizar** de nuevo.
Volver a compartir **reemplaza** la lista con el borrador actual — no hay un
paso separado de "añadir un miembro", así que asegúrate de que el borrador
incluya a todos los que deban tener acceso antes de confirmarlo.

### Abrir un proyecto compartido

Introduce un nombre de proyecto compartido existente y compártelo (o vuelve a
compartirlo con la misma lista) para convertirlo en el **proyecto compartido
activo**. Los paneles de Comentarios y Presencia siempre operan sobre el
proyecto compartido activo, así que abrir uno aquí conecta los tres paneles al
mismo proyecto a la vez.

## Añadir y ver comentarios

Los comentarios viven en el proyecto compartido activo. Abre el hilo con
**Nube → Comentarios**.

### Leer el hilo

La vista de comentarios es un **árbol encadenado** con tres columnas:

- **Autor** — el id de miembro que escribió el comentario.
- **Comentario** — el texto del comentario.
- **Estado** — **Abierto** o **Resuelto**.

Las respuestas se anidan bajo el comentario que responden, así que una
discusión se lee como un hilo con sangría.

### Añadir un comentario

1. Introduce **tu id de miembro** en el campo *Tu id de miembro* (esto se
   registra como el autor del comentario).
2. Escribe tu comentario en el cuadro de texto de abajo. Un **contador de
   bytes** en vivo muestra cuánto has usado del presupuesto por comentario (por
   ejemplo, `18 / 4096 bytes`).
3. *(Opcional)* Para responder a un comentario existente, selecciónalo en el
   hilo y activa **Responder al seleccionado** — tu nuevo comentario se
   encadenará debajo de él.
4. Haz clic en **Añadir comentario**. El comentario aparece en el hilo (anidado
   bajo su padre si era una respuesta) con el estado **Abierto**.

### Resolver un comentario

Selecciona un comentario en el hilo y haz clic en **Resolver**. Su estado
cambia a **Resuelto**. Resolver es una marca de un solo sentido de que un
comentario ha sido atendido; el comentario permanece en el hilo como registro.

!!! warning "Límites de comentarios"
    Se aplican dos límites, ambos comprobados en el borde del panel con
    retroalimentación y verificados de nuevo por la capa de almacenamiento
    (Artículo VII, defensa en profundidad):

    - **Tamaño de comentario** — un solo comentario puede tener como máximo
      **4096 bytes** (`MAX_COMMENT_BYTES`). El límite se mide sobre la
      **longitud en bytes UTF-8**, así que el texto acentuado o no latino cuenta
      su coste real en bytes, no solo caracteres. El contador de bytes en vivo
      convierte esto en un total acumulado.
    - **Número de comentarios** — un proyecto compartido puede contener como
      máximo **1024** comentarios (`MAX_COMMENTS_PER_PROJECT`). Cuando se
      alcanza el límite, el panel muestra el mensaje de la capa de
      almacenamiento en lugar de descartar el comentario en silencio.

!!! note "Los comentarios se validan, nunca se ejecutan"
    El texto de los comentarios se trata como **entrada no confiable**: se
    comprueba por esquema y tamaño antes de almacenarse y **nunca** se evalúa
    ni se ejecuta como código. Una carga malformada o demasiado grande se
    rechaza con un error claro, nunca con un fallo.

## Ver quién está presente

El panel de **Presencia** muestra una lista en vivo de *quién está presente
actualmente* en el proyecto compartido activo. Ábrelo con **Nube → Presencia**.

1. Introduce **tu id de miembro** en el campo de presencia.
2. Haz clic en **Unirse** para anunciarte como presente. Tu id aparece en la
   lista de *Miembros presentes*.
3. Haz clic en **Salir** para borrar tu presencia cuando te alejes.

!!! note "La presencia es efímera"
    La presencia **nunca se guarda en el archivo del proyecto** ni en su estado
    de colaboración — es una señal en vivo, en memoria, de quién está por aquí
    ahora mismo. Cerrar un proyecto compartido o salir borra tu presencia.

!!! info "Lista de presencia frente a cursores en vivo"
    El panel de Presencia muestra la **lista de presencia** — quién está
    presente (`REQ-P10-UI-011`). Dibujar los **cursores y selecciones en vivo**
    de otros colaboradores en tu lienzo es una función distinta — consulta
    [Coedición en tiempo real](#coedicion-en-tiempo-real) más abajo
    (`REQ-P10-UI-013`).

## Cómo convergen las ediciones simultáneas

Cuando varios miembros editan un proyecto compartido, sus cambios se concilian
mediante un **modelo de convergencia híbrido determinista** (`REQ-P10-LOGIC-006`),
así que todos terminan con el **mismo** proyecto sin importar el orden en que
lleguen las ediciones:

- Los **metadatos estructurados** — el árbol de capas, los atributos de capa
  (nombre, opacidad, visibilidad, bloqueo) y el orden de capas por fotograma —
  convergen mediante un **CRDT de secuencia / árbol**.
- Los **píxeles ráster** convergen mediante **el último en escribir gana por
  mosaico**: el lienzo se divide en mosaicos de 64 píxeles, y las ediciones
  concurrentes a mosaicos *distintos* sobreviven ambas, mientras que las
  ediciones concurrentes al *mismo* mosaico se resuelven mediante un desempate
  determinista de reloj lógico + id de sitio. Repartir el trabajo por mosaico
  (en lugar de por píxel) mantiene esto escalable hasta el lienzo de 8K.

El resultado es **determinista**: dado el mismo conjunto de ediciones, cada
participante converge a un proyecto idéntico byte a byte — la fusión no lee
reloj del sistema, aleatoriedad ni configuración regional. Este es el modelo de
conciliación **por lotes**; aplicar ediciones **en vivo** a medida que ocurren
es el camino de tiempo real que se describe a continuación.

## Coedición en tiempo real

La coedición en tiempo real aplica las ediciones de cada participante al
lienzo de **todos** los pares a medida que ocurren, convergiendo con el mismo
modelo determinista que la fusión por lotes anterior (`REQ-P10-LOGIC-007`). Las
ediciones viajan a través de un **backend de sincronización en tiempo real**
dedicado (consulta la [nota para operadores](#nota-para-operadores-ejecutar-el-backend-de-sincronizacion)
más abajo).

### Iniciar o unirse a una sesión

1. Abre el documento que quieres coeditar (un proyecto compartido o cualquier
   pestaña abierta).
2. Elige **Nube → Iniciar tiempo real…**.
3. Introduce **tu id de miembro** cuando se te pida — así es como te ven tus
   pares (y así se etiqueta tu cursor en vivo). La aplicación se une al relé en
   tiempo real del documento.
4. Cuando te conectas, la superposición de **Mostrar cursores en vivo** se
   activa automáticamente.

Todo el que inicie tiempo real en el **mismo documento** se une a la misma
sesión. Si hay un proyecto compartido abierto, la sesión se asocia a ese
proyecto compartido para que todo el equipo converja en un solo documento; si
no, se asocia a tu documento local.

Para salir, elige **Nube → Detener tiempo real**. Puedes volver a conectarte
en cualquier momento; salir borra los cursores en vivo.

!!! note "Quien se une tarde se pone al día automáticamente"
    El backend de sincronización **persiste** el flujo de ediciones de cada
    documento, así que un colaborador que se une después de que empezara la
    edición **reproduce el historial acumulado** y llega al mismo documento
    converged que todos los demás.

!!! note "El tiempo real se mantiene receptivo"
    Las ediciones entrantes se reciben en un trabajador en segundo plano y se
    aplican al documento en vivo en el hilo de la interfaz, repintando
    **solo los mosaicos que cambiaron** (un repintado de región sucia). Una
    sola edición entrante cuesta el tamaño de esa edición, no el lienzo
    completo, así que la coedición se mantiene fluida incluso al tamaño de
    lienzo de 8K (`REALTIME_APPLY_CEILING_MS`).

!!! warning "No confiable por construcción"
    Cada edición y cada payload de cursor entrante se **valida por esquema y
    tamaño** antes de aplicarse y **nunca** se ejecuta como código (Artículo
    VII). Un mensaje malformado o demasiado grande se rechaza con un aviso en
    la barra de estado, nunca con un fallo.

### Cursores y selección en vivo

Mientras el tiempo real está conectado, **Nube → Mostrar cursores en vivo**
alterna una superposición que dibuja los cursores y selecciones de otros
editores en tu lienzo, cada uno etiquetado con el id de miembro del par
(`REQ-P10-UI-013`).

- Los cursores son **efímeros** — son solo una señal en vivo y **nunca** se
  escriben en el `.pixproj` ni en el estado guardado del proyecto.
- Desactiva la superposición en cualquier momento para reducir el desorden
  visual; tu propia edición no se ve afectada.

## Ramificación de arte

La ramificación te permite bifurcar el proyecto actual en una línea
independiente de ediciones, trabajar en ella sin perturbar la línea principal,
y **fusionarla** de vuelta **sin resolución manual de conflictos** — el mismo
modelo CRDT / último-en-escribir-gana que impulsa la convergencia fusiona las
dos líneas automáticamente (`REQ-P10-UI-012`, `REQ-P10-LOGIC-007`). Abre el
panel con **Nube → Ramificación**.

### Crear una rama

1. Con un proyecto abierto, haz clic en **Nueva rama** en el panel de
   Ramificación.
2. Introduce un **nombre de rama** (por ejemplo, `experiment`). La rama se
   bifurca desde el documento actual y aparece en la lista de ramas; la
   **rama principal** siempre está presente.

### Cambiar de rama

Selecciona una rama en la lista y haz clic en **Cambiar**. El documento de la
rama seleccionada se carga en la pestaña activa, así que editas la copia
independiente de esa rama. Cambiar a la **rama principal** vuelve al tronco.

### Fusionar una rama

Selecciona una rama de funcionalidad y haz clic en **Fusionar**. Sus ediciones
se fusionan en la **rama principal** sin conflictos, el documento fusionado se
carga en la pestaña activa, y el panel muestra una línea de **resultado de
fusión** resumiendo lo que ocurrió (por ejemplo, *"Merged branch 'experiment'
(12 edits) into mainline"*).

!!! note "Las fusiones nunca te piden resolver un conflicto"
    Como el modelo subyacente es conmutativo y determinista, una fusión
    siempre tiene éxito y siempre produce el mismo resultado sin importar el
    orden en que se hicieron las ediciones — no hay ningún paso manual de
    resolución de conflictos. La ramificación es estado de sesión y **no** es
    un paso de deshacer en la pila de deshacer.

## Nota para operadores: ejecutar el backend de sincronización

La coedición en tiempo real necesita un **backend de sincronización** — un
servicio pequeño y separado que retransmite y persiste las ediciones entre
colaboradores. **No** forma parte del núcleo de tres capas de la aplicación de
escritorio; vive en su propio paquete de nivel superior `sync_backend/` y
habla con los clientes solo a través del transporte en tiempo real.

- El backend no importa código de interfaz, datos ni Qt, y **nunca** recibe ni
  almacena los tokens de tu proveedor de nube — esos permanecen en el llavero
  del cliente de escritorio.
- Para el desarrollo local y la suite de pruebas automatizada, el backend se
  inicia **dentro del mismo proceso, en un puerto loopback efímero**, así que
  el ciclo completo cliente ↔ backend se ejecuta sobre `127.0.0.1` sin red
  externa ni cuentas. Así es como la comprobación de CI ejerce el tiempo real
  de extremo a extremo.
- Ejecutar el backend como un servicio independiente y accesible por red para
  un equipo distribuido es una **cuestión de despliegue** (host, puerto y
  gestión de procesos), separada de la aplicación de escritorio; su
  arquitectura y ubicación se registran en **ADR-0027**.

La arquitectura de tiempo real y ramificación se registra en **ADR-0027**
(ubicación del backend de sincronización + tiempo real) y **ADR-0028** (modelo
de convergencia híbrido + ramificación al estilo git); conectar un proveedor
de nube real se cubre en la [guía de la nube](cloud.md).
