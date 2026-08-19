# Automatización y extensibilidad

El **sistema de automatización** te permite grabar, programar mediante
scripts, reproducir y procesar por lotes las operaciones propias del editor,
generar contenido de forma procedural, y ampliar la aplicación con
complementos de confianza — todo a través de **un solo** motor que la interfaz
gráfica y la línea de comandos sin interfaz gráfica `pixelart-run` comparten,
así que una automatización se ejecuta **de forma idéntica** tanto si la
activas desde un panel como desde un script de compilación.

!!! note "Seguridad por diseño — nunca `eval`"
    El scripting es un **DSL de comandos acotado y basado en datos**, no
    Python arbitrario. Una automatización es una *lista validada de
    operaciones* (`{name, params, seed}`), nunca un lenguaje: **no hay
    `eval` / `exec` / `compile` / `__import__` de tu entrada en ningún punto**
    de este camino — no hay ningún intérprete del que escapar (Artículo VII de
    la constitución, satisfecho por construcción). Un único despachador de
    confianza comprueba el nombre de cada operación contra una **lista de
    permitidos** y sus parámetros contra un esquema declarado antes de
    construir el comando reversible al que se asigna.

## Macros — grabar, reproducir y el formato `.pixmacro`

El **panel de macros** graba las operaciones que realizas y las reproduce
después:

- **Grabar** captura las *entradas* de cada paso — los parámetros resueltos y,
  para cualquier paso aleatorio, la **semilla** — no una diferencia de
  píxeles. Lo que grabas es lo que una reproducción vuelve a ejecutar.
- **Reproducir** vuelve a aplicar las operaciones grabadas al documento actual
  como **un solo paso de deshacer**, así que deshacer revierte la macro
  completa de una vez.

Una macro se almacena como un archivo **`.pixmacro`** — JSON plano con una
envoltura versionada:

```json
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

- **`schema_version` / `api_version` / `min_app_version`** se comprueban al
  cargar: una versión desconocida o no soportada **falla de forma explícita**
  con un error claro en lugar de reproducirse mal contra una operación cuya
  interfaz cambió de forma incompatible.
- **`params`** son nativos de JSON (números, cadenas, booleanos, `null`,
  listas, objetos anidados), así que guardar y luego cargar una macro produce
  una macro **idéntica** — los colores y los mapas de índices viajan como
  listas (`[[r, g, b, a], …]` / `[[src, dst], …]`).
- **`seed`** se graba para cada paso estocástico, así que la reproducción es
  reproducible.

!!! note "Reproducción determinista"
    Reproducir la misma macro sobre el mismo documento de partida dos veces
    produce un documento **idéntico en estado**. Cada paso aleatorio extrae
    solo de su semilla grabada — sin reloj del sistema, sin aleatoriedad sin
    semilla, sin dependencia de configuración regional, y sin iteración de
    orden inestable. Esto es lo que hace que una macro sea segura de ejecutar
    en una canalización de compilación.

Cargar un `.pixmacro` es **defensivo**: cada campo se comprueba por tipo,
límites y versión (la misma postura que al cargar un `.pixproj`), un
documento malformado o fuera de límites lanza un error claro, y el contenido
**nunca** se pasa a `eval`/`exec`.

## Ejecutar scripts

El **ejecutor de scripts** despacha una lista de operaciones a través del
mismo despachador de confianza que usa la reproducción de macros. Una
ejecución de script es **atómica**:

1. **Cada operación se valida por adelantado** — todos los nombres de
   operación se comprueban contra la lista de permitidos y todos los
   parámetros contra su esquema **antes de aplicar nada**.
2. La ejecución completa se aplica como **un único comando agrupado y
   reversible**.
3. Si alguna operación falla a mitad de camino, las operaciones ya aplicadas
   se **revierten en orden inverso**, así que una ejecución multi-operación
   fallida deja el documento **sin cambios** — nunca a medio aplicar.

Como la ejecución es un único comando agrupado, un script completado es **un
único paso de deshacer**.

## Complementos — el gestor, el consentimiento y el modelo de confianza

El **gestor de complementos** descubre, activa y desactiva complementos. Los
complementos amplían el editor registrando nuevas operaciones del DSL — y
solo eso.

- **El descubrimiento es inerte.** Los complementos instalados se *encuentran*
  (mediante los puntos de entrada estándar de Python) pero **nada se carga ni
  se ejecuta** solo por estar instalado. Los ves listados; no hacen nada hasta
  que actúas.
- **Denegar por defecto, con consentimiento explícito.** Activar un
  complemento le entrega un **objeto de capacidad cuya única superficie es el
  registro de comandos del DSL**. Un complemento no puede hacer
  `eval`/`exec`, no puede alcanzar la interfaz, y no puede tocar el sistema de
  archivos o la red fuera de las capacidades que le concedas — **toda
  capacidad que no declaró y no le concediste se deniega**. Sus operaciones
  están asociadas al espacio de nombres del complemento, así que un
  complemento no puede suplantar una operación integrada.
- **Desactivar es limpio.** Desactivar un complemento anula el registro de
  las operaciones que añadió.

!!! warning "De confianza con consentimiento, en esta versión"
    Como *cargar* un complemento de Python es en sí mismo ejecutar código, el
    modelo de capacidades en proceso es de **fuerza consultiva** — adecuado
    para **extensiones de confianza que instalas y consientes**, no para
    código arbitrario de un mercado no confiable. El aislamiento a nivel de
    sistema operativo de complementos de terceros no confiables queda
    **aplazado** a una fase posterior (Artículo XI de la constitución). Instala
    solo complementos en los que confíes.

## Recolor por lotes

**Recolor por lotes** aplica un remapeo de color a **muchos objetivos a la
vez** como un **único comando transaccional y reversible**:

- Para objetivos **indexados**, remapea índices de paleta
  (`old_index → new_index`); para objetivos **RGBA**, remapea colores
  (`old_rgba → new_rgba`). Reutiliza las operaciones de recolor existentes del
  editor, así que un objetivo procesado por lotes es **idéntico byte a byte**
  a recolorear ese objetivo por sí solo con el mismo mapeo.
- Es **transaccional**: cada objetivo se valida y su paso individual se
  construye **antes de aplicar nada**. Un objetivo inválido (un desajuste de
  modo o un mapeo fuera de rango) falla nombrando el objetivo problemático con
  **cero mutación** — un objetivo defectuoso nunca corrompe a los demás. El
  lote completo es **un único paso de deshacer**.

## Generación procedural

El **panel de procgen** rellena una región con contenido generado. Hay cinco
generadores propios y **con semilla** disponibles:

| Generador | Qué produce |
| --- | --- |
| **Ruido de valor** | Ruido de cuadrícula de valor con semilla. |
| **Ruido de gradiente** | Ruido de gradiente estilo Perlin. |
| **OpenSimplex** | Un ruido de gradiente de cuadrícula simplex libre de patentes. |
| **Celular** | Patrones de autómata celular. |
| **Degradado con dithering** | Un degradado suave de dos colores con dithering aplicado sobre la paleta del documento (usando el dithering ordenado / de Floyd–Steinberg incluido), así que el resultado permanece dentro de la paleta. |

Cada generador es una **función pura y determinista de sus parámetros y
semilla** — la misma semilla y los mismos parámetros siempre producen la
misma salida (la aleatoriedad se extrae solo de la semilla, nunca del reloj
del sistema). El contenido generado se escribe a través del **camino de
comandos reversibles**, así que cualquier generación es un único paso de
deshacer. La salida está acotada por eje según el límite de dimensión de
procgen de la plataforma.

## Reversibilidad y capacidad de respuesta

Cada automatización — una reproducción de macro, una ejecución de script, un
recolor por lotes, un relleno procedural — se apila en la **pila normal de
deshacer como un solo paso**, así que puedes revertir cualquiera de ellas. En
la interfaz gráfica, la automatización se ejecuta en un **hilo trabajador en
segundo plano** con cierre determinista, así que un lote largo o un relleno
procedural grande no congelan la ventana.

## La línea de comandos `pixelart-run`

Para automatización y CI, `pixelart-run` reproduce un `.pixmacro` sobre un
`.pixproj` **sin interfaz gráfica** (sin GUI) a través del **mismo**
despachador de confianza exacto que impulsa la interfaz gráfica — así que el
documento resultante es **idéntico en estado** a la interfaz gráfica
ejecutando la misma automatización sobre la misma entrada. Carga tanto el
proyecto como la macro a través de los mismos cargadores defensivos y
validados que usa la aplicación.

```
pixelart-run --input PROJECT.pixproj --macro MACRO.pixmacro --output OUT.pixproj [options]
```

| Indicador | Significado |
| --- | --- |
| `--input PATH` | **(obligatorio)** el proyecto `.pixproj` de origen sobre el que ejecutar la macro. |
| `--macro PATH` | **(obligatorio)** la macro `.pixmacro` a reproducir. |
| `--output PATH` | **(obligatorio)** la ruta `.pixproj` donde escribir el resultado. |
| `--seed N` | sustituye la semilla de las operaciones que no grabaron ninguna (una semilla grabada siempre prevalece, así que la reproducción se mantiene determinista). |
| `--param KEY=VALUE` | inyecta o sustituye un parámetro de la macro; se puede repetir. Un valor numérico se interpreta como entero; en caso contrario se conserva como cadena. |

**Códigos de salida:** `0` éxito; `1` un fallo de automatización (un error de
script / macro / complemento / lote / procgen, o un fallo de escritura); `2`
argumentos incorrectos o un proyecto o macro de entrada malformado / ilegible.

!!! tip "El mismo camino que la interfaz gráfica"
    Como la CLI y la interfaz gráfica impulsan el mismo despachador, puedes
    grabar una macro de forma interactiva y luego reproducirla exactamente en
    un script de compilación — la salida es idéntica en estado.

!!! note "Punto de entrada de consola"
    `pixelart-run` se instala como un script de consola con `pip install`.

## Lo que no se cubre

- **Scripting arbitrario en Python** — **no soportado por diseño.** El
  scripting es un DSL de comandos acotado y basado en lista de permitidos, no
  un intérprete de propósito general; esto es un límite de seguridad
  deliberado (Artículo VII), no una limitación pendiente de levantar.
- **Aislamiento de complementos de terceros no confiables** — **aplazado.**
  Los complementos son de confianza con consentimiento en esta versión; el
  sandboxing a nivel de sistema operativo de complementos de mercado no
  confiables es un desarrollo posterior de una fase futura (Artículo XI).
  Instala solo complementos en los que confíes.
