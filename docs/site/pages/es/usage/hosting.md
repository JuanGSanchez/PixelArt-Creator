<!-- REQ-P13-BACKEND-003 -->
# Alojar el relé en tiempo real: tres opciones equivalentes

La colaboración en tiempo real (coedición en vivo, cursores y ramificación) se
transporta mediante un pequeño relé de **backend de sincronización** (consulta
la sección de [Coedición en tiempo real](collaboration.md#coedicion-en-tiempo-real)
de la guía de proyectos compartidos). Dónde se ejecuta ese relé es **tu
elección**, y la plataforma ofrece **tres opciones de alojamiento
equivalentes** — ninguna de ellas es una opción "recomendada" o "de
producción" por defecto, y elegir una **no cambia nada** en la app ni en el
backend en sí.

!!! important "Sin opción forzada por defecto"
    El comportamiento de colaboración de la app es idéntico sin importar qué
    opción uses, incluido si no usas ninguna de ellas: el valor por defecto
    entregado es **local/loopback**, y adoptar cualquiera de las otras dos
    opciones no requiere **ningún cambio de código** en la app ni en el
    backend (`REQ-P13-BACKEND-003`).

## Opción 1 — Local/loopback (el valor por defecto entregado)

Nada que configurar. El enlace por defecto del relé es `127.0.0.1`
(loopback), y es lo que usa la app tal cual — para una sola máquina, pruebas
locales o uso sin conexión. Esta es la base con la que se mide cualquier otra
opción, y está completamente probada de extremo a extremo por la suite de
pruebas automatizada.

## Opción 2 — Adaptador de proveedor de nube

La colaboración también puede fluir a través del mismo **puerto de nube
agnóstico de proveedor** usado para los guardados en la nube de un solo
usuario (consulta la guía de [Nube](cloud.md)): el adaptador integrado en
memoria por defecto, o una cuenta real de Google Drive / OneDrive / Dropbox
detrás del mismo flujo de Conectar. Elige esta opción si ya enrutas tus
proyectos a través de un proveedor de nube y quieres que la colaboración siga
el mismo camino — todo se maneja desde el menú **Nube** dentro de la app, así
que no necesitas administrar ningún servidor por tu cuenta. Consulta
[Conectar un proveedor de nube](cloud.md#conectar-un-proveedor-de-nube) y
[Proyectos compartidos y comentarios](collaboration.md) para el flujo de
conectar/compartir.

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
| Local/loopback | Ninguno — es el valor por defecto | Una sola máquina, pruebas locales, uso sin conexión |
| Adaptador de proveedor de nube | Conecta un proveedor desde el menú Nube | Equipos que ya usan un proveedor de nube |
| Autoalojado en un VPS | Despliega los artefactos de `deploy/` anteriores | Alojar tú mismo el relé, en tu propio servidor |

Elijas la que elijas (o ninguna), el resto del flujo de colaboración —
compartir, comentarios, presencia, coedición en tiempo real y ramificación —
se comporta exactamente como se documenta en
[Proyectos compartidos y comentarios](collaboration.md).
