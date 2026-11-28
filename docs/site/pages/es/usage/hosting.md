<!-- surface-only: site — contenido de despliegue/instalación; extraído de la sección "Nota para operadores: ejecutar el backend de sincronización" de collaboration.md del bundle, que sigue siendo la única mención de este material en el bundle -->
# Alojar el relé en tiempo real: tres opciones equivalentes

La colaboración en tiempo real (coedición en vivo y cursores) se
transporta mediante un pequeño relé de **backend de sincronización** (consulta
la sección de [Coedición en tiempo real](collaboration.md#coedicion-en-tiempo-real)
de la guía de proyectos compartidos). Dónde se ejecuta ese relé es **tu
elección**, y la plataforma ofrece **tres opciones de alojamiento
equivalentes** — ninguna de ellas es una opción "recomendada" o "de
producción" por defecto, y elegir una **no cambia nada** en la app ni en el
backend en sí.

!!! warning "No accesible desde la app en esta versión"
    La aplicación de escritorio no tiene configurada ninguna conexión en tiempo
    real: **Nube ▸ Iniciar tiempo real…** muestra en la barra de estado un
    mensaje en inglés que termina en "no real-time transport configured" (no hay
    transporte en tiempo real configurado) en lugar de unirse a un relé. La app
    todavía no puede conectarse a ninguna de las opciones siguientes; describen
    dónde puede ejecutarse el propio relé.

!!! important "Ninguna opción es obligatoria"
    Ninguna de las tres opciones es obligatoria ni se recomienda sobre las
    demás, incluido no usar ninguna de ellas, y adoptar cualquiera de ellas no
    requiere **ningún cambio de código** en la app ni en el backend. El enlace por defecto del propio relé es
    **local/loopback**; el lanzador de `deploy/` de la Opción 3 se enlaza a
    `0.0.0.0` salvo que `PIXELART_SYNC_HOST` indique otra cosa.

## Opción 1 — Local/loopback (el valor por defecto entregado)

Nada que configurar. El enlace por defecto del propio relé (`SyncServer`) es
`127.0.0.1` (loopback) — para una sola máquina, pruebas locales o uso sin
conexión. El lanzador de `deploy/` de la Opción 3 sustituye ese valor por
`0.0.0.0`. Esta es la base con la que se mide cualquier otra opción, y está
completamente probada de extremo a extremo por la suite de pruebas
automatizada.

## Opción 2 — Adaptador de proveedor de nube

La colaboración está diseñada para fluir a través del mismo **puerto de nube
agnóstico de proveedor** usado para los guardados en la nube de un solo usuario
(consulta la guía de [Nube](cloud.md)). En esta versión ese puerto lo sirve
únicamente el adaptador integrado en memoria, y los proveedores reales de
Google Drive / OneDrive / Dropbox no se pueden elegir desde el menú **Nube**,
así que esta opción todavía no está disponible desde la app. Consulta
[Conectar un proveedor de nube](cloud.md#conectar-un-proveedor-de-nube) y
[Proyectos compartidos y comentarios](collaboration.md) para ver qué hace hoy
el menú Nube.

## Opción 3 — Autoalojado en un VPS

Puedes ejecutar tú mismo el relé `sync_backend/` **sin cambios**, en un VPS
genérico accesible por internet, usando los artefactos de despliegue que se
entregan junto al backend:

- **`deploy/Dockerfile`** — construye una imagen de contenedor que ejecuta el
  relé como un proceso sin privilegios de root.
- **`deploy/pixelart-sync.service`** — una unidad systemd para ejecutar el
  relé como un servicio gestionado en un host Linux.
- **`deploy/nginx-sync.conf`** — una configuración de proxy inverso de Nginx
  que termina TLS y hace proxy de WSS hacia el relé, con las cabeceras
  `Upgrade`/`Connection` de WebSocket y el ajuste de tiempo de espera de
  inactividad que necesita para mantenerse conectado.
- **`deploy/run_sync_backend.py`** — el lanzador que usan estos artefactos
  para iniciar el relé.

!!! note "Solo artefactos de despliegue — el código del backend no cambia"
    Estos archivos empaquetan y ejecutan el mismo relé `sync_backend/` que
    usan las otras dos opciones; no lo modifican. Elegir esta opción es
    completamente opcional y reversible, y no tiene ningún efecto sobre
    quienes no la usan.

!!! tip "Detalle de nivel operador"
    El aprovisionamiento de certificados, las reglas de cortafuegos y otros
    pasos de administración de servidor quedan fuera del alcance de esta guía
    de usuario. La configuración detallada para operadores vive en las notas
    de despliegue privadas del proyecto; los comentarios de configuración en
    línea de cada artefacto de `deploy/` anterior son el punto de partida de
    cara al público.

## Elegir entre las tres

| Opción | Esfuerzo de configuración | Adecuada para |
| --- | --- | --- |
| Local/loopback | Ninguno — es el enlace por defecto del propio relé | Una sola máquina, pruebas locales, uso sin conexión |
| Adaptador de proveedor de nube | No disponible desde la app en esta versión | Equipos que ya usan un proveedor de nube |
| Autoalojado en un VPS | Despliega los artefactos de `deploy/` anteriores | Alojar tú mismo el relé, en tu propio servidor |

Elijas la que elijas (o ninguna), la app y el código fuente del backend son los
mismos. El flujo de colaboración — compartir, comentarios, presencia, coedición
en tiempo real y ramificación — se documenta en
[Proyectos compartidos y comentarios](collaboration.md), incluido qué partes no
pueden conectarse en esta versión.
