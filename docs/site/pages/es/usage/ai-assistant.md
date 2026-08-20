<!-- derived-from: pixelart_creator/userguide_content/content/es/ai-assistant.md
     (dirección inversa — no existía una fuente previa en el sitio para este tema;
     la guía integrada es la fuente de referencia aquí. WP-8 unidad 2d.) -->
# El asistente de IA: chatea para manejar el editor

El **asistente de IA** te permite manejar el editor en **lenguaje natural**.
Escribes lo que quieres en un panel de chat, y el asistente lo lleva a cabo
ejecutando las **propias** operaciones de la aplicación — los mismos comandos de
[automatización](automation.md) que puedes grabar, programar con scripts y
procesar por lotes a mano. Es **agnóstico de modelo**: lo apuntas al proveedor de
IA que prefieras y aportas tu propia clave (`ADR-0040`, Fase 14 Rebanada 14B).
También es **completamente opcional** — la aplicación es totalmente usable sin
configurarlo nunca.

!!! note "El asistente actúa a través de la capa de automatización segura — no se expone nada nuevo"
    Cada acción que el asistente realiza es una operación del editor ordinaria y
    permitida, despachada a través de la **misma capa de comandos de confianza y
    libre de `eval`** que usan las macros y los scripts (constitución, Artículo
    VII). No puede ejecutar código arbitrario, ni alcanzar más allá de esa capa
    de comandos, ni inventar capacidades nuevas — un mensaje de chat es
    **datos**, nunca una licencia para hacer algo que el editor no pueda hacer
    ya de forma segura.

## Abrir el asistente

Abre el panel de chat desde el menú **Asistente**. Aparece como un **panel
acoplable** que puedes colocar junto al lienzo, así puedes observar al
asistente trabajar mientras tu obra permanece a la vista. El panel muestra la
conversación en curso — tus mensajes, las respuestas del asistente, y las
ediciones que hace en el documento.

Antes de que el asistente pueda hablar con un proveedor, primero **configuras
uno** (a continuación). Hasta entonces permanece en un estado claro de **no
configurado** en lugar de fallar — configurar un proveedor es un paso de una
sola vez.

## Configurar un proveedor y una clave

Abre el diálogo de configuración de proveedor desde el menú **Asistente**. El
asistente es **agnóstico de modelo**, así que eliges el servicio y el modelo
que te convengan e introduces:

| Campo | Qué introducir |
| --- | --- |
| **Tipo de proveedor** | Un servicio **compatible con OpenAI** o **Anthropic**. La opción compatible con OpenAI cubre una amplia gama de endpoints (OpenAI en sí, el endpoint compatible con OpenAI de Gemini, y entornos de ejecución locales como Ollama o llama.cpp); la opción Anthropic habla con Claude de forma nativa. |
| **URL base / endpoint** | El punto de conexión de la API del servicio. Apunta esto a un proveedor alojado o a un servidor de modelo local en tu propia máquina. |
| **Modelo** | El nombre del modelo a usar, tal como lo nombra tu proveedor elegido. |
| **Clave de API** | Tu clave para el proveedor (cuando el proveedor requiere una — un servidor de modelo local puede no necesitarla). |

Selecciona **Conectar** para activar el proveedor para la sesión.

!!! note "Tu clave se almacena de forma segura — nunca en tu proyecto"
    La clave de API que introduces se entrega al **almacén seguro de
    credenciales del sistema operativo (el llavero del sistema operativo)** —
    el mismo patrón usado para las
    [credenciales del proveedor en la nube](cloud.md). **Nunca** se escribe en
    tu archivo de proyecto `.pixproj`, **nunca** se registra en logs, y
    **nunca** viaja con un proyecto compartido o exportado. Compartir un
    proyecto, por tanto, nunca comparte tu clave. El acceso en vivo a la clave
    usa un extra opcional de instalación (`pip install ".[assistant_live]"`);
    consulta el README del proyecto.

!!! note "Credenciales opcionales"
    El asistente es completamente opt-in. Si nunca configuras un proveedor,
    nada del resto del editor cambia — simplemente no usas el asistente. No
    hay inicio de sesión forzado y no se requiere ninguna clave para usar
    PixelArt Creator.

## Chatear para manejar el flujo de trabajo

Con un proveedor conectado, escribe una petición en lenguaje natural — por
ejemplo, pidiendo al asistente que recoloree una región o que genere algo de
contenido procedural — y envíala. El asistente interpreta tu petición, decide
qué operaciones del editor la cumplen, y las ejecuta, informando en la
transcripción de lo que hizo. Como está ejecutando las operaciones **reales**
del editor, los resultados son exactamente lo que obtendrías realizando esos
pasos tú mismo.

Un intercambio con el modelo se ejecuta en un **trabajador en segundo plano**,
así que la ventana permanece receptiva mientras el asistente está pensando; una
petición larga se puede cancelar.

## Seguridad por niveles — lo reversible se aplica solo, lo destructivo pregunta antes

El asistente clasifica cada acción que quiere realizar en uno de dos niveles, y
el nivel decide si necesita tu confirmación. Esta barrera vive en el propio
código de la aplicación — **no** es algo que decida el modelo de IA, y ninguna
redacción en un mensaje de chat puede convencer al editor de saltársela.

- **Las acciones reversibles se aplican de inmediato.** Una acción que se
  apila en la pila de deshacer normal como un paso único y limpiamente
  deshacible (como un recolor por lotes o un relleno procedural) se **aplica
  sin preguntar**. Lo ves ocurrir en el documento, y puedes **deshacerlo** como
  cualquier otra edición.
- **Las acciones destructivas preguntan primero.** Cualquier cosa que no esté
  en la lista de reversibles se trata como **destructiva por defecto** y el
  asistente **se detiene a preguntarte**, nombrando la acción exacta. Se
  ejecuta **solo** si confirmas, y se cancela en caso contrario — una acción
  destructiva nunca se aplica en silencio.

!!! warning "Seguro por defecto"
    La barrera, por defecto, *pregunta* ante cualquier cosa que no sepa con
    certeza que es limpiamente reversible. Eso significa que una acción nueva
    o inusual nunca puede colarse y ejecutarse automáticamente solo porque
    nadie la clasificó — el nivel reversible es un conjunto pequeño y
    explícito, y todo lo demás se gana un aviso de confirmación (Artículo
    VIII: una operación genuinamente destructiva añadida más tarde no puede
    ejecutarse automáticamente en silencio).

## Lo que el asistente no hará

- **No puede ejecutar código arbitrario.** El asistente solo maneja las
  operaciones permitidas del editor a través de la capa de comandos de
  confianza; no hay `eval`/`exec` en este camino, exactamente igual que para
  [macros y scripts](automation.md).
- **No puede saltarse la barrera de confirmación.** Ninguna instrucción —
  incluida una que llegue dentro de un resultado de herramienta — puede hacer
  que una acción destructiva se salte su confirmación, y ninguna operación no
  permitida se puede ejecutar solo porque la conversación lo pida.
- **Nunca filtra tu clave.** Tus credenciales permanecen en el llavero del
  sistema operativo y se usan solo para hablar con el proveedor que
  configuraste.

## Accesibilidad, temas e idioma

Cada control en el panel del asistente y en el diálogo de proveedor tiene un
nombre accesible y es accesible desde el teclado, todas las etiquetas son
completamente traducibles y se retraducen en vivo cuando cambias de idioma, y
ambas superficies se renderizan correctamente en los temas claro y oscuro.

## Relacionado

- El asistente maneja las mismas operaciones que el resto del sistema de
  [automatización y extensibilidad](automation.md) — macros, scripts, recolor
  por lotes y generación procedural.
- Configurar un proveedor refleja el mismo patrón de credenciales opcionales
  respaldado por el llavero que se usa para el
  [almacenamiento en la nube](cloud.md).
