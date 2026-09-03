<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="es" sourcelanguage="en">
<context>
    <name>Asset_Library_Panel</name>
    <message>
        <location filename="../ui/asset_library_panel.py" line="162"/>
        <source>Broken reference</source>
        <extracomment>Emitted with the selected entry&apos;s ``asset_id`` (``&quot;&quot;`` when cleared). The active filter driven by the search panel (empty = full catalog).</extracomment>
        <translation>Referencia rota</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="186"/>
        <source>Sprite</source>
        <translation>Sprite</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="187"/>
        <source>Animation</source>
        <translation>Animación</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="188"/>
        <source>Tileset</source>
        <translation>Conjunto de tiles</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="189"/>
        <source>Tilemap</source>
        <translation>Mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="190"/>
        <source>Palette</source>
        <translation>Paleta</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="195"/>
        <source>Asset library</source>
        <translation>Biblioteca de recursos</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Name</source>
        <translation>Nombre</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Kind</source>
        <translation>Tipo</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Tags</source>
        <translation>Etiquetas</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Status</source>
        <translation>Estado</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="199"/>
        <source>Catalog assets</source>
        <translation>Recursos del catálogo</translation>
    </message>
</context>
<context>
    <name>Asset_Library_Session</name>
    <message>
        <location filename="../ui/asset_library_actions.py" line="506"/>
        <source>Import asset artifact</source>
        <extracomment>Emitted after any change to the catalog (add / remove / tag do-undo) so the bound panels re-read and repaint. No payload — panels pull the fresh catalog. Emitted after the dependency graph is replaced so the dependency-graph view and the passive break surface re-read and repaint. No payload. Emitted after a registration action commits — carries the :class:`RegistrationOutcome` (REQ-P11-UI-017). Emitted when a registration action cannot commit — carries a translatable message; the catalog, store and revision history are all left unchanged (REQ-P11-UI-017). Emitted when the user cancels the registration prompt — cancelling is not a failure (REQ-P11-UI-017; RP-4). Emitted after a successful registration&apos;s derived dependency edges are computed (ruling P11-R6, REQ-P11-LOGIC-010 / REQ-P11-UI-018) — carries the **accumulated** edge set (this session&apos;s current graph edges plus the newly derived ones), because the bound consumer (:meth:`~pixelart_creator.ui.dependency_graph_view.Dependency_Graph_View. show_edges`) *replaces* the graph it is handed rather than merging into it. This session never calls :meth:`set_graph` itself and never imports the view — ``show_edges`` alone decides whether the accumulated set is accepted (and, on a closed cycle, rejected passively, the prior graph kept) — see ``main_window.py``&apos;s connection of this signal. Emitted after a single library artifact (``.pixasset``) is imported and merged + committed into the already-open library (ruling P11-R5, REQ-P11-UI-015/-016) — carries the imported ``Tuple[AssetDescriptor, ...]``. Emitted when a library-artifact import cannot commit — a translatable message; the catalog and store are unchanged. Emitted when the user cancels the &quot;Import asset artifact&quot; file dialog. Emitted after a chosen catalog subset is written to a library artifact file (REQ-P11-UI-016) — carries the destination path as ``str``. Emitted when a library-subset export cannot complete — a translatable message; no file is written. Emitted when the user cancels the &quot;Export asset artifact&quot; file dialog. Emitted after a project + its whole reference set is written to a ``.pixbundle`` file (the shipped :func:`~pixelart_creator.data.asset_export.export_project_bundle`, unchanged) — carries the destination path as ``str``. Emitted when a project-bundle export cannot complete — a translatable message; no file is written. Emitted when the user cancels the &quot;Export project bundle&quot; file dialog. Emitted after a ``.pixbundle`` is reconstructed into a new project directory (the shipped :func:`~pixelart_creator.data.asset_export.import_project_bundle`, unchanged) — carries the ``(Document, AssetCatalog)`` tuple. This session&apos;s own catalog is untouched: the bundle reconstructs a **new** project, never merging into the open library (plan Section 3.7). Emitted when a project-bundle import cannot complete — a translatable message; ``target_dir`` is left exactly as it was (the shipped function&apos;s own atomic-move guarantee). Emitted when the user cancels the &quot;Import project bundle&quot; file dialog. The shared undo stack the tag commands push onto (REQ-P11-UI-002). The durable catalog root once bound (REQ-P11-DATA-008); ``None`` until :meth:`bind_root` is called, so an unbound session stays purely in-memory. The content-addressable store the registration actions write blobs through, once bound; ``None`` until :meth:`bind_content_store`. The revision store the registration actions record through, once bound; ``None`` until :meth:`bind_revision_store`.</extracomment>
        <translation>Importar artefacto de recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="507"/>
        <location filename="../ui/asset_library_actions.py" line="570"/>
        <source>Asset artifact (*%1)</source>
        <translation>Artefacto de recurso (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="518"/>
        <source>&quot;%1&quot; is a project bundle, not a single asset. Use &quot;Import project bundle...&quot; instead.</source>
        <translation>«%1» es un paquete de proyecto, no un único recurso. Use «Importar paquete de proyecto...» en su lugar.</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="523"/>
        <location filename="../ui/asset_library_actions.py" line="723"/>
        <source>Import asset</source>
        <translation>Importar recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="569"/>
        <source>Export asset artifact</source>
        <translation>Exportar artefacto de recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="624"/>
        <location filename="../ui/asset_library_actions.py" line="741"/>
        <source>Export project bundle</source>
        <translation>Exportar paquete de proyecto</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="625"/>
        <location filename="../ui/asset_library_actions.py" line="676"/>
        <source>Project bundle (*%1)</source>
        <translation>Paquete de proyecto (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="675"/>
        <location filename="../ui/asset_library_actions.py" line="752"/>
        <source>Import project bundle</source>
        <translation>Importar paquete de proyecto</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="720"/>
        <source>Could not import the asset: %1</source>
        <translation>No se pudo importar el recurso: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="727"/>
        <source>Could not export the asset: %1</source>
        <translation>No se pudo exportar el recurso: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="730"/>
        <source>Export asset</source>
        <translation>Exportar recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="736"/>
        <source>Could not export the project bundle: %1</source>
        <translation>No se pudo exportar el paquete de proyecto: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="747"/>
        <source>Could not import the project bundle: %1</source>
        <translation>No se pudo importar el paquete de proyecto: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="817"/>
        <source>There is no active selection to register.</source>
        <translation>No hay ninguna selección activa para registrar.</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="1136"/>
        <source>Could not register the asset: %1</source>
        <translation>No se pudo registrar el recurso: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="1139"/>
        <source>Asset registration</source>
        <translation>Registro de recurso</translation>
    </message>
</context>
<context>
    <name>Asset_Register_Dialog</name>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="164"/>
        <source>Too many tags: %1 given, %2 allowed.</source>
        <extracomment>Combo order = the five shipped kinds, in the vocabulary&apos;s own declaration order (``logic/asset_catalog.AssetKind`` — RP-1&apos;s &quot;five shipped kinds&quot;).</extracomment>
        <translation>Demasiadas etiquetas: %1 proporcionadas, %2 permitidas.</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="170"/>
        <source>Tag &quot;%1&quot; is too long (%2 bytes allowed).</source>
        <translation>La etiqueta «%1» es demasiado larga (%2 bytes permitidos).</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="178"/>
        <source>Enter a name for this asset.</source>
        <translation>Introduzca un nombre para este recurso.</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="190"/>
        <source>Register Asset</source>
        <translation>Registrar recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="191"/>
        <source>Asset registration prompt</source>
        <translation>Cuadro de registro de recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="193"/>
        <source>Name</source>
        <translation>Nombre</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="194"/>
        <source>Asset display name</source>
        <translation>Nombre visible del recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="195"/>
        <source>Display name</source>
        <translation>Nombre visible</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="197"/>
        <source>Kind</source>
        <translation>Tipo</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="198"/>
        <source>Asset kind</source>
        <translation>Tipo de recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="199"/>
        <source>Sprite</source>
        <translation>Sprite</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="200"/>
        <source>Animation</source>
        <translation>Animación</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="201"/>
        <source>Tileset</source>
        <translation>Conjunto de tiles</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="202"/>
        <source>Tilemap</source>
        <translation>Mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="203"/>
        <source>Palette</source>
        <translation>Paleta</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="205"/>
        <source>Tags</source>
        <translation>Etiquetas</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="206"/>
        <source>Asset tags, comma-separated</source>
        <translation>Etiquetas del recurso, separadas por comas</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="207"/>
        <source>Optional tags, comma-separated</source>
        <translation>Etiquetas opcionales, separadas por comas</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="209"/>
        <source>Registration validation message</source>
        <translation>Mensaje de validación del registro</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="213"/>
        <source>Register</source>
        <translation>Registrar</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="214"/>
        <source>Register asset</source>
        <translation>Registrar recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="217"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="218"/>
        <source>Cancel registration</source>
        <translation>Cancelar registro</translation>
    </message>
</context>
<context>
    <name>Asset_Reuse_Panel</name>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="249"/>
        <source>The selected asset is not available.</source>
        <extracomment>Columns of the in-project reference list (REQ-P11-UI-021 indicators). The selected asset row&apos;s ``asset_id`` is stashed on the name column (both trees). Emitted with ``(asset_id, project)`` after a successful reference. Each open project&apos;s real, durable reference set (REQ-P11-UI-021), bound through :meth:`set_project_reference_set` or created empty by :meth:`add_project`. Never a predicate&apos;s own scratch state. In-project reference list — the resolve-state / shared-state indicators (REQ-P11-UI-021), over the *current* project&apos;s real reference set.</extracomment>
        <translation>El recurso seleccionado no está disponible.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="256"/>
        <source>Shared content for %1 is not available.</source>
        <translation>El contenido compartido de %1 no está disponible.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="271"/>
        <source>%1 is already referenced in %2.</source>
        <translation>%1 ya está referenciado en %2.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="277"/>
        <source>Referenced %1 into %2.</source>
        <translation>Se ha referenciado %1 en %2.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="340"/>
        <location filename="../ui/asset_reuse_panel.py" line="403"/>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <location filename="../ui/asset_reuse_panel.py" line="479"/>
        <source>Shared</source>
        <translation>Compartido</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="352"/>
        <location filename="../ui/asset_reuse_panel.py" line="420"/>
        <source>Referenced by another open project</source>
        <translation>Referenciado por otro proyecto abierto</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="399"/>
        <source>In library</source>
        <translation>En la biblioteca</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="401"/>
        <source>Not found in library</source>
        <translation>No encontrado en la biblioteca</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="416"/>
        <source>This reference could not be found in the local library.</source>
        <translation>No se pudo encontrar esta referencia en la biblioteca local.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="425"/>
        <source>%1 unresolved reference(s) in this project.</source>
        <translation>%1 referencia(s) sin resolver en este proyecto.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="431"/>
        <source>All references resolve in the local library.</source>
        <translation>Todas las referencias se resuelven en la biblioteca local.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="447"/>
        <source>Sprite</source>
        <translation>Sprite</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="448"/>
        <source>Animation</source>
        <translation>Animación</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="449"/>
        <source>Tileset</source>
        <translation>Conjunto de tiles</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="450"/>
        <source>Tilemap</source>
        <translation>Mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="451"/>
        <source>Palette</source>
        <translation>Paleta</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="457"/>
        <source>Cross-project reuse</source>
        <translation>Reutilización entre proyectos</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="458"/>
        <source>Project:</source>
        <translation>Proyecto:</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="459"/>
        <source>Target project</source>
        <translation>Proyecto de destino</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="460"/>
        <location filename="../ui/asset_reuse_panel.py" line="461"/>
        <source>New project name</source>
        <translation>Nombre del nuevo proyecto</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="462"/>
        <source>Add Project</source>
        <translation>Añadir proyecto</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="463"/>
        <source>Add a project</source>
        <translation>Añadir un proyecto</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <location filename="../ui/asset_reuse_panel.py" line="476"/>
        <source>Name</source>
        <translation>Nombre</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <location filename="../ui/asset_reuse_panel.py" line="477"/>
        <source>Kind</source>
        <translation>Tipo</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <source>Projects</source>
        <translation>Proyectos</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="467"/>
        <source>Shared assets</source>
        <translation>Recursos compartidos</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="468"/>
        <source>Reference into Project</source>
        <translation>Referenciar en el proyecto</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <source>Reference the selected asset into the project</source>
        <translation>Referenciar el recurso seleccionado en el proyecto</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="472"/>
        <source>Reuse status</source>
        <translation>Estado de reutilización</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="473"/>
        <source>References in this project:</source>
        <translation>Referencias en este proyecto:</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="478"/>
        <source>Resolve state</source>
        <translation>Estado de resolución</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="483"/>
        <source>References in the current project</source>
        <translation>Referencias en el proyecto actual</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="485"/>
        <source>Missing reference count</source>
        <translation>Recuento de referencias faltantes</translation>
    </message>
</context>
<context>
    <name>Asset_Search_Panel</name>
    <message>
        <location filename="../ui/asset_search_panel.py" line="133"/>
        <source>Sprite</source>
        <extracomment>The fixed display order of the kind combo (after the &quot;All kinds&quot; entry). Emitted with ``(name, tags, kind)`` whenever a control changes. ``name`` is a possibly-empty str, ``tags`` a list of str, ``kind`` an ``AssetKind`` or ``None``. The library panel consumes it via ``set_query``.</extracomment>
        <translation>Sprite</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="134"/>
        <source>Animation</source>
        <translation>Animación</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="135"/>
        <source>Tileset</source>
        <translation>Conjunto de tiles</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="136"/>
        <source>Tilemap</source>
        <translation>Mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="137"/>
        <source>Palette</source>
        <translation>Paleta</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="142"/>
        <source>Asset search and filter</source>
        <translation>Búsqueda y filtro de recursos</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="143"/>
        <source>Name:</source>
        <translation>Nombre:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="144"/>
        <location filename="../ui/asset_search_panel.py" line="145"/>
        <source>Search by name</source>
        <translation>Buscar por nombre</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="146"/>
        <source>Tags:</source>
        <translation>Etiquetas:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="147"/>
        <source>Filter by tags (comma-separated)</source>
        <translation>Filtrar por etiquetas (separadas por comas)</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="148"/>
        <source>Filter by tags</source>
        <translation>Filtrar por etiquetas</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="149"/>
        <source>Kind:</source>
        <translation>Tipo:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="150"/>
        <source>Filter by kind</source>
        <translation>Filtrar por tipo</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="151"/>
        <source>All kinds</source>
        <translation>Todos los tipos</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="154"/>
        <source>Clear</source>
        <translation>Limpiar</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="155"/>
        <source>Clear the search and filters</source>
        <translation>Limpiar la búsqueda y los filtros</translation>
    </message>
</context>
<context>
    <name>Asset_Tagging_Panel</name>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="121"/>
        <location filename="../ui/asset_tagging_panel.py" line="145"/>
        <source>Tagging</source>
        <extracomment>The asset whose tags are being edited (``&quot;&quot;`` when none is selected).</extracomment>
        <translation>Etiquetado</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="126"/>
        <source>Add tag &quot;%1&quot;</source>
        <translation>Añadir etiqueta &quot;%1&quot;</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="150"/>
        <source>Remove tag &quot;%1&quot;</source>
        <translation>Eliminar etiqueta &quot;%1&quot;</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="185"/>
        <source>No asset selected</source>
        <translation>Ningún recurso seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="188"/>
        <source>Tags for: %1</source>
        <translation>Etiquetas de: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="192"/>
        <source>Asset tagging</source>
        <translation>Etiquetado de recursos</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="193"/>
        <source>Asset tags</source>
        <translation>Etiquetas del recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="194"/>
        <location filename="../ui/asset_tagging_panel.py" line="195"/>
        <source>New tag</source>
        <translation>Nueva etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="196"/>
        <source>Add Tag</source>
        <translation>Añadir etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="197"/>
        <source>Add tag to asset</source>
        <translation>Añadir etiqueta al recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="198"/>
        <source>Remove Tag</source>
        <translation>Eliminar etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="199"/>
        <source>Remove selected tag</source>
        <translation>Eliminar la etiqueta seleccionada</translation>
    </message>
</context>
<context>
    <name>Asset_Update_Prompt_Dialog</name>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="491"/>
        <source>Library Asset Updated</source>
        <extracomment>This dialog&apos;s own outcome vocabulary — distinct from the *persisted* three-value preference domain (``&quot;ask&quot;`` / ``&quot;always_pick_up&quot;`` / ``&quot;always_keep_referenced&quot;``, declared in ``logic/asset_references.ASSET_LIBRARY_EDIT``): an outcome is what THIS prompt resolved to for ONE edit; the preference is what to do about FUTURE edits without asking. **Promoted aliases (ADR-0062, ruling P11-R13 — same &quot;one definition of a control, aliases kept so no call site moves&quot; move ruling P11-R11 made for ``data/asset_catalog_io.py``&apos;s ``_safe_asset_id`` / ``_resolve_within``, applied here in the other direction):** the canonical outcome domain now lives in the logic layer, :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_PICK_UP` / :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_KEEP`, at byte-identical values — these two names are retained, unchanged, as aliases so every existing reference in this module and its callers still resolves without moving. The two non-default members of ``ASSET_LIBRARY_EDIT.domain`` this prompt writes through :func:`~pixelart_creator.logic.project_prefs.with_value` (the registered seam validates membership; nothing here re-derives the domain). One session-memory entry key: ``(asset_id, edit_token)``. ``edit_token`` is ``None`` when the caller has no content-hash identity to hand yet (see :meth:`Asset_Update_Prompt_Dialog.decide`) — two ``None``-token calls with the same ``asset_id`` are therefore treated as the SAME edit, which is the exact, disclosed limit of this session memory absent a real per-edit identity (module docstring boundary note). Emitted once a button is clicked, before the dialog closes: ``(outcome, dont_ask_again)``. For a caller driving the dialog non-modally (``open()``); :meth:`decide` does not need it. **Per-edit session memory** (extended by plan §3.11 (2b)): &quot;the same edit does not ask again&quot; for :meth:`decide` (``REQ-P11-UI-022``&apos;s own acceptance clause), scoped to one project&apos;s session bucket so a different project (:data:`ProjectPrefs`, ``SC-P11-UI-023-3``) is never affected by another project&apos;s session memory. Keyed by ``id(prefs)`` -&gt; ``(prefs, {edit_key: outcome})`` when no ``project_key`` is supplied (today&apos;s byte-for-byte behaviour — the snapshot itself is held strongly alongside its id so a *live* entry&apos;s id can never be reused by an unrelated, later ``ProjectPrefs`` object, an ``is`` check on lookup is the defensive second line); keyed by the caller-supplied ``project_key`` (a ``str``) instead when one is given — the production route (``ui/main_window.py``, plan §3.11 (2b)), because ``document.prefs`` is *replaced* on any confirmation-preference toggle (``ui/project_prefs_actions.py:165/175``), which would silently orphan an ``id(prefs)``-keyed bucket. This dict itself is still in-memory, per-process runtime state — it is never itself written to disk, and it is never written through ``logic/project_prefs.py`` (that seam is reserved for the &quot;Don&apos;t ask again&quot; preference, ``REQ-P11-UI-023``, a materially different, explicit, durable choice). **Corrected (ADR-0062, ruling P11-R13):** this bucket is no longer the *only* record of an unticked decision — it can be **hydrated** at the start of a session from the durable, per-edit ledger (:class:`~pixelart_creator.logic.asset_edit_decisions.AssetEditDecisions`) via :meth:`prime_session`, and every fresh decision made through :meth:`decide` is handed to that method&apos;s optional ``on_decided`` callback so the caller can persist it (the write-ahead journal / the project-file save) — this module performs no I/O of its own; it only calls out. Disclosed cost, unchanged: a decided ``ProjectPrefs`` snapshot (or a live ``project_key`` bucket) is retained for the life of the process; call :meth:`forget_session` when a project closes to release it.</extracomment>
        <translation>Recurso de biblioteca actualizado</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="492"/>
        <source>Library asset updated confirmation</source>
        <translation>Confirmación de actualización de recurso de biblioteca</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="493"/>
        <source>this asset</source>
        <translation>este recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="496"/>
        <source>The library asset &quot;%1&quot; has changed since your project last referenced it. Pick up the change, or keep the version your project already references?</source>
        <translation>El recurso de biblioteca «%1» ha cambiado desde la última vez que su proyecto lo referenció. ¿Desea adoptar el cambio o mantener la versión que su proyecto ya referencia?</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="501"/>
        <source>Library edit notice</source>
        <translation>Aviso de edición de biblioteca</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="502"/>
        <source>Don&apos;t ask again</source>
        <translation>No volver a preguntar</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="504"/>
        <source>Remember this choice for future edits of this asset</source>
        <translation>Recordar esta elección para futuras ediciones de este recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="506"/>
        <source>Pick Up the Change</source>
        <translation>Adoptar el cambio</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="508"/>
        <source>Pick up the library asset&apos;s change</source>
        <translation>Adoptar el cambio del recurso de biblioteca</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="510"/>
        <source>Keep the Referenced Version</source>
        <translation>Mantener la versión referenciada</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="512"/>
        <source>Keep the version this project already references</source>
        <translation>Mantener la versión que este proyecto ya referencia</translation>
    </message>
</context>
<context>
    <name>Asset_Version_Browser</name>
    <message>
        <location filename="../ui/asset_version_browser.py" line="193"/>
        <source>%1 (current)</source>
        <extracomment>The selected row&apos;s revision ``content_hash`` is stashed on the order column. How many leading characters of a content hash the browser shows (the full hash is kept on the tooltip / item data — this is display abbreviation only, not identity). Emitted with the new head&apos;s ``content_hash`` after a successful restore (so a caller / test can react); no payload semantics beyond the reinstated head hash. The asset whose revisions are shown (``&quot;&quot;`` when none is selected).</extracomment>
        <translation>%1 (actual)</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="194"/>
        <location filename="../ui/asset_version_browser.py" line="233"/>
        <source>(unknown)</source>
        <translation>(desconocido)</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="231"/>
        <location filename="../ui/asset_version_browser.py" line="252"/>
        <location filename="../ui/asset_version_browser.py" line="262"/>
        <source>Version history</source>
        <translation>Historial de versiones</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="235"/>
        <source>Revision %1 — %2 bytes, marker %3, author %4</source>
        <translation>Revisión %1 — %2 bytes, marca %3, autor %4</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="314"/>
        <location filename="../ui/asset_version_browser.py" line="319"/>
        <source>Revisions of: %1</source>
        <translation>Revisiones de: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="322"/>
        <source>No asset selected</source>
        <translation>Ningún recurso seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="326"/>
        <source>Asset version browser</source>
        <translation>Explorador de versiones del recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="328"/>
        <source>#</source>
        <translation>#</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="328"/>
        <source>Created</source>
        <translation>Creado</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="328"/>
        <source>Author</source>
        <translation>Autor</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="328"/>
        <source>Content</source>
        <translation>Contenido</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="330"/>
        <source>Asset revisions</source>
        <translation>Revisiones del recurso</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="331"/>
        <source>Revision details</source>
        <translation>Detalles de la revisión</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="332"/>
        <source>Inspect</source>
        <translation>Inspeccionar</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="333"/>
        <source>Inspect selected revision</source>
        <translation>Inspeccionar la revisión seleccionada</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="334"/>
        <source>Restore</source>
        <translation>Restaurar</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="336"/>
        <source>Restore selected revision as a new head</source>
        <translation>Restaurar la revisión seleccionada como nueva versión principal</translation>
    </message>
</context>
<context>
    <name>Assistant_Dock</name>
    <message>
        <location filename="../ui/assistant_dock.py" line="159"/>
        <source>No AI provider is configured. Use Configure… to set an endpoint and API key.</source>
        <extracomment>Provider of the active document (``None`` when no document tab is open). Provider of the current chat backend (a configured ``data/llm`` adapter, or ``None`` when the user has not configured a provider). Probed fresh on each send so a config change takes effect immediately; ``ui/`` never sees a provider/HTTP type. ``(commands, label)`` — the turn&apos;s ordered, unapplied reversible commands and a translatable undo label; the host wraps them in one ``AssistantCommand``. How many transcript messages have already been rendered (render the tail).</extracomment>
        <translation>No hay ningún proveedor de IA configurado. Usa Configurar… para establecer un punto de conexión y una clave de API.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="167"/>
        <source>Open a document before chatting with the assistant.</source>
        <translation>Abre un documento antes de chatear con el asistente.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="184"/>
        <source>Assistant edit</source>
        <translation>Edición del asistente</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="188"/>
        <source>Assistant error: {0}</source>
        <translation>Error del asistente: {0}</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="206"/>
        <source>Confirm assistant action</source>
        <translation>Confirmar acción del asistente</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="209"/>
        <source>The assistant wants to run &quot;{0}&quot;, which cannot be reliably undone. Allow it?</source>
        <translation>El asistente quiere ejecutar «{0}», que no se puede deshacer de forma fiable. ¿Permitirlo?</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="226"/>
        <source>Provider configuration saved.</source>
        <translation>Configuración del proveedor guardada.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="235"/>
        <source>Working…</source>
        <translation>Trabajando…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="248"/>
        <source>You</source>
        <translation>Tú</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="251"/>
        <source>Assistant</source>
        <translation>Asistente</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="252"/>
        <source>(taking an action…)</source>
        <translation>(realizando una acción…)</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="254"/>
        <source>Action</source>
        <translation>Acción</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="284"/>
        <source>AI Assistant</source>
        <translation>Asistente de IA</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="285"/>
        <source>AI assistant chat</source>
        <translation>Chat del asistente de IA</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="286"/>
        <source>Assistant conversation</source>
        <translation>Conversación del asistente</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="287"/>
        <source>Message to the assistant</source>
        <translation>Mensaje para el asistente</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="288"/>
        <source>Ask the assistant to edit…</source>
        <translation>Pide al asistente que edite…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="289"/>
        <source>Send</source>
        <translation>Enviar</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="290"/>
        <source>Send message</source>
        <translation>Enviar mensaje</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="291"/>
        <source>Configure…</source>
        <translation>Configurar…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="292"/>
        <source>Configure AI provider</source>
        <translation>Configurar proveedor de IA</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="293"/>
        <source>Assistant working indicator</source>
        <translation>Indicador de actividad del asistente</translation>
    </message>
</context>
<context>
    <name>Batch_Export_Panel</name>
    <message>
        <location filename="../ui/batch_export_panel.py" line="159"/>
        <source>%1 — done</source>
        <extracomment>Optional provider returning the document to export against (the active tab).</extracomment>
        <translation>%1 — completado</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="163"/>
        <source>%1 — failed: %2</source>
        <translation>%1 — falló: %2</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="184"/>
        <source>Add Target…</source>
        <translation>Añadir destino…</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="185"/>
        <source>Remove</source>
        <translation>Eliminar</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="186"/>
        <source>Export All</source>
        <translation>Exportar todo</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="187"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="188"/>
        <source>Batch export</source>
        <translation>Exportación por lotes</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="189"/>
        <source>Batch export targets</source>
        <translation>Destinos de exportación por lotes</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="190"/>
        <source>Batch export progress</source>
        <translation>Progreso de exportación por lotes</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="191"/>
        <source>Add export target</source>
        <translation>Añadir destino de exportación</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="192"/>
        <source>Remove export target</source>
        <translation>Eliminar destino de exportación</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="193"/>
        <source>Export all targets</source>
        <translation>Exportar todos los destinos</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="194"/>
        <source>Cancel batch export</source>
        <translation>Cancelar exportación por lotes</translation>
    </message>
</context>
<context>
    <name>Batch_Recolour_Panel</name>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="168"/>
        <source>Running…</source>
        <extracomment>Combo indices for the mapping mode (module-local UI enumeration). Upper bound for the index spin boxes — the widest palette a buffer can address (a display range for the spin control, not a domain tuning value). ``(ops, label)`` — the host should dispatch the ``batch_recolour`` op on the worker as one undoable grouped command (REQ-P8-UI-006/-009). Each pair is ``(src, dst)`` — ints for index mode, RGBA tuples for colour mode. Kept parallel to the visible list.</extracomment>
        <translation>Ejecutando…</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="170"/>
        <source>Done</source>
        <translation>Hecho</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="171"/>
        <source>Idle</source>
        <translation>Inactivo</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="209"/>
        <source>Pick a colour</source>
        <translation>Elegir un color</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="218"/>
        <source>From: %1</source>
        <translation>De: %1</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="221"/>
        <source>To: %1</source>
        <translation>A: %1</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="234"/>
        <source>%1 → %2</source>
        <translation>%1 → %2</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="264"/>
        <source>Batch Recolour</source>
        <translation>Recoloreado por lotes</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="285"/>
        <source>Mapping:</source>
        <translation>Asignación:</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="286"/>
        <source>Index remap</source>
        <translation>Reasignar índices</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="287"/>
        <source>Colour remap</source>
        <translation>Reasignar colores</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="288"/>
        <source>Frame:</source>
        <translation>Fotograma:</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="289"/>
        <source>Add Pair</source>
        <translation>Añadir par</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="290"/>
        <source>Remove</source>
        <translation>Quitar</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="291"/>
        <source>Apply Batch Recolour</source>
        <translation>Aplicar recoloreado por lotes</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="293"/>
        <source>Batch recolour</source>
        <translation>Recoloreado por lotes</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="294"/>
        <source>Recolour mapping mode</source>
        <translation>Modo de asignación de recoloreado</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="295"/>
        <source>Target frame index</source>
        <translation>Índice del fotograma de destino</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="296"/>
        <source>Source palette index</source>
        <translation>Índice de paleta de origen</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="297"/>
        <source>Destination palette index</source>
        <translation>Índice de paleta de destino</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="298"/>
        <source>Pick source colour</source>
        <translation>Elegir color de origen</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="299"/>
        <source>Pick destination colour</source>
        <translation>Elegir color de destino</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="300"/>
        <source>Recolour mapping pairs</source>
        <translation>Pares de asignación de recoloreado</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="301"/>
        <source>Add a recolour pair</source>
        <translation>Añadir un par de recoloreado</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="302"/>
        <source>Remove the selected pair</source>
        <translation>Quitar el par seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="303"/>
        <source>Apply the batch recolour</source>
        <translation>Aplicar el recoloreado por lotes</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="304"/>
        <source>Progress</source>
        <translation>Progreso</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="305"/>
        <source>Batch recolour progress</source>
        <translation>Progreso de recoloreado por lotes</translation>
    </message>
</context>
<context>
    <name>Branch_Diff_Dialog</name>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="179"/>
        <source>Metadata changes</source>
        <extracomment>The four op-tier groups, fixed display order (``REQ-P10-UI-016``) — matches ``branch_diff._CLASS_RANK``&apos;s declaration order (metadata, layer_attr, layer_order, raster; ``convergence.py:228``). Emitted with ``source_name`` when the user activates *Continue to merge*. This view performs **no** merge itself (``REQ-P10-UI-018``) — the caller runs the unchanged ``Branching_Session.merge_to_mainline`` (the same shipped path the panel&apos;s own Merge button uses, ``REQ-P10-UI-019``).</extracomment>
        <translation>Cambios de metadatos</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="180"/>
        <source>Layer attribute changes</source>
        <translation>Cambios de atributos de capa</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="181"/>
        <source>Layer order changes</source>
        <translation>Cambios de orden de capas</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="182"/>
        <source>Raster (pixel) changes</source>
        <translation>Cambios de ráster (píxeles)</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="194"/>
        <source>Metadata &apos;{key}&apos; set to &apos;{value}&apos;</source>
        <translation>Metadato «{key}» establecido a «{value}»</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="198"/>
        <source>Frame {frame}, layer {layer}: {attr} = {value}</source>
        <translation>Fotograma {frame}, capa {layer}: {attr} = {value}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="202"/>
        <source>Frame {frame}: layer order changed</source>
        <translation>Fotograma {frame}: orden de capas modificado</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="207"/>
        <source>Frame {frame}, layer {layer}: tile ({tile_x}, {tile_y})</source>
        <translation>Fotograma {frame}, capa {layer}: tile ({tile_x}, {tile_y})</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="242"/>
        <source>Frame {frame}, layer {layer}: ({x}, {y}) {width}×{height}</source>
        <translation>Fotograma {frame}, capa {layer}: ({x}, {y}) {width}×{height}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="269"/>
        <source>Diff: &apos;{source}&apos; vs &apos;{target}&apos;</source>
        <translation>Diferencias: «{source}» frente a «{target}»</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="273"/>
        <source>Branch diff</source>
        <translation>Diferencias de rama</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="276"/>
        <source>Comparing branch &apos;{source}&apos; (source) against &apos;{target}&apos; (target). This is a snapshot taken now — the merge has not happened yet.</source>
        <translation>Comparando la rama «{source}» (origen) con «{target}» (destino). Esto es una instantánea tomada ahora — la fusión aún no ha ocurrido.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="281"/>
        <source>Diff basis</source>
        <translation>Base de las diferencias</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="286"/>
        <source>Checked: the recorded changes account for everything on this branch.</source>
        <translation>Comprobado: los cambios registrados explican todo lo ocurrido en esta rama.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="293"/>
        <source>Warning: some changes on this branch are not recorded and will not be merged. {detail}</source>
        <translation>Advertencia: algunos cambios de esta rama no están registrados y no se fusionarán. {detail}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="297"/>
        <source>Supervision result</source>
        <translation>Resultado de la supervisión</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="300"/>
        <source>States whether the recorded operation log explains every change on this branch&apos;s live document.</source>
        <translation>Indica si el registro de operaciones grabado explica cada cambio en el documento activo de esta rama.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="307"/>
        <source>This branch has no changes to merge.</source>
        <translation>Esta rama no tiene cambios que fusionar.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="319"/>
        <source>No changes.</source>
        <translation>Sin cambios.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="321"/>
        <source>{count} change(s).</source>
        <translation>{count} cambio(s).</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="323"/>
        <source>{title} list</source>
        <translation>Lista de {title}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="326"/>
        <source>{count} entries.</source>
        <translation>{count} entradas.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="329"/>
        <source>Affected regions</source>
        <translation>Regiones afectadas</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="332"/>
        <source>Each region is reported at the whole {tile}×{tile} pixel tile granularity — a one-pixel change still covers a full tile here.</source>
        <translation>Cada región se informa con la granularidad completa de un tile de {tile}×{tile} píxeles — un cambio de un solo píxel sigue cubriendo un tile completo aquí.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="337"/>
        <source>Affected regions list</source>
        <translation>Lista de regiones afectadas</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="339"/>
        <source>{count} regions.</source>
        <translation>{count} regiones.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="344"/>
        <source>{total} operation(s) total, across {targets} distinct target(s).</source>
        <translation>{total} operación(es) en total, en {targets} destino(s) distinto(s).</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="350"/>
        <source>Divergence total</source>
        <translation>Divergencia total</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="352"/>
        <source>Continue to Merge</source>
        <translation>Continuar a la fusión</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="353"/>
        <source>Continue to merge</source>
        <translation>Continuar a la fusión</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="356"/>
        <source>Performs the same conflict-free merge as the branching panel&apos;s Merge control.</source>
        <translation>Realiza la misma fusión sin conflictos que el control Fusionar del panel de ramificación.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="360"/>
        <location filename="../ui/branch_diff_dialog.py" line="361"/>
        <source>Close</source>
        <translation>Cerrar</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="363"/>
        <source>Closes this view without merging or changing anything.</source>
        <translation>Cierra esta vista sin fusionar ni cambiar nada.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="375"/>
        <source>frames {frames}</source>
        <translation>fotogramas {frames}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="381"/>
        <source>layers {layers}</source>
        <translation>capas {layers}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="389"/>
        <source>attributes {attrs}</source>
        <translation>atributos {attrs}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="398"/>
        <source>metadata keys {keys}</source>
        <translation>claves de metadatos {keys}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="404"/>
        <source>tiles {tiles}</source>
        <translation>tiles {tiles}</translation>
    </message>
</context>
<context>
    <name>Branching_Panel</name>
    <message>
        <location filename="../ui/branching_panel.py" line="363"/>
        <location filename="../ui/branching_panel.py" line="375"/>
        <location filename="../ui/branching_panel.py" line="386"/>
        <source>Branch</source>
        <extracomment>The reserved name of the always-present mainline branch. emitted when the set of branches changed (create / merge). ``(name,)`` — the active branch changed. ``(document,)`` — a branch was materialised/merged; the caller loads it into the active tab (a whole Qt-free :class:`~pixelart_creator.logic.document.Document`). ``(summary,)`` — a merge completed conflict-free; carries a translatable-ready outcome summary the panel surfaces (REQ-P10-UI-012). The Document object the active branch&apos;s edits actually land on — the same instance the caller (``ui/main_window.py``) mutates in place, so a raster trace&apos;s tile bytes are always read post-edit (plan §8.2). ``None`` until a base document is set. ``(name,)`` — the user activated the open-diff affordance for the selected feature branch (REQ-P10-UI-014). The caller (``ui/main_window.py``) supplies the active tab&apos;s live ``Document`` to ``logic/branch_diff.supervise`` and, once ``ui/branch_diff_dialog.py`` exists, opens the pre-merge diff view from it.</extracomment>
        <translation>Rama</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="364"/>
        <source>Open a project first.</source>
        <translation>Abre un proyecto primero.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="368"/>
        <location filename="../ui/branching_panel.py" line="479"/>
        <source>New Branch</source>
        <translation>Nueva rama</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="368"/>
        <source>Branch name:</source>
        <translation>Nombre de la rama:</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="397"/>
        <location filename="../ui/branching_panel.py" line="483"/>
        <source>Merge</source>
        <translation>Fusionar</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="423"/>
        <source>Merged branch &apos;{name}&apos; ({count} edits) into mainline — conflict-free.</source>
        <translation>Rama «{name}» fusionada ({count} ediciones) en la principal — sin conflictos.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="436"/>
        <source>{name} (active)</source>
        <translation>{name} (activa)</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="455"/>
        <source>Open the pre-merge diff for the selected branch.</source>
        <translation>Abre las diferencias previas a la fusión para la rama seleccionada.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="459"/>
        <source>Disabled: open a project first.</source>
        <translation>Deshabilitado: abre un proyecto primero.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="464"/>
        <source>Disabled: select a feature branch, not mainline, to view its diff.</source>
        <translation>Deshabilitado: selecciona una rama de función, no la principal, para ver sus diferencias.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="471"/>
        <source>Branching</source>
        <translation>Ramificación</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="474"/>
        <source>Branch the project to edit a variation independently, then merge it back. Merges are conflict-free.</source>
        <translation>Ramifica el proyecto para editar una variación de forma independiente y luego fusionarla de nuevo. Las fusiones son sin conflictos.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="478"/>
        <source>Branches</source>
        <translation>Ramas</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="480"/>
        <source>Create a new branch</source>
        <translation>Crear una nueva rama</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="481"/>
        <source>Switch</source>
        <translation>Cambiar</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="482"/>
        <source>Switch to the selected branch</source>
        <translation>Cambiar a la rama seleccionada</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="485"/>
        <source>Merge the selected branch into mainline</source>
        <translation>Fusionar la rama seleccionada en la principal</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="487"/>
        <source>Open Diff</source>
        <translation>Abrir diferencias</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="489"/>
        <source>Open the pre-merge diff for the selected branch</source>
        <translation>Abre las diferencias previas a la fusión para la rama seleccionada</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="491"/>
        <source>Merge outcome</source>
        <translation>Resultado de la fusión</translation>
    </message>
</context>
<context>
    <name>Canvas_Size_Dialog</name>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="76"/>
        <source>Canvas Size</source>
        <translation>Tamaño del lienzo</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="77"/>
        <source>Canvas size dialog</source>
        <translation>Diálogo de tamaño del lienzo</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="78"/>
        <source>Target canvas width in pixels</source>
        <translation>Anchura objetivo del lienzo en píxeles</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="79"/>
        <source>Target canvas height in pixels</source>
        <translation>Altura objetivo del lienzo en píxeles</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="80"/>
        <source>Width (px)</source>
        <translation>Anchura (px)</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="81"/>
        <source>Height (px)</source>
        <translation>Altura (px)</translation>
    </message>
</context>
<context>
    <name>Canvas_View</name>
    <message>
        <location filename="../ui/canvas_view.py" line="284"/>
        <location filename="../ui/canvas_view.py" line="1355"/>
        <source>Canvas</source>
        <extracomment>Platform name reported by Qt when running without a windowing system. Emitted with the current zoom scale after any zoom change. Emitted with the buffer ``(x, y)`` when the canvas is right-clicked (seam). Emitted with the picked RGBA tuple when the colour-picker sets a colour. Emitted ``(is_active, is_copy)`` when a floating move/copy state changes (drives the shell&apos;s copy-mode status hint, REQ-P2-UI-032/-036). Emitted when a paint/mask-edit stroke is refused because the active layer is locked (D-05); the shell surfaces a &quot;layer is locked&quot; notice. Emitted when a left-click lands outside the active document&apos;s bounds (FIX 5, 2026-08-24 field defect): a click there must not arm a stroke, and must not fail silently — the shell surfaces a notice, following the ``lockedLayerEditRejected`` precedent exactly. Emitted when a paint/mask-edit is refused because the active layer is a REFERENCE or SMART layer (REQ-P3-UI-006 clause 5: non-editable targets are three classes, not two — locked, reference, and smart — and every one of them must be surfaced, never silently swallowed). Distinct from ``lockedLayerEditRejected`` so the shell can show the right notice; ``is_active_editable()`` returns ``False`` for all three classes, and this signal covers the two this view previously dropped on the floor. Emitted when a tool ran (the guards passed) but produced no pixel change — e.g. a flood fill on a region that already holds the picked colour (REQ-P1-UI-014), or a pencil placed on a pixel that already holds it — so no undo entry was pushed. An explicit, deliberate gesture (a completed colour-hub pick, REQ-P3-UI-006 clause 6) must never answer with silence even when it changed nothing. Emitted with the target frame index a ``Ctrl``+wheel / ``Ctrl``+middle- click frame gesture resolved to (REQ-IS-UI-010/-014); the shell routes it through the shipped frame-selection path. Pushes no command — frame navigation is view state (CL-13). Emitted when a confirmed ``Ctrl``+left-click (no floating move live) should add a frame after the active one (REQ-IS-UI-016); the shell builds and pushes the shipped undoable ``make_add_frame_command``. The three selection tools whose Shift/Alt modifiers stay the shipped add/subtract combine gesture (REQ-IS-UI-015) — Shift+drag pans for every other tool. Mirrors ``Main_Window._SELECTION_ENTRY_TOOL_IDS``. The wrapper every :class:`~pixelart_creator.ui.tools.base.ToolContext` is actually built with (see :class:`_RecordingUndoStack`); reads ``self._undo_stack``/``self._record_trace``/``self._recording_document`` live at each push, so `set_undo_stack`/`set_recording` need not rebuild it. A middle press awaiting the click/drag verdict (REQ-IS-UI-011): ``True`` between a middle press and either its release under ``CLICK_DRAG_THRESHOLD_PX`` (a click) or its promotion to ``_panning`` once the cursor travels past the threshold (a drag). A ``Ctrl``+left press awaiting the click/drag verdict (REQ-IS-UI-016, mirrors ``_middle_pending``): ``True`` between the press and either its release under ``CLICK_DRAG_THRESHOLD_PX`` (adds a frame) or its promotion to an ordinary paint/floating-move drag once the cursor travels past the threshold. The persisted Favourites model a plain wheel notch / unmodified middle click travel (REQ-IS-UI-008/-012); ``None`` until the shell binds one via :meth:`set_favourites_model`. Live mirror-centre override fed to ``logic.symmetry.mirror`` via each stroke&apos;s :class:`ToolContext` (D-28/CF-93); ``None`` keeps the shipped canvas-centre default. Fed by the shell&apos;s Symmetry_Panel. The guide currently being dragged (D-11), or ``None``. Raw (pre-snap) scene point at the start of the current stroke — the perspective direction-lock anchor (``logic.grids.perspective_snap``).</extracomment>
        <translation>Lienzo</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="286"/>
        <location filename="../ui/canvas_view.py" line="1357"/>
        <source>Pixel canvas: left-click to paint, middle-drag to pan</source>
        <translation>Lienzo de píxeles: clic izquierdo para pintar, arrastrar con el botón central para desplazar</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="1257"/>
        <source>Remove guide</source>
        <translation>Eliminar guía</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="1268"/>
        <source>No canvas actions yet</source>
        <translation>Aún no hay acciones de lienzo</translation>
    </message>
</context>
<context>
    <name>Cel_Overwrite_Dialog</name>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="69"/>
        <source>Overwrite Existing Cel?</source>
        <translation>¿Sobrescribir celda existente?</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="70"/>
        <source>Overwrite existing cel confirmation</source>
        <translation>Confirmación de sobrescritura de celda existente</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="73"/>
        <source>The destination cell already has a drawing on it. Proceeding replaces that drawing. This can be undone.</source>
        <translation>La celda de destino ya tiene un dibujo. Continuar reemplaza ese dibujo. Esto se puede deshacer.</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="77"/>
        <source>Overwrite warning</source>
        <translation>Advertencia de sobrescritura</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="78"/>
        <source>Don&apos;t ask again for this project</source>
        <translation>No volver a preguntar para este proyecto</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="80"/>
        <source>Suppress this confirmation for the current project</source>
        <translation>Suprimir esta confirmación para el proyecto actual</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="84"/>
        <location filename="../ui/cel_overwrite_dialog.py" line="85"/>
        <source>Overwrite</source>
        <translation>Sobrescribir</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="88"/>
        <location filename="../ui/cel_overwrite_dialog.py" line="89"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
</context>
<context>
    <name>Colour_Cycling_Panel</name>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="152"/>
        <source>Colour Cycling</source>
        <extracomment>Milliseconds per cycling tick, derived from the tuning FPS (S12). Emitted with a list of display colours to preview (rotated palette). Emitted with ``(start, end, step)`` when Apply commits the cycle state.</extracomment>
        <translation>Ciclo de color</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="153"/>
        <source>Colour cycling panel</source>
        <translation>Panel de ciclo de color</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="154"/>
        <source>Start</source>
        <translation>Inicio</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="155"/>
        <source>End</source>
        <translation>Fin</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="156"/>
        <source>Step</source>
        <translation>Paso</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="157"/>
        <source>Cycle range start index</source>
        <translation>Índice inicial del rango de ciclo</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="158"/>
        <source>Cycle range end index</source>
        <translation>Índice final del rango de ciclo</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="159"/>
        <source>Cycle step</source>
        <translation>Paso del ciclo</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="160"/>
        <source>Play / Stop</source>
        <translation>Reproducir / Detener</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="161"/>
        <source>Apply</source>
        <translation>Aplicar</translation>
    </message>
</context>
<context>
    <name>Colour_Hub_Menu</name>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="508"/>
        <source>Colour Hub</source>
        <extracomment>Emitted with an RGBA tuple whenever a colour is picked (apply immediately, leg 1 — the live preview stream; never refused, REQ-P3-UI-006 clause 1). Emitted with an RGBA tuple on a COMPLETED pick only — one emission per discrete gesture (a wheel-drag release, a keyboard nudge release, a numeric spin&apos;s editingFinished, a single click on a harmony/shade/tint swatch, or a single click on a Favourites entry). A DOUBLE click / a keyboard activation on either swatch surface adopts instead and never reaches this signal (REQ-IS-UI-019/-020/-022, D-11). The shell (``ui/main_window.py``) uses this to run the active tool at the hub&apos;s anchor pixel as leg 2 (REQ-P3-UI-006 clauses 2-6). Re-emitted when the Favourites model changes (so the shell persists it).</extracomment>
        <translation>Centro de color</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="509"/>
        <source>Colour hub</source>
        <translation>Centro de color</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="510"/>
        <source>Add to Favourites</source>
        <translation>Añadir a favoritos</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="513"/>
        <source>This tool does not paint the active colour, so the colour wheel is hidden here.</source>
        <translation>Esta herramienta no pinta el color activo, así que la rueda de color se oculta aquí.</translation>
    </message>
</context>
<context>
    <name>Colour_Wheel_Widget</name>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="555"/>
        <source>Current colour %1</source>
        <translation>Color actual %1</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="618"/>
        <source>Colour wheel picker</source>
        <translation>Selector de rueda de color</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="368"/>
        <location filename="../ui/colour_wheel_widget.py" line="619"/>
        <location filename="../ui/colour_wheel_widget.py" line="632"/>
        <source>Value</source>
        <translation>Valor</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="620"/>
        <source>Brightness value</source>
        <translation>Valor de brillo</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="621"/>
        <source>R</source>
        <translation>R</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="622"/>
        <source>G</source>
        <translation>G</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="623"/>
        <source>B</source>
        <translation>B</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="624"/>
        <source>H</source>
        <translation>H</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="625"/>
        <source>S</source>
        <translation>S</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="626"/>
        <source>V</source>
        <translation>V</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="353"/>
        <location filename="../ui/colour_wheel_widget.py" line="627"/>
        <source>Red channel</source>
        <extracomment>Emitted with the picked :class:`QColor` on any user-initiated change that ADOPTS into the wheel (wheel-pad drag, value slider, numeric entries, and a harmony/shade/tint swatch&apos;s double-click/keyboard activation — never a swatch&apos;s single click). Emitted with a harmony/shade/tint swatch&apos;s own RGBA tuple on a single left click (REQ-IS-UI-020). PAINT-only: the wheel&apos;s own selection is deliberately left unchanged, unlike :attr:`colorPicked`.</extracomment>
        <translation>Canal rojo</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="356"/>
        <location filename="../ui/colour_wheel_widget.py" line="628"/>
        <source>Green channel</source>
        <translation>Canal verde</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="359"/>
        <location filename="../ui/colour_wheel_widget.py" line="629"/>
        <source>Blue channel</source>
        <translation>Canal azul</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="362"/>
        <location filename="../ui/colour_wheel_widget.py" line="630"/>
        <source>Hue</source>
        <translation>Tono</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="365"/>
        <location filename="../ui/colour_wheel_widget.py" line="631"/>
        <source>Saturation</source>
        <translation>Saturación</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="633"/>
        <source>Hex colour</source>
        <translation>Color hexadecimal</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="634"/>
        <source>Complementary</source>
        <translation>Complementario</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="635"/>
        <source>Analogous</source>
        <translation>Análogos</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="636"/>
        <source>Triadic</source>
        <translation>Triádicos</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="637"/>
        <source>Tetradic</source>
        <translation>Tetrádicos</translation>
    </message>
    <message>
        <source>Square</source>
        <translation type="vanished">Cuadrados</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="638"/>
        <source>Split-complementary</source>
        <translation>Complementarios divididos</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="639"/>
        <source>Shades</source>
        <translation>Sombras</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="640"/>
        <source>Tints</source>
        <translation>Tintes</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="651"/>
        <source>harmony</source>
        <translation>armonía</translation>
    </message>
</context>
<context>
    <name>Comments_Panel</name>
    <message>
        <location filename="../ui/comments_panel.py" line="116"/>
        <location filename="../ui/comments_panel.py" line="124"/>
        <location filename="../ui/comments_panel.py" line="134"/>
        <location filename="../ui/comments_panel.py" line="146"/>
        <location filename="../ui/comments_panel.py" line="162"/>
        <location filename="../ui/comments_panel.py" line="224"/>
        <source>Comments</source>
        <translation>Comentarios</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="117"/>
        <source>Open a shared project before commenting.</source>
        <translation>Abre un proyecto compartido antes de comentar.</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="125"/>
        <source>Enter your member id before commenting.</source>
        <translation>Introduce tu id de miembro antes de comentar.</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="135"/>
        <source>A comment may be at most %1 bytes.</source>
        <translation>Un comentario puede tener como máximo %1 bytes.</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="196"/>
        <source>Resolved</source>
        <translation>Resuelto</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="196"/>
        <source>Open</source>
        <translation>Abierto</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="211"/>
        <source>%1 / %2 bytes</source>
        <translation>%1 / %2 bytes</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="225"/>
        <source>Your member id:</source>
        <translation>Tu id de miembro:</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="226"/>
        <source>e.g. alice</source>
        <translation>p. ej. alice</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="227"/>
        <source>Comment author id</source>
        <translation>Id del autor del comentario</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="229"/>
        <source>Author</source>
        <translation>Autor</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="229"/>
        <source>Comment</source>
        <translation>Comentario</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="229"/>
        <source>Status</source>
        <translation>Estado</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="231"/>
        <source>Comment thread</source>
        <translation>Hilo de comentarios</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="232"/>
        <source>Write a comment…</source>
        <translation>Escribe un comentario…</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="233"/>
        <source>New comment text</source>
        <translation>Texto del nuevo comentario</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="234"/>
        <source>Reply to selected</source>
        <translation>Responder al seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="235"/>
        <source>Reply to the selected comment</source>
        <translation>Responder al comentario seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="236"/>
        <source>Add Comment</source>
        <translation>Añadir comentario</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="237"/>
        <source>Add the comment</source>
        <translation>Añadir el comentario</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="238"/>
        <source>Resolve</source>
        <translation>Resolver</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="239"/>
        <source>Resolve the selected comment</source>
        <translation>Resolver el comentario seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="240"/>
        <source>Comment byte count</source>
        <translation>Recuento de bytes del comentario</translation>
    </message>
</context>
<context>
    <name>Cursor_Feedback_Overlay</name>
    <message>
        <location filename="../ui/cursor_feedback_overlay.py" line="103"/>
        <location filename="../ui/cursor_feedback_overlay.py" line="160"/>
        <source>Cursor feedback</source>
        <extracomment>Progress fraction (0..1 of FEEDBACK_DURATION_MS) at which the fall to zero begins.</extracomment>
        <translation>Retroalimentación del cursor</translation>
    </message>
</context>
<context>
    <name>Dependency_Graph_View</name>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="166"/>
        <source>Dependency cycle detected (graph unchanged): %1</source>
        <extracomment>Item roles: whether a row is a broken edge, and the edge it stands for. The asset in scope (``&quot;&quot;`` = the whole catalog). The last cycle the model reported at :meth:`show_edges` (``&quot;&quot;`` = none).</extracomment>
        <translation>Ciclo de dependencia detectado (grafo sin cambios): %1</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="198"/>
        <source>Dependencies (depends on)</source>
        <translation>Dependencias (depende de)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="204"/>
        <source>Dependents (referenced by)</source>
        <translation>Dependientes (referenciado por)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="234"/>
        <source>Broken (%1)</source>
        <translation>Rota (%1)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="258"/>
        <source>%1 (%2)</source>
        <translation>%1 (%2)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="266"/>
        <source>Sprite</source>
        <translation>Sprite</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="267"/>
        <source>Animation</source>
        <translation>Animación</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="268"/>
        <source>Tileset</source>
        <translation>Conjunto de tiles</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="269"/>
        <source>Tilemap</source>
        <translation>Mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="270"/>
        <source>Palette</source>
        <translation>Paleta</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="277"/>
        <source>missing target</source>
        <translation>destino faltante</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="279"/>
        <source>changed target</source>
        <translation>destino modificado</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="286"/>
        <source>No broken references</source>
        <translation>Sin referencias rotas</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="289"/>
        <source>Broken references: %1</source>
        <translation>Referencias rotas: %1</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="291"/>
        <source>Broken reference summary</source>
        <translation>Resumen de referencias rotas</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="295"/>
        <source>Dependency graph</source>
        <translation>Grafo de dependencias</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="296"/>
        <source>Asset</source>
        <translation>Recurso</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="296"/>
        <source>Status</source>
        <translation>Estado</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="297"/>
        <source>Dependency relations</source>
        <translation>Relaciones de dependencia</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="298"/>
        <source>Dependency cycle notice</source>
        <translation>Aviso de ciclo de dependencia</translation>
    </message>
</context>
<context>
    <name>Document_Transform_Confirm_Dialog</name>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="88"/>
        <source>Confirm Large Transform</source>
        <translation>Confirmar transformación grande</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="89"/>
        <source>Confirm large document transform dialog</source>
        <translation>Diálogo de confirmación de transformación grande del documento</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="92"/>
        <source>%1 will resample every layer and mask of this document to %2 × %3 px, using up to %4 of memory at once. Proceed?</source>
        <translation>%1 volverá a muestrear cada capa y máscara de este documento a %2 × %3 px, usando hasta %4 de memoria a la vez. ¿Continuar?</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="100"/>
        <source>Transform cost summary</source>
        <translation>Resumen del coste de la transformación</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="101"/>
        <source>Proceed</source>
        <translation>Continuar</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="102"/>
        <source>Proceed with the transform</source>
        <translation>Continuar con la transformación</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="103"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="104"/>
        <source>Cancel the transform</source>
        <translation>Cancelar la transformación</translation>
    </message>
</context>
<context>
    <name>Document_Transform_Progress_Dialog</name>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="190"/>
        <source>Transforming Document</source>
        <extracomment>Emitted when the user asks to stop — via the button, Escape, or the window&apos;s close control. The caller (the runner) decides what &quot;stop&quot; means; this dialog only reports the request.</extracomment>
        <translation>Transformando documento</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="191"/>
        <source>Document transform progress dialog</source>
        <translation>Diálogo de progreso de transformación del documento</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="192"/>
        <source>%1…</source>
        <translation>%1…</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="193"/>
        <source>Transform operation in progress</source>
        <translation>Operación de transformación en curso</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="194"/>
        <source>Transform progress</source>
        <translation>Progreso de la transformación</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="195"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="196"/>
        <source>Cancel the transform</source>
        <translation>Cancelar la transformación</translation>
    </message>
</context>
<context>
    <name>Document_View</name>
    <message>
        <location filename="../ui/multi_view.py" line="119"/>
        <source>Document view {0}</source>
        <extracomment>Per-wheel-notch zoom step for an extra view (independent of the primary view). Emitted with the picked RGBA tuple when a plain wheel notch travels the shared Favourites cursor (REQ-IS-UI-008, D-16 — this surface is a navigate-only view of the SAME live document scene as the primary Canvas_View, so the active colour it sets is real document context). The persisted Favourites model bound via :meth:`set_favourites_model`; ``None`` until the shell binds one.</extracomment>
        <translation>Vista de documento {0}</translation>
    </message>
    <message>
        <location filename="../ui/multi_view.py" line="123"/>
        <source>An extra synced view of the same document (independent zoom/pan)</source>
        <translation>Una vista sincronizada adicional del mismo documento (zoom/desplazamiento independientes)</translation>
    </message>
</context>
<context>
    <name>Export_Dialog</name>
    <message>
        <location filename="../ui/export_dialog.py" line="259"/>
        <source>%1 → %2</source>
        <extracomment>Presentation-only spin bounds (UI clamps; the logic layer re-validates, S12).</extracomment>
        <translation>%1 → %2</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="287"/>
        <source>Whole document</source>
        <translation>Documento completo</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="295"/>
        <source>Animated GIF (*.gif)</source>
        <translation>GIF animado (*.gif)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="297"/>
        <source>PNG image (*.png)</source>
        <translation>Imagen PNG (*.png)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="299"/>
        <source>Export To</source>
        <translation>Exportar a</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="307"/>
        <source>Export</source>
        <translation>Exportar</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="308"/>
        <source>Format</source>
        <translation>Formato</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="309"/>
        <location filename="../ui/export_dialog.py" line="337"/>
        <source>Engine preset</source>
        <translation>Preajuste de motor</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="310"/>
        <source>Destination</source>
        <translation>Destino</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="311"/>
        <source>Browse…</source>
        <translation>Examinar…</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="312"/>
        <source>Also add to the asset library</source>
        <translation>También añadir a la biblioteca de recursos</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="314"/>
        <source>PNG image</source>
        <translation>Imagen PNG</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="315"/>
        <source>Animated GIF</source>
        <translation>GIF animado</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="316"/>
        <source>Sprite sheet</source>
        <translation>Hoja de sprites</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="317"/>
        <source>Texture atlas</source>
        <translation>Atlas de texturas</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="318"/>
        <source>None</source>
        <translation>Ninguno</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="319"/>
        <source>Unity</source>
        <translation>Unity</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="320"/>
        <source>Godot</source>
        <translation>Godot</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="323"/>
        <source>Exports the first frame as a flattened PNG image.</source>
        <translation>Exporta el primer fotograma como una imagen PNG aplanada.</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="325"/>
        <source>Frames</source>
        <translation>Fotogramas</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="326"/>
        <source>Loop count</source>
        <translation>Número de repeticiones</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="327"/>
        <source>Loop count (0 = loop forever).</source>
        <translation>Número de repeticiones (0 = repetir indefinidamente).</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="328"/>
        <source>Columns</source>
        <translation>Columnas</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="329"/>
        <location filename="../ui/export_dialog.py" line="331"/>
        <source>Padding (px)</source>
        <translation>Relleno (px)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="330"/>
        <location filename="../ui/export_dialog.py" line="333"/>
        <source>Write JSON metadata</source>
        <translation>Escribir metadatos JSON</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="332"/>
        <source>Max dimension (px)</source>
        <translation>Dimensión máxima (px)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="336"/>
        <source>Export format</source>
        <translation>Formato de exportación</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="338"/>
        <source>Destination path</source>
        <translation>Ruta de destino</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="339"/>
        <source>Browse for destination</source>
        <translation>Examinar destino</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="341"/>
        <source>Also add this export to the asset library</source>
        <translation>También añadir esta exportación a la biblioteca de recursos</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="343"/>
        <source>GIF frame source</source>
        <translation>Origen de fotogramas del GIF</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="344"/>
        <source>GIF loop count</source>
        <translation>Número de repeticiones del GIF</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="345"/>
        <source>Sprite-sheet columns</source>
        <translation>Columnas de la hoja de sprites</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="346"/>
        <source>Sprite-sheet padding</source>
        <translation>Relleno de la hoja de sprites</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="347"/>
        <source>Write sprite-sheet JSON</source>
        <translation>Escribir JSON de la hoja de sprites</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="348"/>
        <source>Atlas padding</source>
        <translation>Relleno del atlas</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="349"/>
        <source>Atlas max dimension</source>
        <translation>Dimensión máxima del atlas</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="350"/>
        <source>Write atlas JSON</source>
        <translation>Escribir JSON del atlas</translation>
    </message>
</context>
<context>
    <name>Extract_Palette_Dialog</name>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="127"/>
        <source>Choose Image</source>
        <extracomment>Extraction method tokens carried in the method combo&apos;s item data.</extracomment>
        <translation>Elegir imagen</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="129"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>Imágenes (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="136"/>
        <location filename="../ui/extract_palette_dialog.py" line="153"/>
        <source>Extract Palette</source>
        <translation>Extraer paleta</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="136"/>
        <source>Could not load the image.</source>
        <translation>No se pudo cargar la imagen.</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="160"/>
        <source>Extract Palette from Image</source>
        <translation>Extraer paleta de la imagen</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="161"/>
        <source>Extract palette dialog</source>
        <translation>Diálogo de extracción de paleta</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="162"/>
        <source>Choose Image…</source>
        <translation>Elegir imagen…</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="163"/>
        <source>No image chosen</source>
        <translation>Ninguna imagen elegida</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="164"/>
        <source>Colours (N)</source>
        <translation>Colores (N)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="165"/>
        <source>Method</source>
        <translation>Método</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="166"/>
        <source>Number of colours</source>
        <translation>Número de colores</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="167"/>
        <source>Extraction method</source>
        <translation>Método de extracción</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="168"/>
        <source>Median cut (fast)</source>
        <translation>Corte mediano (rápido)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="169"/>
        <source>K-means (higher quality)</source>
        <translation>K-medias (mayor calidad)</translation>
    </message>
</context>
<context>
    <name>Favourites_Panel</name>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="246"/>
        <source>Favourites</source>
        <extracomment>Edge of a Favourites swatch icon, px (presentation-only sizing). Keys that nudge the wheel pad&apos;s hue/saturation (``_WheelPad.keyPressEvent``); a KeyRelease for one of these is a discrete, already-completed pick (REQ-P3- UI-006 leg 2), unlike Tab/other keys the pad never acts on. Single left click on a favourite — paint that colour, leave the wheel alone. Double left click / Enter / Return on a favourite — adopt that colour into the wheel, paint nothing. Deprecated alias of :attr:`favouriteActivated`, kept for pre-2026-08-31 callers of the pre-split single ``favouriteChosen`` signal. Emitted alongside :attr:`favouriteActivated` ONLY — never alongside :attr:`favouritePicked`, so it never resurrects the fused-gesture defect this split fixes (REQ-IS-UI-019). New code should connect :attr:`favouritePicked` / :attr:`favouriteActivated` directly. Emitted whenever the underlying model is mutated (so the shell persists it).</extracomment>
        <translation>Favoritos</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="247"/>
        <source>Favourites panel</source>
        <translation>Panel de favoritos</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="248"/>
        <source>Favourite colours</source>
        <translation>Colores favoritos</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="249"/>
        <source>Remove</source>
        <translation>Eliminar</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="250"/>
        <source>Move Up</source>
        <translation>Subir</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="251"/>
        <source>Move Down</source>
        <translation>Bajar</translation>
    </message>
</context>
<context>
    <name>Frame_Tags_Panel</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="262"/>
        <source>%1  [%2–%3]  %4</source>
        <extracomment>Emitted with the :class:`FrameTag` to play as a named animation (UI-014).</extracomment>
        <translation>%1  [%2–%3]  %4</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="263"/>
        <source>(unnamed)</source>
        <translation>(sin nombre)</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="312"/>
        <location filename="../ui/frame_tags_panel.py" line="314"/>
        <location filename="../ui/frame_tags_panel.py" line="380"/>
        <source>Add Tag</source>
        <translation>Añadir etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="336"/>
        <location filename="../ui/frame_tags_panel.py" line="338"/>
        <location filename="../ui/frame_tags_panel.py" line="381"/>
        <source>Edit Tag</source>
        <translation>Editar etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="349"/>
        <location filename="../ui/frame_tags_panel.py" line="382"/>
        <source>Remove Tag</source>
        <translation>Eliminar etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="374"/>
        <source>Frame tags panel</source>
        <translation>Panel de etiquetas de fotogramas</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="375"/>
        <source>Tag actions</source>
        <translation>Acciones de etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="376"/>
        <source>Frame tags</source>
        <translation>Etiquetas de fotogramas</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="378"/>
        <source>Named animations; double-click to edit</source>
        <translation>Animaciones con nombre; haga doble clic para editar</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="383"/>
        <source>Play Tag</source>
        <translation>Reproducir etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="385"/>
        <source>Play the selected tag as its own animation</source>
        <translation>Reproducir la etiqueta seleccionada como su propia animación</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="387"/>
        <source>Play tag</source>
        <translation>Reproducir etiqueta</translation>
    </message>
</context>
<context>
    <name>Iso_Grid_Dialog</name>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="117"/>
        <source>Configure Isometric Grid</source>
        <extracomment>Sane bounds for the ``W:H`` tile ratio field (2:1 dimetric default is 2.0; true-iso is ~1.732). Not a lattice geometry decision — just a widget bound keeping the field away from non-finite/degenerate input before it ever reaches ``IsoGridConfig`` validation (S12).</extracomment>
        <translation>Configurar cuadrícula isométrica</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="118"/>
        <source>Tile width</source>
        <translation>Ancho de tile</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="119"/>
        <source>Tile ratio (W:H)</source>
        <translation>Proporción de tile (ancho:alto)</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="120"/>
        <source>Origin X</source>
        <translation>Origen X</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="121"/>
        <source>Origin Y</source>
        <translation>Origen Y</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="122"/>
        <source>Isometric tile width</source>
        <translation>Ancho de tile isométrico</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="123"/>
        <source>Isometric tile ratio</source>
        <translation>Proporción de tile isométrico</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="124"/>
        <source>Isometric grid origin X</source>
        <translation>Origen X de la cuadrícula isométrica</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="125"/>
        <source>Isometric grid origin Y</source>
        <translation>Origen Y de la cuadrícula isométrica</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="128"/>
        <source>OK</source>
        <translation>Aceptar</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="131"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
</context>
<context>
    <name>Layer_Panel</name>
    <message>
        <location filename="../ui/layer_panel.py" line="443"/>
        <source>Normal</source>
        <extracomment>Emitted with the selected node (``Layer`` / ``LayerGroup`` / ``None``). Emitted when the &quot;edit mask&quot; toggle flips (route paint to the mask buffer). Emitted when a mask attach/remove/edit is refused because the target node is locked (D-05); the shell surfaces a &quot;layer is locked&quot; notice.</extracomment>
        <translation>Normal</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="444"/>
        <source>Multiply</source>
        <translation>Multiplicar</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="445"/>
        <source>Screen</source>
        <translation>Trama</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="446"/>
        <source>Overlay</source>
        <translation>Superponer</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="447"/>
        <source>Darken</source>
        <translation>Oscurecer</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="448"/>
        <source>Lighten</source>
        <translation>Aclarar</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="449"/>
        <source>Colour Dodge</source>
        <translation>Sobreexponer color</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="450"/>
        <source>Colour Burn</source>
        <translation>Subexponer color</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="451"/>
        <source>Hard Light</source>
        <translation>Luz fuerte</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="452"/>
        <source>Soft Light</source>
        <translation>Luz suave</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="453"/>
        <source>Difference</source>
        <translation>Diferencia</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="454"/>
        <source>Exclusion</source>
        <translation>Exclusión</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="650"/>
        <source>Layer</source>
        <translation>Capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="654"/>
        <location filename="../ui/layer_panel.py" line="883"/>
        <source>Add Layer</source>
        <translation>Añadir capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="667"/>
        <location filename="../ui/layer_panel.py" line="884"/>
        <source>Remove Layer</source>
        <translation>Eliminar capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="680"/>
        <location filename="../ui/layer_panel.py" line="885"/>
        <source>Duplicate Layer</source>
        <translation>Duplicar capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="689"/>
        <location filename="../ui/layer_panel.py" line="886"/>
        <source>Group</source>
        <translation>Agrupar</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="693"/>
        <source>Group Layers</source>
        <translation>Agrupar capas</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="705"/>
        <source>Ungroup Layers</source>
        <translation>Desagrupar capas</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="726"/>
        <location filename="../ui/layer_panel.py" line="871"/>
        <location filename="../ui/layer_panel.py" line="891"/>
        <source>Add Mask</source>
        <translation>Añadir máscara</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="733"/>
        <location filename="../ui/layer_panel.py" line="871"/>
        <source>Remove Mask</source>
        <translation>Eliminar máscara</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="757"/>
        <source>Toggle Reference</source>
        <translation>Alternar referencia</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="767"/>
        <source>Smart</source>
        <translation>Inteligente</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="771"/>
        <source>Create Smart Layer</source>
        <translation>Crear capa inteligente</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="828"/>
        <source>Move Layer</source>
        <translation>Mover capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="877"/>
        <source>Layers panel</source>
        <translation>Panel de capas</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="878"/>
        <source>Layer actions</source>
        <translation>Acciones de capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="879"/>
        <source>Layer tree</source>
        <translation>Árbol de capas</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="881"/>
        <source>Layers top-to-bottom; drag to reorder or re-parent</source>
        <translation>Capas de arriba abajo; arrastra para reordenar o reasignar</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="887"/>
        <source>Ungroup</source>
        <translation>Desagrupar</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="888"/>
        <source>Edit Mask</source>
        <translation>Editar máscara</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="889"/>
        <source>Reference</source>
        <translation>Referencia</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="890"/>
        <source>Smart Layer</source>
        <translation>Capa inteligente</translation>
    </message>
</context>
<context>
    <name>Macro_Controls</name>
    <message>
        <location filename="../ui/macro_controls.py" line="143"/>
        <source>Running…</source>
        <extracomment>``(Macro, label)`` — the host should replay this macro on the active document (as one undoable grouped command, REQ-P8-UI-002). ``(recording,)`` — recording started / stopped (view state, not undoable). The user asked to cancel the in-flight automation run (C-07); the host relays this to ``Automation_Controller.cancel()``.</extracomment>
        <translation>Ejecutando…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="145"/>
        <source>Done</source>
        <translation>Hecho</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="146"/>
        <source>Idle</source>
        <translation>Inactivo</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="184"/>
        <source>Macro Error</source>
        <translation>Error de macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="188"/>
        <source>Recording %1 (%2 steps)</source>
        <translation>Grabando %1 (%2 pasos)</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="211"/>
        <source>Macro</source>
        <translation>Macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="229"/>
        <source>Save Macro</source>
        <translation>Guardar macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="231"/>
        <location filename="../ui/macro_controls.py" line="251"/>
        <source>Macro files (*%1)</source>
        <translation>Archivos de macro (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="238"/>
        <source>Save Macro Failed</source>
        <translation>Error al guardar la macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="249"/>
        <source>Load Macro</source>
        <translation>Cargar macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="258"/>
        <source>Load Macro Failed</source>
        <translation>Error al cargar la macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="288"/>
        <source>Recording… %1 steps captured</source>
        <translation>Grabando… %1 pasos capturados</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="291"/>
        <source>Not recording</source>
        <translation>Sin grabar</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="295"/>
        <source>Stop Recording</source>
        <translation>Detener grabación</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="295"/>
        <source>Record Macro</source>
        <translation>Grabar macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="297"/>
        <source>Replay</source>
        <translation>Reproducir</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="298"/>
        <source>Save…</source>
        <translation>Guardar…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="299"/>
        <source>Load…</source>
        <translation>Cargar…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="300"/>
        <source>Remove</source>
        <translation>Quitar</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="301"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="302"/>
        <source>Macro controls</source>
        <translation>Controles de macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="303"/>
        <source>Record or stop a macro</source>
        <translation>Grabar o detener una macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="304"/>
        <source>Macro recording status</source>
        <translation>Estado de grabación de la macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="305"/>
        <source>Recorded and loaded macros</source>
        <translation>Macros grabadas y cargadas</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="306"/>
        <source>Replay the selected macro</source>
        <translation>Reproducir la macro seleccionada</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="307"/>
        <source>Save the selected macro</source>
        <translation>Guardar la macro seleccionada</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="308"/>
        <source>Load a macro from a file</source>
        <translation>Cargar una macro desde un archivo</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="309"/>
        <source>Remove the selected macro</source>
        <translation>Quitar la macro seleccionada</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="310"/>
        <source>Cancel the running automation</source>
        <translation>Cancelar la automatización en curso</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="312"/>
        <source>Stops the in-flight automation run; enabled only while busy.</source>
        <translation>Detiene la automatización en curso; solo se activa mientras está ocupado.</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="314"/>
        <source>Progress</source>
        <translation>Progreso</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="315"/>
        <source>Macro replay progress</source>
        <translation>Progreso de repetición de la macro</translation>
    </message>
</context>
<context>
    <name>Main_Window</name>
    <message>
        <location filename="../ui/main_window.py" line="1220"/>
        <source>&amp;Undo</source>
        <extracomment>Live mirror-centre override from the Symmetry_Panel (D-28/CF-93); ``None`` keeps the shipped canvas-centre default. The DSL ops of the in-flight automation run (recorded into a macro on success if recording is active); ``None`` for a macro replay (a replay is not itself re-recorded). True while an in-session timelapse playback holds the active tab&apos;s canvas + the shared undo/redo actions read-only (REQ-P9-UI-016); see ``_on_timelapse_playback_lock_changed``. The cloud project id last saved to / opened from (drives version browse). D-13: the most recently fetched remote version list (cached from the last &quot;open_list&quot;/&quot;versions&quot;/&quot;save&quot; result) — feeds the read-only ``compute_sync_state`` for the Cloud menu status line and the version browser, without a network round trip on every tab switch. D-13: the version id of a restore/recover in flight, consumed once the reconstructed document lands in its new tab (see ``_on_cloud_succeeded``). Live-cursor overlays are per-tab (attached in _create_tab_aids); toggled on connect. The local member id broadcast with presence (never a token).</extracomment>
        <translation>&amp;Deshacer</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="1222"/>
        <source>&amp;Redo</source>
        <translation>&amp;Rehacer</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2084"/>
        <source>Untitled</source>
        <translation>Sin título</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3301"/>
        <source>Copying selection — release, Enter to commit, Esc to cancel</source>
        <extracomment>Incoming tool ids that discard the active selection on entry (REQ-IS-UI-029, CL-IS-08/-09). Re-activating an already-active selection tool is included deliberately, so it doubles as a start-fresh gesture — an assumption (CL-IS-08), flagged and cheap to reverse. Every other incoming tool leaves the selection untouched, so mask-constrained drawing (REQ-P2-LOGIC-006) survives a tool switch.</extracomment>
        <translation>Copiando selección — suelta, Enter para confirmar, Esc para cancelar</translation>
    </message>
    <message>
        <source>Moving selection — hold Ctrl or Alt to copy; Enter to commit, Esc to cancel</source>
        <translation type="vanished">Moviendo selección — mantén Ctrl o Alt para copiar; Enter para confirmar, Esc para cancelar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3417"/>
        <source>Add Shade Ramp</source>
        <translation>Añadir rampa de sombra</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3435"/>
        <location filename="../ui/main_window.py" line="3441"/>
        <source>Constrain to Palette</source>
        <translation>Restringir a la paleta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3462"/>
        <location filename="../ui/main_window.py" line="3471"/>
        <location filename="../ui/main_window.py" line="5330"/>
        <source>Colour Cycling</source>
        <translation>Ciclo de color</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3463"/>
        <source>Colour cycling applies to indexed documents.</source>
        <translation>El ciclo de color se aplica a documentos indexados.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3477"/>
        <source>Colour Cycle</source>
        <translation>Ciclo de color</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3495"/>
        <source>Extract Palette</source>
        <translation>Extraer paleta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3506"/>
        <location filename="../ui/main_window.py" line="3524"/>
        <location filename="../ui/main_window.py" line="3530"/>
        <source>Palette Swap</source>
        <translation>Intercambio de paleta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3507"/>
        <source>Palette swap applies to indexed documents.</source>
        <translation>El intercambio de paleta se aplica a documentos indexados.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3553"/>
        <location filename="../ui/main_window.py" line="3559"/>
        <source>Convert to Indexed</source>
        <translation>Convertir a indexado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3579"/>
        <location filename="../ui/main_window.py" line="3585"/>
        <source>Convert to RGBA</source>
        <translation>Convertir a RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4036"/>
        <source>Open Project</source>
        <translation>Abrir proyecto</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3066"/>
        <location filename="../ui/main_window.py" line="4038"/>
        <location filename="../ui/main_window.py" line="4054"/>
        <source>Pixel projects (*%1)</source>
        <translation>Proyectos de píxeles (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2999"/>
        <source>Unsaved Changes</source>
        <translation>Cambios sin guardar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3001"/>
        <source>The current document has unsaved changes. Save it before opening the dropped project?</source>
        <translation>El documento actual tiene cambios sin guardar. ¿Guardarlo antes de abrir el proyecto soltado?</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3036"/>
        <source>Load Palette</source>
        <translation>Cargar paleta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3064"/>
        <location filename="../ui/main_window.py" line="4052"/>
        <source>Save Project</source>
        <translation>Guardar proyecto</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3076"/>
        <source>Unsupported file type: %1</source>
        <translation>Tipo de archivo no admitido: %1</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3173"/>
        <source>Open a document before loading a palette.</source>
        <translation>Abre un documento antes de cargar una paleta.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3181"/>
        <source>Import Failed</source>
        <translation>Error de importación</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3182"/>
        <source>Could not import %1:
%2</source>
        <translation>No se pudo importar %1:
%2</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3306"/>
        <source>Moving selection — hold Ctrl to copy; Enter to commit, Esc to cancel</source>
        <translation>Moviendo selección — mantén Ctrl para copiar; Enter para confirmar, Esc para cancelar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4063"/>
        <source>Cloud project name:</source>
        <translation>Nombre del proyecto en la nube:</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4068"/>
        <source>Enter a project name.</source>
        <translation>Introduce un nombre de proyecto.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4077"/>
        <source>Connect to a cloud provider first.</source>
        <translation>Conéctate primero a un proveedor en la nube.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4276"/>
        <source>Save to Cloud</source>
        <translation>Guardar en la nube</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4133"/>
        <location filename="../ui/main_window.py" line="4281"/>
        <source>Open a document first.</source>
        <translation>Abre primero un documento.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2648"/>
        <source>Add Frame</source>
        <translation>Añadir fotograma</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3087"/>
        <source>Layer is locked.</source>
        <translation>La capa está bloqueada.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3102"/>
        <source>This is the last remaining frame; a document must keep at least one.</source>
        <translation>Este es el último fotograma restante; un documento debe conservar al menos uno.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3115"/>
        <source>Click was outside the document.</source>
        <translation>El clic quedó fuera del documento.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3128"/>
        <source>This layer cannot be edited directly.</source>
        <translation>Esta capa no se puede editar directamente.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3141"/>
        <source>No change: the colour already matched.</source>
        <translation>Sin cambios: el color ya coincidía.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3154"/>
        <source>No tileset bound to this tilemap yet.</source>
        <translation>Aún no hay ningún tileset vinculado a este mapa de tiles.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3166"/>
        <source>Select a tile first.</source>
        <translation>Selecciona un tile primero.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3711"/>
        <source>Register Selection</source>
        <translation>Registrar selección</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3800"/>
        <source>Choose a new folder for the imported project</source>
        <translation>Elija una carpeta nueva para el proyecto importado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3809"/>
        <source>&quot;%1&quot; already exists. Choose a name for a new folder.</source>
        <translation>«%1» ya existe. Elija un nombre para una carpeta nueva.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3828"/>
        <source>Imported Project</source>
        <translation>Proyecto importado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4111"/>
        <source>Cloud status: —</source>
        <translation>Estado de la nube: —</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4119"/>
        <source>Cloud status: Up to date</source>
        <translation>Estado de la nube: al día</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4121"/>
        <source>Cloud status: Not yet saved to cloud</source>
        <translation>Estado de la nube: aún no guardado en la nube</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4123"/>
        <source>Cloud status: Newer version in cloud</source>
        <translation>Estado de la nube: hay una versión más reciente en la nube</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4124"/>
        <source>Cloud status: Diverged</source>
        <translation>Estado de la nube: divergente</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4130"/>
        <source>Real-time</source>
        <translation>Tiempo real</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4135"/>
        <source>Your member id:</source>
        <translation>Tu id de miembro:</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4165"/>
        <source>Real-time: {msg}</source>
        <translation>Tiempo real: {msg}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4269"/>
        <source>Merge</source>
        <translation>Fusionar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4298"/>
        <source>Open from Cloud</source>
        <translation>Abrir desde la nube</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4316"/>
        <location filename="../ui/main_window.py" line="4433"/>
        <source>Cloud Version History</source>
        <translation>Historial de versiones en la nube</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4403"/>
        <source>Saved to cloud.</source>
        <translation>Guardado en la nube.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4410"/>
        <source>Cloud Project</source>
        <translation>Proyecto en la nube</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4412"/>
        <source>Recovered</source>
        <translation>Recuperado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4420"/>
        <source>Restored from cloud.</source>
        <translation>Restaurado desde la nube.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4434"/>
        <source>No versions found for this project.</source>
        <translation>No se encontraron versiones para este proyecto.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4461"/>
        <source>Cloud</source>
        <translation>Nube</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4587"/>
        <source>Clear Selection</source>
        <translation>Borrar selección</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4702"/>
        <source>Flip Horizontal</source>
        <translation>Voltear horizontalmente</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4705"/>
        <source>Flip Vertical</source>
        <translation>Voltear verticalmente</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4709"/>
        <source>Rotate 90° CW</source>
        <translation>Rotar 90° horario</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4714"/>
        <source>Rotate 90° CCW</source>
        <translation>Rotar 90° antihorario</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4735"/>
        <location filename="../ui/main_window.py" line="4738"/>
        <location filename="../ui/main_window.py" line="4742"/>
        <location filename="../ui/main_window.py" line="4751"/>
        <location filename="../ui/main_window.py" line="4754"/>
        <source>Scale Canvas</source>
        <translation>Escalar lienzo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4783"/>
        <location filename="../ui/main_window.py" line="4786"/>
        <source>Canvas Size</source>
        <translation>Tamaño del lienzo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4804"/>
        <source>Rotate (RotSprite)</source>
        <translation>Rotar (RotSprite)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4972"/>
        <location filename="../ui/main_window.py" line="4981"/>
        <source>Open Tileset Image</source>
        <translation>Abrir imagen de tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4974"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>Imágenes (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4990"/>
        <source>New Tileset</source>
        <translation>Nuevo tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4996"/>
        <source>Add Tileset</source>
        <translation>Añadir tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5006"/>
        <location filename="../ui/main_window.py" line="5057"/>
        <source>Attach Tileset</source>
        <translation>Adjuntar tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5019"/>
        <source>Tilemap</source>
        <translation>Mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5022"/>
        <source>Layer 1</source>
        <translation>Capa 1</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5029"/>
        <source>Add Tilemap</source>
        <translation>Añadir mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5049"/>
        <source>Import Tilemap</source>
        <translation>Importar mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5081"/>
        <source>Export Tiled Map</source>
        <translation>Exportar mapa de Tiled</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5082"/>
        <source>There is no tilemap to export.</source>
        <translation>No hay ningún mapa de tiles para exportar.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5110"/>
        <source>Exporting…</source>
        <translation>Exportando…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5115"/>
        <source>Exporting %1 of %2…</source>
        <translation>Exportando %1 de %2…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5158"/>
        <source>Export Failed</source>
        <translation>Error de exportación</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5159"/>
        <source>%1 export target(s) failed:
%2</source>
        <translation>%1 destino(s) de exportación fallaron:
%2</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5166"/>
        <source>Export complete (%1 file(s)).</source>
        <translation>Exportación completada (%1 archivo(s)).</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5218"/>
        <source>Automation</source>
        <translation>Automatización</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5240"/>
        <source>Automation Error</source>
        <translation>Error de automatización</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5258"/>
        <source>Running automation…</source>
        <translation>Ejecutando automatización…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5304"/>
        <source>Assistant edit</source>
        <translation>Edición del asistente</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5319"/>
        <source>PixelArt Creator</source>
        <translation>PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5320"/>
        <source>Tools</source>
        <translation>Herramientas</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5321"/>
        <source>Palette</source>
        <translation>Paleta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5322"/>
        <source>Symmetry</source>
        <translation>Simetría</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5323"/>
        <source>Layers</source>
        <translation>Capas</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5324"/>
        <source>Timeline</source>
        <translation>Línea de tiempo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5325"/>
        <source>Onion Skin</source>
        <translation>Papel cebolla</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5326"/>
        <source>Frame Tags</source>
        <translation>Etiquetas de fotogramas</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5327"/>
        <source>Palette Editor</source>
        <translation>Editor de paleta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5328"/>
        <source>Constraints</source>
        <translation>Restricciones</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5329"/>
        <source>Shade Ramps</source>
        <translation>Rampas de sombra</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5331"/>
        <source>Analytics</source>
        <translation>Analíticas</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5332"/>
        <source>Tileset Editor</source>
        <translation>Editor de tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5333"/>
        <source>Tilemap Layers</source>
        <translation>Capas del mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5334"/>
        <source>Tilemap Canvas</source>
        <translation>Lienzo del mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5335"/>
        <source>Batch Export</source>
        <translation>Exportación por lotes</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5336"/>
        <source>Macros</source>
        <translation>Macros</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5337"/>
        <source>Script Runner</source>
        <translation>Ejecutor de scripts</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5338"/>
        <source>Plugins</source>
        <translation>Complementos</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5339"/>
        <source>Batch Recolour</source>
        <translation>Recoloreado por lotes</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5340"/>
        <source>Procedural Generation</source>
        <translation>Generación procedural</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5341"/>
        <source>Shared Projects</source>
        <translation>Proyectos compartidos</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5342"/>
        <source>Comments</source>
        <translation>Comentarios</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5343"/>
        <source>Presence</source>
        <translation>Presencia</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5344"/>
        <source>Branching</source>
        <translation>Ramificación</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5345"/>
        <source>Asset Library</source>
        <translation>Biblioteca de recursos</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5346"/>
        <source>Asset Search</source>
        <translation>Búsqueda de recursos</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5347"/>
        <source>Asset Tagging</source>
        <translation>Etiquetado de recursos</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5348"/>
        <source>Dependency Graph</source>
        <translation>Grafo de dependencias</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5349"/>
        <source>Asset Versions</source>
        <translation>Versiones del recurso</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5350"/>
        <source>Asset Reuse</source>
        <translation>Reutilización de recursos</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5354"/>
        <source>Real-Size Preview</source>
        <translation>Vista a tamaño real</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5355"/>
        <source>Timelapse</source>
        <translation>Timelapse</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5356"/>
        <source>Reopened Recording</source>
        <translation>Grabación reabierta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5357"/>
        <source>Open documents</source>
        <translation>Documentos abiertos</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5358"/>
        <source>Floating selection status</source>
        <translation>Estado de selección flotante</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5362"/>
        <source>Pencil</source>
        <translation>Lápiz</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5363"/>
        <source>Eraser</source>
        <translation>Borrador</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5364"/>
        <source>Fill</source>
        <translation>Relleno</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5365"/>
        <source>Line</source>
        <translation>Línea</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5366"/>
        <source>Colour picker</source>
        <translation>Selector de color</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5367"/>
        <source>Rectangle</source>
        <translation>Rectángulo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5368"/>
        <source>Ellipse</source>
        <translation>Elipse</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5369"/>
        <source>Rectangle select</source>
        <translation>Selección rectangular</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5370"/>
        <source>Lasso select</source>
        <translation>Selección de lazo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5371"/>
        <source>Magic wand</source>
        <translation>Varita mágica</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5372"/>
        <location filename="../ui/main_window.py" line="5430"/>
        <source>Dither</source>
        <translation>Tramado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5381"/>
        <source>&amp;New</source>
        <translation>&amp;Nuevo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5382"/>
        <source>&amp;Open…</source>
        <translation>&amp;Abrir…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5383"/>
        <source>&amp;Save</source>
        <translation>&amp;Guardar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5384"/>
        <source>Save &amp;As…</source>
        <translation>Guardar &amp;como…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5385"/>
        <source>&amp;Export…</source>
        <translation>&amp;Exportar…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5386"/>
        <source>&amp;Close</source>
        <translation>&amp;Cerrar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5388"/>
        <source>&amp;Connect…</source>
        <translation>&amp;Conectar…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5389"/>
        <source>&amp;Disconnect</source>
        <translation>&amp;Desconectar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5390"/>
        <source>&amp;Save to Cloud…</source>
        <translation>&amp;Guardar en la nube…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5391"/>
        <source>&amp;Open from Cloud…</source>
        <translation>&amp;Abrir desde la nube…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5392"/>
        <source>&amp;Version History…</source>
        <translation>&amp;Historial de versiones…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5394"/>
        <source>Start &amp;Real-time…</source>
        <translation>Iniciar &amp;tiempo real…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5395"/>
        <source>Stop Real-&amp;time</source>
        <translation>Detener t&amp;iempo real</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5396"/>
        <source>Show &amp;Live Cursors</source>
        <translation>Mostrar &amp;cursores en vivo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5397"/>
        <source>Zoom &amp;In</source>
        <translation>&amp;Acercar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5398"/>
        <source>Zoom &amp;Out</source>
        <translation>A&amp;lejar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5399"/>
        <source>&amp;Fit to View</source>
        <translation>&amp;Ajustar a la vista</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5400"/>
        <source>Fit to &amp;Content</source>
        <translation>Ajustar al &amp;contenido</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5401"/>
        <source>Show &amp;Grid</source>
        <translation>Mostrar &amp;cuadrícula</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5402"/>
        <source>&amp;Snap to Grid</source>
        <translation>&amp;Ajustar a la cuadrícula</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5403"/>
        <source>&amp;Anti-aliasing Off</source>
        <translation>&amp;Suavizado desactivado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5408"/>
        <source>New Tileset from Image…</source>
        <translation>Nuevo tileset desde imagen…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5409"/>
        <source>New Tilemap</source>
        <translation>Nuevo mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5410"/>
        <source>Import Tiled JSON…</source>
        <translation>Importar JSON de Tiled…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5411"/>
        <source>Export Tiled JSON…</source>
        <translation>Exportar JSON de Tiled…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5412"/>
        <source>Stamp Tool</source>
        <translation>Herramienta de sello</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5413"/>
        <source>Place the selected tile</source>
        <translation>Coloca el tile seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5414"/>
        <source>Tile Eraser</source>
        <translation>Borrador de tiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5415"/>
        <source>Clear the target cell</source>
        <translation>Limpia la celda de destino</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5416"/>
        <source>Rectangle Fill</source>
        <translation>Relleno rectangular</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5418"/>
        <source>Fill a dragged rectangle with the selected tile</source>
        <translation>Rellena un rectángulo arrastrado con el tile seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5420"/>
        <source>Flip Stamp Horizontal</source>
        <translation>Voltear sello horizontalmente</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5421"/>
        <source>Flip Stamp Vertical</source>
        <translation>Voltear sello verticalmente</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5422"/>
        <source>Rotate Stamp 90° CW</source>
        <translation>Rotar sello 90° a la derecha</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5426"/>
        <source>Fille&amp;d Shapes</source>
        <translation>&amp;Formas rellenas</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5427"/>
        <source>&amp;Pixel Perfect</source>
        <translation>&amp;Píxel perfecto</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5450"/>
        <source>Canvas &amp;Size…</source>
        <translation>&amp;Tamaño del lienzo…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5455"/>
        <source>Configure &amp;Isometric Grid…</source>
        <translation>Configurar &amp;cuadrícula isométrica…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5457"/>
        <source>Configure &amp;Perspective…</source>
        <translation>Configurar &amp;perspectiva…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5471"/>
        <source>&amp;Library</source>
        <translation>&amp;Biblioteca</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5473"/>
        <source>&amp;Register Active Document…</source>
        <translation>Registrar &amp;documento activo…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5475"/>
        <source>Register &amp;Selection…</source>
        <translation>Registrar &amp;selección…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5476"/>
        <source>&amp;Import Asset…</source>
        <translation>&amp;Importar recurso…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5477"/>
        <source>&amp;Export Asset…</source>
        <translation>&amp;Exportar recurso…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5478"/>
        <source>Export Project &amp;Bundle…</source>
        <translation>Exportar &amp;paquete de proyecto…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5479"/>
        <source>I&amp;mport Project Bundle…</source>
        <translation>Importar pa&amp;quete de proyecto…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5482"/>
        <source>&amp;Help</source>
        <translation>&amp;Ayuda</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5483"/>
        <source>&amp;User Guide</source>
        <translation>&amp;Guía del usuario</translation>
    </message>
    <message>
        <source>Anti-aliasing Off</source>
        <translation type="vanished">Suavizado desactivado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5404"/>
        <source>&amp;Tiled Mode</source>
        <translation>Modo &amp;mosaico</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5405"/>
        <source>Light</source>
        <translation>Claro</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5406"/>
        <source>Dark</source>
        <translation>Oscuro</translation>
    </message>
    <message>
        <source>Filled Shapes</source>
        <translation type="vanished">Formas rellenas</translation>
    </message>
    <message>
        <source>Pixel Perfect</source>
        <translation type="vanished">Píxel perfecto</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5428"/>
        <source>Tolerance</source>
        <translation>Tolerancia</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5429"/>
        <source>Magic-wand tolerance</source>
        <translation>Tolerancia de la varita mágica</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5431"/>
        <source>Dither mode</source>
        <translation>Modo de tramado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5432"/>
        <source>Ordered (Bayer)</source>
        <translation>Ordenado (Bayer)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5433"/>
        <source>Floyd–Steinberg</source>
        <translation>Floyd–Steinberg</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5434"/>
        <source>&amp;Extract from Image…</source>
        <translation>&amp;Extraer de imagen…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5435"/>
        <source>Palette &amp;Swap…</source>
        <translation>Intercambio de &amp;paleta…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5437"/>
        <source>Convert to Inde&amp;xed</source>
        <translation>Convertir a inde&amp;xado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5438"/>
        <source>&amp;Convert to RGBA</source>
        <translation>&amp;Convertir a RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5440"/>
        <source>Select &amp;All</source>
        <translation>Seleccionar &amp;todo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5441"/>
        <source>&amp;Deselect</source>
        <translation>&amp;Deseleccionar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5442"/>
        <source>&amp;Invert Selection</source>
        <translation>&amp;Invertir selección</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5443"/>
        <source>&amp;Clear Selection</source>
        <translation>&amp;Borrar selección</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5445"/>
        <source>Flip &amp;Horizontal</source>
        <translation>Voltear &amp;horizontalmente</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5446"/>
        <source>Flip &amp;Vertical</source>
        <translation>Voltear &amp;verticalmente</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5447"/>
        <source>Rotate 90° C&amp;W</source>
        <translation>Rotar 90° &amp;horario</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5448"/>
        <source>Rotate 90° CC&amp;W</source>
        <translation>Rotar 90° &amp;antihorario</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5449"/>
        <source>&amp;Scale…</source>
        <translation>&amp;Escalar…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5451"/>
        <source>&amp;Rotate (RotSprite)…</source>
        <translation>&amp;Rotar (RotSprite)…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5453"/>
        <source>Guides &amp;&amp; &amp;Rulers</source>
        <translation>Guías &amp;&amp; &amp;Reglas</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5454"/>
        <source>&amp;Isometric Grid</source>
        <translation>Cuadrícula &amp;Isométrica</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5456"/>
        <source>&amp;Perspective Grid</source>
        <translation>Cuadrícula en &amp;Perspectiva</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5458"/>
        <source>&amp;New View</source>
        <translation>&amp;Nueva Vista</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5459"/>
        <source>Reference &amp;Board</source>
        <translation>Panel de &amp;Referencia</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5461"/>
        <source>&amp;File</source>
        <translation>&amp;Archivo</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5462"/>
        <source>&amp;Edit</source>
        <translation>&amp;Editar</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5463"/>
        <source>&amp;Select</source>
        <translation>&amp;Selección</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5464"/>
        <source>&amp;Image</source>
        <translation>&amp;Imagen</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5465"/>
        <source>&amp;View</source>
        <translation>&amp;Ver</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5466"/>
        <source>&amp;Aids</source>
        <translation>A&amp;yudas</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5467"/>
        <source>&amp;Palette</source>
        <translation>&amp;Paleta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5468"/>
        <source>Tile&amp;map</source>
        <translation>Mapa de &amp;tiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5469"/>
        <source>&amp;Automation</source>
        <translation>&amp;Automatización</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5470"/>
        <source>&amp;Cloud</source>
        <translation>&amp;Nube</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5480"/>
        <source>&amp;Theme</source>
        <translation>&amp;Tema</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5481"/>
        <source>&amp;Language</source>
        <translation>&amp;Idioma</translation>
    </message>
</context>
<context>
    <name>New_Document_Dialog</name>
    <message>
        <location filename="../ui/new_document_dialog.py" line="78"/>
        <source>New Document</source>
        <translation>Nuevo documento</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="79"/>
        <source>New document dialog</source>
        <translation>Diálogo de nuevo documento</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="80"/>
        <source>Document width in pixels</source>
        <translation>Anchura del documento en píxeles</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="81"/>
        <source>Document height in pixels</source>
        <translation>Altura del documento en píxeles</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="82"/>
        <source>Width (px)</source>
        <translation>Anchura (px)</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="83"/>
        <source>Height (px)</source>
        <translation>Altura (px)</translation>
    </message>
</context>
<context>
    <name>Onion_Skin_Controls</name>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="105"/>
        <location filename="../ui/onion_skin_controls.py" line="176"/>
        <source>Previous frames</source>
        <extracomment>Emitted with the current :class:`OnionSettings` on any change (live update).</extracomment>
        <translation>Fotogramas anteriores</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="106"/>
        <location filename="../ui/onion_skin_controls.py" line="177"/>
        <source>Next frames</source>
        <translation>Fotogramas siguientes</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="132"/>
        <location filename="../ui/onion_skin_controls.py" line="183"/>
        <source>Previous-frame tint</source>
        <translation>Tinte del fotograma anterior</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="139"/>
        <location filename="../ui/onion_skin_controls.py" line="185"/>
        <source>Next-frame tint</source>
        <translation>Tinte del fotograma siguiente</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="173"/>
        <source>Onion skin controls</source>
        <translation>Controles de papel cebolla</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="174"/>
        <source>Enable onion skinning</source>
        <translation>Activar papel cebolla</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="175"/>
        <source>Onion skin toggle</source>
        <translation>Alternar papel cebolla</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="178"/>
        <source>Previous onion frame count</source>
        <translation>Número de fotogramas anteriores de papel cebolla</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="179"/>
        <source>How many earlier frames to ghost</source>
        <translation>Cuántos fotogramas anteriores mostrar como fantasma</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="180"/>
        <source>Next onion frame count</source>
        <translation>Número de fotogramas siguientes de papel cebolla</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="181"/>
        <source>How many later frames to ghost</source>
        <translation>Cuántos fotogramas posteriores mostrar como fantasma</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="182"/>
        <location filename="../ui/onion_skin_controls.py" line="184"/>
        <source>Tint…</source>
        <translation>Tinte…</translation>
    </message>
</context>
<context>
    <name>Overwrite_Confirm_Dialog</name>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="76"/>
        <source>Overwrite Existing Pixels?</source>
        <translation>¿Sobrescribir píxeles existentes?</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="77"/>
        <source>Overwrite existing pixels confirmation</source>
        <translation>Confirmación de sobrescritura de píxeles existentes</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="80"/>
        <source>The destination already has pixels on it. Continuing replaces that content. This can be undone.</source>
        <translation>El destino ya tiene píxeles. Continuar reemplaza ese contenido. Esto se puede deshacer.</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="84"/>
        <source>Overwrite warning</source>
        <translation>Advertencia de sobrescritura</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="85"/>
        <source>Don&apos;t ask again for this project</source>
        <translation>No volver a preguntar para este proyecto</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="87"/>
        <source>Suppress this confirmation for the current project</source>
        <translation>Suprimir esta confirmación para el proyecto actual</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="91"/>
        <location filename="../ui/overwrite_confirm_dialog.py" line="92"/>
        <source>Continue</source>
        <translation>Continuar</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="95"/>
        <location filename="../ui/overwrite_confirm_dialog.py" line="96"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
</context>
<context>
    <name>Palette_Analytics_View</name>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="171"/>
        <source>Palette Analytics</source>
        <extracomment>Edge of a colour-swatch icon in the table, px (presentation-only sizing). Debounce window (ms) coalescing a burst of deferred refresh requests into a single buffer scan (presentation-only timing, not a domain tuning value — cf. _SWATCH_PX). Short enough to feel instant when the dock becomes visible.</extracomment>
        <translation>Analíticas de paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="172"/>
        <source>Palette analytics view</source>
        <translation>Vista de analíticas de paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="173"/>
        <source>Colour usage counts</source>
        <translation>Recuentos de uso de color</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="175"/>
        <source>Colour / Index</source>
        <translation>Color / Índice</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="175"/>
        <source>Usage count</source>
        <translation>Recuento de uso</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="177"/>
        <source>Refresh</source>
        <translation>Actualizar</translation>
    </message>
</context>
<context>
    <name>Palette_Constraint_Panel</name>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="60"/>
        <source>Constrain to Hardware Palette</source>
        <extracomment>Preset identifiers routed back to the shell (which owns the logic call). Emitted with a preset id (``PRESET_NES`` / ``PRESET_GAME_BOY``) on click.</extracomment>
        <translation>Restringir a paleta de hardware</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="61"/>
        <source>Palette constraint presets</source>
        <translation>Ajustes de restricción de paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="62"/>
        <source>Constrain to NES</source>
        <translation>Restringir a NES</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="63"/>
        <source>Constrain to Game Boy</source>
        <translation>Restringir a Game Boy</translation>
    </message>
</context>
<context>
    <name>Palette_Editor_Panel</name>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="225"/>
        <location filename="../ui/palette_editor_panel.py" line="229"/>
        <source>Add Colour</source>
        <extracomment>Edge of an editor swatch icon, px (presentation-only sizing). Maps a save/open dialog filter label to the ``palette_io`` format token. Emitted with an RGBA tuple when a swatch is selected (sets active colour).</extracomment>
        <translation>Añadir color</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="225"/>
        <source>The palette is full.</source>
        <translation>La paleta está llena.</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="244"/>
        <source>Remove Colour</source>
        <translation>Eliminar color</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="256"/>
        <location filename="../ui/palette_editor_panel.py" line="270"/>
        <source>Reorder Palette</source>
        <translation>Reordenar paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="279"/>
        <location filename="../ui/palette_editor_panel.py" line="288"/>
        <source>Export Palette</source>
        <translation>Exportar paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="295"/>
        <location filename="../ui/palette_editor_panel.py" line="305"/>
        <location filename="../ui/palette_editor_panel.py" line="307"/>
        <source>Import Palette</source>
        <translation>Importar paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="321"/>
        <source>Palette Editor</source>
        <translation>Editor de paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="322"/>
        <source>Palette editor panel</source>
        <translation>Panel del editor de paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="323"/>
        <source>Editable colour palette</source>
        <translation>Paleta de colores editable</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="324"/>
        <source>Add</source>
        <translation>Añadir</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="325"/>
        <source>Add the active colour</source>
        <translation>Añadir el color activo</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="326"/>
        <source>Remove</source>
        <translation>Eliminar</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="327"/>
        <source>Move Up</source>
        <translation>Subir</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="328"/>
        <source>Move Down</source>
        <translation>Bajar</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="329"/>
        <source>Import…</source>
        <translation>Importar…</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="330"/>
        <source>Export…</source>
        <translation>Exportar…</translation>
    </message>
</context>
<context>
    <name>Palette_Panel</name>
    <message>
        <location filename="../ui/main_window.py" line="513"/>
        <source>Colour palette</source>
        <extracomment>Stable cloud recovery-slot key for the working document when no named cloud project is active (presentation-only identifier, not a domain tuning value). A sensible starter palette for a new document (usability, not a spec value). Swatch icon edge, px (presentation-only sizing, not a domain tuning value). Filename of the app-level Favourites store under AppConfigLocation (ADR-0004). Longest edge of a RotSprite preview thumbnail, px (presentation-only sizing, not a domain tuning value — cf. _SWATCH_PX). Tool ids whose stroke WRITES the active colour to the buffer (CL-18, 2026-08-24 ruling UR-HUBFILL-2): the value written is ``ctx.paint_value()`` / ``ctx.active_color`` itself, not merely a live-preview tint. These five run under REQ-P3-UI-006 leg (2) from a completed colour-hub pick; the other six tool ids (eraser, the three selection tools, picker, dither) hide the hub&apos;s wheel/value/numeric/harmony pick surface (``set_pick_surface_visible``) and never run from a hub pick, even a Favourites activation (SC-U006-13). Tool identifiers, not numeric tuning values, so this stays a set of the tools&apos; own ``tool_id`` class attributes rather than a `constants.py` entry. FIX 3 (2026-08-24 field defect, RC-1 follow-up). Every right-hand &quot;workflow&quot; panel is tabified into ONE dock group (``_add_workflow_dock``), and a Qt tab group&apos;s minimum width is the MAXIMUM over its members&apos; own content-derived ``minimumSizeHint()`` — verified up to 766 px for one panel (probe-runtime-canvas-20260824.py). That floor overrides FIX 1&apos;s ``CANVAS_PANE_WIDTH_RATIO`` split regardless of window width, so no per-panel edit can fix it: the override has to happen once, here, at the single place every workflow dock is created. Overriding ``QWidget.setMinimumWidth()`` on the panel (verified empirically to lower ``QDockWidget.minimumSizeHint()`` even though the panel&apos;s own ``minimumSizeHint()`` is unchanged and content can clip below it — Qt&apos;s dock layout consults the explicit minimum, not the generic ``QLayoutItem.minimumSize()`` ``expandedTo`` rule) is presentation sizing, not a domain tuning value, so it stays local exactly like _SWATCH_PX / _PREVIEW_MAX_EDGE_PX above — see the FIX-3 report note requesting this be promoted to logic/constants.py (a logic-layer surface) as e.g. ``WORKFLOW_DOCK_MIN_WIDTH_PX`` rather than reached into from here. FIX 3 (2026-08-24 field defect). Bound on ``Main_Window._settle_width()``&apos;s event-flush loop (presentation-only startup timing, not a domain tuning value — cf. _SWATCH_PX / _PREVIEW_MAX_EDGE_PX above). Observed settling in 2 passes on the probe&apos;s offscreen run; this leaves generous headroom without risking an unbounded/hanging wait on a layout that never settles. FIX 1 (2026-08-24 field defect, RC-1 follow-up on the earlier FIX 1). The window was never given an explicit default size; Qt sized it to its layout hint, which on a real desktop happened to land the canvas at only ~10% of the window even after the FIX 1/FIX 3 dock-splitting work above, because that split is a RATIO of whatever width the window already has -- a window with no deliberate width defeats a width RATIO. Fraction of the primary screen&apos;s *available* geometry (excludes taskbars/docks) the window claims on first launch, absent any saved geometry restore (presentation-only startup sizing, not a domain tuning value -- cf. _WORKFLOW_DOCK_MIN_WIDTH_PX / _SWATCH_PX above). Report note: a candidate for promotion to logic/constants.py as e.g. DEFAULT_LAUNCH_SIZE_RATIO, exactly like that floor&apos;s own promotion note -- left local here on the same precedent.</extracomment>
        <translation>Paleta de colores</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="514"/>
        <source>Palette panel</source>
        <translation>Panel de paleta</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="515"/>
        <source>Colour mode</source>
        <translation>Modo de color</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="520"/>
        <source>Mode: Indexed</source>
        <translation>Modo: Indexado</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="522"/>
        <source>Mode: RGBA</source>
        <translation>Modo: RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="524"/>
        <source>Mode: —</source>
        <translation>Modo: —</translation>
    </message>
</context>
<context>
    <name>Palette_Swap_Dialog</name>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="102"/>
        <source>Palette Swap</source>
        <translation>Intercambio de paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="103"/>
        <source>Palette swap dialog</source>
        <translation>Diálogo de intercambio de paleta</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="104"/>
        <source>From index</source>
        <translation>Desde índice</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="105"/>
        <source>To index</source>
        <translation>A índice</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="106"/>
        <source>Source index</source>
        <translation>Índice de origen</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="107"/>
        <source>Target index</source>
        <translation>Índice de destino</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="108"/>
        <source>Add</source>
        <translation>Añadir</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="109"/>
        <source>Remove</source>
        <translation>Eliminar</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="110"/>
        <source>Index remap entries</source>
        <translation>Entradas de reasignación de índices</translation>
    </message>
</context>
<context>
    <name>Playback_Controls</name>
    <message>
        <location filename="../ui/playback_controls.py" line="364"/>
        <source>Loop</source>
        <extracomment>Type of the per-tick step yielded by the sequencing engine: (index, ms). Emitted with the frame index to display on each playback tick (scrub-like). Emitted ``True`` when playback becomes active, ``False`` when it halts. The shell suppresses onion skinning while active (CL-11).</extracomment>
        <translation>Bucle</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="365"/>
        <source>Once</source>
        <translation>Una vez</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="366"/>
        <source>Ping-Pong</source>
        <translation>Ping-Pong</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="367"/>
        <source>Reverse</source>
        <translation>Inversa</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="372"/>
        <source>Playback controls</source>
        <translation>Controles de reproducción</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="373"/>
        <location filename="../ui/playback_controls.py" line="375"/>
        <source>Play</source>
        <translation>Reproducir</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="374"/>
        <source>Play (Space)</source>
        <translation>Reproducir (Espacio)</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="376"/>
        <location filename="../ui/playback_controls.py" line="378"/>
        <source>Pause</source>
        <translation>Pausar</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="377"/>
        <source>Pause (Space)</source>
        <translation>Pausar (Espacio)</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="379"/>
        <location filename="../ui/playback_controls.py" line="381"/>
        <source>Stop</source>
        <translation>Detener</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="380"/>
        <source>Stop and return to the start frame</source>
        <translation>Detener y volver al fotograma inicial</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="382"/>
        <source>Playback mode</source>
        <translation>Modo de reproducción</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="383"/>
        <source>Global playback mode</source>
        <translation>Modo de reproducción global</translation>
    </message>
</context>
<context>
    <name>Plugin_Manager_Panel</name>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="133"/>
        <source>Add Plugin Manifest</source>
        <extracomment>Enabled plugin handles keyed by plugin name (view/session state).</extracomment>
        <translation>Añadir manifiesto de complemento</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="135"/>
        <source>Manifest files (*.json)</source>
        <translation>Archivos de manifiesto (*.json)</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="142"/>
        <source>Install Failed</source>
        <translation>Error de instalación</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="165"/>
        <source>No Manifest</source>
        <translation>Sin manifiesto</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="167"/>
        <source>This plugin has no loaded manifest. Use Add Manifest to load its declared permissions before enabling it.</source>
        <translation>Este complemento no tiene un manifiesto cargado. Usa Añadir manifiesto para cargar sus permisos declarados antes de habilitarlo.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="174"/>
        <source>Enable Plugin</source>
        <translation>Habilitar complemento</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="176"/>
        <source>Enable %1 and grant it these permissions?

%2

The plugin runs sandboxed and can only edit through reversible commands. It cannot reach the UI, filesystem, or network.</source>
        <translation>¿Habilitar %1 y concederle estos permisos?

%2

El complemento se ejecuta en un entorno aislado y solo puede editar mediante comandos reversibles. No puede acceder a la interfaz, al sistema de archivos ni a la red.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="188"/>
        <source>Enable Failed</source>
        <translation>Error al habilitar</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="215"/>
        <source>enabled</source>
        <translation>habilitado</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="215"/>
        <source>disabled</source>
        <translation>deshabilitado</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="216"/>
        <source>%1 v%2 — %3</source>
        <translation>%1 v%2 — %3</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="245"/>
        <source>(no manifest loaded — permissions unknown)</source>
        <translation>(sin manifiesto cargado — permisos desconocidos)</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="258"/>
        <source>Select a plugin to view its permissions.</source>
        <translation>Selecciona un complemento para ver sus permisos.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="268"/>
        <source>Refresh</source>
        <translation>Actualizar</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="269"/>
        <source>Add Manifest…</source>
        <translation>Añadir manifiesto…</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="270"/>
        <source>Enable</source>
        <translation>Habilitar</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="271"/>
        <source>Disable</source>
        <translation>Deshabilitar</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="272"/>
        <source>Declared permissions:</source>
        <translation>Permisos declarados:</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="273"/>
        <source>Plugin manager</source>
        <translation>Gestor de complementos</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="274"/>
        <source>Discovered and installed plugins</source>
        <translation>Complementos descubiertos e instalados</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="275"/>
        <source>Selected plugin permissions</source>
        <translation>Permisos del complemento seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="276"/>
        <source>Refresh the plugin list</source>
        <translation>Actualizar la lista de complementos</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="277"/>
        <source>Add a plugin manifest</source>
        <translation>Añadir un manifiesto de complemento</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="278"/>
        <source>Enable the selected plugin</source>
        <translation>Habilitar el complemento seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="279"/>
        <source>Disable the selected plugin</source>
        <translation>Deshabilitar el complemento seleccionado</translation>
    </message>
</context>
<context>
    <name>Presence_Panel</name>
    <message>
        <location filename="../ui/presence_panel.py" line="100"/>
        <location filename="../ui/presence_panel.py" line="108"/>
        <location filename="../ui/presence_panel.py" line="115"/>
        <location filename="../ui/presence_panel.py" line="154"/>
        <source>Presence</source>
        <translation>Presencia</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="101"/>
        <source>Open a shared project first.</source>
        <translation>Abre primero un proyecto compartido.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="109"/>
        <source>Enter your member id to announce presence.</source>
        <translation>Introduce tu id de miembro para anunciar tu presencia.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="157"/>
        <source>Members currently present in the shared project. Presence is ephemeral and is never saved into the project file.</source>
        <translation>Miembros presentes actualmente en el proyecto compartido. La presencia es efímera y nunca se guarda en el archivo del proyecto.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="161"/>
        <location filename="../ui/presence_panel.py" line="162"/>
        <source>Your member id</source>
        <translation>Tu id de miembro</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="163"/>
        <source>Join</source>
        <translation>Unirse</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="164"/>
        <source>Announce your presence</source>
        <translation>Anunciar tu presencia</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="165"/>
        <source>Leave</source>
        <translation>Salir</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="166"/>
        <source>Clear your presence</source>
        <translation>Borrar tu presencia</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="167"/>
        <source>Present members</source>
        <translation>Miembros presentes</translation>
    </message>
</context>
<context>
    <name>Prewarm_Indicator</name>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="81"/>
        <source>Playback preparation progress</source>
        <extracomment>Emitted when the user cancels the pre-warm (wired to Stop by the shell).</extracomment>
        <translation>Progreso de la preparación de la reproducción</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="82"/>
        <source>Preparing playback…</source>
        <translation>Preparando la reproducción…</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="83"/>
        <source>Frames prepared</source>
        <translation>Fotogramas preparados</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="84"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="85"/>
        <location filename="../ui/prewarm_indicator.py" line="86"/>
        <source>Cancel playback preparation</source>
        <translation>Cancelar la preparación de la reproducción</translation>
    </message>
</context>
<context>
    <name>Procgen_Panel</name>
    <message>
        <location filename="../ui/procgen_panel.py" line="79"/>
        <location filename="../ui/procgen_panel.py" line="83"/>
        <location filename="../ui/procgen_panel.py" line="207"/>
        <location filename="../ui/procgen_panel.py" line="208"/>
        <source> px</source>
        <extracomment>Largest seed the spin box offers (a display range for the control; the engine accepts any int seed). 2**31 - 1 keeps the value in the Qt spin box&apos;s int range. ``(ops, label)`` — the host should dispatch the ``procgen`` op on the worker as one undoable grouped command (REQ-P8-UI-007/-009).</extracomment>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="150"/>
        <source>Running…</source>
        <translation>Ejecutando…</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="152"/>
        <source>Done</source>
        <translation>Hecho</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="153"/>
        <source>Idle</source>
        <translation>Inactivo</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="168"/>
        <source>Procedural Generation</source>
        <translation>Generación procedural</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="191"/>
        <source>Value noise</source>
        <translation>Ruido de valor</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="192"/>
        <source>Gradient noise</source>
        <translation>Ruido de gradiente</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="193"/>
        <source>OpenSimplex noise</source>
        <translation>Ruido OpenSimplex</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="194"/>
        <source>Cellular automata</source>
        <translation>Autómatas celulares</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="195"/>
        <source>Dithered gradient</source>
        <translation>Gradiente con tramado</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="201"/>
        <source>Algorithm</source>
        <translation>Algoritmo</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="202"/>
        <source>Seed</source>
        <translation>Semilla</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="203"/>
        <source>Width</source>
        <translation>Ancho</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="204"/>
        <source>Height</source>
        <translation>Alto</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="205"/>
        <source>Frequency</source>
        <translation>Frecuencia</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="206"/>
        <source>Octaves</source>
        <translation>Octavas</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="209"/>
        <source>Generate</source>
        <translation>Generar</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="211"/>
        <source>Procedural generation</source>
        <translation>Generación procedural</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="212"/>
        <source>Generation algorithm</source>
        <translation>Algoritmo de generación</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="213"/>
        <source>Random seed</source>
        <translation>Semilla aleatoria</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="214"/>
        <source>Output width in pixels</source>
        <translation>Ancho de salida en píxeles</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="215"/>
        <source>Output height in pixels</source>
        <translation>Alto de salida en píxeles</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="216"/>
        <source>Noise base frequency</source>
        <translation>Frecuencia base del ruido</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="217"/>
        <source>Noise octaves</source>
        <translation>Octavas del ruido</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="218"/>
        <source>Generate content</source>
        <translation>Generar contenido</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="219"/>
        <source>Progress</source>
        <translation>Progreso</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="220"/>
        <source>Generation progress</source>
        <translation>Progreso de generación</translation>
    </message>
</context>
<context>
    <name>Provider_Config_Dialog</name>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="257"/>
        <source>The OS keyring is unavailable; install the &apos;assistant_live&apos; extra to store an API key. The provider settings were saved.</source>
        <extracomment>Provider-kind identifiers. These double as the keyring service namespace segment (``pixelart-creator:assistant:{provider}``) and the adapter&apos;s ``provider`` arg, so the key stored here is the key the adapter loads. Module-local vocabulary (ADR-0001), not a numeric constant. The keyring account the single-user key is stored under (matches ``data/llm``&apos;s ``_DEFAULT_ACCOUNT`` so the adapter loads the same credential). :class:`QSettings` group + keys for the NON-SECRET configuration only. Sensible default endpoints per provider kind (the user may override).</extracomment>
        <translation>El llavero del sistema operativo no está disponible; instala el extra «assistant_live» para guardar una clave de API. La configuración del proveedor se guardó.</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="267"/>
        <source>Could not store the API key: {0}</source>
        <translation>No se pudo guardar la clave de API: {0}</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="275"/>
        <source>Configure AI Assistant Provider</source>
        <translation>Configurar proveedor del asistente de IA</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="276"/>
        <source>AI assistant provider configuration</source>
        <translation>Configuración del proveedor del asistente de IA</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="277"/>
        <source>OpenAI-compatible</source>
        <translation>Compatible con OpenAI</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="278"/>
        <source>Anthropic (Claude)</source>
        <translation>Anthropic (Claude)</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="279"/>
        <location filename="../ui/provider_config_dialog.py" line="280"/>
        <source>Provider</source>
        <translation>Proveedor</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="281"/>
        <source>Endpoint URL</source>
        <translation>URL del punto de conexión</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="282"/>
        <source>Provider endpoint URL</source>
        <translation>URL del punto de conexión del proveedor</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="283"/>
        <source>https://…</source>
        <translation>https://…</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="284"/>
        <source>Model</source>
        <translation>Modelo</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="285"/>
        <source>Model name</source>
        <translation>Nombre del modelo</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="286"/>
        <source>e.g. gpt-4o-mini</source>
        <translation>p. ej. gpt-4o-mini</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="287"/>
        <source>API key</source>
        <translation>Clave de API</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="288"/>
        <source>API key (stored in the OS keyring)</source>
        <translation>Clave de API (almacenada en el llavero del sistema operativo)</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="290"/>
        <source>Leave blank to keep the existing key</source>
        <translation>Déjalo en blanco para conservar la clave existente</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="294"/>
        <source>The API key is stored only in your OS keyring — never in a project file or a log.</source>
        <translation>La clave de API se almacena solo en el llavero de tu sistema operativo, nunca en un archivo de proyecto ni en un registro.</translation>
    </message>
</context>
<context>
    <name>Real_Size_Calibration_Dialog</name>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="82"/>
        <source> mm</source>
        <extracomment>On-screen calibration bar length in device-independent px (a known ruler the user matches against a real ruler / credit card to derive the true DPI). Millimetres per inch (calibration converts a measured mm length to DPI).</extracomment>
        <translation> mm</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="109"/>
        <source>Calibrate Real Size</source>
        <translation>Calibrar tamaño real</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="112"/>
        <source>Hold a ruler against the bar below and enter its measured length so real size matches your screen.</source>
        <translation>Coloca una regla contra la barra de abajo e introduce su longitud medida para que el tamaño real coincida con tu pantalla.</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="116"/>
        <source>Measured length</source>
        <translation>Longitud medida</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="118"/>
        <source>Measured calibration bar length in millimetres</source>
        <translation>Longitud medida de la barra de calibración en milímetros</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="120"/>
        <source>Calibration bar</source>
        <translation>Barra de calibración</translation>
    </message>
</context>
<context>
    <name>Real_Size_Preview_Window</name>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="255"/>
        <source>calibrated</source>
        <extracomment>A user-calibrated DPI override (``None`` =&gt; use the queried physical DPI).</extracomment>
        <translation>calibrado</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="255"/>
        <source>screen</source>
        <translation>pantalla</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="258"/>
        <source>Real size: {0:.0f} PPI ({1}), scale {2:.2f}×</source>
        <translation>Tamaño real: {0:.0f} PPP ({1}), escala {2:.2f}×</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="264"/>
        <source>Real-Size Preview</source>
        <translation>Vista previa a tamaño real</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="265"/>
        <source>Real-size preview</source>
        <translation>Vista previa a tamaño real</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="266"/>
        <source>Real-size document preview</source>
        <translation>Vista previa del documento a tamaño real</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="267"/>
        <source>Calibrate…</source>
        <translation>Calibrar…</translation>
    </message>
</context>
<context>
    <name>Recovery_Prompt</name>
    <message>
        <location filename="../ui/recovery_prompt.py" line="74"/>
        <source>Recover Unsaved Work</source>
        <translation>Recuperar trabajo sin guardar</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="77"/>
        <source>Unsaved work from a previous session was found. Recover it into a new tab? Your last explicit save is not affected.</source>
        <translation>Se encontró trabajo sin guardar de una sesión anterior. ¿Recuperarlo en una nueva pestaña? Tu último guardado explícito no se ve afectado.</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="81"/>
        <source>Recover</source>
        <translation>Recuperar</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="82"/>
        <source>Discard</source>
        <translation>Descartar</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="83"/>
        <source>Recover unsaved work</source>
        <translation>Recuperar trabajo sin guardar</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="84"/>
        <source>Discard unsaved work</source>
        <translation>Descartar trabajo sin guardar</translation>
    </message>
</context>
<context>
    <name>Reference_Board</name>
    <message>
        <location filename="../ui/reference_board.py" line="319"/>
        <source>Reference board full</source>
        <extracomment>Emitted with the picked RGBA tuple when a plain wheel notch travels the shared Favourites cursor (REQ-IS-UI-008, D-16). The board never touches the document/buffers/undo stack (REQ-P9-UI-010); this only sets the app-wide active colour/palette state, same as every other surface. The persisted Favourites model bound via :meth:`set_favourites_model` (D-16); ``None`` until the shell binds one.</extracomment>
        <translation>Panel de referencia lleno</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="320"/>
        <source>The board already holds the maximum of {0} images.</source>
        <translation>El panel ya contiene el máximo de {0} imágenes.</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="329"/>
        <source>Cannot load image</source>
        <translation>No se puede cargar la imagen</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="330"/>
        <source>The file could not be read as an image: {0}</source>
        <translation>No se pudo leer el archivo como imagen: {0}</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="401"/>
        <source>Save Reference Board</source>
        <translation>Guardar panel de referencia</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="403"/>
        <location filename="../ui/reference_board.py" line="417"/>
        <source>Reference board (*.pixboard)</source>
        <translation>Panel de referencia (*.pixboard)</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="410"/>
        <source>Save failed</source>
        <translation>Error al guardar</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="415"/>
        <source>Open Reference Board</source>
        <translation>Abrir panel de referencia</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="425"/>
        <source>Open failed</source>
        <translation>Error al abrir</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="432"/>
        <source>Add Reference Image</source>
        <translation>Añadir imagen de referencia</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="434"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>Imágenes (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="500"/>
        <source>Reference Board</source>
        <translation>Panel de referencia</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="501"/>
        <source>Reference board</source>
        <translation>Panel de referencia</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="502"/>
        <source>Reference board canvas</source>
        <translation>Lienzo del panel de referencia</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="503"/>
        <source>Add Image…</source>
        <translation>Añadir imagen…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="504"/>
        <source>Save…</source>
        <translation>Guardar…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="505"/>
        <source>Open…</source>
        <translation>Abrir…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="506"/>
        <source>Always on Top</source>
        <translation>Siempre encima</translation>
    </message>
</context>
<context>
    <name>Reference_Item</name>
    <message>
        <location filename="../ui/reference_board.py" line="246"/>
        <source>Raise</source>
        <extracomment>Per-wheel-notch board zoom step. Corner grab-handle edge, in item-local px (REQ-P9-UI-006 resize gesture). No matching UI-metric constant exists in ``logic/constants.py`` today (gap reported in this task&apos;s EXIT_STATUS); this module already keeps its own UI-only metrics locally (see ``_BOARD_ZOOM_STEP`` above), so the same convention is followed here rather than inlining a literal (S12). Minimum absolute scale factor a corner-drag resize may reach (guards against a degenerate/zero-size or inverted reference item). Opposite-corner anchor used while resizing (the anchor stays fixed).</extracomment>
        <translation>Subir</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="249"/>
        <source>Lower</source>
        <translation>Bajar</translation>
    </message>
</context>
<context>
    <name>RotSprite_Dialog</name>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="90"/>
        <source>No preview</source>
        <extracomment>Angle input bounds, degrees (a full turn either way; not a domain tuning value). Preview label edge, px (presentation-only sizing). Renders a preview :class:`QImage` for a candidate angle (or ``None``).</extracomment>
        <translation>Sin vista previa</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="103"/>
        <source>Rotate (RotSprite)</source>
        <translation>Rotar (RotSprite)</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="104"/>
        <source>RotSprite rotation dialog</source>
        <translation>Diálogo de rotación RotSprite</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="105"/>
        <source>Rotation angle in degrees</source>
        <translation>Ángulo de rotación en grados</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="106"/>
        <source>Rotation preview</source>
        <translation>Vista previa de rotación</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="107"/>
        <source>Angle (deg)</source>
        <translation>Ángulo (grados)</translation>
    </message>
</context>
<context>
    <name>Ruler_Strip</name>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="347"/>
        <source>Horizontal ruler</source>
        <extracomment>z-order in the aid band, just below the grid overlays so guides read under grids. Ruler strip thickness in device-independent px (presentation sizing). Default overlay/ruler colours (overridden by the theme&apos;s role colours, 025). Emitted ``(orientation, doc_position)`` when a guide is dragged out.</extracomment>
        <translation>Regla horizontal</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="349"/>
        <source>Drag down to create a horizontal guide</source>
        <translation>Arrastra hacia abajo para crear una guía horizontal</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="352"/>
        <source>Vertical ruler</source>
        <translation>Regla vertical</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="354"/>
        <source>Drag right to create a vertical guide</source>
        <translation>Arrastra hacia la derecha para crear una guía vertical</translation>
    </message>
</context>
<context>
    <name>Scale_Dialog</name>
    <message>
        <location filename="../ui/transform_dialog.py" line="107"/>
        <source>Scale Canvas</source>
        <translation>Escalar lienzo</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="108"/>
        <source>Scale canvas dialog</source>
        <translation>Diálogo de escalado de lienzo</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="109"/>
        <source>Scale factor</source>
        <translation>Factor de escala</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="110"/>
        <source>Target width in pixels</source>
        <translation>Anchura objetivo en píxeles</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="111"/>
        <source>Target height in pixels</source>
        <translation>Altura objetivo en píxeles</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="112"/>
        <source>Factor</source>
        <translation>Factor</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="113"/>
        <source>Width (px)</source>
        <translation>Anchura (px)</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="114"/>
        <source>Height (px)</source>
        <translation>Altura (px)</translation>
    </message>
</context>
<context>
    <name>Script_Runner_Panel</name>
    <message>
        <location filename="../ui/script_runner_panel.py" line="113"/>
        <source>Running…</source>
        <extracomment>A compact, copy-pasteable example so the empty editor is self-documenting. ``(ops, label)`` — the host should dispatch these DSL ops on the worker as one undoable grouped command (REQ-P8-UI-004/-009).</extracomment>
        <translation>Ejecutando…</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="115"/>
        <source>Done</source>
        <translation>Hecho</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="116"/>
        <source>Idle</source>
        <translation>Inactivo</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="131"/>
        <source>Invalid JSON: %1</source>
        <translation>JSON no válido: %1</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="133"/>
        <source>A script must be a JSON array of steps.</source>
        <translation>Un script debe ser un arreglo JSON de pasos.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="138"/>
        <source>Each step needs a &apos;name&apos; and optional &apos;params&apos;/&apos;seed&apos;.</source>
        <translation>Cada paso necesita un &apos;name&apos; y opcionalmente &apos;params&apos;/&apos;seed&apos;.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="144"/>
        <source>Step &apos;name&apos; must be a string.</source>
        <translation>El &apos;name&apos; del paso debe ser una cadena.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="146"/>
        <source>Step &apos;params&apos; must be an object.</source>
        <translation>Los &apos;params&apos; del paso deben ser un objeto.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="158"/>
        <source>Script Error</source>
        <translation>Error de script</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="162"/>
        <location filename="../ui/script_runner_panel.py" line="184"/>
        <source>Run Script</source>
        <translation>Ejecutar script</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="183"/>
        <source>DSL script (JSON list of steps):</source>
        <translation>Script DSL (lista JSON de pasos):</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="185"/>
        <source>Script runner</source>
        <translation>Ejecutor de scripts</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="186"/>
        <source>Script source</source>
        <translation>Código fuente del script</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="187"/>
        <source>Run the script</source>
        <translation>Ejecutar el script</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="188"/>
        <source>Progress</source>
        <translation>Progreso</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="189"/>
        <source>Script run progress</source>
        <translation>Progreso de ejecución del script</translation>
    </message>
</context>
<context>
    <name>Shade_Ramp_Picker</name>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="150"/>
        <source>Shade Ramps</source>
        <extracomment>Edge of a ramp swatch button, px (presentation-only sizing). Emitted with an RGBA tuple when a ramp swatch is activated. Emitted with a list of RGBA colours when a whole ramp is added.</extracomment>
        <translation>Rampas de sombra</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="151"/>
        <source>Shade ramp picker</source>
        <translation>Selector de rampas de sombra</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="152"/>
        <source>Shades (toward black)</source>
        <translation>Sombras (hacia el negro)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="153"/>
        <source>Tints (toward white)</source>
        <translation>Tintes (hacia el blanco)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="154"/>
        <source>Tones (toward grey)</source>
        <translation>Tonos (hacia el gris)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="156"/>
        <source>Add to Palette</source>
        <translation>Añadir a la paleta</translation>
    </message>
</context>
<context>
    <name>Shared_Projects_Panel</name>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="143"/>
        <location filename="../ui/shared_projects_panel.py" line="150"/>
        <location filename="../ui/shared_projects_panel.py" line="180"/>
        <location filename="../ui/shared_projects_panel.py" line="187"/>
        <location filename="../ui/shared_projects_panel.py" line="194"/>
        <source>Shared Project</source>
        <extracomment>Fixed display order for the role combo (a stable subset of the module-local :data:`MEMBER_ROLES` vocabulary; presentation ordering, not a domain value). The roster being edited before it is committed via Share/Update.</extracomment>
        <translation>Proyecto compartido</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="144"/>
        <source>Member %1 is already in the roster.</source>
        <translation>El miembro %1 ya está en la lista.</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="151"/>
        <source>A shared project may have at most %1 members.</source>
        <translation>Un proyecto compartido puede tener como máximo %1 miembros.</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="181"/>
        <source>Enter a shared-project name first.</source>
        <translation>Introduce primero un nombre de proyecto compartido.</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="188"/>
        <source>Add at least one member before sharing.</source>
        <translation>Añade al menos un miembro antes de compartir.</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="236"/>
        <source>Owner</source>
        <translation>Propietario</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="237"/>
        <source>Editor</source>
        <translation>Editor</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="238"/>
        <source>Viewer</source>
        <translation>Visualizador</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="243"/>
        <source>Shared projects</source>
        <translation>Proyectos compartidos</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="244"/>
        <source>Shared-project name:</source>
        <translation>Nombre del proyecto compartido:</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="245"/>
        <source>e.g. team-sprite</source>
        <translation>p. ej. team-sprite</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="246"/>
        <source>Shared-project name</source>
        <translation>Nombre del proyecto compartido</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="247"/>
        <location filename="../ui/shared_projects_panel.py" line="248"/>
        <source>Member id to invite</source>
        <translation>Id de miembro a invitar</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="249"/>
        <source>Member role</source>
        <translation>Rol del miembro</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="252"/>
        <source>Add Member</source>
        <translation>Añadir miembro</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="253"/>
        <source>Add member to roster</source>
        <translation>Añadir miembro a la lista</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="254"/>
        <source>Roster to share</source>
        <translation>Lista para compartir</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="255"/>
        <source>Current members</source>
        <translation>Miembros actuales</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="256"/>
        <source>Remove</source>
        <translation>Eliminar</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="257"/>
        <source>Remove selected member</source>
        <translation>Eliminar el miembro seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="258"/>
        <source>Share / Update</source>
        <translation>Compartir / Actualizar</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="259"/>
        <source>Share or update the project</source>
        <translation>Compartir o actualizar el proyecto</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="260"/>
        <source>Member</source>
        <translation>Miembro</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="260"/>
        <source>Role</source>
        <translation>Rol</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="263"/>
        <source>Editable member roster</source>
        <translation>Lista de miembros editable</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="264"/>
        <source>Shared member list</source>
        <translation>Lista de miembros compartida</translation>
    </message>
</context>
<context>
    <name>Symmetry_Panel</name>
    <message>
        <location filename="../ui/symmetry_panel.py" line="155"/>
        <source>Off</source>
        <extracomment>Emitted with the newly selected :class:`SymmetryAxis`. Emitted with the mirror centre as ``Optional[Tuple[int, int]]`` once the user edits a position spinbox (``None`` = unset, ``mirror`` defaults to the canvas centre itself, CL-9). Never emitted from programmatic :meth:`set_canvas_size` calls, so a resize alone never fabricates a user-authored position. Axis order shown in the combo (value stored in the item&apos;s user data).</extracomment>
        <translation>Desactivada</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="156"/>
        <source>Vertical</source>
        <translation>Vertical</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="157"/>
        <source>Horizontal</source>
        <translation>Horizontal</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="158"/>
        <source>Both</source>
        <translation>Ambas</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="159"/>
        <source>Diagonal</source>
        <translation>Diagonal</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="163"/>
        <source>Symmetry</source>
        <translation>Simetría</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="164"/>
        <source>Axis position</source>
        <translation>Posición del eje</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="165"/>
        <source>X</source>
        <translation>X</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="166"/>
        <source>Y</source>
        <translation>Y</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="167"/>
        <source>Reset to centre</source>
        <translation>Restablecer al centro</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="168"/>
        <source>Symmetry axis panel</source>
        <translation>Panel de eje de simetría</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="169"/>
        <source>Symmetry axis</source>
        <translation>Eje de simetría</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="170"/>
        <source>Symmetry axis position X</source>
        <translation>Posición X del eje de simetría</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="171"/>
        <source>Symmetry axis position Y</source>
        <translation>Posición Y del eje de simetría</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="173"/>
        <source>Reset symmetry axis position to centre</source>
        <translation>Restablecer la posición del eje de simetría al centro</translation>
    </message>
</context>
<context>
    <name>Tag_Dialog</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="144"/>
        <location filename="../ui/frame_tags_panel.py" line="188"/>
        <source>Tag colour</source>
        <translation>Color de la etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="175"/>
        <source>Frame Tag</source>
        <translation>Etiqueta de fotograma</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="176"/>
        <source>Name</source>
        <translation>Nombre</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="177"/>
        <source>From frame</source>
        <translation>Desde el fotograma</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="178"/>
        <source>To frame</source>
        <translation>Hasta el fotograma</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="179"/>
        <source>Mode</source>
        <translation>Modo</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="180"/>
        <source>Repeat (0 = infinite)</source>
        <translation>Repetición (0 = infinito)</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="181"/>
        <source>Colour</source>
        <translation>Color</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="182"/>
        <source>Tag name</source>
        <translation>Nombre de la etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="183"/>
        <source>Tag start frame</source>
        <translation>Fotograma inicial de la etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="184"/>
        <source>Tag end frame</source>
        <translation>Fotograma final de la etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="185"/>
        <source>Tag playback mode</source>
        <translation>Modo de reproducción de la etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="186"/>
        <source>Tag repeat count</source>
        <translation>Número de repeticiones de la etiqueta</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="187"/>
        <source>Colour…</source>
        <translation>Color…</translation>
    </message>
</context>
<context>
    <name>Tile_Edit_Dialog</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="191"/>
        <source>Edit Tile</source>
        <translation>Editar tile</translation>
    </message>
</context>
<context>
    <name>Tilemap_Canvas</name>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="722"/>
        <source>Auto-tile</source>
        <extracomment>Initial scene window (px) for a fresh infinite map; grows to include stamps. Edge (px) of one checker square drawn behind the map (presentation-only). Platform name Qt reports with no windowing system (keep the raster viewport). MiB budget of the chunk pixmap LRU (D1). A 16x16 chunk at 16 px tiles is a 256x256 RGBA pixmap (~256 KiB), so ~128 MiB keeps a large working set resident while staying bounded on an infinite / fully filled map. Presentation/resource sizing (like frame_cache&apos;s budget), so it lives here in ui/, not logic/constants. Max cold chunks rendered *inline* per paint before the rest stream off-thread (D4). A cold chunk is ~0.84 ms (measured), so a handful stays well under the 16 ms budget and keeps a stamp / small pan instant; a full cold viewport streams. Bounded wait (ms) for an in-flight off-thread chunk render to finish on rebind / window close before the pool is torn down (mirrors canvas_scene&apos;s shutdown wait). Emitted after a layer&apos;s auto-tile mode changes (drives the panel checkbox). Emitted when a stamp/fill is refused because the tilemap has no tileset bound yet (CI-red field defect, 2026-08-24: the original FIX 5 routed this refusal through a blocking ``QMessageBox.warning``, which hangs a headless parallel worker with nothing to dismiss it). Follows the ``Canvas_View.lockedLayerEditRejected`` precedent exactly -- a signal the shell surfaces non-blockingly, never a modal, for a refusal reachable from a plain mouse gesture. Emitted when a stamp/fill is refused because no tile is selected as the active brush (a tileset IS bound; the brush gid is 0). Kept distinct from ``noTilesetBoundRejected`` so the shell shows the honest message for each case, exactly as the two ``_warn_no_active_brush`` branches already did. Emitted with the picked RGBA tuple when a plain wheel notch / an unmodified middle click travels the shared Favourites cursor (REQ-IS-UI-008/-012). Mirrors ``Canvas_View.colorPicked`` — the tilemap has no colour of its own to paint with, but the app-wide active colour/palette state is shared across every surface. A middle press awaiting the click/drag verdict — see ``Canvas_View._middle_pending`` (REQ-IS-UI-011); same behaviour here. The persisted Favourites model bound via :meth:`set_favourites_model` ``None`` until the shell binds one.</extracomment>
        <translation>Auto-tile</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="980"/>
        <source>Stamp</source>
        <translation>Sellar</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="982"/>
        <source>Stamp Tile</source>
        <translation>Sellar tile</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="991"/>
        <source>Erase</source>
        <translation>Borrar</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="993"/>
        <source>Erase Tile</source>
        <translation>Borrar tile</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1011"/>
        <source>Fill</source>
        <translation>Relleno</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1013"/>
        <source>Fill Rectangle</source>
        <translation>Rellenar rectángulo</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1071"/>
        <source>Tilemap canvas</source>
        <translation>Lienzo del mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1074"/>
        <source>Tilemap: left-click to stamp/erase/fill, middle-drag to pan, H/V flip, R rotate</source>
        <translation>Mapa de tiles: clic izquierdo para sellar/borrar/rellenar, arrastrar con el botón central para desplazar, H/V voltear, R rotar</translation>
    </message>
</context>
<context>
    <name>Tilemap_Layer_Panel</name>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="174"/>
        <source>Layer %1</source>
        <extracomment>Emitted with the active layer index (view state, no undo). Emitted when the auto-tile checkbox is toggled (canvas builds the ruleset).</extracomment>
        <translation>Capa %1</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="178"/>
        <location filename="../ui/tilemap_layer_panel.py" line="180"/>
        <location filename="../ui/tilemap_layer_panel.py" line="276"/>
        <source>Add Layer</source>
        <translation>Añadir capa</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="190"/>
        <location filename="../ui/tilemap_layer_panel.py" line="192"/>
        <location filename="../ui/tilemap_layer_panel.py" line="277"/>
        <source>Remove Layer</source>
        <translation>Eliminar capa</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="224"/>
        <location filename="../ui/tilemap_layer_panel.py" line="226"/>
        <source>Reorder Layer</source>
        <translation>Reordenar capa</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="242"/>
        <source>Layer Visibility</source>
        <translation>Visibilidad de capa</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="244"/>
        <source>Toggle Layer Visibility</source>
        <translation>Alternar visibilidad de capa</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="270"/>
        <source>Tilemap layers panel</source>
        <translation>Panel de capas del mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="271"/>
        <source>Layer actions</source>
        <translation>Acciones de capa</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="272"/>
        <source>Tilemap layers</source>
        <translation>Capas del mapa de tiles</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="274"/>
        <source>Ordered map layers; tick to show/hide, top layer first</source>
        <translation>Capas del mapa ordenadas; marca para mostrar/ocultar, capa superior primero</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="278"/>
        <source>Move Up</source>
        <translation>Subir</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="279"/>
        <source>Move Down</source>
        <translation>Bajar</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="280"/>
        <source>Auto-tile (Blob-47)</source>
        <translation>Auto-tile (Blob-47)</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="282"/>
        <source>Resolve tile edges automatically from neighbours</source>
        <translation>Resuelve los bordes de los tiles automáticamente según los vecinos</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="284"/>
        <source>Auto-tile toggle</source>
        <translation>Alternar auto-tile</translation>
    </message>
</context>
<context>
    <name>Tileset_Editor_Panel</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="316"/>
        <source>Tile %1</source>
        <translation>Tile %1</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="367"/>
        <location filename="../ui/tileset_editor_panel.py" line="369"/>
        <source>Re-slice Tileset</source>
        <translation>Volver a cortar el tileset</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="386"/>
        <location filename="../ui/tileset_editor_panel.py" line="388"/>
        <source>Edit Tile</source>
        <translation>Editar tile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="415"/>
        <source>Tileset editor panel</source>
        <translation>Panel del editor de tileset</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="216"/>
        <location filename="../ui/tileset_editor_panel.py" line="416"/>
        <location filename="../ui/tileset_editor_panel.py" line="424"/>
        <source>Tile width</source>
        <extracomment>Emitted with the selected tile&apos;s **global gid** (view state, no undo).</extracomment>
        <translation>Ancho de tile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="219"/>
        <location filename="../ui/tileset_editor_panel.py" line="417"/>
        <location filename="../ui/tileset_editor_panel.py" line="425"/>
        <source>Tile height</source>
        <translation>Alto de tile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="418"/>
        <source>Margin</source>
        <translation>Margen</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="419"/>
        <source>Spacing</source>
        <translation>Espaciado</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="420"/>
        <location filename="../ui/tileset_editor_panel.py" line="421"/>
        <location filename="../ui/tileset_editor_panel.py" line="422"/>
        <location filename="../ui/tileset_editor_panel.py" line="423"/>
        <source> px</source>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="222"/>
        <location filename="../ui/tileset_editor_panel.py" line="426"/>
        <source>Tile margin</source>
        <translation>Margen de tile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="225"/>
        <location filename="../ui/tileset_editor_panel.py" line="427"/>
        <source>Tile spacing</source>
        <translation>Espaciado de tile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="428"/>
        <source>Re-slice</source>
        <translation>Volver a cortar</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="429"/>
        <source>Re-slice the source image</source>
        <translation>Vuelve a cortar la imagen de origen</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="430"/>
        <source>Re-slice tileset</source>
        <translation>Volver a cortar el tileset</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="431"/>
        <source>Edit Tile…</source>
        <translation>Editar tile…</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="432"/>
        <source>Paint into the selected source tile</source>
        <translation>Pinta en el tile de origen seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="433"/>
        <source>Edit selected tile</source>
        <translation>Editar el tile seleccionado</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="434"/>
        <source>Tileset tiles</source>
        <translation>Tiles del tileset</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="436"/>
        <source>Sliced tiles in row-major order; click to select for stamping</source>
        <translation>Tiles cortados en orden por filas; haz clic para seleccionar y sellar</translation>
    </message>
</context>
<context>
    <name>Timelapse_Controls</name>
    <message numerus="yes">
        <location filename="../ui/timelapse_controls.py" line="422"/>
        <source>%n frame(s) were dropped because the edits they recorded were undone and replaced.</source>
        <extracomment>A Document -&gt; RGBA ``ndarray`` renderer (e.g. wrapping ``blend.composite_stack``), injected by the host rather than authored here (S11 — no domain/composite maths in this widget). Returns the currently active document for a bound ``QUndoStack`` (S11 — this widget reads it, it never derives it). Emitted with the current frame count after a record / load / reset. Emitted with one reconstructed RGBA ``ndarray`` per displayed frame, whichever substrate served it (in-session or a loaded payload). Emitted ``True`` while document edits must be refused (playing or paused mid-sequence), ``False`` once playback stops or completes. Emitted with the number of frames dropped by a discarded branch (REQ-P9-UI-021), once per occurrence. The per-recording identity half (REQ-P9-LOGIC-022; plan §10.1) — one :mod:`secrets` draw, minted once per recording (here, and again on every :meth:`reset`). Never an adversarial-strength token (``TIMELAPSE_RECORDING_ID_BYTES``&apos; own docstring): it only has to not collide, and it is paid for on every frame. The monotone ordinal half — only ever ``+= 1``, never reset, rewound, or derived from ``len(session.frames)``: every rewrite path rebuilds the frames *tuple*, and a counter living inside it would rewind with it (plan §10.1). The id of the document this session was recorded against (REQ-P9-UI-020) — ``None`` until the first frame is recorded. The id of the document currently bound (the active tab). stack index -&gt; the FrameId minted the last time that index was reached forward (plan §10.2). On every forward index change to ``i``, every entry with key ``&gt;= i`` is evicted **before** any new mint — an event-time observation, exact because nothing has been reused yet, never a resolution-time inference from a count. Its value set is both the surviving-identity set passed to :func:`~pixelart_creator.logic.timelapse.drop_discarded` and the live HISTORY extent handed to :class:`~pixelart_creator.ui.timelapse_playback.History_Document_Provider`. Set by :meth:`load_reopened_recording` when reviewing a loaded, cross-session payload rather than the live in-session history. ``True`` only while this widget is itself driving the bound ``QUndoStack`` through a provider (a historical render or a save&apos;s payload snapshot pass) — every ``indexChanged`` this causes is this widget&apos;s own bookkeeping, never a user commit, and must not be recorded or misread as a discard boundary (D1 fix; see ``_render_all``/``_build_payload_tables``).</extracomment>
        <translation>
            <numerusform>%n fotograma se descartó porque las ediciones que registraba se deshicieron y se sustituyeron.</numerusform>
            <numerusform>%n fotogramas se descartaron porque las ediciones que registraban se deshicieron y se sustituyeron.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="464"/>
        <source>Recording stopped</source>
        <translation>Grabación detenida</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="466"/>
        <source>Recording was stopped because it reached the maximum number of frames. The frames already recorded are kept. Save this recording, or reset it to start a new one.</source>
        <translation>La grabación se detuvo porque alcanzó el número máximo de fotogramas. Los fotogramas ya grabados se conservan. Guarda esta grabación, o reiníciala para empezar una nueva.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="538"/>
        <source>Different document</source>
        <translation>Documento diferente</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="540"/>
        <source>This recording belongs to a different document. Switch to that document to resume it, or reset first to start a new one here.</source>
        <translation>Esta grabación pertenece a un documento diferente. Cambia a ese documento para reanudarla, o reinicia primero para empezar una nueva aquí.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="557"/>
        <source>Save Timelapse</source>
        <translation>Guardar timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="559"/>
        <location filename="../ui/timelapse_controls.py" line="673"/>
        <source>Timelapse (*.pixtimelapse)</source>
        <translation>Timelapse (*.pixtimelapse)</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="568"/>
        <location filename="../ui/timelapse_controls.py" line="586"/>
        <location filename="../ui/timelapse_controls.py" line="603"/>
        <source>Save failed</source>
        <translation>Error al guardar</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="570"/>
        <source>This recording could not be saved because a recorded state could not be reconstructed from the current history.</source>
        <translation>Esta grabación no se pudo guardar porque no fue posible reconstruir un estado grabado a partir del historial actual.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="588"/>
        <source>This recording was not saved because it is too large. Nothing was written. Discard some frames and try again.</source>
        <translation>Esta grabación no se guardó porque es demasiado grande. No se escribió nada. Descarta algunos fotogramas e inténtalo de nuevo.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="605"/>
        <source>This recording could not be saved. The file could not be written, or its data could not be encoded.</source>
        <translation>Esta grabación no se pudo guardar. El archivo no se pudo escribir, o sus datos no se pudieron codificar.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="671"/>
        <source>Open Timelapse</source>
        <translation>Abrir timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="688"/>
        <source>Open failed</source>
        <translation>Error al abrir</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="690"/>
        <source>This file could not be opened. It is missing, unreadable, or not a valid timelapse recording.</source>
        <translation>Este archivo no se pudo abrir. Falta, no se puede leer, o no es una grabación de timelapse válida.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="749"/>
        <source>There is nothing recorded to play yet.</source>
        <translation>Todavía no hay nada grabado para reproducir.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="756"/>
        <source>This recording belongs to a different document. Switch to that document to play it.</source>
        <translation>Esta grabación pertenece a un documento diferente. Cambia a ese documento para reproducirla.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="761"/>
        <source>Playback is not available yet.</source>
        <translation>La reproducción todavía no está disponible.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="777"/>
        <source>This recording was saved in a form that cannot be replayed.</source>
        <translation>Esta grabación se guardó en un formato que no se puede reproducir.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="782"/>
        <source>This recording&apos;s saved data is incomplete and cannot be fully replayed.</source>
        <translation>Los datos guardados de esta grabación están incompletos y no se pueden reproducir por completo.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="788"/>
        <source>Some recorded frames are no longer reachable in the current history and cannot be played.</source>
        <translation>Algunos fotogramas grabados ya no son accesibles en el historial actual y no se pueden reproducir.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="793"/>
        <source>This recording&apos;s history no longer matches; it cannot be replayed from here.</source>
        <translation>El historial de esta grabación ya no coincide; no se puede reproducir desde aquí.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="807"/>
        <source>This recording was saved in an earlier form whose frames cannot be told apart reliably, so it will not be replayed.</source>
        <translation>Esta grabación se guardó en un formato anterior cuyos fotogramas no se pueden distinguir de forma fiable, por lo que no se reproducirá.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="810"/>
        <source>This recording cannot be played.</source>
        <translation>Esta grabación no se puede reproducir.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="839"/>
        <source>Cannot play</source>
        <translation>No se puede reproducir</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="847"/>
        <source>Playback failed</source>
        <translation>Error de reproducción</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="848"/>
        <source>This recording could not be replayed.</source>
        <translation>Esta grabación no se pudo reproducir.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="935"/>
        <source>Frame {0} of {1}</source>
        <translation>Fotograma {0} de {1}</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="940"/>
        <source>Recorded frames: {0}</source>
        <translation>Fotogramas grabados: {0}</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="972"/>
        <source>Stop Recording</source>
        <translation>Detener grabación</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="972"/>
        <source>Record</source>
        <translation>Grabar</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="977"/>
        <source>Pause</source>
        <translation>Pausar</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="977"/>
        <source>Play</source>
        <translation>Reproducir</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="981"/>
        <source>Timelapse</source>
        <translation>Timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="982"/>
        <source>Timelapse controls</source>
        <translation>Controles de timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="983"/>
        <source>Save…</source>
        <translation>Guardar…</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="984"/>
        <source>Open…</source>
        <translation>Abrir…</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="985"/>
        <source>Stop</source>
        <translation>Detener</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="986"/>
        <source>Timelapse position</source>
        <translation>Posición del timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="987"/>
        <source>Playback speed</source>
        <translation>Velocidad de reproducción</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="992"/>
        <source>Playback refusal reason</source>
        <translation>Motivo del rechazo de reproducción</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="993"/>
        <source>Recorded frame count</source>
        <translation>Número de fotogramas grabados</translation>
    </message>
</context>
<context>
    <name>Timelapse_Frame_View</name>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="52"/>
        <location filename="../ui/timelapse_frame_view.py" line="116"/>
        <source>Reopened recording — not the current document</source>
        <translation>Grabación reabierta — no es el documento actual</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="110"/>
        <source>Reopened Recording</source>
        <translation>Grabación reabierta</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="111"/>
        <source>Reopened timelapse recording</source>
        <translation>Grabación de timelapse reabierta</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="113"/>
        <source>Reopened recording — this is not your current document</source>
        <translation>Grabación reabierta — este no es tu documento actual</translation>
    </message>
</context>
<context>
    <name>Timeline_Grid_View</name>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="555"/>
        <source>Toggle Cel Visibility</source>
        <extracomment>Emitted with the frame index a selection (of any kind) settled on (REQ-P5-UI-023). Pushes no command. Emitted with the ``layer_id`` a cell/row-header selection settled on (REQ-P5-UI-023). Pushes no command. Emitted with the frame index the cursor is scrubbing over during a body drag away from any occupied cell (REQ-P5-UI-025). Pushes no command. Emitted when a Ctrl+right-click removal was refused because the target document has only one frame left (D-22). ``Document._ensure_frame_removable`` is the single, unconditional owner of that invariant; this view asks the bound document itself (``len(document.frames)``) rather than keeping a second, independently-maintained notion of &quot;removable&quot; — so the two can never drift apart. Pushes no command; the gesture stays inert.</extracomment>
        <translation>Alternar visibilidad de celda</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="591"/>
        <source>Create Cel Here</source>
        <translation>Crear celda aquí</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="593"/>
        <source>Create a new drawing on this track in this frame</source>
        <translation>Crear un nuevo dibujo en esta pista en este fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="611"/>
        <source>Create Cel</source>
        <translation>Crear celda</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="644"/>
        <source>Remove Frame</source>
        <translation>Eliminar fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="668"/>
        <source>Reorder Frame</source>
        <translation>Reordenar fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="818"/>
        <source>Copy Cel</source>
        <translation>Copiar celda</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="826"/>
        <source>Move Cel</source>
        <translation>Mover celda</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="853"/>
        <source>Timeline grid</source>
        <translation>Cuadrícula de la línea de tiempo</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="856"/>
        <source>Frames as columns, layer tracks as rows; drag a header to reorder, drag a drawing to move it (hold Ctrl to copy), or open the context menu on an empty cell to create a cel there</source>
        <translation>Fotogramas como columnas, pistas de capa como filas; arrastra un encabezado para reordenar, arrastra un dibujo para moverlo (mantén Ctrl para copiar), o abre el menú contextual en una celda vacía para crear una celda ahí</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="861"/>
        <source>Frame headers</source>
        <translation>Encabezados de fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="862"/>
        <source>Layer track headers</source>
        <translation>Encabezados de pista de capa</translation>
    </message>
</context>
<context>
    <name>Timeline_Panel</name>
    <message>
        <location filename="../ui/timeline_panel.py" line="272"/>
        <source>Frame %1</source>
        <extracomment>Index of the strip surface in the cell-surface QStackedWidget — the default (REQ-P5-UI-020: &quot;the strip is the default&quot;). Not a domain constant (Article II does not reach a fixed widget-stack index); grouped with the other presentation literals this module already carries. Longest edge (px) of a cached per-cell frame thumbnail. Presentation-only sizing (like ``_SWATCH_PX`` in ``main_window``); the resident buffer is never culled — only the small display thumbnail is downscaled (F7). Ceiling for the per-frame duration spin box (ms). A presentation-only cap on how high the editor spins (like ``_THUMBNAIL_EDGE``); it is NOT a domain tuning value — the authoritative bound is the logic ``make_set_frame_duration_command`` positive-int guard, which alone validates. Emitted with the frame index a click/keyboard selected (settled — onion on). Emitted with the frame index the cursor is dragging over (scrub — onion off). Emitted with a ``layer_id`` the grid cell surface&apos;s selection settled on (REQ-P5-UI-023, BF-G1); the strip has no layer axis and never emits this.</extracomment>
        <translation>Fotograma %1</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="280"/>
        <source>Frame %1 — %2 ms</source>
        <translation>Fotograma %1 — %2 ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="394"/>
        <location filename="../ui/timeline_panel.py" line="513"/>
        <source>Add Frame</source>
        <translation>Añadir fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="406"/>
        <location filename="../ui/timeline_panel.py" line="515"/>
        <source>Remove Frame</source>
        <translation>Eliminar fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="417"/>
        <location filename="../ui/timeline_panel.py" line="517"/>
        <source>Duplicate Frame</source>
        <translation>Duplicar fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="450"/>
        <source>Reorder Frame</source>
        <translation>Reordenar fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="466"/>
        <source>Set Frame Duration</source>
        <translation>Establecer duración del fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="507"/>
        <source>Timeline panel</source>
        <translation>Panel de línea de tiempo</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="508"/>
        <source>Frame actions</source>
        <translation>Acciones de fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="509"/>
        <source>Frame strip</source>
        <translation>Tira de fotogramas</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="511"/>
        <source>Frames left-to-right in playback order; drag to reorder</source>
        <translation>Fotogramas de izquierda a derecha en orden de reproducción; arrastre para reordenar</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="514"/>
        <source>Insert a new frame after the active one</source>
        <translation>Insertar un nuevo fotograma después del activo</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="516"/>
        <source>Delete the active frame</source>
        <translation>Eliminar el fotograma activo</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="519"/>
        <source>Insert a copy of the active frame after it</source>
        <translation>Insertar una copia del fotograma activo a continuación</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="521"/>
        <source>Grid View</source>
        <translation>Vista de cuadrícula</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="523"/>
        <source>Show frames and layer tracks as a grid instead of a strip</source>
        <translation>Muestra fotogramas y pistas de capa como una cuadrícula en lugar de una tira</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="525"/>
        <source>Timeline cell surface</source>
        <translation>Superficie de celdas de la línea de tiempo</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="526"/>
        <source>Duration</source>
        <translation>Duración</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="528"/>
        <source> ms</source>
        <translation> ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="529"/>
        <source>Frame duration</source>
        <translation>Duración del fotograma</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="531"/>
        <source>Display time of the active frame, in milliseconds</source>
        <translation>Tiempo de visualización del fotograma activo, en milisegundos</translation>
    </message>
</context>
<context>
    <name>User_Guide_Dialog</name>
    <message>
        <location filename="../ui/user_guide.py" line="301"/>
        <source>Could not load this topic:

%1</source>
        <extracomment>Qt roles that would resolve an anchor to the network or the local filesystem; the viewer is fully offline (REQ-UG-UI-007), so a click on such a link is a no-op — it is never fetched. The UserRole slot carrying a topic id on a ToC / results item. The in-guide markdown image URL the mark resolves against. Another agent&apos;s guide content writes ``![PixelArt Creator](pac-logo.png)`` under this EXACT string -- it is the contract between the content and this widget&apos;s document-resource registration; do not change it here. A reader callable: a bundle-relative content ref -&gt; the Markdown text. Defaults to the defensive ``data`` reader; injectable so headless tests can substitute a fixture reader without touching the real bundle. A locale provider: returns the active UI locale code (e.g. ``&quot;en&quot;``). Defaults to the guide&apos;s default locale; the main window passes the LanguageManager&apos;s ``current_language`` so content follows the UI language (REQ-UG-UI-011 / CL-3).</extracomment>
        <translation>No se pudo cargar este tema:

%1</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="346"/>
        <source>The User Guide content could not be loaded:

%1</source>
        <translation>No se pudo cargar el contenido de la Guía del usuario:

%1</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="349"/>
        <source>The User Guide content could not be loaded.</source>
        <translation>No se pudo cargar el contenido de la Guía del usuario.</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="441"/>
        <location filename="../ui/user_guide.py" line="442"/>
        <source>User Guide</source>
        <translation>Guía del usuario</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="443"/>
        <source>Search the guide…</source>
        <translation>Buscar en la guía…</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="444"/>
        <source>Search the guide</source>
        <translation>Buscar en la guía</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="445"/>
        <source>Guide contents</source>
        <translation>Índice de la guía</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="446"/>
        <source>Search results</source>
        <translation>Resultados de la búsqueda</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="447"/>
        <source>Guide content</source>
        <translation>Contenido de la guía</translation>
    </message>
</context>
<context>
    <name>Vanishing_Point_Dialog</name>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="152"/>
        <source>1-point</source>
        <translation>1 punto</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="153"/>
        <source>2-point</source>
        <translation>2 puntos</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="154"/>
        <source>3-point</source>
        <translation>3 puntos</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="158"/>
        <source>Configure Perspective</source>
        <translation>Configurar perspectiva</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="159"/>
        <source>Vanishing points</source>
        <translation>Puntos de fuga</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="160"/>
        <source>Horizon Y</source>
        <translation>Y del horizonte</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="161"/>
        <source>Vanishing-point mode</source>
        <translation>Modo de punto de fuga</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="162"/>
        <source>Horizon Y position</source>
        <translation>Posición Y del horizonte</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="166"/>
        <source>Vanishing point {n}</source>
        <translation>Punto de fuga {n}</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="168"/>
        <source>X</source>
        <translation>X</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="169"/>
        <source>Y</source>
        <translation>Y</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="171"/>
        <source>Vanishing point {n} X</source>
        <translation>X del punto de fuga {n}</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="174"/>
        <source>Vanishing point {n} Y</source>
        <translation>Y del punto de fuga {n}</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="178"/>
        <source>OK</source>
        <translation>Aceptar</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="181"/>
        <source>Cancel</source>
        <translation>Cancelar</translation>
    </message>
</context>
<context>
    <name>Version_History_Browser</name>
    <message>
        <location filename="../ui/version_history_browser.py" line="169"/>
        <source>Select a version to restore.</source>
        <extracomment>Column order of the version tree (presentation-only layout, not a domain value). QSS role-selector property (never a hard-coded colour): the status label carries the computed :class:`SyncState` as a dynamic property so BOTH themes can style it by role (``QLabel[syncState=&quot;diverged&quot;]`` etc.) — see D-13.</extracomment>
        <translation>Selecciona una versión para restaurar.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="173"/>
        <source>Version %1 — %2 bytes (created marker %3).</source>
        <translation>Versión %1 — %2 bytes (marcador de creación %3).</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="184"/>
        <source>Up to date with the cloud.</source>
        <translation>Al día con la nube.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="186"/>
        <source>Local changes have not been saved to the cloud yet.</source>
        <translation>Los cambios locales aún no se han guardado en la nube.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="188"/>
        <source>A newer version exists in the cloud.</source>
        <translation>Hay una versión más reciente en la nube.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="189"/>
        <source>Local and cloud history have diverged.</source>
        <translation>El historial local y el de la nube han divergido.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="194"/>
        <source>Cloud Version History</source>
        <translation>Historial de versiones en la nube</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="197"/>
        <source>Prior cloud saves, oldest first. Restoring opens the chosen version in a new tab — your current work is not overwritten.</source>
        <translation>Guardados anteriores en la nube, del más antiguo al más reciente. Al restaurar se abre la versión elegida en una nueva pestaña; tu trabajo actual no se sobrescribe.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="202"/>
        <source>Cloud sync status</source>
        <translation>Estado de sincronización con la nube</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="205"/>
        <source>Version</source>
        <translation>Versión</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="206"/>
        <source>Marker</source>
        <translation>Marcador</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="207"/>
        <source>Size (bytes)</source>
        <translation>Tamaño (bytes)</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="208"/>
        <source>Pinned</source>
        <translation>Fijada</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="209"/>
        <source>Parent</source>
        <translation>Padre</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="212"/>
        <source>Yes</source>
        <translation>Sí</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="213"/>
        <source>No</source>
        <translation>No</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="221"/>
        <source>Restore</source>
        <translation>Restaurar</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="222"/>
        <source>Cloud version list</source>
        <translation>Lista de versiones en la nube</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="223"/>
        <source>Restore selected version</source>
        <translation>Restaurar la versión seleccionada</translation>
    </message>
</context>
<context>
    <name>_Node_Row</name>
    <message>
        <location filename="../ui/layer_panel.py" line="180"/>
        <source>Ref</source>
        <extracomment>A node address in the frame tree — the logic index path used by the document layer ops (top-level index, then indices descending through nested groups). A fully-shown mask (opaque alpha everywhere ⇒ no modulation, LOGIC-012).</extracomment>
        <translation>Ref</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="182"/>
        <source>Mask</source>
        <translation>Másc</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="184"/>
        <source>Smart</source>
        <translation>Intel</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="196"/>
        <source>Toggle Visibility</source>
        <translation>Alternar visibilidad</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="205"/>
        <source>Toggle Lock</source>
        <translation>Alternar bloqueo</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="217"/>
        <source>Set Blend Mode</source>
        <translation>Establecer modo de fusión</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="251"/>
        <source>Set Opacity</source>
        <translation>Establecer opacidad</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="257"/>
        <source>V</source>
        <translation>V</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="258"/>
        <source>Toggle layer visibility</source>
        <translation>Alternar visibilidad de la capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="259"/>
        <source>Visibility</source>
        <translation>Visibilidad</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="260"/>
        <source>L</source>
        <translation>B</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="261"/>
        <source>Lock layer against painting</source>
        <translation>Bloquear la capa contra el pintado</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="262"/>
        <source>Lock</source>
        <translation>Bloqueo</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="263"/>
        <source>Layer name</source>
        <translation>Nombre de la capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="264"/>
        <source>Layer flags</source>
        <translation>Indicadores de la capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="265"/>
        <source>Layer opacity</source>
        <translation>Opacidad de la capa</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="266"/>
        <source>Opacity</source>
        <translation>Opacidad</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="267"/>
        <location filename="../ui/layer_panel.py" line="268"/>
        <source>Blend mode</source>
        <translation>Modo de fusión</translation>
    </message>
</context>
<context>
    <name>_Project_Prefs_Menu</name>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="71"/>
        <source>Ask me every time</source>
        <extracomment>A domain wider than this renders as a nested exclusive submenu rather than a single checkable action (plan §3.4) — a plain boolean-shaped preference (ask / suppressed) keeps the shipped single-checkbox rendering. Menu-rendering strings share one translation context with the class below so :func:`value_label_for` — a free function, exported for a future renderer (phase-6&apos;s settings dialog) — is caught by the same ``tr()`` extraction pass as the class&apos;s own strings.</extracomment>
        <translation>Preguntarme cada vez</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="74"/>
        <source>Always pick up the library change</source>
        <translation>Adoptar siempre el cambio de la biblioteca</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="77"/>
        <source>Always keep the referenced version</source>
        <translation>Mantener siempre la versión referenciada</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="83"/>
        <source>Set to: %1</source>
        <translation>Establecido en: %1</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="218"/>
        <source>Confirm before overwriting a cel</source>
        <extracomment>The provider the caller supplies: returns the active document, or ``None`` when no document is open.</extracomment>
        <translation>Confirmar antes de sobrescribir una celda</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="220"/>
        <source>When a referenced library asset changes</source>
        <translation>Cuando cambia un recurso de biblioteca referenciado</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="221"/>
        <source>Confirm: %1</source>
        <translation>Confirmar: %1</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="224"/>
        <location filename="../ui/project_prefs_actions.py" line="225"/>
        <source>Project confirmations</source>
        <translation>Confirmaciones del proyecto</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="230"/>
        <source>Restore this confirmation so it asks again</source>
        <translation>Restaurar esta confirmación para que vuelva a preguntar</translation>
    </message>
</context>
<context>
    <name>_Tile_Pixel_Editor</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="111"/>
        <location filename="../ui/tileset_editor_panel.py" line="155"/>
        <source>Tile pixel editor</source>
        <extracomment>Thumbnail edge (px) for a tile swatch in the grid list (presentation-only, not a domain tuning value — cf. Palette_Panel&apos;s swatch size). On-screen pixel size of one tile pixel in the tile editor dialog.</extracomment>
        <translation>Editor de píxeles de tile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="113"/>
        <location filename="../ui/tileset_editor_panel.py" line="157"/>
        <source>Left-click to paint, right-click to erase</source>
        <translation>Clic izquierdo para pintar, clic derecho para borrar</translation>
    </message>
</context>
<context>
    <name>_Track_Table_Model</name>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="239"/>
        <source>Frame %1</source>
        <extracomment>Longest edge (px) of a cached per-cell thumbnail. Mirrors ``timeline_panel._THUMBNAIL_EDGE`` exactly (visual consistency between the two cell surfaces the toggle swaps between); a presentation-only sizing literal, not a domain tuning value (Article II does not reach it, like its strip twin). Custom data roles carried on every cell, alongside the standard Qt roles.</extracomment>
        <translation>Fotograma %1</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="256"/>
        <source>%1, %2</source>
        <translation>%1, %2</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="261"/>
        <source>%1, %2 — empty</source>
        <translation>%1, %2 — vacía</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="268"/>
        <source>%1, track %2</source>
        <translation>%1, pista %2</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="273"/>
        <source>%1, track %2, empty</source>
        <translation>%1, pista %2, vacía</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="278"/>
        <source>Occupied cell</source>
        <translation>Celda ocupada</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="278"/>
        <source>Empty cell</source>
        <translation>Celda vacía</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="326"/>
        <source>%1
%2 ms</source>
        <translation>%1
%2 ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="332"/>
        <source>Frame %1, %2 milliseconds</source>
        <translation>Fotograma %1, %2 milisegundos</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="343"/>
        <source>Track %1</source>
        <translation>Pista %1</translation>
    </message>
</context>
<context>
    <name>_WheelPad</name>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="308"/>
        <source>Colour wheel</source>
        <extracomment>Hue at the top of the circle, in degrees (achromatic fallback keeps this hue). Number of conical-gradient stops sweeping the hue circle (six primaries + wrap). Edge of a harmony/preview swatch button, px (presentation-only sizing). Minimum wheel diameter, px (presentation-only sizing). Marker radius drawn at the current hue/saturation, px. Keyboard nudge steps for the wheel (hue degrees / saturation fraction). Single left click — paint this swatch&apos;s colour, leave the wheel alone. Double left click / Space / Return — adopt this swatch&apos;s colour into the wheel, paint nothing. Emitted with ``(hue_degrees, saturation)`` when the user picks on the wheel.</extracomment>
        <translation>Rueda de color</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="311"/>
        <source>Hue and saturation wheel; use the arrow keys or the numeric fields to pick a colour without a mouse</source>
        <translation>Rueda de tono y saturación; use las teclas de flecha o los campos numéricos para elegir un color sin ratón</translation>
    </message>
</context>
<context>
    <name>export</name>
    <message>
        <location filename="../ui/export_actions.py" line="98"/>
        <location filename="../ui/export_actions.py" line="109"/>
        <source>Export</source>
        <extracomment>The source document that was submitted for export (never the exported file&apos;s own bytes — REQ-P11-UI-014). The export settings as used for this run (JSON-scalar values only — bounded by ``logic.constants.MAX_METADATA_BYTES`` at ingress).</extracomment>
        <translation>Exportar</translation>
    </message>
    <message>
        <location filename="../ui/export_actions.py" line="99"/>
        <source>Open a document before exporting.</source>
        <translation>Abre un documento antes de exportar.</translation>
    </message>
    <message>
        <location filename="../ui/export_actions.py" line="110"/>
        <source>Choose a destination path before exporting.</source>
        <translation>Elige una ruta de destino antes de exportar.</translation>
    </message>
</context>
<context>
    <name>theme</name>
    <message>
        <location filename="../ui/theme.py" line="160"/>
        <source>unknown theme: %1</source>
        <extracomment>Cross-OS UI-font fallback chain (REQ-P13-UI-001). Defined **once, by role** here (never per-widget): the UI names no specific family (the QSS below carries no ``font-family`` and the app sets no :class:`QFont`), so each OS already resolves its own default system UI font. This map is the belt-and- braces guard for the single-OS families that a platform default *reports* as its name (e.g. Windows &quot;Segoe UI&quot;, macOS &quot;.AppleSystemUIFont&quot;/&quot;Helvetica Neue&quot;): if such a family is ever requested on an OS that lacks it (a cross-OS project theme, a future stylesheet, a canvas glyph label), Qt substitutes the first available entry instead of rendering ``.notdef`` boxes. Where the named family exists (its native OS) Qt uses it directly, so this changes nothing on the platform that owns the font — it only adds a resolvable fallback on the others. The tail generics are resolved by the Qt platform plugin to a present family on every OS. Role palette per theme. Every role key exists in both themes (QT-D1) so no widget ever needs a single-theme literal.</extracomment>
        <translation>tema desconocido: %1</translation>
    </message>
</context>
<context>
    <name>tilemap_io</name>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="38"/>
        <source>Export Tiled Map</source>
        <extracomment>Tiled JSON file filter (format identifier, not a translated string).</extracomment>
        <translation>Exportar mapa de Tiled</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="49"/>
        <source>Export failed</source>
        <translation>Error de exportación</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="50"/>
        <source>Could not export the map: %1</source>
        <translation>No se pudo exportar el mapa: %1</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="67"/>
        <source>Import Tiled Map</source>
        <translation>Importar mapa de Tiled</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="78"/>
        <source>Import failed</source>
        <translation>Error de importación</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="79"/>
        <source>Could not import the map: %1</source>
        <translation>No se pudo importar el mapa: %1</translation>
    </message>
</context>
<context>
    <name>tool_icons</name>
    <message>
        <location filename="../ui/tool_icons.py" line="127"/>
        <source>unknown tool glyph id: %1</source>
        <extracomment>The importable package the glyph bundle is shipped inside (package data), matching ``data/guide_content.py``&apos;s ``BUNDLE_PACKAGE`` convention. Package-data subdirectory holding the eleven glyphs, relative to :data:`_ICON_PACKAGE` (``pixelart_creator/icons/tools/``). SVG file extension for a glyph resource. Square render size, in device-independent pixels, for the rasterised glyph and its tinted pixmap. One named constant, referenced everywhere a size is needed in this module (S12) — this module owns no other size. The theme role whose colour tints every glyph (`ui/theme.py`&apos;s role palette; `text` exists in both themes, QT-D1). The eleven shipped `tool_id`s, one per authored glyph stem (`pixelart_creator/icons/tools/&lt;id&gt;.svg`) — the exact `tool_id` class attributes carried by `ui/tools/*.py` (pencil, eraser, fill, line, picker, rectangle, ellipse, select_rect, select_lasso, select_wand, dither). Kept as a literal tuple here (not imported from each tool class) so this module has no dependency on the tool-strategy classes themselves — only on the glyph *ids* they happen to share.</extracomment>
        <translation>id de glifo de herramienta desconocido: %1</translation>
    </message>
    <message>
        <location filename="../ui/tool_icons.py" line="134"/>
        <source>missing tool glyph asset for: %1</source>
        <translation>falta el recurso de glifo de herramienta para: %1</translation>
    </message>
    <message>
        <location filename="../ui/tool_icons.py" line="152"/>
        <source>unknown theme: %1</source>
        <translation>tema desconocido: %1</translation>
    </message>
</context>
<context>
    <name>tools</name>
    <message>
        <location filename="../ui/tools/pencil.py" line="49"/>
        <source>Pencil</source>
        <translation>Lápiz</translation>
    </message>
    <message>
        <location filename="../ui/tools/eraser.py" line="25"/>
        <source>Eraser</source>
        <extracomment>Indexed buffers erase to palette index 0 (the buffer&apos;s own default value).</extracomment>
        <translation>Borrador</translation>
    </message>
    <message>
        <location filename="../ui/tools/fill.py" line="23"/>
        <source>Fill</source>
        <translation>Relleno</translation>
    </message>
    <message>
        <location filename="../ui/tools/line.py" line="29"/>
        <source>Line</source>
        <translation>Línea</translation>
    </message>
    <message>
        <location filename="../ui/tools/ellipse_tool.py" line="29"/>
        <source>Ellipse</source>
        <translation>Elipse</translation>
    </message>
    <message>
        <source>Move Selection</source>
        <extracomment>A wand click always (re)selects; it never starts a floating move. Colour tolerance; default exact match (CL-1). Set by the shell control.</extracomment>
        <translation type="vanished">Mover selección</translation>
    </message>
    <message>
        <location filename="../ui/tools/rectangle_tool.py" line="29"/>
        <source>Rectangle</source>
        <translation>Rectángulo</translation>
    </message>
    <message>
        <location filename="../ui/tools/lasso_tool.py" line="30"/>
        <source>Lasso Select</source>
        <translation>Selección de lazo</translation>
    </message>
    <message>
        <location filename="../ui/tools/magic_wand_tool.py" line="36"/>
        <source>Magic Wand</source>
        <extracomment>A wand click always (re)selects; it never starts a floating move. Colour tolerance; default exact match (CL-1). Set by the shell control.</extracomment>
        <translation>Varita mágica</translation>
    </message>
    <message>
        <location filename="../ui/tools/rect_select_tool.py" line="23"/>
        <source>Rectangle Select</source>
        <translation>Selección rectangular</translation>
    </message>
    <message>
        <location filename="../ui/tools/dither_tool.py" line="65"/>
        <source>Dither</source>
        <extracomment>The two dither modes accepted by ``logic.dither.make_dither_command``.</extracomment>
        <translation>Tramado</translation>
    </message>
</context>
<context>
    <name>widget</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="59"/>
        <source>Loop</source>
        <translation>Bucle</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="60"/>
        <source>Once</source>
        <translation>Una vez</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="61"/>
        <source>Ping-Pong</source>
        <translation>Ping-Pong</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="62"/>
        <source>Reverse</source>
        <translation>Inversa</translation>
    </message>
</context>
</TS>
