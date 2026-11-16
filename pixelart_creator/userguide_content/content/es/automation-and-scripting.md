# Automatización, macros, scripting y complementos

El **sistema de automatización** te permite grabar, programar con scripts, reproducir
y procesar por lotes las propias operaciones del editor, y generar contenido de forma
procedural — todo a través de
**un solo** motor que la interfaz gráfica y la línea de comandos sin interfaz
`pixelart-run` comparten, así que una automatización se ejecuta **de forma idéntica**
tanto si la activas desde un panel como desde un script de compilación.

> **Seguridad por diseño — nunca `eval`.** El scripting es un **DSL de comandos
> acotado y basado en datos**, no Python arbitrario. Una automatización es una *lista
> validada de operaciones* (`{name, params, seed}`), nunca un lenguaje: **no hay
> `eval`/`exec`/`compile`/`__import__` de tu entrada en ningún punto** de este
> camino — no hay ningún intérprete del que escapar. Un único despachador de
> confianza comprueba el nombre de cada operación contra una **lista de permitidos**
> y sus parámetros contra un esquema declarado antes de construir el comando
> reversible al que se asigna.

## Macros — grabar, reproducir y el formato `.pixmacro`

El panel **Macros** graba las operaciones que realizas y las reproduce después:

- **Grabar** captura las *entradas* de cada paso — los parámetros resueltos y, para
  cualquier paso aleatorio, la **semilla** — no una diferencia de píxeles. Lo que
  grabas es lo que una reproducción vuelve a ejecutar.
- **Reproducir** vuelve a aplicar las operaciones grabadas al documento actual como
  **un paso de deshacer**, así que deshacer revierte la macro completa de una vez.

Una macro se almacena como un archivo **`.pixmacro`** — JSON plano con una envoltura
versionada:

```
{
  "format": "pixmacro",
  "schema_version": "1",
  "min_app_version": "0.8.0",
  "api_version": "1",
  "ops": [
    { "op": "batch_recolour", "params": { }, "seed": null },
    { "op": "procgen",        "params": { }, "seed": 12345 }
  ]
}
```

- **`schema_version` / `api_version` / `min_app_version`** se comprueban al cargar:
  una versión desconocida o no soportada **falla de forma explícita** con un error
  claro en lugar de reproducirse mal.
- **`params`** son nativos de JSON, así que guardar y luego cargar una macro produce
  una macro **idéntica** — los colores y los mapas de índices viajan como listas.
- **`seed`** se graba para cada paso estocástico, así que la reproducción es
  reproducible.

> **Reproducción determinista.** Reproducir la misma macro sobre el mismo documento
> de partida dos veces produce un documento **idéntico en estado**. Cada paso
> aleatorio extrae solo de su semilla grabada — sin reloj del sistema, sin
> aleatoriedad sin semilla, sin dependencia de configuración regional. Esto es lo que
> hace que una macro sea segura de ejecutar en una canalización de compilación.

Cargar un `.pixmacro` es **defensivo**: cada campo se comprueba por tipo, límites y
versión, un documento malformado o fuera de límites lanza un error claro, y el
contenido **nunca** se pasa a `eval`/`exec`.

## Ejecutar scripts

El **Ejecutor de scripts** despacha una lista de operaciones a través del mismo
despachador de confianza que usa la reproducción de macros. Una ejecución de script
es **atómica**:

1. **Cada operación se valida por adelantado** — todos los nombres de operación se
   comprueban contra la lista de permitidos y todos los parámetros contra su esquema
   **antes de aplicar nada**.
2. La ejecución completa se aplica como **un único comando agrupado y reversible**.
3. Si alguna operación falla a mitad de camino, las operaciones ya aplicadas se
   **revierten en orden inverso**, así que una ejecución multi-operación fallida deja
   el documento **sin cambios** — nunca a medio aplicar.

Como la ejecución es un único comando agrupado, un script completado es **un único
paso de deshacer**.

## Complementos — el gestor, el consentimiento y el modelo de confianza

El panel **Complementos** lista los complementos, muestra los permisos de cada
complemento cuyo manifiesto has cargado, y los habilita y deshabilita. Un complemento
está pensado para ampliar el editor registrando nuevas operaciones del DSL. **En esta
versión la aplicación no tiene ningún paso que cargue o ejecute el código de un
complemento:** descubrir un complemento, cargar un manifiesto, habilitar y
deshabilitar nunca invocan a un complemento. Los permisos que declara un manifiesto
describen el uso previsto del complemento; no son un límite de lo que puede hacer el
código propio del complemento (consulta la nota de abajo).

- **El descubrimiento es inerte.** La aplicación encuentra los complementos instalados
  mediante los puntos de entrada estándar de Python, pero solo lee sus nombres y
  versiones: **no** carga ni ejecuta su código. Un complemento descubierto no muestra
  permisos y no se puede habilitar, porque la aplicación no lee los permisos del propio
  complemento. Los permisos proceden de un archivo de manifiesto que añades al panel
  desde el disco, y que aparece como una entrada propia en la lista. La aplicación no
  comprueba que un manifiesto pertenezca a un complemento que hayas instalado.
- **El consentimiento cubre lo que declara el manifiesto.** **Habilitar** muestra los
  permisos que declara el manifiesto y te pide que confirmes. Los apruebas en
  conjunto, o no habilitas el complemento. La aplicación no comprueba el manifiesto
  frente a lo que el código del complemento hace realmente. Habilitar registra los
  permisos que aprobaste, en memoria, y marca el complemento como habilitado; no
  ejecuta el código del complemento, porque la aplicación no tiene ningún paso que lo
  haga. Tu consentimiento no se guarda: todos los complementos vuelven a quedar
  deshabilitados cuando cierras el editor. El anfitrión de complementos está escrito de
  modo que, si el código que lo llama le proporcionara un paso de activación, a ese paso
  se le entregaría un objeto de permisos, y se rechazaría toda llamada a través de ese
  objeto cuyo permiso no se hubiera concedido; en esta versión nada proporciona un
  paso así. Las operaciones registradas a través de ese objeto llevan como prefijo el
  nombre del complemento, así que no pueden coincidir con el nombre de una operación
  integrada, y un permiso de lectura a través de él devuelve el documento que se le
  pasa, no una copia. El código que no pasa por el objeto no queda limitado por él:
  puede registrar o eliminar operaciones directamente, incluidas las integradas.
- **Deshabilitar elimina las operaciones del complemento.** **Deshabilitar** anula el
  registro de las operaciones que se registraron a través del objeto de permisos; en
  esta versión no hay ninguna, porque nada registra ninguna. No deshace nada de lo que
  el código propio de un complemento ya ha hecho.

> **Los complementos no están dentro de un entorno aislado (sandbox).** Un complemento
> no está aislado de tu equipo, y la aplicación no proporciona aislamiento para ningún
> complemento en esta versión. Instalar un complemento coloca en tu equipo código de
> Python ajeno, y la aplicación ni realiza ni comprueba la instalación. Un paquete
> también puede pedirle a Python que ejecute código cada vez que Python se inicia en el
> entorno donde está instalado, lo cual incluye el editor, así que instalar un
> complemento puede bastar para que su código se ejecute, aunque nunca abras el panel
> **Complementos**. El código que se ejecuta en el propio proceso del editor, sea cual
> sea el modo en que haya llegado allí, tiene el mismo acceso a tus archivos y a la red
> que el editor mismo, cualesquiera que sean los permisos que haya declarado el
> complemento. Instala y habilita solo complementos en los que confíes.

## Recolor por lotes

**Recolor por lotes** aplica un remapeo de color a **muchos objetivos a la vez** como
un **único comando transaccional y reversible**:

- Para objetivos **indexados**, remapea índices de paleta (`índice_antiguo →
  índice_nuevo`); para objetivos **RGBA**, remapea colores (`rgba_antiguo →
  rgba_nuevo`). Reutiliza las operaciones de recolor existentes del editor, así que
  un objetivo procesado por lotes es **idéntico byte a byte** a recolorear ese
  objetivo por sí solo con el mismo mapeo.
- Es **transaccional**: cada objetivo se valida y su paso individual se construye
  **antes de aplicar nada**. Un objetivo inválido falla nombrando el objetivo
  problemático con **cero mutación**. El lote completo es **un único paso de
  deshacer**.

## Generación procedural

El panel **Generación procedural** rellena una región con contenido generado. Hay cinco
generadores propios y **con semilla** disponibles:

| Generador | Qué produce |
| --- | --- |
| **Ruido de valor** | Ruido de cuadrícula de valor con semilla. |
| **Ruido de gradiente** | Ruido de gradiente estilo Perlin. |
| **Ruido OpenSimplex** | Un ruido de gradiente de cuadrícula simplex libre de patentes. |
| **Autómatas celulares** | Patrones de autómata celular. |
| **Gradiente con tramado** | Un degradado suave de dos colores con tramado aplicado sobre la paleta del documento, así que el resultado permanece dentro de la paleta. |

Cada generador es una **función pura y determinista de sus parámetros y semilla** —
la misma semilla y los mismos parámetros siempre producen la misma salida. El
contenido generado se escribe a través del **camino de comandos reversibles**, así
que cualquier generación es un único paso de deshacer. La salida está acotada por eje
según el límite de dimensión de procgen de la plataforma.

## Reversibilidad y capacidad de respuesta

Cada automatización — una reproducción de macro, una ejecución de script, un recolor
por lotes, un relleno procedural — se apila en la **pila normal de deshacer como un
paso**, así que puedes revertir cualquiera de ellas. En la interfaz gráfica, la
automatización se ejecuta en un **hilo trabajador en segundo plano** con cierre
determinista, así que un lote largo o un relleno procedural grande no congelan la
ventana.

## La línea de comandos `pixelart-run`

Para automatización y CI, `pixelart-run` reproduce un `.pixmacro` sobre un
`.pixproj` **sin interfaz gráfica** (sin GUI) a través del **mismo** despachador de
confianza exacto que impulsa la interfaz gráfica — así que el documento resultante es
**idéntico en estado** a la interfaz gráfica ejecutando la misma automatización sobre
la misma entrada.

```
pixelart-run --input PROYECTO.pixproj --macro MACRO.pixmacro --output SALIDA.pixproj [opciones]
```

| Indicador | Significado |
| --- | --- |
| `--input RUTA` | **(obligatorio)** el proyecto `.pixproj` de origen sobre el que ejecutar la macro. |
| `--macro RUTA` | **(obligatorio)** la macro `.pixmacro` a reproducir. |
| `--output RUTA` | **(obligatorio)** la ruta `.pixproj` donde escribir el resultado. |
| `--seed N` | sustituye la semilla de las operaciones que no grabaron ninguna (una semilla grabada siempre prevalece). |
| `--param CLAVE=VALOR` | inyecta o sustituye un parámetro de la macro; se puede repetir. |

**Códigos de salida:** `0` éxito; `1` un fallo de automatización (un error de
script/macro/lote/procgen, o un fallo de escritura); `2` argumentos
incorrectos o un proyecto o macro de entrada malformado/ilegible.

> **Punto de entrada de consola.** `pixelart-run` se instala como un script de
> consola con `pip install`.

## Lo que no se cubre

- **Scripting arbitrario en Python** — **no soportado por diseño.** El scripting es
  un DSL de comandos acotado y basado en lista de permitidos, no un intérprete de
  propósito general; esto es un límite de seguridad deliberado, no una limitación
  pendiente de levantar.
- **Aislamiento de complementos de terceros no confiables** — **aplazado.** Los
  complementos no están dentro de un entorno aislado en esta versión; instala y
  habilita solo complementos en los que confíes.

## Temas relacionados

- Las automatizaciones componen las mismas operaciones que realizas a mano — consulta
  [capas](layers.md), [exportación](export-and-pipeline.md), y el
  [centro de color](colour-hub.md).
