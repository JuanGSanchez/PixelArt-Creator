<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="fr" sourcelanguage="en">
<context>
    <name>About_Dialog</name>
    <message>
        <location filename="../ui/about_dialog.py" line="280"/>
        <source>About PixelArt Creator</source>
        <extracomment>The dialog&apos;s fixed links, in the order shown (REQ-AV-UI-005).</extracomment>
        <translation>À propos de PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="281"/>
        <source>About PixelArt Creator dialog</source>
        <translation>Boîte de dialogue À propos de PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="283"/>
        <source>PixelArt Creator icon</source>
        <translation>Icône de PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="284"/>
        <source>Application name</source>
        <translation>Nom de l&apos;application</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="285"/>
        <source>Version:</source>
        <translation>Version :</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="286"/>
        <source>Application version</source>
        <translation>Version de l&apos;application</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="287"/>
        <source>Licence:</source>
        <translation>Licence :</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="288"/>
        <source>Licence name</source>
        <translation>Nom de la licence</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="289"/>
        <source>Environment:</source>
        <translation>Environnement :</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="290"/>
        <source>Environment summary</source>
        <translation>Résumé de l&apos;environnement</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="294"/>
        <source>Repository</source>
        <translation>Dépôt</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="295"/>
        <source>Documentation</source>
        <translation>Documentation</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="296"/>
        <source>Releases</source>
        <translation>Versions publiées</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="307"/>
        <source>&amp;Copy</source>
        <translation>Copier</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="308"/>
        <source>Copy environment summary</source>
        <translation>Copier le résumé de l&apos;environnement</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="309"/>
        <source>C&amp;lose</source>
        <translation>Fermer</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="310"/>
        <source>Close the About dialog</source>
        <translation>Fermer la boîte de dialogue À propos</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="314"/>
        <source>unknown</source>
        <translation>inconnu</translation>
    </message>
</context>
<context>
    <name>Asset_Library_Panel</name>
    <message>
        <location filename="../ui/asset_library_panel.py" line="162"/>
        <source>Broken reference</source>
        <extracomment>Emitted with the selected entry&apos;s ``asset_id`` (``&quot;&quot;`` when cleared). The active filter driven by the search panel (empty = full catalog).</extracomment>
        <translation>Référence rompue</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="186"/>
        <source>Sprite</source>
        <translation>Sprite</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="187"/>
        <source>Animation</source>
        <translation>Animation</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="188"/>
        <source>Tileset</source>
        <translation>Tileset</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="189"/>
        <source>Tilemap</source>
        <translation>Tilemap</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="190"/>
        <source>Palette</source>
        <translation>Palette</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="195"/>
        <source>Asset library</source>
        <translation>Bibliothèque de ressources</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Name</source>
        <translation>Nom</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Kind</source>
        <translation>Type</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Tags</source>
        <translation>Étiquettes</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Status</source>
        <translation>Statut</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="199"/>
        <source>Catalog assets</source>
        <translation>Ressources du catalogue</translation>
    </message>
</context>
<context>
    <name>Asset_Library_Session</name>
    <message>
        <location filename="../ui/asset_library_actions.py" line="506"/>
        <source>Import asset artifact</source>
        <extracomment>Emitted after any change to the catalog (add / remove / tag do-undo) so the bound panels re-read and repaint. No payload — panels pull the fresh catalog. Emitted after the dependency graph is replaced so the dependency-graph view and the passive break surface re-read and repaint. No payload. Emitted after a registration action commits — carries the :class:`RegistrationOutcome` (REQ-P11-UI-017). Emitted when a registration action cannot commit — carries a translatable message; the catalog, store and revision history are all left unchanged (REQ-P11-UI-017). Emitted when the user cancels the registration prompt — cancelling is not a failure (REQ-P11-UI-017; RP-4). Emitted after a successful registration&apos;s derived dependency edges are computed (ruling P11-R6, REQ-P11-LOGIC-010 / REQ-P11-UI-018) — carries the **accumulated** edge set (this session&apos;s current graph edges plus the newly derived ones), because the bound consumer (:meth:`~pixelart_creator.ui.dependency_graph_view.Dependency_Graph_View. show_edges`) *replaces* the graph it is handed rather than merging into it. This session never calls :meth:`set_graph` itself and never imports the view — ``show_edges`` alone decides whether the accumulated set is accepted (and, on a closed cycle, rejected passively, the prior graph kept) — see ``main_window.py``&apos;s connection of this signal. Emitted after a single library artifact (``.pixasset``) is imported and merged + committed into the already-open library (ruling P11-R5, REQ-P11-UI-015/-016) — carries the imported ``Tuple[AssetDescriptor, ...]``. Emitted when a library-artifact import cannot commit — a translatable message; the catalog and store are unchanged. Emitted when the user cancels the &quot;Import asset artifact&quot; file dialog. Emitted after a chosen catalog subset is written to a library artifact file (REQ-P11-UI-016) — carries the destination path as ``str``. Emitted when a library-subset export cannot complete — a translatable message; no file is written. Emitted when the user cancels the &quot;Export asset artifact&quot; file dialog. Emitted after a project + its whole reference set is written to a ``.pixbundle`` file (the shipped :func:`~pixelart_creator.data.asset_export.export_project_bundle`, unchanged) — carries the destination path as ``str``. Emitted when a project-bundle export cannot complete — a translatable message; no file is written. Emitted when the user cancels the &quot;Export project bundle&quot; file dialog. Emitted after a ``.pixbundle`` is reconstructed into a new project directory (the shipped :func:`~pixelart_creator.data.asset_export.import_project_bundle`, unchanged) — carries the ``(Document, AssetCatalog)`` tuple. This session&apos;s own catalog is untouched: the bundle reconstructs a **new** project, never merging into the open library (plan Section 3.7). Emitted when a project-bundle import cannot complete — a translatable message; ``target_dir`` is left exactly as it was (the shipped function&apos;s own atomic-move guarantee). Emitted when the user cancels the &quot;Import project bundle&quot; file dialog. The shared undo stack the tag commands push onto (REQ-P11-UI-002). The durable catalog root once bound (REQ-P11-DATA-008); ``None`` until :meth:`bind_root` is called, so an unbound session stays purely in-memory. The content-addressable store the registration actions write blobs through, once bound; ``None`` until :meth:`bind_content_store`. The revision store the registration actions record through, once bound; ``None`` until :meth:`bind_revision_store`.</extracomment>
        <translation>Importer un fichier de ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="507"/>
        <location filename="../ui/asset_library_actions.py" line="570"/>
        <source>Asset artifact (*%1)</source>
        <translation>Fichier de ressource (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="518"/>
        <source>&quot;%1&quot; is a project bundle, not a single asset. Use &quot;Import project bundle…&quot; instead.</source>
        <translation>« %1 » est un paquet de projet, et non une ressource isolée. Utilisez plutôt « Importer un paquet de projet… ».</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="523"/>
        <location filename="../ui/asset_library_actions.py" line="723"/>
        <source>Import asset</source>
        <translation>Importer une ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="569"/>
        <source>Export asset artifact</source>
        <translation>Exporter un fichier de ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="624"/>
        <location filename="../ui/asset_library_actions.py" line="741"/>
        <source>Export project bundle</source>
        <translation>Exporter un paquet de projet</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="625"/>
        <location filename="../ui/asset_library_actions.py" line="676"/>
        <source>Project bundle (*%1)</source>
        <translation>Paquet de projet (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="675"/>
        <location filename="../ui/asset_library_actions.py" line="752"/>
        <source>Import project bundle</source>
        <translation>Importer un paquet de projet</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="720"/>
        <source>Could not import the asset: %1</source>
        <translation>Impossible d&apos;importer la ressource : %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="727"/>
        <source>Could not export the asset: %1</source>
        <translation>Impossible d&apos;exporter la ressource : %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="730"/>
        <source>Export asset</source>
        <translation>Exporter une ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="736"/>
        <source>Could not export the project bundle: %1</source>
        <translation>Impossible d&apos;exporter le paquet de projet : %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="747"/>
        <source>Could not import the project bundle: %1</source>
        <translation>Impossible d&apos;importer le paquet de projet : %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="817"/>
        <source>There is no active selection to register.</source>
        <translation>Il n&apos;y a aucune sélection active à inscrire.</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="1136"/>
        <source>Could not register the asset: %1</source>
        <translation>Impossible d&apos;inscrire la ressource : %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="1139"/>
        <source>Asset registration</source>
        <translation>Inscription de la ressource</translation>
    </message>
</context>
<context>
    <name>Asset_Register_Dialog</name>
    <message numerus="yes">
        <location filename="../ui/asset_register_dialog.py" line="165"/>
        <source>Too many tags: %n given, %2 allowed.</source>
        <extracomment>Combo order = the five shipped kinds, in the vocabulary&apos;s own declaration order (``logic/asset_catalog.AssetKind`` — RP-1&apos;s &quot;five shipped kinds&quot;).</extracomment>
        <translation>
            <numerusform>Trop d&apos;étiquettes : %n fournie, %2 autorisées.</numerusform>
            <numerusform>Trop d&apos;étiquettes : %n fournies, %2 autorisées.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_register_dialog.py" line="170"/>
        <source>Tag &quot;%1&quot; is too long (%n bytes allowed).</source>
        <translation>
            <numerusform>L&apos;étiquette « %1 » est trop longue (%n octet autorisé).</numerusform>
            <numerusform>L&apos;étiquette « %1 » est trop longue (%n octets autorisés).</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="178"/>
        <source>Enter a name for this asset.</source>
        <translation>Saisissez un nom pour cette ressource.</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="190"/>
        <source>Register Asset</source>
        <translation>Inscrire une ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="191"/>
        <source>Asset registration prompt</source>
        <translation>Invite d&apos;inscription de la ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="193"/>
        <source>Name</source>
        <translation>Nom</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="194"/>
        <source>Asset display name</source>
        <translation>Nom d&apos;affichage de la ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="195"/>
        <source>Display name</source>
        <translation>Nom d&apos;affichage</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="197"/>
        <source>Kind</source>
        <translation>Type</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="198"/>
        <source>Asset kind</source>
        <translation>Type de ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="199"/>
        <source>Sprite</source>
        <translation>Sprite</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="200"/>
        <source>Animation</source>
        <translation>Animation</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="201"/>
        <source>Tileset</source>
        <translation>Tileset</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="202"/>
        <source>Tilemap</source>
        <translation>Tilemap</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="203"/>
        <source>Palette</source>
        <translation>Palette</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="205"/>
        <source>Tags</source>
        <translation>Étiquettes</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="206"/>
        <source>Asset tags, comma-separated</source>
        <translation>Étiquettes de la ressource, séparées par des virgules</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="207"/>
        <source>Optional tags, comma-separated</source>
        <translation>Étiquettes facultatives, séparées par des virgules</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="209"/>
        <source>Registration validation message</source>
        <translation>Message de validation de l&apos;inscription</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="213"/>
        <source>Register</source>
        <translation>Inscrire</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="214"/>
        <source>Register asset</source>
        <translation>Inscrire la ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="217"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="218"/>
        <source>Cancel registration</source>
        <translation>Annuler l&apos;inscription</translation>
    </message>
</context>
<context>
    <name>Asset_Reuse_Panel</name>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="249"/>
        <source>The selected asset is not available.</source>
        <extracomment>Columns of the in-project reference list (REQ-P11-UI-021 indicators). The selected asset row&apos;s ``asset_id`` is stashed on the name column (both trees). Emitted with ``(asset_id, project)`` after a successful reference. Each open project&apos;s real, durable reference set (REQ-P11-UI-021), bound through :meth:`set_project_reference_set` or created empty by :meth:`add_project`. Never a predicate&apos;s own scratch state. In-project reference list — the resolve-state / shared-state indicators (REQ-P11-UI-021), over the *current* project&apos;s real reference set.</extracomment>
        <translation>La ressource sélectionnée n&apos;est pas disponible.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="256"/>
        <source>Shared content for %1 is not available.</source>
        <translation>Le contenu partagé pour %1 n&apos;est pas disponible.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="271"/>
        <source>%1 is already referenced in %2.</source>
        <translation>%1 est déjà référencé dans %2.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="277"/>
        <source>Referenced %1 into %2.</source>
        <translation>%1 a été référencé dans %2.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="340"/>
        <location filename="../ui/asset_reuse_panel.py" line="403"/>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <location filename="../ui/asset_reuse_panel.py" line="479"/>
        <source>Shared</source>
        <translation>Partagé</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="352"/>
        <location filename="../ui/asset_reuse_panel.py" line="420"/>
        <source>Referenced by another open project</source>
        <translation>Référencé par un autre projet ouvert</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="399"/>
        <source>In library</source>
        <translation>Dans la bibliothèque</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="401"/>
        <source>Not found in library</source>
        <translation>Introuvable dans la bibliothèque</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="416"/>
        <source>This reference could not be found in the local library.</source>
        <translation>Cette référence est introuvable dans la bibliothèque locale.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_reuse_panel.py" line="426"/>
        <source>%n unresolved reference(s) in this project.</source>
        <translation>
            <numerusform>%n référence non résolue dans ce projet.</numerusform>
            <numerusform>%n références non résolues dans ce projet.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="431"/>
        <source>All references resolve in the local library.</source>
        <translation>Toutes les références sont résolues dans la bibliothèque locale.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="447"/>
        <source>Sprite</source>
        <translation>Sprite</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="448"/>
        <source>Animation</source>
        <translation>Animation</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="449"/>
        <source>Tileset</source>
        <translation>Tileset</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="450"/>
        <source>Tilemap</source>
        <translation>Tilemap</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="451"/>
        <source>Palette</source>
        <translation>Palette</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="457"/>
        <source>Cross-project reuse</source>
        <translation>Réutilisation entre projets</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="458"/>
        <source>Project:</source>
        <translation>Projet :</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="459"/>
        <source>Target project</source>
        <translation>Projet cible</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="460"/>
        <location filename="../ui/asset_reuse_panel.py" line="461"/>
        <source>New project name</source>
        <translation>Nom du nouveau projet</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="462"/>
        <source>Add Project</source>
        <translation>Ajouter un projet</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="463"/>
        <source>Add a project</source>
        <translation>Ajouter un projet</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <location filename="../ui/asset_reuse_panel.py" line="476"/>
        <source>Name</source>
        <translation>Nom</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <location filename="../ui/asset_reuse_panel.py" line="477"/>
        <source>Kind</source>
        <translation>Type</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <source>Projects</source>
        <translation>Projets</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="467"/>
        <source>Shared assets</source>
        <translation>Ressources partagées</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="468"/>
        <source>Reference into Project</source>
        <translation>Référencer dans le projet</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <source>Reference the selected asset into the project</source>
        <translation>Référencer la ressource sélectionnée dans le projet</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="472"/>
        <source>Reuse status</source>
        <translation>État de réutilisation</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="473"/>
        <source>References in this project:</source>
        <translation>Références dans ce projet :</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="478"/>
        <source>Resolve state</source>
        <translation>État de résolution</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="483"/>
        <source>References in the current project</source>
        <translation>Références dans le projet actuel</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="485"/>
        <source>Missing reference count</source>
        <translation>Nombre de références manquantes</translation>
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
        <translation>Animation</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="135"/>
        <source>Tileset</source>
        <translation>Tileset</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="136"/>
        <source>Tilemap</source>
        <translation>Tilemap</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="137"/>
        <source>Palette</source>
        <translation>Palette</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="142"/>
        <source>Asset search and filter</source>
        <translation>Recherche et filtre de ressources</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="143"/>
        <source>Name:</source>
        <translation>Nom :</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="144"/>
        <location filename="../ui/asset_search_panel.py" line="145"/>
        <source>Search by name</source>
        <translation>Rechercher par nom</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="146"/>
        <source>Tags:</source>
        <translation>Étiquettes :</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="147"/>
        <source>Filter by tags (comma-separated)</source>
        <translation>Filtrer par étiquettes (séparées par des virgules)</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="148"/>
        <source>Filter by tags</source>
        <translation>Filtrer par étiquettes</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="149"/>
        <source>Kind:</source>
        <translation>Type :</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="150"/>
        <source>Filter by kind</source>
        <translation>Filtrer par type</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="151"/>
        <source>All kinds</source>
        <translation>Tous les types</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="154"/>
        <source>Clear</source>
        <translation>Effacer</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="155"/>
        <source>Clear the search and filters</source>
        <translation>Effacer la recherche et les filtres</translation>
    </message>
</context>
<context>
    <name>Asset_Tagging_Panel</name>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="121"/>
        <location filename="../ui/asset_tagging_panel.py" line="145"/>
        <source>Tagging</source>
        <extracomment>The asset whose tags are being edited (``&quot;&quot;`` when none is selected).</extracomment>
        <translation>Étiquetage</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="126"/>
        <source>Add tag &quot;%1&quot;</source>
        <translation>Ajouter l&apos;étiquette « %1 »</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="150"/>
        <source>Remove tag &quot;%1&quot;</source>
        <translation>Supprimer l&apos;étiquette « %1 »</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="185"/>
        <source>No asset selected</source>
        <translation>Aucune ressource sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="188"/>
        <source>Tags for: %1</source>
        <translation>Étiquettes pour : %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="192"/>
        <source>Asset tagging</source>
        <translation>Étiquetage des ressources</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="193"/>
        <source>Asset tags</source>
        <translation>Étiquettes de ressources</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="194"/>
        <location filename="../ui/asset_tagging_panel.py" line="195"/>
        <source>New tag</source>
        <translation>Nouvelle étiquette</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="196"/>
        <source>Add Tag</source>
        <translation>Ajouter une étiquette</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="197"/>
        <source>Add tag to asset</source>
        <translation>Ajouter une étiquette à la ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="198"/>
        <source>Remove Tag</source>
        <translation>Supprimer l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="199"/>
        <source>Remove selected tag</source>
        <translation>Supprimer l&apos;étiquette sélectionnée</translation>
    </message>
</context>
<context>
    <name>Asset_Update_Prompt_Dialog</name>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="491"/>
        <source>Library Asset Updated</source>
        <extracomment>This dialog&apos;s own outcome vocabulary — distinct from the *persisted* three-value preference domain (``&quot;ask&quot;`` / ``&quot;always_pick_up&quot;`` / ``&quot;always_keep_referenced&quot;``, declared in ``logic/asset_references.ASSET_LIBRARY_EDIT``): an outcome is what THIS prompt resolved to for ONE edit; the preference is what to do about FUTURE edits without asking. **Promoted aliases (ADR-0062, ruling P11-R13 — same &quot;one definition of a control, aliases kept so no call site moves&quot; move ruling P11-R11 made for ``data/asset_catalog_io.py``&apos;s ``_safe_asset_id`` / ``_resolve_within``, applied here in the other direction):** the canonical outcome domain now lives in the logic layer, :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_PICK_UP` / :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_KEEP`, at byte-identical values — these two names are retained, unchanged, as aliases so every existing reference in this module and its callers still resolves without moving. The two non-default members of ``ASSET_LIBRARY_EDIT.domain`` this prompt writes through :func:`~pixelart_creator.logic.project_prefs.with_value` (the registered seam validates membership; nothing here re-derives the domain). One session-memory entry key: ``(asset_id, edit_token)``. ``edit_token`` is ``None`` when the caller has no content-hash identity to hand yet (see :meth:`Asset_Update_Prompt_Dialog.decide`) — two ``None``-token calls with the same ``asset_id`` are therefore treated as the SAME edit, which is the exact, disclosed limit of this session memory absent a real per-edit identity (module docstring boundary note). Emitted once a button is clicked, before the dialog closes: ``(outcome, dont_ask_again)``. For a caller driving the dialog non-modally (``open()``); :meth:`decide` does not need it. **Per-edit session memory** (extended by plan §3.11 (2b)): &quot;the same edit does not ask again&quot; for :meth:`decide` (``REQ-P11-UI-022``&apos;s own acceptance clause), scoped to one project&apos;s session bucket so a different project (:data:`ProjectPrefs`, ``SC-P11-UI-023-3``) is never affected by another project&apos;s session memory. Keyed by ``id(prefs)`` -&gt; ``(prefs, {edit_key: outcome})`` when no ``project_key`` is supplied (today&apos;s byte-for-byte behaviour — the snapshot itself is held strongly alongside its id so a *live* entry&apos;s id can never be reused by an unrelated, later ``ProjectPrefs`` object, an ``is`` check on lookup is the defensive second line); keyed by the caller-supplied ``project_key`` (a ``str``) instead when one is given — the production route (``ui/main_window.py``, plan §3.11 (2b)), because ``document.prefs`` is *replaced* on any confirmation-preference toggle (``ui/project_prefs_actions.py:165/175``), which would silently orphan an ``id(prefs)``-keyed bucket. This dict itself is still in-memory, per-process runtime state — it is never itself written to disk, and it is never written through ``logic/project_prefs.py`` (that seam is reserved for the &quot;Don&apos;t ask again&quot; preference, ``REQ-P11-UI-023``, a materially different, explicit, durable choice). **Corrected (ADR-0062, ruling P11-R13):** this bucket is no longer the *only* record of an unticked decision — it can be **hydrated** at the start of a session from the durable, per-edit ledger (:class:`~pixelart_creator.logic.asset_edit_decisions.AssetEditDecisions`) via :meth:`prime_session`, and every fresh decision made through :meth:`decide` is handed to that method&apos;s optional ``on_decided`` callback so the caller can persist it (the write-ahead journal / the project-file save) — this module performs no I/O of its own; it only calls out. Disclosed cost, unchanged: a decided ``ProjectPrefs`` snapshot (or a live ``project_key`` bucket) is retained for the life of the process; call :meth:`forget_session` when a project closes to release it.</extracomment>
        <translation>Ressource de la bibliothèque mise à jour</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="492"/>
        <source>Library asset updated confirmation</source>
        <translation>Confirmation de mise à jour de la ressource de la bibliothèque</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="493"/>
        <source>this asset</source>
        <translation>cette ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="496"/>
        <source>The library asset &quot;%1&quot; has changed since your project last referenced it. Pick up the change, or keep the version your project already references?</source>
        <translation>La ressource de la bibliothèque « %1 » a changé depuis la dernière fois que votre projet l&apos;a référencée. Récupérer la modification, ou conserver la version déjà référencée par votre projet ?</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="501"/>
        <source>Library edit notice</source>
        <translation>Avis de modification de la bibliothèque</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="502"/>
        <source>Don&apos;t ask again</source>
        <translation>Ne plus demander</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="504"/>
        <source>Remember this choice for future edits of this asset</source>
        <translation>Mémoriser ce choix pour les prochaines modifications de cette ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="506"/>
        <source>Pick Up the Change</source>
        <translation>Récupérer la modification</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="508"/>
        <source>Pick up the library asset&apos;s change</source>
        <translation>Récupérer la modification de la ressource de la bibliothèque</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="510"/>
        <source>Keep the Referenced Version</source>
        <translation>Conserver la version référencée</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="512"/>
        <source>Keep the version this project already references</source>
        <translation>Conserver la version déjà référencée par ce projet</translation>
    </message>
</context>
<context>
    <name>Asset_Version_Browser</name>
    <message>
        <location filename="../ui/asset_version_browser.py" line="193"/>
        <source>%1 (current)</source>
        <extracomment>The selected row&apos;s revision ``content_hash`` is stashed on the order column. How many leading characters of a content hash the browser shows (the full hash is kept on the tooltip / item data — this is display abbreviation only, not identity). Emitted with the new head&apos;s ``content_hash`` after a successful restore (so a caller / test can react); no payload semantics beyond the reinstated head hash. The asset whose revisions are shown (``&quot;&quot;`` when none is selected).</extracomment>
        <translation>%1 (actuelle)</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="194"/>
        <location filename="../ui/asset_version_browser.py" line="233"/>
        <source>(unknown)</source>
        <translation>(inconnu)</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="231"/>
        <location filename="../ui/asset_version_browser.py" line="251"/>
        <location filename="../ui/asset_version_browser.py" line="261"/>
        <source>Version history</source>
        <translation>Historique des versions</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_version_browser.py" line="235"/>
        <source>Revision %1 — %n bytes, marker %3, author %4</source>
        <translation>
            <numerusform>Révision %1 — %n octet, marqueur %3, auteur %4</numerusform>
            <numerusform>Révision %1 — %n octets, marqueur %3, auteur %4</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="313"/>
        <location filename="../ui/asset_version_browser.py" line="318"/>
        <source>Revisions of: %1</source>
        <translation>Révisions de : %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="321"/>
        <source>No asset selected</source>
        <translation>Aucune ressource sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="325"/>
        <source>Asset version browser</source>
        <translation>Navigateur de versions de ressources</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="327"/>
        <source>#</source>
        <translation>#</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="327"/>
        <source>Created</source>
        <translation>Création</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="327"/>
        <source>Author</source>
        <translation>Auteur</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="327"/>
        <source>Content</source>
        <translation>Contenu</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="329"/>
        <source>Asset revisions</source>
        <translation>Révisions de la ressource</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="330"/>
        <source>Revision details</source>
        <translation>Détails de la révision</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="331"/>
        <source>Inspect</source>
        <translation>Examiner</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="332"/>
        <source>Inspect selected revision</source>
        <translation>Examiner la révision sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="333"/>
        <source>Restore</source>
        <translation>Restaurer</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="335"/>
        <source>Restore selected revision as a new head</source>
        <translation>Restaurer la révision sélectionnée comme nouvelle révision de tête</translation>
    </message>
</context>
<context>
    <name>Assistant_Dock</name>
    <message>
        <location filename="../ui/assistant_dock.py" line="159"/>
        <source>No AI provider is configured. Use Configure… to set an endpoint and API key.</source>
        <extracomment>Provider of the active document (``None`` when no document tab is open). Provider of the current chat backend (a configured ``data/llm`` adapter, or ``None`` when the user has not configured a provider). Probed fresh on each send so a config change takes effect immediately; ``ui/`` never sees a provider/HTTP type. ``(commands, label)`` — the turn&apos;s ordered, unapplied reversible commands and a translatable undo label; the host wraps them in one ``AssistantCommand``. How many transcript messages have already been rendered (render the tail).</extracomment>
        <translation>Aucun fournisseur d&apos;IA n&apos;est configuré. Utilisez Configurer… pour définir un point de terminaison et une clé d&apos;API.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="167"/>
        <source>Open a document before chatting with the assistant.</source>
        <translation>Ouvrez un document avant de discuter avec l&apos;assistant.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="184"/>
        <source>Assistant edit</source>
        <translation>Modification de l&apos;assistant</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="188"/>
        <source>Assistant error: {0}</source>
        <translation>Erreur de l&apos;assistant : {0}</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="206"/>
        <source>Confirm assistant action</source>
        <translation>Confirmer l&apos;action de l&apos;assistant</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="209"/>
        <source>The assistant wants to run &quot;{0}&quot;, which cannot be reliably undone. Allow it?</source>
        <translation>L&apos;assistant veut exécuter « {0} », ce qui ne peut pas être annulé de façon fiable. L&apos;autoriser ?</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="226"/>
        <source>Provider configuration saved.</source>
        <translation>Configuration du fournisseur enregistrée.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="235"/>
        <source>Working…</source>
        <translation>Traitement en cours…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="248"/>
        <source>You</source>
        <translation>Vous</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="251"/>
        <source>Assistant</source>
        <translation>Assistant</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="252"/>
        <source>(taking an action…)</source>
        <translation>(action en cours…)</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="254"/>
        <source>Action</source>
        <translation>Action</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="284"/>
        <source>AI Assistant</source>
        <translation>Assistant IA</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="285"/>
        <source>AI assistant chat</source>
        <translation>Discussion avec l&apos;assistant IA</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="286"/>
        <source>Assistant conversation</source>
        <translation>Conversation avec l&apos;assistant</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="287"/>
        <source>Message to the assistant</source>
        <translation>Message à l&apos;assistant</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="288"/>
        <source>Ask the assistant to edit…</source>
        <translation>Demandez à l&apos;assistant de modifier…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="289"/>
        <source>Send</source>
        <translation>Envoyer</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="290"/>
        <source>Send message</source>
        <translation>Envoyer le message</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="291"/>
        <source>Configure…</source>
        <translation>Configurer…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="292"/>
        <source>Configure AI provider</source>
        <translation>Configurer le fournisseur d&apos;IA</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="293"/>
        <source>Assistant working indicator</source>
        <translation>Indicateur d&apos;activité de l&apos;assistant</translation>
    </message>
</context>
<context>
    <name>Batch_Export_Panel</name>
    <message>
        <location filename="../ui/batch_export_panel.py" line="159"/>
        <source>%1 — done</source>
        <extracomment>Optional provider returning the document to export against (the active tab).</extracomment>
        <translation>%1 — terminé</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="163"/>
        <source>%1 — failed: %2</source>
        <translation>%1 — échec : %2</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="184"/>
        <source>Add Target…</source>
        <translation>Ajouter une cible…</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="185"/>
        <source>Remove</source>
        <translation>Supprimer</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="186"/>
        <source>Export All</source>
        <translation>Tout exporter</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="187"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="188"/>
        <source>Batch export</source>
        <translation>Exportation par lot</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="189"/>
        <source>Batch export targets</source>
        <translation>Cibles d&apos;exportation par lot</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="190"/>
        <source>Batch export progress</source>
        <translation>Progression de l&apos;exportation par lot</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="191"/>
        <source>Add export target</source>
        <translation>Ajouter une cible d&apos;exportation</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="192"/>
        <source>Remove export target</source>
        <translation>Supprimer la cible d&apos;exportation</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="193"/>
        <source>Export all targets</source>
        <translation>Exporter toutes les cibles</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="194"/>
        <source>Cancel batch export</source>
        <translation>Annuler l&apos;exportation par lot</translation>
    </message>
</context>
<context>
    <name>Batch_Recolour_Panel</name>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="168"/>
        <source>Running…</source>
        <extracomment>Combo indices for the mapping mode (module-local UI enumeration). Upper bound for the index spin boxes — the widest palette a buffer can address (a display range for the spin control, not a domain tuning value). ``(ops, label)`` — the host should dispatch the ``batch_recolour`` op on the worker as one undoable grouped command (REQ-P8-UI-006/-009). Each pair is ``(src, dst)`` — ints for index mode, RGBA tuples for colour mode. Kept parallel to the visible list.</extracomment>
        <translation>Exécution en cours…</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="170"/>
        <source>Done</source>
        <translation>Terminé</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="171"/>
        <source>Idle</source>
        <translation>En attente</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="209"/>
        <source>Pick a colour</source>
        <translation>Choisir une couleur</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="218"/>
        <source>From: %1</source>
        <translation>De : %1</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="221"/>
        <source>To: %1</source>
        <translation>Vers : %1</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="234"/>
        <source>%1 → %2</source>
        <translation>%1 → %2</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="264"/>
        <source>Batch Recolour</source>
        <translation>Recoloration par lot</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="285"/>
        <source>Mapping:</source>
        <translation>Correspondance :</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="286"/>
        <source>Index remap</source>
        <translation>Remappage d&apos;indices</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="287"/>
        <source>Colour remap</source>
        <translation>Remappage de couleurs</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="288"/>
        <source>Frame:</source>
        <translation>Image :</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="289"/>
        <source>Add Pair</source>
        <translation>Ajouter une paire</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="290"/>
        <source>Remove</source>
        <translation>Supprimer</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="291"/>
        <source>Apply Batch Recolour</source>
        <translation>Appliquer la recoloration par lot</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="293"/>
        <source>Batch recolour</source>
        <translation>Recoloration par lot</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="294"/>
        <source>Recolour mapping mode</source>
        <translation>Mode de correspondance de recoloration</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="295"/>
        <source>Target frame index</source>
        <translation>Indice de l&apos;image cible</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="296"/>
        <source>Source palette index</source>
        <translation>Indice de palette source</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="297"/>
        <source>Destination palette index</source>
        <translation>Indice de palette de destination</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="298"/>
        <source>Pick source colour</source>
        <translation>Choisir la couleur source</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="299"/>
        <source>Pick destination colour</source>
        <translation>Choisir la couleur de destination</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="300"/>
        <source>Recolour mapping pairs</source>
        <translation>Paires de correspondance de recoloration</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="301"/>
        <source>Add a recolour pair</source>
        <translation>Ajouter une paire de recoloration</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="302"/>
        <source>Remove the selected pair</source>
        <translation>Supprimer la paire sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="303"/>
        <source>Apply the batch recolour</source>
        <translation>Appliquer la recoloration par lot</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="304"/>
        <source>Progress</source>
        <translation>Progression</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="305"/>
        <source>Batch recolour progress</source>
        <translation>Progression de la recoloration par lot</translation>
    </message>
</context>
<context>
    <name>Branch_Diff_Dialog</name>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="179"/>
        <source>Metadata changes</source>
        <extracomment>The four op-tier groups, fixed display order (``REQ-P10-UI-016``) — matches ``branch_diff._CLASS_RANK``&apos;s declaration order (metadata, layer_attr, layer_order, raster; ``convergence.py:228``). Emitted with ``source_name`` when the user activates *Continue to merge*. This view performs **no** merge itself (``REQ-P10-UI-018``) — the caller runs the unchanged ``Branching_Session.merge_to_mainline`` (the same shipped path the panel&apos;s own Merge button uses, ``REQ-P10-UI-019``).</extracomment>
        <translation>Modifications des métadonnées</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="180"/>
        <source>Layer attribute changes</source>
        <translation>Modifications des attributs de calque</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="181"/>
        <source>Layer order changes</source>
        <translation>Modifications de l&apos;ordre des calques</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="182"/>
        <source>Raster (pixel) changes</source>
        <translation>Modifications raster (pixels)</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="194"/>
        <source>Metadata &apos;{key}&apos; set to &apos;{value}&apos;</source>
        <translation>Métadonnée « {key} » définie sur « {value} »</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="198"/>
        <source>Frame {frame}, layer {layer}: {attr} = {value}</source>
        <translation>Image {frame}, calque {layer} : {attr} = {value}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="202"/>
        <source>Frame {frame}: layer order changed</source>
        <translation>Image {frame} : ordre des calques modifié</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="207"/>
        <source>Frame {frame}, layer {layer}: tile ({tile_x}, {tile_y})</source>
        <translation>Image {frame}, calque {layer} : tuile ({tile_x}, {tile_y})</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="242"/>
        <source>Frame {frame}, layer {layer}: ({x}, {y}) {width}×{height}</source>
        <translation>Image {frame}, calque {layer} : ({x}, {y}) {width}×{height}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="269"/>
        <source>Diff: &apos;{source}&apos; vs &apos;{target}&apos;</source>
        <translation>Différences : « {source} » par rapport à « {target} »</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="273"/>
        <source>Branch diff</source>
        <translation>Différences entre branches</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="276"/>
        <source>Comparing branch &apos;{source}&apos; (source) against &apos;{target}&apos; (target). This is a snapshot taken now — the merge has not happened yet.</source>
        <translation>Comparaison de la branche « {source} » (source) avec « {target} » (cible). Il s&apos;agit d&apos;un instantané pris à l&apos;instant : la fusion n&apos;a pas encore eu lieu.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="281"/>
        <source>Diff basis</source>
        <translation>Base de comparaison</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="286"/>
        <source>Checked: the recorded changes account for everything on this branch.</source>
        <translation>Vérifié : les modifications consignées expliquent tout ce qui figure sur cette branche.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="293"/>
        <source>Warning: some changes on this branch are not recorded and will not be merged. {detail}</source>
        <translation>Attention : certaines modifications de cette branche ne sont pas consignées et ne seront pas fusionnées. {detail}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="297"/>
        <source>Supervision result</source>
        <translation>Résultat de la supervision</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="300"/>
        <source>States whether the recorded operation log explains every change on this branch&apos;s live document.</source>
        <translation>Indique si le journal des opérations consignées explique toutes les modifications du document actif de cette branche.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="307"/>
        <source>This branch has no changes to merge.</source>
        <translation>Cette branche ne contient aucune modification à fusionner.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="319"/>
        <source>No changes.</source>
        <translation>Aucune modification.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="321"/>
        <source>%n change(s).</source>
        <translation>
            <numerusform>%n modification.</numerusform>
            <numerusform>%n modifications.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="323"/>
        <source>{title} list</source>
        <translation>Liste : {title}</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="325"/>
        <source>%n entries.</source>
        <translation>
            <numerusform>%n entrée.</numerusform>
            <numerusform>%n entrées.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="327"/>
        <source>Affected regions</source>
        <translation>Régions concernées</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="330"/>
        <source>Each region is reported at the whole {tile}×{tile} pixel tile granularity — a one-pixel change still covers a full tile here.</source>
        <translation>Chaque région est signalée à la granularité d&apos;une tuile entière de {tile}×{tile} pixels : une modification d&apos;un seul pixel couvre ici une tuile entière.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="335"/>
        <source>Affected regions list</source>
        <translation>Liste des régions concernées</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="337"/>
        <source>%n regions.</source>
        <translation>
            <numerusform>%n région.</numerusform>
            <numerusform>%n régions.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="342"/>
        <source>%n operation(s) total, across %2 distinct target(s).</source>
        <translation>
            <numerusform>%n opération au total, sur %2 cible(s) distincte(s).</numerusform>
            <numerusform>%n opérations au total, sur %2 cible(s) distincte(s).</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="347"/>
        <source>Divergence total</source>
        <translation>Total des divergences</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="349"/>
        <source>Continue to Merge</source>
        <translation>Passer à la fusion</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="350"/>
        <source>Continue to merge</source>
        <translation>Passer à la fusion</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="353"/>
        <source>Performs the same conflict-free merge as the branching panel&apos;s Merge control.</source>
        <translation>Effectue la même fusion sans conflit que la commande Fusionner du panneau des branches.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="357"/>
        <location filename="../ui/branch_diff_dialog.py" line="358"/>
        <source>Close</source>
        <translation>Fermer</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="360"/>
        <source>Closes this view without merging or changing anything.</source>
        <translation>Ferme cette vue sans fusionner ni rien modifier.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="372"/>
        <source>frames {frames}</source>
        <translation>images {frames}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="378"/>
        <source>layers {layers}</source>
        <translation>calques {layers}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="386"/>
        <source>attributes {attrs}</source>
        <translation>attributs {attrs}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="395"/>
        <source>metadata keys {keys}</source>
        <translation>clés de métadonnées {keys}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="401"/>
        <source>tiles {tiles}</source>
        <translation>tuiles {tiles}</translation>
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
        <translation>Branche</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="364"/>
        <source>Open a project first.</source>
        <translation>Ouvrez d&apos;abord un projet.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="368"/>
        <location filename="../ui/branching_panel.py" line="480"/>
        <source>New Branch</source>
        <translation>Nouvelle branche</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="368"/>
        <source>Branch name:</source>
        <translation>Nom de la branche :</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="397"/>
        <location filename="../ui/branching_panel.py" line="484"/>
        <source>Merge</source>
        <translation>Fusionner</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branching_panel.py" line="423"/>
        <source>Merged branch &apos;{name}&apos; (%n edits) into mainline — conflict-free.</source>
        <translation>
            <numerusform>Branche « {name} » (%n modification) fusionnée dans la branche principale — sans conflit.</numerusform>
            <numerusform>Branche « {name} » (%n modifications) fusionnée dans la branche principale — sans conflit.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="437"/>
        <source>{name} (active)</source>
        <translation>{name} (active)</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="456"/>
        <source>Open the pre-merge diff for the selected branch.</source>
        <translation>Ouvrez les différences avant fusion de la branche sélectionnée.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="460"/>
        <source>Disabled: open a project first.</source>
        <translation>Désactivé : ouvrez d&apos;abord un projet.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="465"/>
        <source>Disabled: select a feature branch, not mainline, to view its diff.</source>
        <translation>Désactivé : sélectionnez une branche secondaire, et non la branche principale, pour voir ses différences.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="472"/>
        <source>Branching</source>
        <translation>Branches</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="475"/>
        <source>Branch the project to edit a variation independently, then merge it back. Merges are conflict-free.</source>
        <translation>Créez une branche du projet pour modifier une variante de façon indépendante, puis fusionnez-la de nouveau dans le projet. Les fusions se font sans conflit.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="479"/>
        <source>Branches</source>
        <translation>Branches</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="481"/>
        <source>Create a new branch</source>
        <translation>Créer une nouvelle branche</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="482"/>
        <source>Switch</source>
        <translation>Basculer</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="483"/>
        <source>Switch to the selected branch</source>
        <translation>Basculer vers la branche sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="486"/>
        <source>Merge the selected branch into mainline</source>
        <translation>Fusionner la branche sélectionnée dans la branche principale</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="488"/>
        <source>Open Diff</source>
        <translation>Ouvrir les différences</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="490"/>
        <source>Open the pre-merge diff for the selected branch</source>
        <translation>Ouvrir les différences avant fusion de la branche sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="492"/>
        <source>Merge outcome</source>
        <translation>Résultat de la fusion</translation>
    </message>
</context>
<context>
    <name>Canvas_Size_Dialog</name>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="76"/>
        <source>Canvas Size</source>
        <translation>Taille du canvas</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="77"/>
        <source>Canvas size dialog</source>
        <translation>Boîte de dialogue Taille du canvas</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="78"/>
        <source>Target canvas width in pixels</source>
        <translation>Largeur cible du canvas en pixels</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="79"/>
        <source>Target canvas height in pixels</source>
        <translation>Hauteur cible du canvas en pixels</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="80"/>
        <source>Width (px)</source>
        <translation>Largeur (px)</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="81"/>
        <source>Height (px)</source>
        <translation>Hauteur (px)</translation>
    </message>
</context>
<context>
    <name>Canvas_View</name>
    <message>
        <location filename="../ui/canvas_view.py" line="318"/>
        <location filename="../ui/canvas_view.py" line="1443"/>
        <source>Canvas</source>
        <extracomment>Platform name reported by Qt when running without a windowing system. Emitted with the current zoom scale after any zoom change. Emitted with the buffer ``(x, y)`` when the canvas is right-clicked (seam). Emitted with the picked RGBA tuple when the colour-picker sets a colour. Emitted ``(is_active, is_copy)`` when a floating move/copy state changes (drives the shell&apos;s copy-mode status hint, REQ-P2-UI-032/-036). Emitted when a paint/mask-edit stroke is refused because the active layer is locked (D-05); the shell surfaces a &quot;layer is locked&quot; notice. Emitted when a left-click lands outside the active document&apos;s bounds (FIX 5, 2026-08-24 field defect): a click there must not arm a stroke, and must not fail silently — the shell surfaces a notice, following the ``lockedLayerEditRejected`` precedent exactly. Emitted when a paint/mask-edit is refused because the active layer is a REFERENCE or SMART layer (REQ-P3-UI-006 clause 5: non-editable targets are three classes, not two — locked, reference, and smart — and every one of them must be surfaced, never silently swallowed). Distinct from ``lockedLayerEditRejected`` so the shell can show the right notice; ``is_active_editable()`` returns ``False`` for all three classes, and this signal covers the two this view previously dropped on the floor. Emitted when a tool ran (the guards passed) but produced no pixel change — e.g. a flood fill on a region that already holds the picked colour (REQ-P1-UI-014), or a pencil placed on a pixel that already holds it — so no undo entry was pushed. An explicit, deliberate gesture (a completed colour-hub pick, REQ-P3-UI-006 clause 6) must never answer with silence even when it changed nothing. Emitted with the target frame index a ``Ctrl``+wheel / ``Ctrl``+middle- click frame gesture resolved to (REQ-IS-UI-010/-014); the shell routes it through the shipped frame-selection path. Pushes no command — frame navigation is view state (CL-13). Emitted when a confirmed ``Ctrl``+left-click (no floating move live) should add a frame after the active one (REQ-IS-UI-016); the shell builds and pushes the shipped undoable ``make_add_frame_command``. The three selection tools whose Shift/Alt modifiers stay the shipped add/subtract combine gesture (REQ-IS-UI-015) — Shift+drag pans for every other tool. Mirrors ``Main_Window._SELECTION_ENTRY_TOOL_IDS``. The wrapper every :class:`~pixelart_creator.ui.tools.base.ToolContext` is actually built with (see :class:`_RecordingUndoStack`); reads ``self._undo_stack``/``self._record_trace``/``self._recording_document`` live at each push, so `set_undo_stack`/`set_recording` need not rebuild it. A middle press awaiting the click/drag verdict (REQ-IS-UI-011): ``True`` between a middle press and either its release under ``CLICK_DRAG_THRESHOLD_PX`` (a click) or its promotion to ``_panning`` once the cursor travels past the threshold (a drag). A ``Ctrl``+left press awaiting the click/drag verdict (REQ-IS-UI-016, mirrors ``_middle_pending``): ``True`` between the press and either its release under ``CLICK_DRAG_THRESHOLD_PX`` (adds a frame) or its promotion to an ordinary paint/floating-move drag once the cursor travels past the threshold. The persisted Favourites model a plain wheel notch / unmodified middle click travel (REQ-IS-UI-008/-012); ``None`` until the shell binds one via :meth:`set_favourites_model`. The ``timestamp()`` of the RightButton press currently being dispatched through ``_menu_hook``, ``None`` for the keyboard (Menu key / Shift+F10) trigger. Consumed once via :meth:`pop_pending_right_press_timestamp` — deliberately NOT threaded as a third positional argument to ``_menu_hook`` itself, so the hook&apos;s signature (``Callable[[int, int], None]``) and every existing 2-argument hook (tests included) stay unchanged. Live mirror-centre override fed to ``logic.symmetry.mirror`` via each stroke&apos;s :class:`ToolContext` (D-28/CF-93); ``None`` keeps the shipped canvas-centre default. Fed by the shell&apos;s Symmetry_Panel. The guide currently being dragged (D-11), or ``None``. Raw (pre-snap) scene point at the start of the current stroke — the perspective direction-lock anchor (``logic.grids.perspective_snap``).</extracomment>
        <translation>Canvas</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="320"/>
        <location filename="../ui/canvas_view.py" line="1445"/>
        <source>Pixel canvas: left-click to paint, middle-drag to pan</source>
        <translation>Canvas de pixels : clic gauche pour peindre, glisser avec le bouton central pour se déplacer</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="1335"/>
        <source>Remove guide</source>
        <translation>Supprimer le repère</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="1346"/>
        <source>No canvas actions yet</source>
        <translation>Aucune action sur le canvas pour le moment</translation>
    </message>
</context>
<context>
    <name>Cel_Overwrite_Dialog</name>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="69"/>
        <source>Overwrite Existing Cel?</source>
        <translation>Écraser le cel existant ?</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="70"/>
        <source>Overwrite existing cel confirmation</source>
        <translation>Confirmation d&apos;écrasement du cel existant</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="73"/>
        <source>The destination cell already has a drawing on it. Proceeding replaces that drawing. This can be undone.</source>
        <translation>La cellule de destination contient déjà un dessin. Si vous continuez, il sera remplacé. Cette action peut être annulée.</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="77"/>
        <source>Overwrite warning</source>
        <translation>Avertissement d&apos;écrasement</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="78"/>
        <source>Don&apos;t ask again for this project</source>
        <translation>Ne plus demander pour ce projet</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="80"/>
        <source>Suppress this confirmation for the current project</source>
        <translation>Ne plus afficher cette confirmation pour le projet actuel</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="84"/>
        <location filename="../ui/cel_overwrite_dialog.py" line="85"/>
        <source>Overwrite</source>
        <translation>Écraser</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="88"/>
        <location filename="../ui/cel_overwrite_dialog.py" line="89"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
</context>
<context>
    <name>Colour_Cycling_Panel</name>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="152"/>
        <source>Colour Cycling</source>
        <extracomment>Milliseconds per cycling tick, derived from the tuning FPS (S12). Emitted with a list of display colours to preview (rotated palette). Emitted with ``(start, end, step)`` when Apply commits the cycle state.</extracomment>
        <translation>Cyclage des couleurs</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="153"/>
        <source>Colour cycling panel</source>
        <translation>Panneau de cyclage des couleurs</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="154"/>
        <source>Start</source>
        <translation>Début</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="155"/>
        <source>End</source>
        <translation>Fin</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="156"/>
        <source>Step</source>
        <translation>Pas</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="157"/>
        <source>Cycle range start index</source>
        <translation>Indice de début de la plage de cyclage</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="158"/>
        <source>Cycle range end index</source>
        <translation>Indice de fin de la plage de cyclage</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="159"/>
        <source>Cycle step</source>
        <translation>Pas de cyclage</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="160"/>
        <source>Play / Stop</source>
        <translation>Lecture / arrêt</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="161"/>
        <source>Apply</source>
        <translation>Appliquer</translation>
    </message>
</context>
<context>
    <name>Colour_Hub_Menu</name>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="642"/>
        <source>Colour Hub</source>
        <extracomment>Emitted with an RGBA tuple whenever a colour is picked (apply immediately, leg 1 — the live preview stream; never refused, REQ-P3-UI-006 clause 1). Emitted with an RGBA tuple on a COMPLETED pick only — one emission per discrete gesture (a wheel-drag release, a keyboard nudge release, a numeric spin&apos;s editingFinished, a single click on a harmony/shade/tint swatch, or a single click on a Favourites entry). A DOUBLE click / a keyboard activation on either swatch surface adopts instead and never reaches this signal (REQ-IS-UI-019/-020/-022, D-11). The shell (``ui/main_window.py``) uses this to run the active tool at the hub&apos;s anchor pixel as leg 2 (REQ-P3-UI-006 clauses 2-6). Re-emitted when the Favourites model changes (so the shell persists it). Set by the app-wide dismiss filter (below) to the ``timestamp()`` of the RightButton press that just hid this hub, and consumed once by :meth:`consume_dismiss_timestamp`. ``None`` when no dismissal is pending recognition.</extracomment>
        <translation>Centre de couleurs</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="643"/>
        <source>Colour hub</source>
        <translation>Centre de couleurs</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="644"/>
        <source>Add to Favourites</source>
        <translation>Ajouter aux favoris</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="647"/>
        <source>This tool does not paint the active colour, so the colour wheel is hidden here.</source>
        <translation>Cet outil ne peint pas avec la couleur active ; la roue chromatique est donc masquée ici.</translation>
    </message>
</context>
<context>
    <name>Colour_Wheel_Widget</name>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="353"/>
        <location filename="../ui/colour_wheel_widget.py" line="627"/>
        <source>Red channel</source>
        <extracomment>Emitted with the picked :class:`QColor` on any user-initiated change that ADOPTS into the wheel (wheel-pad drag, value slider, numeric entries, and a harmony/shade/tint swatch&apos;s double-click/keyboard activation — never a swatch&apos;s single click). Emitted with a harmony/shade/tint swatch&apos;s own RGBA tuple on a single left click (REQ-IS-UI-020). PAINT-only: the wheel&apos;s own selection is deliberately left unchanged, unlike :attr:`colorPicked`.</extracomment>
        <translation>Canal rouge</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="356"/>
        <location filename="../ui/colour_wheel_widget.py" line="628"/>
        <source>Green channel</source>
        <translation>Canal vert</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="359"/>
        <location filename="../ui/colour_wheel_widget.py" line="629"/>
        <source>Blue channel</source>
        <translation>Canal bleu</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="362"/>
        <location filename="../ui/colour_wheel_widget.py" line="630"/>
        <source>Hue</source>
        <translation>Teinte</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="365"/>
        <location filename="../ui/colour_wheel_widget.py" line="631"/>
        <source>Saturation</source>
        <translation>Saturation</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="368"/>
        <location filename="../ui/colour_wheel_widget.py" line="619"/>
        <location filename="../ui/colour_wheel_widget.py" line="632"/>
        <source>Value</source>
        <translation>Valeur</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="555"/>
        <source>Current colour %1</source>
        <translation>Couleur actuelle %1</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="618"/>
        <source>Colour wheel picker</source>
        <translation>Sélecteur à roue chromatique</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="620"/>
        <source>Brightness value</source>
        <translation>Valeur de luminosité</translation>
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
        <location filename="../ui/colour_wheel_widget.py" line="633"/>
        <source>Hex colour</source>
        <translation>Couleur hexadécimale</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="634"/>
        <source>Complementary</source>
        <translation>Complémentaire</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="635"/>
        <source>Analogous</source>
        <translation>Analogue</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="636"/>
        <source>Triadic</source>
        <translation>Triadique</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="637"/>
        <source>Tetradic</source>
        <translation>Tétradique</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="638"/>
        <source>Split-complementary</source>
        <translation>Complémentaire divisée</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="639"/>
        <source>Shades</source>
        <translation>Tons foncés</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="640"/>
        <source>Tints</source>
        <translation>Tons clairs</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="651"/>
        <source>harmony</source>
        <translation>harmonie</translation>
    </message>
</context>
<context>
    <name>Comments_Panel</name>
    <message>
        <location filename="../ui/comments_panel.py" line="116"/>
        <location filename="../ui/comments_panel.py" line="124"/>
        <location filename="../ui/comments_panel.py" line="134"/>
        <location filename="../ui/comments_panel.py" line="144"/>
        <location filename="../ui/comments_panel.py" line="160"/>
        <location filename="../ui/comments_panel.py" line="220"/>
        <source>Comments</source>
        <translation>Commentaires</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="117"/>
        <source>Open a shared project before commenting.</source>
        <translation>Ouvrez un projet partagé avant de commenter.</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="125"/>
        <source>Enter your member id before commenting.</source>
        <translation>Saisissez votre identifiant de membre avant de commenter.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/comments_panel.py" line="135"/>
        <source>A comment may be at most %n bytes.</source>
        <translation>
            <numerusform>Un commentaire peut faire %n octet au maximum.</numerusform>
            <numerusform>Un commentaire peut faire %n octets au maximum.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="194"/>
        <source>Resolved</source>
        <translation>Résolu</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="194"/>
        <source>Open</source>
        <translation>Ouvert</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/comments_panel.py" line="209"/>
        <source>%1 / %n bytes</source>
        <translation>
            <numerusform>%1 / %n octet</numerusform>
            <numerusform>%1 / %n octets</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="221"/>
        <source>Your member id:</source>
        <translation>Votre identifiant de membre :</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="222"/>
        <source>e.g. alice</source>
        <translation>p. ex. alice</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="223"/>
        <source>Comment author id</source>
        <translation>Identifiant de l&apos;auteur du commentaire</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="225"/>
        <source>Author</source>
        <translation>Auteur</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="225"/>
        <source>Comment</source>
        <translation>Commentaire</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="225"/>
        <source>Status</source>
        <translation>Statut</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="227"/>
        <source>Comment thread</source>
        <translation>Fil de commentaires</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="228"/>
        <source>Write a comment…</source>
        <translation>Écrire un commentaire…</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="229"/>
        <source>New comment text</source>
        <translation>Texte du nouveau commentaire</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="230"/>
        <source>Reply to selected</source>
        <translation>Répondre à la sélection</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="231"/>
        <source>Reply to the selected comment</source>
        <translation>Répondre au commentaire sélectionné</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="232"/>
        <source>Add Comment</source>
        <translation>Ajouter un commentaire</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="233"/>
        <source>Add the comment</source>
        <translation>Ajouter le commentaire</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="234"/>
        <source>Resolve</source>
        <translation>Résoudre</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="235"/>
        <source>Resolve the selected comment</source>
        <translation>Résoudre le commentaire sélectionné</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="236"/>
        <source>Comment byte count</source>
        <translation>Nombre d&apos;octets du commentaire</translation>
    </message>
</context>
<context>
    <name>Cursor_Feedback_Overlay</name>
    <message>
        <location filename="../ui/cursor_feedback_overlay.py" line="103"/>
        <location filename="../ui/cursor_feedback_overlay.py" line="160"/>
        <source>Cursor feedback</source>
        <extracomment>Progress fraction (0..1 of FEEDBACK_DURATION_MS) at which the fall to zero begins.</extracomment>
        <translation>Retour visuel du curseur</translation>
    </message>
</context>
<context>
    <name>Dependency_Graph_View</name>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="166"/>
        <source>Dependency cycle detected (graph unchanged): %1</source>
        <extracomment>Item roles: whether a row is a broken edge, and the edge it stands for. The asset in scope (``&quot;&quot;`` = the whole catalog). The last cycle the model reported at :meth:`show_edges` (``&quot;&quot;`` = none).</extracomment>
        <translation>Cycle de dépendances détecté (graphe inchangé) : %1</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="198"/>
        <source>Dependencies (depends on)</source>
        <translation>Dépendances (dépend de)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="204"/>
        <source>Dependents (referenced by)</source>
        <translation>Dépendants (référencés par)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="234"/>
        <source>Broken (%1)</source>
        <translation>Rompues (%1)</translation>
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
        <translation>Animation</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="268"/>
        <source>Tileset</source>
        <translation>Tileset</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="269"/>
        <source>Tilemap</source>
        <translation>Tilemap</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="270"/>
        <source>Palette</source>
        <translation>Palette</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="277"/>
        <source>missing target</source>
        <translation>cible manquante</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="279"/>
        <source>changed target</source>
        <translation>cible modifiée</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="286"/>
        <source>No broken references</source>
        <translation>Aucune référence rompue</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="289"/>
        <source>Broken references: %1</source>
        <translation>Références rompues : %1</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="291"/>
        <source>Broken reference summary</source>
        <translation>Résumé des références rompues</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="295"/>
        <source>Dependency graph</source>
        <translation>Graphe des dépendances</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="296"/>
        <source>Asset</source>
        <translation>Ressource</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="296"/>
        <source>Status</source>
        <translation>Statut</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="297"/>
        <source>Dependency relations</source>
        <translation>Relations de dépendance</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="298"/>
        <source>Dependency cycle notice</source>
        <translation>Avis de cycle de dépendances</translation>
    </message>
</context>
<context>
    <name>Document_Transform_Confirm_Dialog</name>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="88"/>
        <source>Confirm Large Transform</source>
        <translation>Confirmer la transformation importante</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="89"/>
        <source>Confirm large document transform dialog</source>
        <translation>Boîte de dialogue de confirmation de transformation importante du document</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="92"/>
        <source>%1 will resample every layer and mask of this document to %2 × %3 px, using up to %4 of memory at once. Proceed?</source>
        <translation>L&apos;opération « %1 » rééchantillonnera chaque calque et chaque masque de ce document à %2 × %3 px, en utilisant jusqu&apos;à %4 de mémoire à la fois. Continuer ?</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="100"/>
        <source>Transform cost summary</source>
        <translation>Résumé du coût de la transformation</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="101"/>
        <source>Proceed</source>
        <translation>Continuer</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="102"/>
        <source>Proceed with the transform</source>
        <translation>Continuer la transformation</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="103"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="104"/>
        <source>Cancel the transform</source>
        <translation>Annuler la transformation</translation>
    </message>
</context>
<context>
    <name>Document_Transform_Progress_Dialog</name>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="190"/>
        <source>Transforming Document</source>
        <extracomment>Emitted when the user asks to stop — via the button, Escape, or the window&apos;s close control. The caller (the runner) decides what &quot;stop&quot; means; this dialog only reports the request.</extracomment>
        <translation>Transformation du document</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="191"/>
        <source>Document transform progress dialog</source>
        <translation>Boîte de dialogue de progression de la transformation du document</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="192"/>
        <source>%1…</source>
        <translation>%1…</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="193"/>
        <source>Transform operation in progress</source>
        <translation>Transformation en cours</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="194"/>
        <source>Transform progress</source>
        <translation>Progression de la transformation</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="195"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="196"/>
        <source>Cancel the transform</source>
        <translation>Annuler la transformation</translation>
    </message>
</context>
<context>
    <name>Document_View</name>
    <message>
        <location filename="../ui/multi_view.py" line="119"/>
        <source>Document view {0}</source>
        <extracomment>Per-wheel-notch zoom step for an extra view (independent of the primary view). Emitted with the picked RGBA tuple when a plain wheel notch travels the shared Favourites cursor (REQ-IS-UI-008, D-16 — this surface is a navigate-only view of the SAME live document scene as the primary Canvas_View, so the active colour it sets is real document context). The persisted Favourites model bound via :meth:`set_favourites_model`; ``None`` until the shell binds one.</extracomment>
        <translation>Vue du document {0}</translation>
    </message>
    <message>
        <location filename="../ui/multi_view.py" line="123"/>
        <source>An extra synced view of the same document (independent zoom/pan)</source>
        <translation>Une vue supplémentaire synchronisée du même document (zoom et déplacement indépendants)</translation>
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
        <translation>Document entier</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="295"/>
        <source>Animated GIF (*.gif)</source>
        <translation>GIF animé (*.gif)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="297"/>
        <source>PNG image (*.png)</source>
        <translation>Image PNG (*.png)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="299"/>
        <source>Export To</source>
        <translation>Exporter vers</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="307"/>
        <source>Export</source>
        <translation>Exporter</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="308"/>
        <source>Format</source>
        <translation>Format</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="309"/>
        <location filename="../ui/export_dialog.py" line="337"/>
        <source>Engine preset</source>
        <translation>Préréglage de moteur</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="310"/>
        <source>Destination</source>
        <translation>Destination</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="311"/>
        <source>Browse…</source>
        <translation>Parcourir…</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="312"/>
        <source>Also add to the asset library</source>
        <translation>Ajouter aussi à la bibliothèque de ressources</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="314"/>
        <source>PNG image</source>
        <translation>Image PNG</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="315"/>
        <source>Animated GIF</source>
        <translation>GIF animé</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="316"/>
        <source>Sprite sheet</source>
        <translation>Feuille de sprites</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="317"/>
        <source>Texture atlas</source>
        <translation>Atlas de textures</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="318"/>
        <source>None</source>
        <translation>Aucun</translation>
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
        <translation>Exporte la première image sous forme de fichier PNG aplati.</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="325"/>
        <source>Frames</source>
        <translation>Images</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="326"/>
        <source>Loop count</source>
        <translation>Nombre de boucles</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="327"/>
        <source>Loop count (0 = loop forever).</source>
        <translation>Nombre de boucles (0 = boucle infinie).</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="328"/>
        <source>Columns</source>
        <translation>Colonnes</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="329"/>
        <location filename="../ui/export_dialog.py" line="331"/>
        <source>Padding (px)</source>
        <translation>Marge (px)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="330"/>
        <location filename="../ui/export_dialog.py" line="333"/>
        <source>Write JSON metadata</source>
        <translation>Écrire les métadonnées JSON</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="332"/>
        <source>Max dimension (px)</source>
        <translation>Dimension maximale (px)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="336"/>
        <source>Export format</source>
        <translation>Format d&apos;exportation</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="338"/>
        <source>Destination path</source>
        <translation>Chemin de destination</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="339"/>
        <source>Browse for destination</source>
        <translation>Parcourir pour choisir la destination</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="341"/>
        <source>Also add this export to the asset library</source>
        <translation>Ajouter aussi cette exportation à la bibliothèque de ressources</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="343"/>
        <source>GIF frame source</source>
        <translation>Source des images du GIF</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="344"/>
        <source>GIF loop count</source>
        <translation>Nombre de boucles du GIF</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="345"/>
        <source>Sprite-sheet columns</source>
        <translation>Colonnes de la feuille de sprites</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="346"/>
        <source>Sprite-sheet padding</source>
        <translation>Marge de la feuille de sprites</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="347"/>
        <source>Write sprite-sheet JSON</source>
        <translation>Écrire le JSON de la feuille de sprites</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="348"/>
        <source>Atlas padding</source>
        <translation>Marge de l&apos;atlas</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="349"/>
        <source>Atlas max dimension</source>
        <translation>Dimension maximale de l&apos;atlas</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="350"/>
        <source>Write atlas JSON</source>
        <translation>Écrire le JSON de l&apos;atlas</translation>
    </message>
</context>
<context>
    <name>Extract_Palette_Dialog</name>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="127"/>
        <source>Choose Image</source>
        <extracomment>Extraction method tokens carried in the method combo&apos;s item data.</extracomment>
        <translation>Choisir une image</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="129"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>Images (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="136"/>
        <location filename="../ui/extract_palette_dialog.py" line="153"/>
        <source>Extract Palette</source>
        <translation>Extraire la palette</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="136"/>
        <source>Could not load the image.</source>
        <translation>Impossible de charger l&apos;image.</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="160"/>
        <source>Extract Palette from Image</source>
        <translation>Extraire la palette d&apos;une image</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="161"/>
        <source>Extract palette dialog</source>
        <translation>Boîte de dialogue d&apos;extraction de palette</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="162"/>
        <source>Choose Image…</source>
        <translation>Choisir une image…</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="163"/>
        <source>No image chosen</source>
        <translation>Aucune image choisie</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="164"/>
        <source>Colours (N)</source>
        <translation>Couleurs (N)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="165"/>
        <source>Method</source>
        <translation>Méthode</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="166"/>
        <source>Number of colours</source>
        <translation>Nombre de couleurs</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="167"/>
        <source>Extraction method</source>
        <translation>Méthode d&apos;extraction</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="168"/>
        <source>Median cut (fast)</source>
        <translation>Coupe médiane (rapide)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="169"/>
        <source>K-means (higher quality)</source>
        <translation>K-moyennes (meilleure qualité)</translation>
    </message>
</context>
<context>
    <name>Favourites_Panel</name>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="279"/>
        <source>Favourites</source>
        <extracomment>Edge of a Favourites swatch icon, px (presentation-only sizing). Keys that nudge the wheel pad&apos;s hue/saturation (``_WheelPad.keyPressEvent``); a KeyRelease for one of these is a discrete, already-completed pick (REQ-P3- UI-006 leg 2), unlike Tab/other keys the pad never acts on. Single left click on a favourite — paint that colour, leave the wheel alone. Double left click / Enter / Return on a favourite — adopt that colour into the wheel, paint nothing. Deprecated alias of :attr:`favouriteActivated`, kept for pre-2026-08-31 callers of the pre-split single ``favouriteChosen`` signal. Emitted alongside :attr:`favouriteActivated` ONLY — never alongside :attr:`favouritePicked`, so it never resurrects the fused-gesture defect this split fixes (REQ-IS-UI-019). New code should connect :attr:`favouritePicked` / :attr:`favouriteActivated` directly. Emitted whenever the underlying model is mutated (so the shell persists it).</extracomment>
        <translation>Favoris</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="280"/>
        <source>Favourites panel</source>
        <translation>Panneau des favoris</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="281"/>
        <source>Favourite colours</source>
        <translation>Couleurs favorites</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="282"/>
        <source>Remove</source>
        <translation>Supprimer</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="283"/>
        <source>Move Up</source>
        <translation>Monter</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="284"/>
        <source>Move Down</source>
        <translation>Descendre</translation>
    </message>
</context>
<context>
    <name>Frame_Tags_Panel</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="261"/>
        <source>%1  [%2–%3]  %4</source>
        <extracomment>Emitted with the :class:`FrameTag` to play as a named animation (UI-014).</extracomment>
        <translation>%1  [%2–%3]  %4</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="262"/>
        <source>(unnamed)</source>
        <translation>(sans nom)</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="311"/>
        <location filename="../ui/frame_tags_panel.py" line="313"/>
        <location filename="../ui/frame_tags_panel.py" line="379"/>
        <source>Add Tag</source>
        <translation>Ajouter une étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="335"/>
        <location filename="../ui/frame_tags_panel.py" line="337"/>
        <location filename="../ui/frame_tags_panel.py" line="380"/>
        <source>Edit Tag</source>
        <translation>Modifier l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="348"/>
        <location filename="../ui/frame_tags_panel.py" line="381"/>
        <source>Remove Tag</source>
        <translation>Supprimer l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="373"/>
        <source>Frame tags panel</source>
        <translation>Panneau des étiquettes d&apos;images</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="374"/>
        <source>Tag actions</source>
        <translation>Actions sur les étiquettes</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="375"/>
        <source>Frame tags</source>
        <translation>Étiquettes d&apos;images</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="377"/>
        <source>Named animations; double-click to edit</source>
        <translation>Animations nommées ; double-cliquez pour modifier</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="382"/>
        <source>Play Tag</source>
        <translation>Lire l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="384"/>
        <source>Play the selected tag as its own animation</source>
        <translation>Lire l&apos;étiquette sélectionnée comme une animation à part entière</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="386"/>
        <source>Play tag</source>
        <translation>Lire l&apos;étiquette</translation>
    </message>
</context>
<context>
    <name>Guide_Logo_Switch_Widget</name>
    <message>
        <location filename="../ui/guide_logo_switch.py" line="121"/>
        <source>Switch the pixel font for the guide&apos;s pages</source>
        <extracomment>Accessible name of the switch; screen readers announce it.</extracomment>
        <translation>Changer la police pixel des pages du guide</translation>
    </message>
</context>
<context>
    <name>Iso_Grid_Dialog</name>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="117"/>
        <source>Configure Isometric Grid</source>
        <extracomment>Sane bounds for the ``W:H`` tile ratio field (2:1 dimetric default is 2.0; true-iso is ~1.732). Not a lattice geometry decision — just a widget bound keeping the field away from non-finite/degenerate input before it ever reaches ``IsoGridConfig`` validation (S12).</extracomment>
        <translation>Configurer la grille isométrique</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="118"/>
        <source>Tile width</source>
        <translation>Largeur de tuile</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="119"/>
        <source>Tile ratio (W:H)</source>
        <translation>Rapport de tuile (W:H)</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="120"/>
        <source>Origin X</source>
        <translation>Origine X</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="121"/>
        <source>Origin Y</source>
        <translation>Origine Y</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="122"/>
        <source>Isometric tile width</source>
        <translation>Largeur de tuile isométrique</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="123"/>
        <source>Isometric tile ratio</source>
        <translation>Rapport de tuile isométrique</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="124"/>
        <source>Isometric grid origin X</source>
        <translation>Origine X de la grille isométrique</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="125"/>
        <source>Isometric grid origin Y</source>
        <translation>Origine Y de la grille isométrique</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="128"/>
        <source>OK</source>
        <translation>OK</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="131"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
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
        <translation>Produit</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="445"/>
        <source>Screen</source>
        <translation>Superposition</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="446"/>
        <source>Overlay</source>
        <translation>Incrustation</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="447"/>
        <source>Darken</source>
        <translation>Assombrir</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="448"/>
        <source>Lighten</source>
        <translation>Éclaircir</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="449"/>
        <source>Colour Dodge</source>
        <translation>Densité de couleur -</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="450"/>
        <source>Colour Burn</source>
        <translation>Densité de couleur +</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="451"/>
        <source>Hard Light</source>
        <translation>Lumière crue</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="452"/>
        <source>Soft Light</source>
        <translation>Lumière tamisée</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="453"/>
        <source>Difference</source>
        <translation>Différence</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="454"/>
        <source>Exclusion</source>
        <translation>Exclusion</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="650"/>
        <source>Layer</source>
        <translation>Calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="654"/>
        <location filename="../ui/layer_panel.py" line="883"/>
        <source>Add Layer</source>
        <translation>Ajouter un calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="667"/>
        <location filename="../ui/layer_panel.py" line="884"/>
        <source>Remove Layer</source>
        <translation>Supprimer le calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="680"/>
        <location filename="../ui/layer_panel.py" line="885"/>
        <source>Duplicate Layer</source>
        <translation>Dupliquer le calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="689"/>
        <location filename="../ui/layer_panel.py" line="886"/>
        <source>Group</source>
        <translation>Groupe</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="693"/>
        <source>Group Layers</source>
        <translation>Grouper les calques</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="705"/>
        <source>Ungroup Layers</source>
        <translation>Dégrouper les calques</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="726"/>
        <location filename="../ui/layer_panel.py" line="871"/>
        <location filename="../ui/layer_panel.py" line="891"/>
        <source>Add Mask</source>
        <translation>Ajouter un masque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="733"/>
        <location filename="../ui/layer_panel.py" line="871"/>
        <source>Remove Mask</source>
        <translation>Supprimer le masque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="757"/>
        <source>Toggle Reference</source>
        <translation>Basculer la référence</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="767"/>
        <source>Smart</source>
        <translation>Intelligent</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="771"/>
        <source>Create Smart Layer</source>
        <translation>Créer un calque intelligent</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="828"/>
        <source>Move Layer</source>
        <translation>Déplacer le calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="877"/>
        <source>Layers panel</source>
        <translation>Panneau des calques</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="878"/>
        <source>Layer actions</source>
        <translation>Actions sur les calques</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="879"/>
        <source>Layer tree</source>
        <translation>Arborescence des calques</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="881"/>
        <source>Layers top-to-bottom; drag to reorder or re-parent</source>
        <translation>Calques du haut vers le bas ; glissez pour réorganiser ou changer de parent</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="887"/>
        <source>Ungroup</source>
        <translation>Dégrouper</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="888"/>
        <source>Edit Mask</source>
        <translation>Modifier le masque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="889"/>
        <source>Reference</source>
        <translation>Référence</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="890"/>
        <source>Smart Layer</source>
        <translation>Calque intelligent</translation>
    </message>
</context>
<context>
    <name>Macro_Controls</name>
    <message>
        <location filename="../ui/macro_controls.py" line="143"/>
        <source>Running…</source>
        <extracomment>``(Macro, label)`` — the host should replay this macro on the active document (as one undoable grouped command, REQ-P8-UI-002). ``(recording,)`` — recording started / stopped (view state, not undoable). The user asked to cancel the in-flight automation run (C-07); the host relays this to ``Automation_Controller.cancel()``.</extracomment>
        <translation>Exécution en cours…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="145"/>
        <source>Done</source>
        <translation>Terminé</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="146"/>
        <source>Idle</source>
        <translation>En attente</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="184"/>
        <source>Macro Error</source>
        <translation>Erreur de macro</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/macro_controls.py" line="188"/>
        <source>Recording %1 (%n steps)</source>
        <translation>
            <numerusform>Capture : %1 (%n étape)</numerusform>
            <numerusform>Capture : %1 (%n étapes)</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="210"/>
        <source>Macro</source>
        <translation>Macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="228"/>
        <source>Save Macro</source>
        <translation>Enregistrer la macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="230"/>
        <location filename="../ui/macro_controls.py" line="250"/>
        <source>Macro files (*%1)</source>
        <translation>Fichiers de macro (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="237"/>
        <source>Save Macro Failed</source>
        <translation>Échec de l&apos;enregistrement de la macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="248"/>
        <source>Load Macro</source>
        <translation>Charger une macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="257"/>
        <source>Load Macro Failed</source>
        <translation>Échec du chargement de la macro</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/macro_controls.py" line="288"/>
        <source>Recording… %n steps captured</source>
        <translation>
            <numerusform>Capture en cours… %n étape capturée</numerusform>
            <numerusform>Capture en cours… %n étapes capturées</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="291"/>
        <source>Not recording</source>
        <translation>Aucune capture en cours</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="295"/>
        <source>Stop Recording</source>
        <translation>Arrêter la capture</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="295"/>
        <source>Record Macro</source>
        <translation>Lancer la capture de macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="297"/>
        <source>Replay</source>
        <translation>Rejouer</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="298"/>
        <source>Save…</source>
        <translation>Enregistrer…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="299"/>
        <source>Load…</source>
        <translation>Charger…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="300"/>
        <source>Remove</source>
        <translation>Supprimer</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="301"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="302"/>
        <source>Macro controls</source>
        <translation>Contrôles de macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="303"/>
        <source>Record or stop a macro</source>
        <translation>Lancer ou arrêter la capture d&apos;une macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="304"/>
        <source>Macro recording status</source>
        <translation>État de la capture de macro</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="305"/>
        <source>Recorded and loaded macros</source>
        <translation>Macros capturées et chargées</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="306"/>
        <source>Replay the selected macro</source>
        <translation>Rejouer la macro sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="307"/>
        <source>Save the selected macro</source>
        <translation>Enregistrer la macro sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="308"/>
        <source>Load a macro from a file</source>
        <translation>Charger une macro depuis un fichier</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="309"/>
        <source>Remove the selected macro</source>
        <translation>Supprimer la macro sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="310"/>
        <source>Cancel the running automation</source>
        <translation>Annuler l&apos;automatisation en cours</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="312"/>
        <source>Stops the in-flight automation run; enabled only while busy.</source>
        <translation>Arrête l&apos;exécution de l&apos;automatisation en cours ; disponible uniquement pendant l&apos;exécution.</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="314"/>
        <source>Progress</source>
        <translation>Progression</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="315"/>
        <source>Macro replay progress</source>
        <translation>Progression de la relecture de macro</translation>
    </message>
</context>
<context>
    <name>Main_Window</name>
    <message>
        <location filename="../ui/main_window.py" line="1295"/>
        <source>&amp;Undo</source>
        <extracomment>Emitted when &quot;Use system font&quot; changes (stored here; the font itself is switched by the listener that owns it). Emitted when &quot;Pixel-perfect interface&quot; changes (stored here; it takes effect at the next launch). Live mirror-centre override from the Symmetry_Panel (D-28/CF-93); ``None`` keeps the shipped canvas-centre default. The DSL ops of the in-flight automation run (recorded into a macro on success if recording is active); ``None`` for a macro replay (a replay is not itself re-recorded). True while an in-session timelapse playback holds the active tab&apos;s canvas + the shared undo/redo actions read-only (REQ-P9-UI-016); see ``_on_timelapse_playback_lock_changed``. The cloud project id last saved to / opened from (drives version browse). D-13: the most recently fetched remote version list (cached from the last &quot;open_list&quot;/&quot;versions&quot;/&quot;save&quot; result) — feeds the read-only ``compute_sync_state`` for the Cloud menu status line and the version browser, without a network round trip on every tab switch. D-13: the version id of a restore/recover in flight, consumed once the reconstructed document lands in its new tab (see ``_on_cloud_succeeded``). Live-cursor overlays are per-tab (attached in _create_tab_aids); toggled on connect. The local member id broadcast with presence (never a token).</extracomment>
        <translation>Annuler</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="1297"/>
        <source>&amp;Redo</source>
        <translation>Rétablir</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2215"/>
        <source>Untitled</source>
        <translation>Sans titre</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2790"/>
        <source>Add Frame</source>
        <translation>Ajouter une image</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3141"/>
        <source>Unsaved Changes</source>
        <translation>Modifications non enregistrées</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3143"/>
        <source>The current document has unsaved changes. Save it before opening the dropped project?</source>
        <translation>Le document actuel contient des modifications non enregistrées. L&apos;enregistrer avant d&apos;ouvrir le projet déposé ?</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3178"/>
        <source>Load Palette</source>
        <translation>Charger une palette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3206"/>
        <location filename="../ui/main_window.py" line="4227"/>
        <source>Save Project</source>
        <translation>Enregistrer le projet</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3208"/>
        <location filename="../ui/main_window.py" line="4213"/>
        <location filename="../ui/main_window.py" line="4229"/>
        <source>Pixel projects (*%1)</source>
        <translation>Projets pixel (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3218"/>
        <source>Unsupported file type: %1</source>
        <translation>Type de fichier non pris en charge : %1</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3229"/>
        <source>Layer is locked.</source>
        <translation>Le calque est verrouillé.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3244"/>
        <source>This is the last remaining frame; a document must keep at least one.</source>
        <translation>Il s&apos;agit de la dernière image restante ; un document doit en conserver au moins une.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3257"/>
        <source>Click was outside the document.</source>
        <translation>Le clic était en dehors du document.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3270"/>
        <source>This layer cannot be edited directly.</source>
        <translation>Ce calque ne peut pas être modifié directement.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3283"/>
        <source>No change: the colour already matched.</source>
        <translation>Aucun changement : la couleur correspondait déjà.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3296"/>
        <source>No tileset bound to this tilemap yet.</source>
        <translation>Aucun tileset n&apos;est encore lié à cette tilemap.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3308"/>
        <source>Select a tile first.</source>
        <translation>Sélectionnez d&apos;abord une tuile.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3315"/>
        <source>Open a document before loading a palette.</source>
        <translation>Ouvrez un document avant de charger une palette.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3323"/>
        <source>Import Failed</source>
        <translation>Échec de l&apos;importation</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3324"/>
        <source>Could not import %1:
%2</source>
        <translation>Impossible d&apos;importer %1 :
%2</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3443"/>
        <source>Copying selection — release, Enter to commit, Esc to cancel</source>
        <extracomment>Incoming tool ids that discard the active selection on entry (REQ-IS-UI-029). Re-activating an already-active selection tool is included deliberately, so it doubles as a start-fresh gesture — an assumption, flagged and cheap to reverse. Every other incoming tool leaves the selection untouched, so mask-constrained drawing (REQ-P2-LOGIC-006) survives a tool switch.</extracomment>
        <translation>Copie de la sélection — relâchez, Enter pour valider, Esc pour annuler</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3448"/>
        <source>Moving selection — hold Ctrl to copy; Enter to commit, Esc to cancel</source>
        <translation>Déplacement de la sélection — maintenez Ctrl pour copier ; Enter pour valider, Esc pour annuler</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3559"/>
        <source>Add Shade Ramp</source>
        <translation>Ajouter une rampe de tons</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3577"/>
        <location filename="../ui/main_window.py" line="3583"/>
        <source>Constrain to Palette</source>
        <translation>Contraindre à la palette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3604"/>
        <location filename="../ui/main_window.py" line="3613"/>
        <location filename="../ui/main_window.py" line="5612"/>
        <source>Colour Cycling</source>
        <translation>Cyclage des couleurs</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3605"/>
        <source>Colour cycling applies to indexed documents.</source>
        <translation>Le cyclage des couleurs s&apos;applique aux documents indexés.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3619"/>
        <source>Colour Cycle</source>
        <translation>Cycle de couleurs</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3637"/>
        <source>Extract Palette</source>
        <translation>Extraire la palette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3648"/>
        <location filename="../ui/main_window.py" line="3666"/>
        <location filename="../ui/main_window.py" line="3672"/>
        <source>Palette Swap</source>
        <translation>Échange de palette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3649"/>
        <source>Palette swap applies to indexed documents.</source>
        <translation>L&apos;échange de palette s&apos;applique aux documents indexés.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3695"/>
        <location filename="../ui/main_window.py" line="3701"/>
        <source>Convert to Indexed</source>
        <translation>Convertir en indexé</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3721"/>
        <location filename="../ui/main_window.py" line="3727"/>
        <source>Convert to RGBA</source>
        <translation>Convertir en RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3853"/>
        <source>Register Selection</source>
        <translation>Inscrire la sélection</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3942"/>
        <source>Choose a new folder for the imported project</source>
        <translation>Choisissez un nouveau dossier pour le projet importé</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3951"/>
        <source>&quot;%1&quot; already exists. Choose a name for a new folder.</source>
        <translation>« %1 » existe déjà. Choisissez un nom pour un nouveau dossier.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3970"/>
        <source>Imported Project</source>
        <translation>Projet importé</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4211"/>
        <source>Open Project</source>
        <translation>Ouvrir un projet</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4238"/>
        <source>Cloud project name:</source>
        <translation>Nom du projet cloud :</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4243"/>
        <source>Enter a project name.</source>
        <translation>Saisissez un nom de projet.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4252"/>
        <source>Connect to a cloud provider first.</source>
        <translation>Connectez-vous d&apos;abord à un fournisseur cloud.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4286"/>
        <source>Cloud status: —</source>
        <translation>État du cloud : —</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4294"/>
        <source>Cloud status: Up to date</source>
        <translation>État du cloud : à jour</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4296"/>
        <source>Cloud status: Not yet saved to cloud</source>
        <translation>État du cloud : pas encore enregistré dans le cloud</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4298"/>
        <source>Cloud status: Newer version in cloud</source>
        <translation>État du cloud : version plus récente dans le cloud</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4299"/>
        <source>Cloud status: Diverged</source>
        <translation>État du cloud : divergence</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4305"/>
        <source>Real-time</source>
        <translation>Temps réel</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4308"/>
        <location filename="../ui/main_window.py" line="4456"/>
        <source>Open a document first.</source>
        <translation>Ouvrez d&apos;abord un document.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4310"/>
        <source>Your member id:</source>
        <translation>Votre identifiant de membre :</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4340"/>
        <source>Real-time: {msg}</source>
        <translation>Temps réel : {msg}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4444"/>
        <source>Merge</source>
        <translation>Fusionner</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4451"/>
        <source>Save to Cloud</source>
        <translation>Enregistrer dans le cloud</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4473"/>
        <source>Open from Cloud</source>
        <translation>Ouvrir depuis le cloud</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4491"/>
        <location filename="../ui/main_window.py" line="4608"/>
        <source>Cloud Version History</source>
        <translation>Historique des versions du cloud</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4578"/>
        <source>Saved to cloud.</source>
        <translation>Enregistré dans le cloud.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4585"/>
        <source>Cloud Project</source>
        <translation>Projet cloud</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4587"/>
        <source>Recovered</source>
        <translation>Récupéré</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4595"/>
        <source>Restored from cloud.</source>
        <translation>Restauré depuis le cloud.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4609"/>
        <source>No versions found for this project.</source>
        <translation>Aucune version trouvée pour ce projet.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4636"/>
        <source>Cloud</source>
        <translation>Cloud</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4762"/>
        <source>Clear Selection</source>
        <translation>Effacer la sélection</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4877"/>
        <source>Flip Horizontal</source>
        <translation>Retourner horizontalement</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4880"/>
        <source>Flip Vertical</source>
        <translation>Retourner verticalement</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4884"/>
        <source>Rotate 90° CW</source>
        <translation>Pivoter de 90° (sens horaire)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4889"/>
        <source>Rotate 90° CCW</source>
        <translation>Pivoter de 90° (sens antihoraire)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4910"/>
        <location filename="../ui/main_window.py" line="4913"/>
        <location filename="../ui/main_window.py" line="4917"/>
        <location filename="../ui/main_window.py" line="4926"/>
        <location filename="../ui/main_window.py" line="4929"/>
        <source>Scale Canvas</source>
        <translation>Mettre le canvas à l&apos;échelle</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4958"/>
        <location filename="../ui/main_window.py" line="4961"/>
        <source>Canvas Size</source>
        <translation>Taille du canvas</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4979"/>
        <source>Rotate (RotSprite)</source>
        <translation>Pivoter (RotSprite)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5127"/>
        <source>Pixel-perfect interface: the change applies the next time the application starts.</source>
        <translation>Interface pixel perfect : la modification s&apos;appliquera au prochain démarrage de l&apos;application.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5254"/>
        <location filename="../ui/main_window.py" line="5263"/>
        <source>Open Tileset Image</source>
        <translation>Ouvrir une image de tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5256"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>Images (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5272"/>
        <source>New Tileset</source>
        <translation>Nouveau tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5278"/>
        <source>Add Tileset</source>
        <translation>Ajouter un tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5288"/>
        <location filename="../ui/main_window.py" line="5339"/>
        <source>Attach Tileset</source>
        <translation>Associer un tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5301"/>
        <source>Tilemap</source>
        <translation>Tilemap</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5304"/>
        <source>Layer 1</source>
        <translation>Calque 1</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5311"/>
        <source>Add Tilemap</source>
        <translation>Ajouter une tilemap</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5331"/>
        <source>Import Tilemap</source>
        <translation>Importer une tilemap</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5363"/>
        <source>Export Tiled Map</source>
        <translation>Exporter une carte Tiled</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5364"/>
        <source>There is no tilemap to export.</source>
        <translation>Il n&apos;y a aucune tilemap à exporter.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5392"/>
        <source>Exporting…</source>
        <translation>Exportation…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5397"/>
        <source>Exporting %1 of %2…</source>
        <translation>Exportation : %1 sur %2…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5440"/>
        <source>Export Failed</source>
        <translation>Échec de l&apos;exportation</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/main_window.py" line="5442"/>
        <source>%n export target(s) failed:
%2</source>
        <translation>
            <numerusform>%n cible d&apos;exportation a échoué :
%2</numerusform>
            <numerusform>%n cibles d&apos;exportation ont échoué :
%2</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/main_window.py" line="5450"/>
        <source>Export complete (%n file(s)).</source>
        <translation>
            <numerusform>Exportation terminée (%n fichier).</numerusform>
            <numerusform>Exportation terminée (%n fichiers).</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5500"/>
        <source>Automation</source>
        <translation>Automatisation</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5522"/>
        <source>Automation Error</source>
        <translation>Erreur d&apos;automatisation</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5540"/>
        <source>Running automation…</source>
        <translation>Automatisation en cours…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5586"/>
        <source>Assistant edit</source>
        <translation>Modification de l&apos;assistant</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5601"/>
        <source>PixelArt Creator</source>
        <translation>PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5602"/>
        <source>Tools</source>
        <translation>Outils</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5603"/>
        <source>Palette</source>
        <translation>Palette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5604"/>
        <source>Symmetry</source>
        <translation>Symétrie</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5605"/>
        <source>Layers</source>
        <translation>Calques</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5606"/>
        <source>Timeline</source>
        <translation>Ligne temporelle</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5607"/>
        <source>Onion Skin</source>
        <translation>Pelure d&apos;oignon</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5608"/>
        <source>Frame Tags</source>
        <translation>Étiquettes d&apos;images</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5609"/>
        <source>Palette Editor</source>
        <translation>Éditeur de palette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5610"/>
        <source>Constraints</source>
        <translation>Contraintes</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5611"/>
        <source>Shade Ramps</source>
        <translation>Rampes de tons</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5613"/>
        <source>Analytics</source>
        <translation>Analyses</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5614"/>
        <source>Tileset Editor</source>
        <translation>Éditeur de tileset</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5615"/>
        <source>Tilemap Layers</source>
        <translation>Calques de tilemap</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5616"/>
        <source>Tilemap Canvas</source>
        <translation>Canvas de tilemap</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5617"/>
        <source>Batch Export</source>
        <translation>Exportation par lot</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5618"/>
        <source>Macros</source>
        <translation>Macros</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5619"/>
        <source>Script Runner</source>
        <translation>Exécuteur de scripts</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5620"/>
        <source>Plugins</source>
        <translation>Plugins</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5621"/>
        <source>Batch Recolour</source>
        <translation>Recoloration par lot</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5622"/>
        <source>Procedural Generation</source>
        <translation>Génération procédurale</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5623"/>
        <source>Shared Projects</source>
        <translation>Projets partagés</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5624"/>
        <source>Comments</source>
        <translation>Commentaires</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5625"/>
        <source>Presence</source>
        <translation>Présence</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5626"/>
        <source>Branching</source>
        <translation>Branches</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5627"/>
        <source>Asset Library</source>
        <translation>Bibliothèque de ressources</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5628"/>
        <source>Asset Search</source>
        <translation>Recherche de ressources</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5629"/>
        <source>Asset Tagging</source>
        <translation>Étiquetage des ressources</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5630"/>
        <source>Dependency Graph</source>
        <translation>Graphe des dépendances</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5631"/>
        <source>Asset Versions</source>
        <translation>Versions des ressources</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5632"/>
        <source>Asset Reuse</source>
        <translation>Réutilisation de ressources</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5636"/>
        <source>Real-Size Preview</source>
        <translation>Aperçu à taille réelle</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5637"/>
        <source>Timelapse</source>
        <translation>Timelapse</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5638"/>
        <source>Reopened Recording</source>
        <translation>Capture rouverte</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5639"/>
        <source>Open documents</source>
        <translation>Documents ouverts</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5640"/>
        <source>Floating selection status</source>
        <translation>État de la sélection flottante</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5644"/>
        <source>Pencil</source>
        <translation>Crayon</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5645"/>
        <source>Eraser</source>
        <translation>Gomme</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5646"/>
        <source>Fill</source>
        <translation>Pot de peinture</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5647"/>
        <source>Line</source>
        <translation>Ligne</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5648"/>
        <source>Colour picker</source>
        <translation>Pipette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5649"/>
        <source>Rectangle</source>
        <translation>Rectangle</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5650"/>
        <source>Ellipse</source>
        <translation>Ellipse</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5651"/>
        <source>Rectangle select</source>
        <translation>Sélection rectangulaire</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5652"/>
        <source>Lasso select</source>
        <translation>Sélection au lasso</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5653"/>
        <source>Magic wand</source>
        <translation>Baguette magique</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5654"/>
        <location filename="../ui/main_window.py" line="5713"/>
        <source>Dither</source>
        <translation>Tramage</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5663"/>
        <source>&amp;New</source>
        <translation>Nouveau</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5664"/>
        <source>&amp;Open…</source>
        <translation>Ouvrir…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5665"/>
        <source>&amp;Save</source>
        <translation>Enregistrer</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5666"/>
        <source>Save &amp;As…</source>
        <translation>Enregistrer sous…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5667"/>
        <source>&amp;Export…</source>
        <translation>Exporter…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5668"/>
        <source>&amp;Close</source>
        <translation>Fermer</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5670"/>
        <source>&amp;Connect…</source>
        <translation>Se connecter…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5671"/>
        <source>&amp;Disconnect</source>
        <translation>Se déconnecter</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5672"/>
        <source>&amp;Save to Cloud…</source>
        <translation>Enregistrer dans le cloud…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5673"/>
        <source>&amp;Open from Cloud…</source>
        <translation>Ouvrir depuis le cloud…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5674"/>
        <source>&amp;Version History…</source>
        <translation>Historique des versions…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5676"/>
        <source>Start &amp;Real-time…</source>
        <translation>Démarrer le mode temps réel…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5677"/>
        <source>Stop Real-&amp;time</source>
        <translation>Arrêter le mode temps réel</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5678"/>
        <source>Show &amp;Live Cursors</source>
        <translation>Afficher les curseurs en direct</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5679"/>
        <source>Zoom &amp;In</source>
        <translation>Zoom avant</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5680"/>
        <source>Zoom &amp;Out</source>
        <translation>Zoom arrière</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5681"/>
        <source>&amp;Fit to View</source>
        <translation>Ajuster à la vue</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5682"/>
        <source>Fit to &amp;Content</source>
        <translation>Ajuster au contenu</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5683"/>
        <source>Show &amp;Grid</source>
        <translation>Afficher la grille</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5684"/>
        <source>&amp;Snap to Grid</source>
        <translation>Aligner sur la grille</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5685"/>
        <source>&amp;Anti-aliasing Off</source>
        <translation>Anticrénelage désactivé</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5686"/>
        <source>&amp;Tiled Mode</source>
        <translation>Mode tuilé</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5687"/>
        <source>Light</source>
        <translation>Clair</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5688"/>
        <source>Dark</source>
        <translation>Sombre</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5691"/>
        <source>New Tileset from Image…</source>
        <translation>Nouveau tileset à partir d&apos;une image…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5692"/>
        <source>New Tilemap</source>
        <translation>Nouvelle tilemap</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5693"/>
        <source>Import Tiled JSON…</source>
        <translation>Importer du JSON Tiled…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5694"/>
        <source>Export Tiled JSON…</source>
        <translation>Exporter en JSON Tiled…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5695"/>
        <source>Stamp Tool</source>
        <translation>Outil tampon</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5696"/>
        <source>Place the selected tile</source>
        <translation>Placer la tuile sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5697"/>
        <source>Tile Eraser</source>
        <translation>Gomme à tuiles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5698"/>
        <source>Clear the target cell</source>
        <translation>Effacer la cellule cible</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5699"/>
        <source>Rectangle Fill</source>
        <translation>Remplissage rectangulaire</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5701"/>
        <source>Fill a dragged rectangle with the selected tile</source>
        <translation>Remplir un rectangle tracé avec la tuile sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5703"/>
        <source>Flip Stamp Horizontal</source>
        <translation>Retourner le tampon horizontalement</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5704"/>
        <source>Flip Stamp Vertical</source>
        <translation>Retourner le tampon verticalement</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5705"/>
        <source>Rotate Stamp 90° CW</source>
        <translation>Pivoter le tampon de 90° (sens horaire)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5709"/>
        <source>Fille&amp;d Shapes</source>
        <translation>Formes remplies</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5710"/>
        <source>&amp;Pixel Perfect</source>
        <translation>Pixel perfect</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5711"/>
        <source>Tolerance</source>
        <translation>Tolérance</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5712"/>
        <source>Magic-wand tolerance</source>
        <translation>Tolérance de la baguette magique</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5714"/>
        <source>Dither mode</source>
        <translation>Mode de tramage</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5715"/>
        <source>Ordered (Bayer)</source>
        <translation>Ordonné (Bayer)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5716"/>
        <source>Floyd–Steinberg</source>
        <translation>Floyd–Steinberg</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5717"/>
        <source>&amp;Extract from Image…</source>
        <translation>Extraire depuis une image…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5718"/>
        <source>Palette &amp;Swap…</source>
        <translation>Échange de palette…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5720"/>
        <source>Convert to Inde&amp;xed</source>
        <translation>Convertir en indexé</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5721"/>
        <source>&amp;Convert to RGBA</source>
        <translation>Convertir en RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5723"/>
        <source>Select &amp;All</source>
        <translation>Tout sélectionner</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5724"/>
        <source>&amp;Deselect</source>
        <translation>Désélectionner</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5725"/>
        <source>&amp;Invert Selection</source>
        <translation>Inverser la sélection</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5726"/>
        <source>&amp;Clear Selection</source>
        <translation>Effacer la sélection</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5728"/>
        <source>Flip &amp;Horizontal</source>
        <translation>Retourner horizontalement</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5729"/>
        <source>Flip &amp;Vertical</source>
        <translation>Retourner verticalement</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5730"/>
        <source>Rotate 90° C&amp;W</source>
        <translation>Pivoter de 90° (sens horaire)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5731"/>
        <source>Rotate 90° &amp;CCW</source>
        <translation>Pivoter de 90° (sens antihoraire)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5732"/>
        <source>&amp;Scale…</source>
        <translation>Mettre à l&apos;échelle…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5733"/>
        <source>Canvas S&amp;ize…</source>
        <translation>Taille du canvas…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5734"/>
        <source>&amp;Rotate (RotSprite)…</source>
        <translation>Pivoter (RotSprite)…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5736"/>
        <source>Guides &amp;&amp; &amp;Rulers</source>
        <translation>Repères &amp;&amp; règles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5737"/>
        <source>&amp;Isometric Grid</source>
        <translation>Grille isométrique</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5738"/>
        <source>&amp;Configure Isometric Grid…</source>
        <translation>Configurer la grille isométrique…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5739"/>
        <source>&amp;Perspective Grid</source>
        <translation>Grille en perspective</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5740"/>
        <source>Confi&amp;gure Perspective…</source>
        <translation>Configurer la perspective…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5741"/>
        <source>&amp;New View</source>
        <translation>Nouvelle vue</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5742"/>
        <source>Reference &amp;Board</source>
        <translation>Planche de référence</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5744"/>
        <source>&amp;File</source>
        <translation>Fichier</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5745"/>
        <source>&amp;Edit</source>
        <translation>Édition</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5746"/>
        <source>&amp;Select</source>
        <translation>Sélection</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5747"/>
        <source>&amp;Image</source>
        <translation>Image</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5748"/>
        <source>&amp;View</source>
        <translation>Affichage</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5749"/>
        <source>Visual Ai&amp;ds</source>
        <translation>Aides visuelles</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5750"/>
        <source>&amp;Palette</source>
        <translation>Palette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5751"/>
        <source>Tile&amp;map</source>
        <translation>Tilemap</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5752"/>
        <source>&amp;Automation</source>
        <translation>Automatisation</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5753"/>
        <source>&amp;Cloud</source>
        <translation>Cloud</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5754"/>
        <source>&amp;Library</source>
        <translation>Bibliothèque</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5756"/>
        <source>&amp;Register Active Document…</source>
        <translation>Inscrire le document actif…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5758"/>
        <source>Register &amp;Selection…</source>
        <translation>Inscrire la sélection…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5759"/>
        <source>&amp;Import Asset…</source>
        <translation>Importer une ressource…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5760"/>
        <source>&amp;Export Asset…</source>
        <translation>Exporter une ressource…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5761"/>
        <source>Export Project &amp;Bundle…</source>
        <translation>Exporter un paquet de projet…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5762"/>
        <source>I&amp;mport Project Bundle…</source>
        <translation>Importer un paquet de projet…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5763"/>
        <source>&amp;Theme</source>
        <translation>Thème</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5764"/>
        <source>La&amp;nguage</source>
        <translation>Langue</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5765"/>
        <source>&amp;Help</source>
        <translation>Aide</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5766"/>
        <source>&amp;User Guide</source>
        <translation>Guide de l&apos;utilisateur</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5767"/>
        <source>&amp;About PixelArt Creator</source>
        <translation>À propos de PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5772"/>
        <source>Washi &amp;&amp; Kintsugi</source>
        <translation>Washi &amp;&amp; Kintsugi</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5773"/>
        <source>Edo Night</source>
        <translation>Edo Night</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5774"/>
        <source>Arcade Kikko</source>
        <translation>Arcade Kikko</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5780"/>
        <source>&amp;Style</source>
        <translation>Style</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5781"/>
        <source>Choose the visual style</source>
        <translation>Choisir le style visuel</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5784"/>
        <source>Use system &amp;font</source>
        <translation>Utiliser la police système</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5786"/>
        <source>Use the operating system&apos;s interface font instead of Nifen Art</source>
        <translation>Utiliser la police d&apos;interface du système d&apos;exploitation au lieu de Nifen Art</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5789"/>
        <source>Pixel-perfect &amp;interface</source>
        <translation>Interface pixel perfect</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5792"/>
        <source>Scale the interface by whole numbers only (next launch)</source>
        <translation>Mettre l&apos;interface à l&apos;échelle par nombres entiers uniquement (au prochain lancement)</translation>
    </message>
</context>
<context>
    <name>New_Document_Dialog</name>
    <message>
        <location filename="../ui/new_document_dialog.py" line="78"/>
        <source>New Document</source>
        <translation>Nouveau document</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="79"/>
        <source>New document dialog</source>
        <translation>Boîte de dialogue Nouveau document</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="80"/>
        <source>Document width in pixels</source>
        <translation>Largeur du document en pixels</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="81"/>
        <source>Document height in pixels</source>
        <translation>Hauteur du document en pixels</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="82"/>
        <source>Width (px)</source>
        <translation>Largeur (px)</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="83"/>
        <source>Height (px)</source>
        <translation>Hauteur (px)</translation>
    </message>
</context>
<context>
    <name>Onion_Skin_Controls</name>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="105"/>
        <location filename="../ui/onion_skin_controls.py" line="173"/>
        <source>Previous frames</source>
        <extracomment>Emitted with the current :class:`OnionSettings` on any change (live update).</extracomment>
        <translation>Images précédentes</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="106"/>
        <location filename="../ui/onion_skin_controls.py" line="174"/>
        <source>Next frames</source>
        <translation>Images suivantes</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="132"/>
        <location filename="../ui/onion_skin_controls.py" line="180"/>
        <source>Previous-frame tint</source>
        <translation>Teinte de l&apos;image précédente</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="139"/>
        <location filename="../ui/onion_skin_controls.py" line="182"/>
        <source>Next-frame tint</source>
        <translation>Teinte de l&apos;image suivante</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="170"/>
        <source>Onion skin controls</source>
        <translation>Contrôles de la pelure d&apos;oignon</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="171"/>
        <source>Enable onion skinning</source>
        <translation>Activer la pelure d&apos;oignon</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="172"/>
        <source>Onion skin toggle</source>
        <translation>Activation de la pelure d&apos;oignon</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="175"/>
        <source>Previous onion frame count</source>
        <translation>Nombre d&apos;images précédentes de la pelure d&apos;oignon</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="176"/>
        <source>How many earlier frames to ghost</source>
        <translation>Nombre d&apos;images antérieures à afficher en transparence</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="177"/>
        <source>Next onion frame count</source>
        <translation>Nombre d&apos;images suivantes de la pelure d&apos;oignon</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="178"/>
        <source>How many later frames to ghost</source>
        <translation>Nombre d&apos;images ultérieures à afficher en transparence</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="179"/>
        <location filename="../ui/onion_skin_controls.py" line="181"/>
        <source>Tint…</source>
        <translation>Teinte…</translation>
    </message>
</context>
<context>
    <name>Overwrite_Confirm_Dialog</name>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="76"/>
        <source>Overwrite Existing Pixels?</source>
        <translation>Écraser les pixels existants ?</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="77"/>
        <source>Overwrite existing pixels confirmation</source>
        <translation>Confirmation d&apos;écrasement des pixels existants</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="80"/>
        <source>The destination already has pixels on it. Continuing replaces that content. This can be undone.</source>
        <translation>La destination contient déjà des pixels. Si vous continuez, ce contenu sera remplacé. Cette action peut être annulée.</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="84"/>
        <source>Overwrite warning</source>
        <translation>Avertissement d&apos;écrasement</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="85"/>
        <source>Don&apos;t ask again for this project</source>
        <translation>Ne plus demander pour ce projet</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="87"/>
        <source>Suppress this confirmation for the current project</source>
        <translation>Ne plus afficher cette confirmation pour le projet actuel</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="91"/>
        <location filename="../ui/overwrite_confirm_dialog.py" line="92"/>
        <source>Continue</source>
        <translation>Continuer</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="95"/>
        <location filename="../ui/overwrite_confirm_dialog.py" line="96"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
</context>
<context>
    <name>Palette_Analytics_View</name>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="171"/>
        <source>Palette Analytics</source>
        <extracomment>Edge of a colour-swatch icon in the table, px (presentation-only sizing). Debounce window (ms) coalescing a burst of deferred refresh requests into a single buffer scan (presentation-only timing, not a domain tuning value — cf. _SWATCH_PX). Short enough to feel instant when the dock becomes visible.</extracomment>
        <translation>Analyse de la palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="172"/>
        <source>Palette analytics view</source>
        <translation>Vue d&apos;analyse de la palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="173"/>
        <source>Colour usage counts</source>
        <translation>Nombre d&apos;utilisations des couleurs</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="175"/>
        <source>Colour / Index</source>
        <translation>Couleur / indice</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="175"/>
        <source>Usage count</source>
        <translation>Nombre d&apos;utilisations</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="177"/>
        <source>Refresh</source>
        <translation>Actualiser</translation>
    </message>
</context>
<context>
    <name>Palette_Constraint_Panel</name>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="60"/>
        <source>Constrain to Hardware Palette</source>
        <extracomment>Preset identifiers routed back to the shell (which owns the logic call). Emitted with a preset id (``PRESET_NES`` / ``PRESET_GAME_BOY``) on click.</extracomment>
        <translation>Contraindre à une palette matérielle</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="61"/>
        <source>Palette constraint presets</source>
        <translation>Préréglages de contrainte de palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="62"/>
        <source>Constrain to NES</source>
        <translation>Contraindre à la NES</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="63"/>
        <source>Constrain to Game Boy</source>
        <translation>Contraindre à la Game Boy</translation>
    </message>
</context>
<context>
    <name>Palette_Editor_Panel</name>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="225"/>
        <location filename="../ui/palette_editor_panel.py" line="229"/>
        <source>Add Colour</source>
        <extracomment>Edge of an editor swatch icon, px (presentation-only sizing). Maps a save/open dialog filter label to the ``palette_io`` format token. Emitted with an RGBA tuple when a swatch is selected (sets active colour).</extracomment>
        <translation>Ajouter une couleur</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="225"/>
        <source>The palette is full.</source>
        <translation>La palette est pleine.</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="244"/>
        <source>Remove Colour</source>
        <translation>Supprimer la couleur</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="256"/>
        <location filename="../ui/palette_editor_panel.py" line="270"/>
        <source>Reorder Palette</source>
        <translation>Réorganiser la palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="279"/>
        <location filename="../ui/palette_editor_panel.py" line="288"/>
        <source>Export Palette</source>
        <translation>Exporter la palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="295"/>
        <location filename="../ui/palette_editor_panel.py" line="305"/>
        <location filename="../ui/palette_editor_panel.py" line="307"/>
        <source>Import Palette</source>
        <translation>Importer la palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="321"/>
        <source>Palette Editor</source>
        <translation>Éditeur de palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="322"/>
        <source>Palette editor panel</source>
        <translation>Panneau de l&apos;éditeur de palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="323"/>
        <source>Editable colour palette</source>
        <translation>Palette de couleurs modifiable</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="324"/>
        <source>Add</source>
        <translation>Ajouter</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="325"/>
        <source>Add the active colour</source>
        <translation>Ajouter la couleur active</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="326"/>
        <source>Remove</source>
        <translation>Supprimer</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="327"/>
        <source>Move Up</source>
        <translation>Monter</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="328"/>
        <source>Move Down</source>
        <translation>Descendre</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="329"/>
        <source>Import…</source>
        <translation>Importer…</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="330"/>
        <source>Export…</source>
        <translation>Exporter…</translation>
    </message>
</context>
<context>
    <name>Palette_Panel</name>
    <message>
        <location filename="../ui/main_window.py" line="545"/>
        <source>Colour palette</source>
        <extracomment>Stable cloud recovery-slot key for the working document when no named cloud project is active (presentation-only identifier, not a domain tuning value). A sensible starter palette for a new document (usability, not a spec value). Swatch icon edge, px (presentation-only sizing, not a domain tuning value). Filename of the app-level Favourites store under AppConfigLocation (ADR-0004). Longest edge of a RotSprite preview thumbnail, px (presentation-only sizing, not a domain tuning value — cf. _SWATCH_PX). Tool ids whose stroke WRITES the active colour to the buffer: the value written is ``ctx.paint_value()`` / ``ctx.active_color`` itself, not merely a live-preview tint. These five run under REQ-P3-UI-006 leg (2) from a completed colour-hub pick; the other six tool ids (eraser, the three selection tools, picker, dither) hide the hub&apos;s wheel/value/numeric/harmony pick surface (``set_pick_surface_visible``) and never run from a hub pick, even a Favourites activation (SC-U006-13). Tool identifiers, not numeric tuning values, so this stays a set of the tools&apos; own ``tool_id`` class attributes rather than a `constants.py` entry. FIX 3 (2026-08-24 field defect, RC-1 follow-up). Every right-hand &quot;workflow&quot; panel is tabified into ONE dock group (``_add_workflow_dock``), and a Qt tab group&apos;s minimum width is the MAXIMUM over its members&apos; own content-derived ``minimumSizeHint()`` — verified up to 766 px for one panel (probe-runtime-canvas-20260824.py). That floor overrides FIX 1&apos;s ``CANVAS_PANE_WIDTH_RATIO`` split regardless of window width, so no per-panel edit can fix it: the override has to happen once, here, at the single place every workflow dock is created. Overriding ``QWidget.setMinimumWidth()`` on the panel (verified empirically to lower ``QDockWidget.minimumSizeHint()`` even though the panel&apos;s own ``minimumSizeHint()`` is unchanged and content can clip below it — Qt&apos;s dock layout consults the explicit minimum, not the generic ``QLayoutItem.minimumSize()`` ``expandedTo`` rule) is presentation sizing, not a domain tuning value, so it stays local exactly like _SWATCH_PX / _PREVIEW_MAX_EDGE_PX above — see the FIX-3 report note requesting this be promoted to logic/constants.py (a logic-layer surface) as e.g. ``WORKFLOW_DOCK_MIN_WIDTH_PX`` rather than reached into from here. FIX 3 (2026-08-24 field defect). Bound on ``Main_Window._settle_width()``&apos;s event-flush loop (presentation-only startup timing, not a domain tuning value — cf. _SWATCH_PX / _PREVIEW_MAX_EDGE_PX above). Observed settling in 2 passes on the probe&apos;s offscreen run; this leaves generous headroom without risking an unbounded/hanging wait on a layout that never settles. FIX 1 (2026-08-24 field defect, RC-1 follow-up on the earlier FIX 1). The window was never given an explicit default size; Qt sized it to its layout hint, which on a real desktop happened to land the canvas at only ~10% of the window even after the FIX 1/FIX 3 dock-splitting work above, because that split is a RATIO of whatever width the window already has -- a window with no deliberate width defeats a width RATIO. Fraction of the primary screen&apos;s *available* geometry (excludes taskbars/docks) the window claims on first launch, absent any saved geometry restore (presentation-only startup sizing, not a domain tuning value -- cf. _WORKFLOW_DOCK_MIN_WIDTH_PX / _SWATCH_PX above). Report note: a candidate for promotion to logic/constants.py as e.g. DEFAULT_LAUNCH_SIZE_RATIO, exactly like that floor&apos;s own promotion note -- left local here on the same precedent.</extracomment>
        <translation>Palette de couleurs</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="546"/>
        <source>Palette panel</source>
        <translation>Panneau de la palette</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="547"/>
        <source>Colour mode</source>
        <translation>Mode de couleur</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="552"/>
        <source>Mode: Indexed</source>
        <translation>Mode : indexé</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="554"/>
        <source>Mode: RGBA</source>
        <translation>Mode : RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="556"/>
        <source>Mode: —</source>
        <translation>Mode : —</translation>
    </message>
</context>
<context>
    <name>Palette_Swap_Dialog</name>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="102"/>
        <source>Palette Swap</source>
        <translation>Échange de palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="103"/>
        <source>Palette swap dialog</source>
        <translation>Boîte de dialogue Échange de palette</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="104"/>
        <source>From index</source>
        <translation>De l&apos;indice</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="105"/>
        <source>To index</source>
        <translation>À l&apos;indice</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="106"/>
        <source>Source index</source>
        <translation>Indice source</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="107"/>
        <source>Target index</source>
        <translation>Indice cible</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="108"/>
        <source>Add</source>
        <translation>Ajouter</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="109"/>
        <source>Remove</source>
        <translation>Supprimer</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="110"/>
        <source>Index remap entries</source>
        <translation>Entrées de remappage des indices</translation>
    </message>
</context>
<context>
    <name>Playback_Controls</name>
    <message>
        <location filename="../ui/playback_controls.py" line="364"/>
        <source>Loop</source>
        <extracomment>Type of the per-tick step yielded by the sequencing engine: (index, ms). Emitted with the frame index to display on each playback tick (scrub-like). Emitted ``True`` when playback becomes active, ``False`` when it halts. The shell suppresses onion skinning while active (CL-11).</extracomment>
        <translation>Boucle</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="365"/>
        <source>Once</source>
        <translation>Une fois</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="366"/>
        <source>Ping-Pong</source>
        <translation>Ping-pong</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="367"/>
        <source>Reverse</source>
        <translation>Inverse</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="372"/>
        <source>Playback controls</source>
        <translation>Contrôles de lecture</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="373"/>
        <location filename="../ui/playback_controls.py" line="375"/>
        <source>Play</source>
        <translation>Lecture</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="374"/>
        <source>Play (Space)</source>
        <translation>Lecture (Space)</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="376"/>
        <location filename="../ui/playback_controls.py" line="378"/>
        <source>Pause</source>
        <translation>Pause</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="377"/>
        <source>Pause (Space)</source>
        <translation>Pause (Space)</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="379"/>
        <location filename="../ui/playback_controls.py" line="381"/>
        <source>Stop</source>
        <translation>Arrêter</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="380"/>
        <source>Stop and return to the start frame</source>
        <translation>Arrêter et revenir à l&apos;image de départ</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="382"/>
        <source>Playback mode</source>
        <translation>Mode de lecture</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="383"/>
        <source>Global playback mode</source>
        <translation>Mode de lecture global</translation>
    </message>
</context>
<context>
    <name>Plugin_Manager_Panel</name>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="133"/>
        <source>Add Plugin Manifest</source>
        <extracomment>Enabled plugin handles keyed by plugin name (view/session state).</extracomment>
        <translation>Ajouter un manifeste de plugin</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="135"/>
        <source>Manifest files (*.json)</source>
        <translation>Fichiers manifestes (*.json)</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="142"/>
        <source>Install Failed</source>
        <translation>Échec de l&apos;installation</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="165"/>
        <source>No Manifest</source>
        <translation>Aucun manifeste</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="167"/>
        <source>This plugin has no loaded manifest. Use Add Manifest to load its declared permissions before enabling it.</source>
        <translation>Ce plugin n&apos;a aucun manifeste chargé. Utilisez Ajouter un manifeste pour charger ses permissions déclarées avant de l&apos;activer.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="174"/>
        <source>Enable Plugin</source>
        <translation>Activer le plugin</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="176"/>
        <source>Enable %1 and grant it these permissions?

%2

The plugin runs sandboxed and can only edit through reversible commands. It cannot reach the UI, filesystem, or network.</source>
        <translation>Activer %1 et lui accorder ces permissions ?

%2

Le plugin s&apos;exécute dans un bac à sable et ne peut effectuer de modifications que par des commandes réversibles. Il ne peut accéder ni à l&apos;interface, ni au système de fichiers, ni au réseau.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="188"/>
        <source>Enable Failed</source>
        <translation>Échec de l&apos;activation</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="215"/>
        <source>enabled</source>
        <translation>activé</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="215"/>
        <source>disabled</source>
        <translation>désactivé</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="216"/>
        <source>%1 v%2 — %3</source>
        <translation>%1 v%2 — %3</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="245"/>
        <source>(no manifest loaded — permissions unknown)</source>
        <translation>(aucun manifeste chargé — permissions inconnues)</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="258"/>
        <source>Select a plugin to view its permissions.</source>
        <translation>Sélectionnez un plugin pour afficher ses permissions.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="268"/>
        <source>Refresh</source>
        <translation>Actualiser</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="269"/>
        <source>Add Manifest…</source>
        <translation>Ajouter un manifeste…</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="270"/>
        <source>Enable</source>
        <translation>Activer</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="271"/>
        <source>Disable</source>
        <translation>Désactiver</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="272"/>
        <source>Declared permissions:</source>
        <translation>Permissions déclarées :</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="273"/>
        <source>Plugin manager</source>
        <translation>Gestionnaire de plugins</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="274"/>
        <source>Discovered and installed plugins</source>
        <translation>Plugins détectés et installés</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="275"/>
        <source>Selected plugin permissions</source>
        <translation>Permissions du plugin sélectionné</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="276"/>
        <source>Refresh the plugin list</source>
        <translation>Actualiser la liste des plugins</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="277"/>
        <source>Add a plugin manifest</source>
        <translation>Ajouter un manifeste de plugin</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="278"/>
        <source>Enable the selected plugin</source>
        <translation>Activer le plugin sélectionné</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="279"/>
        <source>Disable the selected plugin</source>
        <translation>Désactiver le plugin sélectionné</translation>
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
        <translation>Présence</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="101"/>
        <source>Open a shared project first.</source>
        <translation>Ouvrez d&apos;abord un projet partagé.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="109"/>
        <source>Enter your member id to announce presence.</source>
        <translation>Saisissez votre identifiant de membre pour signaler votre présence.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="157"/>
        <source>Members currently present in the shared project. Presence is ephemeral and is never saved into the project file.</source>
        <translation>Membres actuellement présents dans le projet partagé. La présence est éphémère et n&apos;est jamais enregistrée dans le fichier du projet.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="161"/>
        <location filename="../ui/presence_panel.py" line="162"/>
        <source>Your member id</source>
        <translation>Votre identifiant de membre</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="163"/>
        <source>Join</source>
        <translation>Rejoindre</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="164"/>
        <source>Announce your presence</source>
        <translation>Signaler votre présence</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="165"/>
        <source>Leave</source>
        <translation>Quitter</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="166"/>
        <source>Clear your presence</source>
        <translation>Effacer votre présence</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="167"/>
        <source>Present members</source>
        <translation>Membres présents</translation>
    </message>
</context>
<context>
    <name>Prewarm_Indicator</name>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="81"/>
        <source>Playback preparation progress</source>
        <extracomment>Emitted when the user cancels the pre-warm (wired to Stop by the shell).</extracomment>
        <translation>Progression de la préparation de la lecture</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="82"/>
        <source>Preparing playback…</source>
        <translation>Préparation de la lecture…</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="83"/>
        <source>Frames prepared</source>
        <translation>Images préparées</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="84"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="85"/>
        <location filename="../ui/prewarm_indicator.py" line="86"/>
        <source>Cancel playback preparation</source>
        <translation>Annuler la préparation de la lecture</translation>
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
        <translation> px</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="150"/>
        <source>Running…</source>
        <translation>Exécution en cours…</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="152"/>
        <source>Done</source>
        <translation>Terminé</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="153"/>
        <source>Idle</source>
        <translation>En attente</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="168"/>
        <source>Procedural Generation</source>
        <translation>Génération procédurale</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="191"/>
        <source>Value noise</source>
        <translation>Bruit de valeur</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="192"/>
        <source>Gradient noise</source>
        <translation>Bruit de gradient</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="193"/>
        <source>OpenSimplex noise</source>
        <translation>Bruit OpenSimplex</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="194"/>
        <source>Cellular automata</source>
        <translation>Automates cellulaires</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="195"/>
        <source>Dithered gradient</source>
        <translation>Dégradé tramé</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="201"/>
        <source>Algorithm</source>
        <translation>Algorithme</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="202"/>
        <source>Seed</source>
        <translation>Graine</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="203"/>
        <source>Width</source>
        <translation>Largeur</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="204"/>
        <source>Height</source>
        <translation>Hauteur</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="205"/>
        <source>Frequency</source>
        <translation>Fréquence</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="206"/>
        <source>Octaves</source>
        <translation>Octaves</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="209"/>
        <source>Generate</source>
        <translation>Générer</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="211"/>
        <source>Procedural generation</source>
        <translation>Génération procédurale</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="212"/>
        <source>Generation algorithm</source>
        <translation>Algorithme de génération</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="213"/>
        <source>Random seed</source>
        <translation>Graine aléatoire</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="214"/>
        <source>Output width in pixels</source>
        <translation>Largeur de sortie en pixels</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="215"/>
        <source>Output height in pixels</source>
        <translation>Hauteur de sortie en pixels</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="216"/>
        <source>Noise base frequency</source>
        <translation>Fréquence de base du bruit</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="217"/>
        <source>Noise octaves</source>
        <translation>Octaves du bruit</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="218"/>
        <source>Generate content</source>
        <translation>Générer le contenu</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="219"/>
        <source>Progress</source>
        <translation>Progression</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="220"/>
        <source>Generation progress</source>
        <translation>Progression de la génération</translation>
    </message>
</context>
<context>
    <name>Provider_Config_Dialog</name>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="257"/>
        <source>The OS keyring is unavailable; install the &apos;assistant_live&apos; extra to store an API key. The provider settings were saved.</source>
        <extracomment>Provider-kind identifiers. These double as the keyring service namespace segment (``pixelart-creator:assistant:{provider}``) and the adapter&apos;s ``provider`` arg, so the key stored here is the key the adapter loads. Module-local vocabulary (ADR-0001), not a numeric constant. The keyring account the single-user key is stored under (matches ``data/llm``&apos;s ``_DEFAULT_ACCOUNT`` so the adapter loads the same credential). :class:`QSettings` group + keys for the NON-SECRET configuration only. Sensible default endpoints per provider kind (the user may override).</extracomment>
        <translation>Le trousseau de clés du système est indisponible ; installez l&apos;extra « assistant_live » pour stocker une clé d&apos;API. Les paramètres du fournisseur ont été enregistrés.</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="267"/>
        <source>Could not store the API key: {0}</source>
        <translation>Impossible de stocker la clé d&apos;API : {0}</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="275"/>
        <source>Configure AI Assistant Provider</source>
        <translation>Configurer le fournisseur de l&apos;assistant IA</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="276"/>
        <source>AI assistant provider configuration</source>
        <translation>Configuration du fournisseur de l&apos;assistant IA</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="277"/>
        <source>OpenAI-compatible</source>
        <translation>Compatible OpenAI</translation>
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
        <translation>Fournisseur</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="281"/>
        <source>Endpoint URL</source>
        <translation>URL du point de terminaison</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="282"/>
        <source>Provider endpoint URL</source>
        <translation>URL du point de terminaison du fournisseur</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="283"/>
        <source>https://…</source>
        <translation>https://…</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="284"/>
        <source>Model</source>
        <translation>Modèle</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="285"/>
        <source>Model name</source>
        <translation>Nom du modèle</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="286"/>
        <source>e.g. gpt-4o-mini</source>
        <translation>p. ex. gpt-4o-mini</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="287"/>
        <source>API key</source>
        <translation>Clé d&apos;API</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="288"/>
        <source>API key (stored in the OS keyring)</source>
        <translation>Clé d&apos;API (stockée dans le trousseau de clés du système)</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="290"/>
        <source>Leave blank to keep the existing key</source>
        <translation>Laissez vide pour conserver la clé existante</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="294"/>
        <source>The API key is stored only in your OS keyring — never in a project file or a log.</source>
        <translation>La clé d&apos;API est stockée uniquement dans le trousseau de clés de votre système, jamais dans un fichier de projet ni dans un journal.</translation>
    </message>
</context>
<context>
    <name>Real_Size_Calibration_Dialog</name>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="82"/>
        <source> mm</source>
        <extracomment>On-screen calibration bar length in device-independent px (a known ruler the user matches against a real ruler / credit card to derive the true DPI). Millimetres per inch (calibration converts a measured mm length to DPI).</extracomment>
        <translation> mm</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="109"/>
        <source>Calibrate Real Size</source>
        <translation>Étalonner la taille réelle</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="112"/>
        <source>Hold a ruler against the bar below and enter its measured length so real size matches your screen.</source>
        <translation>Placez une règle contre la barre ci-dessous et saisissez sa longueur mesurée afin que la taille réelle corresponde à votre écran.</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="116"/>
        <source>Measured length</source>
        <translation>Longueur mesurée</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="118"/>
        <source>Measured calibration bar length in millimetres</source>
        <translation>Longueur mesurée de la barre d&apos;étalonnage, en millimètres</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="120"/>
        <source>Calibration bar</source>
        <translation>Barre d&apos;étalonnage</translation>
    </message>
</context>
<context>
    <name>Real_Size_Preview_Window</name>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="255"/>
        <source>calibrated</source>
        <extracomment>A user-calibrated DPI override (``None`` =&gt; use the queried physical DPI).</extracomment>
        <translation>étalonné</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="255"/>
        <source>screen</source>
        <translation>écran</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="258"/>
        <source>Real size: {0:.0f} PPI ({1}), scale {2:.2f}×</source>
        <translation>Taille réelle : {0:.0f} PPI ({1}), échelle {2:.2f}×</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="264"/>
        <source>Real-Size Preview</source>
        <translation>Aperçu à taille réelle</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="265"/>
        <source>Real-size preview</source>
        <translation>Aperçu à taille réelle</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="266"/>
        <source>Real-size document preview</source>
        <translation>Aperçu du document à taille réelle</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="267"/>
        <source>Calibrate…</source>
        <translation>Étalonner…</translation>
    </message>
</context>
<context>
    <name>Recovery_Prompt</name>
    <message>
        <location filename="../ui/recovery_prompt.py" line="74"/>
        <source>Recover Unsaved Work</source>
        <translation>Récupérer le travail non enregistré</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="77"/>
        <source>Unsaved work from a previous session was found. Recover it into a new tab? Your last explicit save is not affected.</source>
        <translation>Un travail non enregistré d&apos;une session précédente a été trouvé. Le récupérer dans un nouvel onglet ? Votre dernier enregistrement manuel n&apos;est pas affecté.</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="81"/>
        <source>Recover</source>
        <translation>Récupérer</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="82"/>
        <source>Discard</source>
        <translation>Abandonner</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="83"/>
        <source>Recover unsaved work</source>
        <translation>Récupérer le travail non enregistré</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="84"/>
        <source>Discard unsaved work</source>
        <translation>Abandonner le travail non enregistré</translation>
    </message>
</context>
<context>
    <name>Reference_Board</name>
    <message>
        <location filename="../ui/reference_board.py" line="319"/>
        <source>Reference board full</source>
        <extracomment>Emitted with the picked RGBA tuple when a plain wheel notch travels the shared Favourites cursor (REQ-IS-UI-008, D-16). The board never touches the document/buffers/undo stack (REQ-P9-UI-010); this only sets the app-wide active colour/palette state, same as every other surface. The persisted Favourites model bound via :meth:`set_favourites_model` (D-16); ``None`` until the shell binds one.</extracomment>
        <translation>Planche de référence pleine</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/reference_board.py" line="321"/>
        <source>The board already holds the maximum of %n images.</source>
        <translation>
            <numerusform>La planche contient déjà le maximum de %n image.</numerusform>
            <numerusform>La planche contient déjà le maximum de %n images.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="331"/>
        <source>Cannot load image</source>
        <translation>Impossible de charger l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="332"/>
        <source>The file could not be read as an image: {0}</source>
        <translation>Le fichier n&apos;a pas pu être lu comme une image : {0}</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="403"/>
        <source>Save Reference Board</source>
        <translation>Enregistrer la planche de référence</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="405"/>
        <location filename="../ui/reference_board.py" line="419"/>
        <source>Reference board (*.pixboard)</source>
        <translation>Planche de référence (*.pixboard)</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="412"/>
        <source>Save failed</source>
        <translation>Échec de l&apos;enregistrement</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="417"/>
        <source>Open Reference Board</source>
        <translation>Ouvrir la planche de référence</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="427"/>
        <source>Open failed</source>
        <translation>Échec de l&apos;ouverture</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="434"/>
        <source>Add Reference Image</source>
        <translation>Ajouter une image de référence</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="436"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>Images (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="502"/>
        <source>Reference Board</source>
        <translation>Planche de référence</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="503"/>
        <source>Reference board</source>
        <translation>Planche de référence</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="504"/>
        <source>Reference board canvas</source>
        <translation>Canvas de la planche de référence</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="505"/>
        <source>Add Image…</source>
        <translation>Ajouter une image…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="506"/>
        <source>Save…</source>
        <translation>Enregistrer…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="507"/>
        <source>Open…</source>
        <translation>Ouvrir…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="508"/>
        <source>Always on Top</source>
        <translation>Toujours au premier plan</translation>
    </message>
</context>
<context>
    <name>Reference_Item</name>
    <message>
        <location filename="../ui/reference_board.py" line="246"/>
        <source>Raise</source>
        <extracomment>Per-wheel-notch board zoom step. Corner grab-handle edge, in item-local px (REQ-P9-UI-006 resize gesture). No matching UI-metric constant exists in ``logic/constants.py`` today (gap reported in this task&apos;s EXIT_STATUS); this module already keeps its own UI-only metrics locally (see ``_BOARD_ZOOM_STEP`` above), so the same convention is followed here rather than inlining a literal (S12). Minimum absolute scale factor a corner-drag resize may reach (guards against a degenerate/zero-size or inverted reference item). Opposite-corner anchor used while resizing (the anchor stays fixed).</extracomment>
        <translation>Placer devant</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="249"/>
        <source>Lower</source>
        <translation>Placer derrière</translation>
    </message>
</context>
<context>
    <name>RotSprite_Dialog</name>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="90"/>
        <source>No preview</source>
        <extracomment>Angle input bounds, degrees (a full turn either way; not a domain tuning value). Preview label edge, px (presentation-only sizing). Renders a preview :class:`QImage` for a candidate angle (or ``None``).</extracomment>
        <translation>Aucun aperçu</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="103"/>
        <source>Rotate (RotSprite)</source>
        <translation>Pivoter (RotSprite)</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="104"/>
        <source>RotSprite rotation dialog</source>
        <translation>Boîte de dialogue de rotation RotSprite</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="105"/>
        <source>Rotation angle in degrees</source>
        <translation>Angle de rotation en degrés</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="106"/>
        <source>Rotation preview</source>
        <translation>Aperçu de la rotation</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="107"/>
        <source>Angle (deg)</source>
        <translation>Angle (°)</translation>
    </message>
</context>
<context>
    <name>Ruler_Strip</name>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="347"/>
        <source>Horizontal ruler</source>
        <extracomment>z-order in the aid band, just below the grid overlays so guides read under grids. Ruler strip thickness in device-independent px (presentation sizing). Default overlay/ruler colours (overridden by the theme&apos;s role colours, 025). Emitted ``(orientation, doc_position)`` when a guide is dragged out.</extracomment>
        <translation>Règle horizontale</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="349"/>
        <source>Drag down to create a horizontal guide</source>
        <translation>Faites glisser vers le bas pour créer un repère horizontal</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="352"/>
        <source>Vertical ruler</source>
        <translation>Règle verticale</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="354"/>
        <source>Drag right to create a vertical guide</source>
        <translation>Faites glisser vers la droite pour créer un repère vertical</translation>
    </message>
</context>
<context>
    <name>Scale_Dialog</name>
    <message>
        <location filename="../ui/transform_dialog.py" line="107"/>
        <source>Scale Canvas</source>
        <translation>Mettre le canvas à l&apos;échelle</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="108"/>
        <source>Scale canvas dialog</source>
        <translation>Boîte de dialogue de mise à l&apos;échelle du canvas</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="109"/>
        <source>Scale factor</source>
        <translation>Facteur d&apos;échelle</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="110"/>
        <source>Target width in pixels</source>
        <translation>Largeur cible en pixels</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="111"/>
        <source>Target height in pixels</source>
        <translation>Hauteur cible en pixels</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="112"/>
        <source>Factor</source>
        <translation>Facteur</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="113"/>
        <source>Width (px)</source>
        <translation>Largeur (px)</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="114"/>
        <source>Height (px)</source>
        <translation>Hauteur (px)</translation>
    </message>
</context>
<context>
    <name>Script_Runner_Panel</name>
    <message>
        <location filename="../ui/script_runner_panel.py" line="113"/>
        <source>Running…</source>
        <extracomment>A compact, copy-pasteable example so the empty editor is self-documenting. ``(ops, label)`` — the host should dispatch these DSL ops on the worker as one undoable grouped command (REQ-P8-UI-004/-009).</extracomment>
        <translation>Exécution en cours…</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="115"/>
        <source>Done</source>
        <translation>Terminé</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="116"/>
        <source>Idle</source>
        <translation>En attente</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="131"/>
        <source>Invalid JSON: %1</source>
        <translation>JSON non valide : %1</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="133"/>
        <source>A script must be a JSON array of steps.</source>
        <translation>Un script doit être un tableau JSON d&apos;étapes.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="138"/>
        <source>Each step needs a &apos;name&apos; and optional &apos;params&apos;/&apos;seed&apos;.</source>
        <translation>Chaque étape nécessite un « name », ainsi que des « params » et un « seed » facultatifs.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="144"/>
        <source>Step &apos;name&apos; must be a string.</source>
        <translation>Le « name » d&apos;une étape doit être une chaîne de caractères.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="146"/>
        <source>Step &apos;params&apos; must be an object.</source>
        <translation>Les « params » d&apos;une étape doivent être un objet.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="158"/>
        <source>Script Error</source>
        <translation>Erreur de script</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="162"/>
        <location filename="../ui/script_runner_panel.py" line="184"/>
        <source>Run Script</source>
        <translation>Exécuter le script</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="183"/>
        <source>DSL script (JSON list of steps):</source>
        <translation>Script DSL (liste JSON d&apos;étapes) :</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="185"/>
        <source>Script runner</source>
        <translation>Exécuteur de scripts</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="186"/>
        <source>Script source</source>
        <translation>Source du script</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="187"/>
        <source>Run the script</source>
        <translation>Exécuter le script</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="188"/>
        <source>Progress</source>
        <translation>Progression</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="189"/>
        <source>Script run progress</source>
        <translation>Progression de l&apos;exécution du script</translation>
    </message>
</context>
<context>
    <name>Shade_Ramp_Picker</name>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="150"/>
        <source>Shade Ramps</source>
        <extracomment>Edge of a ramp swatch button, px (presentation-only sizing). Emitted with an RGBA tuple when a ramp swatch is activated. Emitted with a list of RGBA colours when a whole ramp is added.</extracomment>
        <translation>Rampes de tons</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="151"/>
        <source>Shade ramp picker</source>
        <translation>Sélecteur de rampe de tons</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="152"/>
        <source>Shades (toward black)</source>
        <translation>Tons foncés (vers le noir)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="153"/>
        <source>Tints (toward white)</source>
        <translation>Tons clairs (vers le blanc)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="154"/>
        <source>Tones (toward grey)</source>
        <translation>Tons grisés (vers le gris)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="156"/>
        <source>Add to Palette</source>
        <translation>Ajouter à la palette</translation>
    </message>
</context>
<context>
    <name>Shared_Projects_Panel</name>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="143"/>
        <location filename="../ui/shared_projects_panel.py" line="150"/>
        <location filename="../ui/shared_projects_panel.py" line="182"/>
        <location filename="../ui/shared_projects_panel.py" line="189"/>
        <location filename="../ui/shared_projects_panel.py" line="196"/>
        <source>Shared Project</source>
        <extracomment>Fixed display order for the role combo (a stable subset of the module-local :data:`MEMBER_ROLES` vocabulary; presentation ordering, not a domain value). The roster being edited before it is committed via Share/Update.</extracomment>
        <translation>Projet partagé</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="144"/>
        <source>Member %1 is already in the roster.</source>
        <translation>Le membre %1 figure déjà dans la liste.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/shared_projects_panel.py" line="152"/>
        <source>A shared project may have at most %n members.</source>
        <translation>
            <numerusform>Un projet partagé peut compter %n membre au maximum.</numerusform>
            <numerusform>Un projet partagé peut compter %n membres au maximum.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="183"/>
        <source>Enter a shared-project name first.</source>
        <translation>Saisissez d&apos;abord un nom de projet partagé.</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="190"/>
        <source>Add at least one member before sharing.</source>
        <translation>Ajoutez au moins un membre avant de partager.</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="238"/>
        <source>Owner</source>
        <translation>Propriétaire</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="239"/>
        <source>Editor</source>
        <translation>Éditeur</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="240"/>
        <source>Viewer</source>
        <translation>Lecteur</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="245"/>
        <source>Shared projects</source>
        <translation>Projets partagés</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="246"/>
        <source>Shared-project name:</source>
        <translation>Nom du projet partagé :</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="247"/>
        <source>e.g. team-sprite</source>
        <translation>p. ex. team-sprite</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="248"/>
        <source>Shared-project name</source>
        <translation>Nom du projet partagé</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="249"/>
        <location filename="../ui/shared_projects_panel.py" line="250"/>
        <source>Member id to invite</source>
        <translation>Identifiant du membre à inviter</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="251"/>
        <source>Member role</source>
        <translation>Rôle du membre</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="254"/>
        <source>Add Member</source>
        <translation>Ajouter un membre</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="255"/>
        <source>Add member to roster</source>
        <translation>Ajouter un membre à la liste</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="256"/>
        <source>Roster to share</source>
        <translation>Liste à partager</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="257"/>
        <source>Current members</source>
        <translation>Membres actuels</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="258"/>
        <source>Remove</source>
        <translation>Supprimer</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="259"/>
        <source>Remove selected member</source>
        <translation>Supprimer le membre sélectionné</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="260"/>
        <source>Share / Update</source>
        <translation>Partager / Mettre à jour</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="261"/>
        <source>Share or update the project</source>
        <translation>Partager ou mettre à jour le projet</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="262"/>
        <source>Member</source>
        <translation>Membre</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="262"/>
        <source>Role</source>
        <translation>Rôle</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="265"/>
        <source>Editable member roster</source>
        <translation>Liste des membres modifiable</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="266"/>
        <source>Shared member list</source>
        <translation>Liste des membres partagés</translation>
    </message>
</context>
<context>
    <name>Symmetry_Panel</name>
    <message>
        <location filename="../ui/symmetry_panel.py" line="155"/>
        <source>Off</source>
        <extracomment>Emitted with the newly selected :class:`SymmetryAxis`. Emitted with the mirror centre as ``Optional[Tuple[int, int]]`` once the user edits a position spinbox (``None`` = unset, ``mirror`` defaults to the canvas centre itself, CL-9). Never emitted from programmatic :meth:`set_canvas_size` calls, so a resize alone never fabricates a user-authored position. Axis order shown in the combo (value stored in the item&apos;s user data).</extracomment>
        <translation>Désactivée</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="156"/>
        <source>Vertical</source>
        <translation>Verticale</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="157"/>
        <source>Horizontal</source>
        <translation>Horizontale</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="158"/>
        <source>Both</source>
        <translation>Les deux</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="159"/>
        <source>Diagonal</source>
        <translation>Diagonale</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="163"/>
        <source>Symmetry</source>
        <translation>Symétrie</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="164"/>
        <source>Axis position</source>
        <translation>Position de l&apos;axe</translation>
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
        <translation>Réinitialiser au centre</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="168"/>
        <source>Symmetry axis panel</source>
        <translation>Panneau de l&apos;axe de symétrie</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="169"/>
        <source>Symmetry axis</source>
        <translation>Axe de symétrie</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="170"/>
        <source>Symmetry axis position X</source>
        <translation>Position X de l&apos;axe de symétrie</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="171"/>
        <source>Symmetry axis position Y</source>
        <translation>Position Y de l&apos;axe de symétrie</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="173"/>
        <source>Reset symmetry axis position to centre</source>
        <translation>Réinitialiser la position de l&apos;axe de symétrie au centre</translation>
    </message>
</context>
<context>
    <name>Tag_Dialog</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="145"/>
        <location filename="../ui/frame_tags_panel.py" line="187"/>
        <source>Tag colour</source>
        <translation>Couleur de l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="174"/>
        <source>Frame Tag</source>
        <translation>Étiquette d&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="175"/>
        <source>Name</source>
        <translation>Nom</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="176"/>
        <source>From frame</source>
        <translation>De l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="177"/>
        <source>To frame</source>
        <translation>À l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="178"/>
        <source>Mode</source>
        <translation>Mode</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="179"/>
        <source>Repeat (0 = infinite)</source>
        <translation>Répétitions (0 = infini)</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="180"/>
        <source>Colour</source>
        <translation>Couleur</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="181"/>
        <source>Tag name</source>
        <translation>Nom de l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="182"/>
        <source>Tag start frame</source>
        <translation>Image de début de l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="183"/>
        <source>Tag end frame</source>
        <translation>Image de fin de l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="184"/>
        <source>Tag playback mode</source>
        <translation>Mode de lecture de l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="185"/>
        <source>Tag repeat count</source>
        <translation>Nombre de répétitions de l&apos;étiquette</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="186"/>
        <source>Colour…</source>
        <translation>Couleur…</translation>
    </message>
</context>
<context>
    <name>Tile_Edit_Dialog</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="191"/>
        <source>Edit Tile</source>
        <translation>Modifier la tuile</translation>
    </message>
</context>
<context>
    <name>Tilemap_Canvas</name>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="732"/>
        <source>Auto-tile</source>
        <extracomment>Initial scene window (px) for a fresh infinite map; grows to include stamps. Edge (px) of one checker square drawn behind the map (presentation-only). Platform name Qt reports with no windowing system (keep the raster viewport). MiB budget of the chunk pixmap LRU (D1). A 16x16 chunk at 16 px tiles is a 256x256 RGBA pixmap (~256 KiB), so ~128 MiB keeps a large working set resident while staying bounded on an infinite / fully filled map. Presentation/resource sizing (like frame_cache&apos;s budget), so it lives here in ui/, not logic/constants. Max cold chunks rendered *inline* per paint before the rest stream off-thread (D4). A cold chunk is ~0.84 ms (measured), so a handful stays well under the 16 ms budget and keeps a stamp / small pan instant; a full cold viewport streams. Bounded wait (ms) for an in-flight off-thread chunk render to finish on rebind / window close before the pool is torn down (mirrors canvas_scene&apos;s shutdown wait). Emitted after a layer&apos;s auto-tile mode changes (drives the panel checkbox). Emitted when a stamp/fill is refused because the tilemap has no tileset bound yet (CI-red field defect, 2026-08-24: the original FIX 5 routed this refusal through a blocking ``QMessageBox.warning``, which hangs a headless parallel worker with nothing to dismiss it). Follows the ``Canvas_View.lockedLayerEditRejected`` precedent exactly -- a signal the shell surfaces non-blockingly, never a modal, for a refusal reachable from a plain mouse gesture. Emitted when a stamp/fill is refused because no tile is selected as the active brush (a tileset IS bound; the brush gid is 0). Kept distinct from ``noTilesetBoundRejected`` so the shell shows the honest message for each case, exactly as the two ``_warn_no_active_brush`` branches already did. Emitted with the picked RGBA tuple when a plain wheel notch / an unmodified middle click travels the shared Favourites cursor (REQ-IS-UI-008/-012). Mirrors ``Canvas_View.colorPicked`` — the tilemap has no colour of its own to paint with, but the app-wide active colour/palette state is shared across every surface. A middle press awaiting the click/drag verdict — see ``Canvas_View._middle_pending`` (REQ-IS-UI-011); same behaviour here. The persisted Favourites model bound via :meth:`set_favourites_model` ``None`` until the shell binds one.</extracomment>
        <translation>Tuilage automatique</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="990"/>
        <source>Stamp</source>
        <translation>Tamponner</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="992"/>
        <source>Stamp Tile</source>
        <translation>Tamponner une tuile</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1001"/>
        <source>Erase</source>
        <translation>Effacer</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1003"/>
        <source>Erase Tile</source>
        <translation>Effacer une tuile</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1021"/>
        <source>Fill</source>
        <translation>Remplir</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1023"/>
        <source>Fill Rectangle</source>
        <translation>Remplir un rectangle</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1081"/>
        <source>Tilemap canvas</source>
        <translation>Canvas de tilemap</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1084"/>
        <source>Tilemap: left-click to stamp/erase/fill, middle-drag to pan, H/V flip, R rotate</source>
        <translation>Tilemap : clic gauche pour tamponner, effacer ou remplir, glisser avec le bouton central pour se déplacer, H/V pour retourner, R pour pivoter</translation>
    </message>
</context>
<context>
    <name>Tilemap_Layer_Panel</name>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="174"/>
        <source>Layer %1</source>
        <extracomment>Emitted with the active layer index (view state, no undo). Emitted when the auto-tile checkbox is toggled (canvas builds the ruleset).</extracomment>
        <translation>Calque %1</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="178"/>
        <location filename="../ui/tilemap_layer_panel.py" line="180"/>
        <location filename="../ui/tilemap_layer_panel.py" line="276"/>
        <source>Add Layer</source>
        <translation>Ajouter un calque</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="190"/>
        <location filename="../ui/tilemap_layer_panel.py" line="192"/>
        <location filename="../ui/tilemap_layer_panel.py" line="277"/>
        <source>Remove Layer</source>
        <translation>Supprimer le calque</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="224"/>
        <location filename="../ui/tilemap_layer_panel.py" line="226"/>
        <source>Reorder Layer</source>
        <translation>Réorganiser le calque</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="242"/>
        <source>Layer Visibility</source>
        <translation>Visibilité du calque</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="244"/>
        <source>Toggle Layer Visibility</source>
        <translation>Basculer la visibilité du calque</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="270"/>
        <source>Tilemap layers panel</source>
        <translation>Panneau des calques de tilemap</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="271"/>
        <source>Layer actions</source>
        <translation>Actions sur les calques</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="272"/>
        <source>Tilemap layers</source>
        <translation>Calques de tilemap</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="274"/>
        <source>Ordered map layers; tick to show/hide, top layer first</source>
        <translation>Calques de la carte ordonnés ; cochez pour afficher ou masquer, calque du dessus en premier</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="278"/>
        <source>Move Up</source>
        <translation>Monter</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="279"/>
        <source>Move Down</source>
        <translation>Descendre</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="280"/>
        <source>Auto-tile (Blob-47)</source>
        <translation>Tuilage automatique (Blob-47)</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="282"/>
        <source>Resolve tile edges automatically from neighbours</source>
        <translation>Résoudre automatiquement les bords des tuiles à partir des voisines</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="284"/>
        <source>Auto-tile toggle</source>
        <translation>Activation du tuilage automatique</translation>
    </message>
</context>
<context>
    <name>Tileset_Editor_Panel</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="216"/>
        <location filename="../ui/tileset_editor_panel.py" line="416"/>
        <location filename="../ui/tileset_editor_panel.py" line="424"/>
        <source>Tile width</source>
        <extracomment>Emitted with the selected tile&apos;s **global gid** (view state, no undo).</extracomment>
        <translation>Largeur de tuile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="219"/>
        <location filename="../ui/tileset_editor_panel.py" line="417"/>
        <location filename="../ui/tileset_editor_panel.py" line="425"/>
        <source>Tile height</source>
        <translation>Hauteur de tuile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="222"/>
        <location filename="../ui/tileset_editor_panel.py" line="426"/>
        <source>Tile margin</source>
        <translation>Marge des tuiles</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="225"/>
        <location filename="../ui/tileset_editor_panel.py" line="427"/>
        <source>Tile spacing</source>
        <translation>Espacement des tuiles</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="316"/>
        <source>Tile %1</source>
        <translation>Tuile %1</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="367"/>
        <location filename="../ui/tileset_editor_panel.py" line="369"/>
        <source>Re-slice Tileset</source>
        <translation>Redécouper le tileset</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="386"/>
        <location filename="../ui/tileset_editor_panel.py" line="388"/>
        <source>Edit Tile</source>
        <translation>Modifier la tuile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="415"/>
        <source>Tileset editor panel</source>
        <translation>Panneau de l&apos;éditeur de tileset</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="418"/>
        <source>Margin</source>
        <translation>Marge</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="419"/>
        <source>Spacing</source>
        <translation>Espacement</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="420"/>
        <location filename="../ui/tileset_editor_panel.py" line="421"/>
        <location filename="../ui/tileset_editor_panel.py" line="422"/>
        <location filename="../ui/tileset_editor_panel.py" line="423"/>
        <source> px</source>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="428"/>
        <source>Re-slice</source>
        <translation>Redécouper</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="429"/>
        <source>Re-slice the source image</source>
        <translation>Redécouper l&apos;image source</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="430"/>
        <source>Re-slice tileset</source>
        <translation>Redécouper le tileset</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="431"/>
        <source>Edit Tile…</source>
        <translation>Modifier la tuile…</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="432"/>
        <source>Paint into the selected source tile</source>
        <translation>Peindre dans la tuile source sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="433"/>
        <source>Edit selected tile</source>
        <translation>Modifier la tuile sélectionnée</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="434"/>
        <source>Tileset tiles</source>
        <translation>Tuiles du tileset</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="436"/>
        <source>Sliced tiles in row-major order; click to select for stamping</source>
        <translation>Tuiles découpées, ligne par ligne ; cliquez pour sélectionner la tuile à tamponner</translation>
    </message>
</context>
<context>
    <name>Timelapse_Controls</name>
    <message numerus="yes">
        <location filename="../ui/timelapse_controls.py" line="422"/>
        <source>%n frame(s) were dropped because the edits they recorded were undone and replaced.</source>
        <extracomment>A Document -&gt; RGBA ``ndarray`` renderer (e.g. wrapping ``blend.composite_stack``), injected by the host rather than authored here (S11 — no domain/composite maths in this widget). Returns the currently active document for a bound ``QUndoStack`` (S11 — this widget reads it, it never derives it). Emitted with the current frame count after a record / load / reset. Emitted with one reconstructed RGBA ``ndarray`` per displayed frame, whichever substrate served it (in-session or a loaded payload). Emitted ``True`` while document edits must be refused (playing or paused mid-sequence), ``False`` once playback stops or completes. Emitted with the number of frames dropped by a discarded branch (REQ-P9-UI-021), once per occurrence. The per-recording identity half (REQ-P9-LOGIC-022; plan §10.1) — one :mod:`secrets` draw, minted once per recording (here, and again on every :meth:`reset`). Never an adversarial-strength token (``TIMELAPSE_RECORDING_ID_BYTES``&apos; own docstring): it only has to not collide, and it is paid for on every frame. The monotone ordinal half — only ever ``+= 1``, never reset, rewound, or derived from ``len(session.frames)``: every rewrite path rebuilds the frames *tuple*, and a counter living inside it would rewind with it (plan §10.1). The id of the document this session was recorded against (REQ-P9-UI-020) — ``None`` until the first frame is recorded. The id of the document currently bound (the active tab). stack index -&gt; the FrameId minted the last time that index was reached forward (plan §10.2). On every forward index change to ``i``, every entry with key ``&gt;= i`` is evicted **before** any new mint — an event-time observation, exact because nothing has been reused yet, never a resolution-time inference from a count. Its value set is both the surviving-identity set passed to :func:`~pixelart_creator.logic.timelapse.drop_discarded` and the live HISTORY extent handed to :class:`~pixelart_creator.ui.timelapse_playback.History_Document_Provider`. Set by :meth:`load_reopened_recording` when reviewing a loaded, cross-session payload rather than the live in-session history. ``True`` only while this widget is itself driving the bound ``QUndoStack`` through a provider (a historical render or a save&apos;s payload snapshot pass) — every ``indexChanged`` this causes is this widget&apos;s own bookkeeping, never a user commit, and must not be recorded or misread as a discard boundary (D1 fix; see ``_render_all``/``_build_payload_tables``).</extracomment>
        <translation>
            <numerusform>%n image a été supprimée car les modifications qu&apos;elle contenait ont été annulées puis remplacées.</numerusform>
            <numerusform>%n images ont été supprimées car les modifications qu&apos;elles contenaient ont été annulées puis remplacées.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="464"/>
        <source>Recording stopped</source>
        <translation>Capture arrêtée</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="466"/>
        <source>Recording was stopped because it reached the maximum number of frames. The frames already recorded are kept. Save this recording, or reset it to start a new one.</source>
        <translation>La capture a été arrêtée car elle a atteint le nombre maximal d&apos;images. Les images déjà capturées sont conservées. Enregistrez-la ou réinitialisez-la pour en commencer une nouvelle.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="538"/>
        <source>Different document</source>
        <translation>Document différent</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="540"/>
        <source>This recording belongs to a different document. Switch to that document to resume it, or reset first to start a new one here.</source>
        <translation>Cette capture appartient à un autre document. Passez à ce document pour la reprendre, ou réinitialisez d&apos;abord pour en commencer une nouvelle ici.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="557"/>
        <source>Save Timelapse</source>
        <translation>Enregistrer le timelapse</translation>
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
        <translation>Échec de l&apos;enregistrement</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="570"/>
        <source>This recording could not be saved because a recorded state could not be reconstructed from the current history.</source>
        <translation>Cette capture n&apos;a pas pu être enregistrée, car un état capturé n&apos;a pas pu être reconstitué à partir de l&apos;historique actuel.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="588"/>
        <source>This recording was not saved because it is too large. Nothing was written. Discard some frames and try again.</source>
        <translation>Cette capture n&apos;a pas été enregistrée, car elle est trop volumineuse. Rien n&apos;a été écrit. Supprimez quelques images et réessayez.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="605"/>
        <source>This recording could not be saved. The file could not be written, or its data could not be encoded.</source>
        <translation>Cette capture n&apos;a pas pu être enregistrée. Le fichier n&apos;a pas pu être écrit, ou ses données n&apos;ont pas pu être encodées.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="671"/>
        <source>Open Timelapse</source>
        <translation>Ouvrir un timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="688"/>
        <source>Open failed</source>
        <translation>Échec de l&apos;ouverture</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="690"/>
        <source>This file could not be opened. It is missing, unreadable, or not a valid timelapse recording.</source>
        <translation>Ce fichier n&apos;a pas pu être ouvert. Il est introuvable, illisible ou ne contient pas une capture timelapse valide.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="749"/>
        <source>There is nothing recorded to play yet.</source>
        <translation>Aucune capture à lire pour le moment.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="756"/>
        <source>This recording belongs to a different document. Switch to that document to play it.</source>
        <translation>Cette capture appartient à un autre document. Passez à ce document pour la lire.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="761"/>
        <source>Playback is not available yet.</source>
        <translation>La lecture n&apos;est pas encore disponible.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="777"/>
        <source>This recording was saved in a form that cannot be replayed.</source>
        <translation>Cette capture a été enregistrée sous une forme qui ne permet pas de la rejouer.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="782"/>
        <source>This recording&apos;s saved data is incomplete and cannot be fully replayed.</source>
        <translation>Les données enregistrées de cette capture sont incomplètes ; elle ne peut pas être rejouée intégralement.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="788"/>
        <source>Some recorded frames are no longer reachable in the current history and cannot be played.</source>
        <translation>Certaines images capturées ne sont plus accessibles dans l&apos;historique actuel et ne peuvent pas être lues.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="793"/>
        <source>This recording&apos;s history no longer matches; it cannot be replayed from here.</source>
        <translation>L&apos;historique de cette capture ne correspond plus ; elle ne peut pas être rejouée à partir d&apos;ici.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="807"/>
        <source>This recording was saved in an earlier form whose frames cannot be told apart reliably, so it will not be replayed.</source>
        <translation>Cette capture a été enregistrée sous une forme antérieure dont les images ne peuvent pas être distinguées de façon fiable ; elle ne sera donc pas rejouée.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="810"/>
        <source>This recording cannot be played.</source>
        <translation>Cette capture ne peut pas être lue.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="839"/>
        <source>Cannot play</source>
        <translation>Lecture impossible</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="847"/>
        <source>Playback failed</source>
        <translation>Échec de la lecture</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="848"/>
        <source>This recording could not be replayed.</source>
        <translation>Cette capture n&apos;a pas pu être rejouée.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="935"/>
        <source>Frame {0} of {1}</source>
        <translation>Image {0} sur {1}</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="940"/>
        <source>Recorded frames: {0}</source>
        <translation>Images capturées : {0}</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="972"/>
        <source>Stop Recording</source>
        <translation>Arrêter la capture</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="972"/>
        <source>Record</source>
        <translation>Lancer la capture</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="977"/>
        <source>Pause</source>
        <translation>Pause</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="977"/>
        <source>Play</source>
        <translation>Lecture</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="981"/>
        <source>Timelapse</source>
        <translation>Timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="982"/>
        <source>Timelapse controls</source>
        <translation>Contrôles du timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="983"/>
        <source>Save…</source>
        <translation>Enregistrer…</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="984"/>
        <source>Open…</source>
        <translation>Ouvrir…</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="985"/>
        <source>Stop</source>
        <translation>Arrêter</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="986"/>
        <source>Timelapse position</source>
        <translation>Position dans le timelapse</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="987"/>
        <source>Playback speed</source>
        <translation>Vitesse de lecture</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="992"/>
        <source>Playback refusal reason</source>
        <translation>Motif du refus de lecture</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="993"/>
        <source>Recorded frame count</source>
        <translation>Nombre d&apos;images capturées</translation>
    </message>
</context>
<context>
    <name>Timelapse_Frame_View</name>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="52"/>
        <location filename="../ui/timelapse_frame_view.py" line="116"/>
        <source>Reopened recording — not the current document</source>
        <translation>Capture rouverte — pas le document actuel</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="110"/>
        <source>Reopened Recording</source>
        <translation>Capture rouverte</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="111"/>
        <source>Reopened timelapse recording</source>
        <translation>Capture timelapse rouverte</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="113"/>
        <source>Reopened recording — this is not your current document</source>
        <translation>Capture rouverte — il ne s&apos;agit pas de votre document actuel</translation>
    </message>
</context>
<context>
    <name>Timeline_Grid_View</name>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="553"/>
        <source>Toggle Cel Visibility</source>
        <extracomment>Emitted with the frame index a selection (of any kind) settled on (REQ-P5-UI-023). Pushes no command. Emitted with the ``layer_id`` a cell/row-header selection settled on (REQ-P5-UI-023). Pushes no command. Emitted with the frame index the cursor is scrubbing over during a body drag away from any occupied cell (REQ-P5-UI-025). Pushes no command. Emitted when a Ctrl+right-click removal was refused because the target document has only one frame left (D-22). ``Document._ensure_frame_removable`` is the single, unconditional owner of that invariant; this view asks the bound document itself (``len(document.frames)``) rather than keeping a second, independently-maintained notion of &quot;removable&quot; — so the two can never drift apart. Pushes no command; the gesture stays inert.</extracomment>
        <translation>Basculer la visibilité du cel</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="589"/>
        <source>Create Cel Here</source>
        <translation>Créer un cel ici</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="591"/>
        <source>Create a new drawing on this track in this frame</source>
        <translation>Créer un nouveau dessin sur cette piste dans cette image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="609"/>
        <source>Create Cel</source>
        <translation>Créer un cel</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="642"/>
        <source>Remove Frame</source>
        <translation>Supprimer l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="666"/>
        <source>Reorder Frame</source>
        <translation>Réorganiser l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="816"/>
        <source>Copy Cel</source>
        <translation>Copier le cel</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="824"/>
        <source>Move Cel</source>
        <translation>Déplacer le cel</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="851"/>
        <source>Timeline grid</source>
        <translation>Grille de la ligne temporelle</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="854"/>
        <source>Frames as columns, layer tracks as rows; drag a header to reorder, drag a drawing to move it (hold Ctrl to copy), or open the context menu on an empty cell to create a cel there</source>
        <translation>Images en colonnes, pistes de calques en lignes ; faites glisser un en-tête pour réorganiser, faites glisser un dessin pour le déplacer (maintenez Ctrl pour le copier), ou ouvrez le menu contextuel sur une cellule vide pour y créer un cel</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="859"/>
        <source>Frame headers</source>
        <translation>En-têtes d&apos;images</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="860"/>
        <source>Layer track headers</source>
        <translation>En-têtes des pistes de calques</translation>
    </message>
</context>
<context>
    <name>Timeline_Panel</name>
    <message>
        <location filename="../ui/timeline_panel.py" line="272"/>
        <source>Frame %1</source>
        <extracomment>Index of the strip surface in the cell-surface QStackedWidget — the default (REQ-P5-UI-020: &quot;the strip is the default&quot;). Not a domain constant (Article II does not reach a fixed widget-stack index); grouped with the other presentation literals this module already carries. Longest edge (px) of a cached per-cell frame thumbnail. Presentation-only sizing (like ``_SWATCH_PX`` in ``main_window``); the resident buffer is never culled — only the small display thumbnail is downscaled (F7). Ceiling for the per-frame duration spin box (ms). A presentation-only cap on how high the editor spins (like ``_THUMBNAIL_EDGE``); it is NOT a domain tuning value — the authoritative bound is the logic ``make_set_frame_duration_command`` positive-int guard, which alone validates. Emitted with the frame index a click/keyboard selected (settled — onion on). Emitted with the frame index the cursor is dragging over (scrub — onion off). Emitted with a ``layer_id`` the grid cell surface&apos;s selection settled on (REQ-P5-UI-023, BF-G1); the strip has no layer axis and never emits this.</extracomment>
        <translation>Image %1</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="280"/>
        <source>Frame %1 — %2 ms</source>
        <translation>Image %1 — %2 ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="394"/>
        <location filename="../ui/timeline_panel.py" line="513"/>
        <source>Add Frame</source>
        <translation>Ajouter une image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="406"/>
        <location filename="../ui/timeline_panel.py" line="515"/>
        <source>Remove Frame</source>
        <translation>Supprimer l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="417"/>
        <location filename="../ui/timeline_panel.py" line="517"/>
        <source>Duplicate Frame</source>
        <translation>Dupliquer l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="450"/>
        <source>Reorder Frame</source>
        <translation>Réorganiser l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="466"/>
        <source>Set Frame Duration</source>
        <translation>Définir la durée de l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="507"/>
        <source>Timeline panel</source>
        <translation>Panneau de la ligne temporelle</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="508"/>
        <source>Frame actions</source>
        <translation>Actions sur les images</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="509"/>
        <source>Frame strip</source>
        <translation>Bande d&apos;images</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="511"/>
        <source>Frames left-to-right in playback order; drag to reorder</source>
        <translation>Images de gauche à droite dans l&apos;ordre de lecture ; faites glisser pour réorganiser</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="514"/>
        <source>Insert a new frame after the active one</source>
        <translation>Insérer une nouvelle image après l&apos;image active</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="516"/>
        <source>Delete the active frame</source>
        <translation>Supprimer l&apos;image active</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="519"/>
        <source>Insert a copy of the active frame after it</source>
        <translation>Insérer une copie de l&apos;image active après celle-ci</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="521"/>
        <source>Grid View</source>
        <translation>Vue en grille</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="523"/>
        <source>Show frames and layer tracks as a grid instead of a strip</source>
        <translation>Afficher les images et les pistes de calques sous forme de grille plutôt que de bande</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="525"/>
        <source>Timeline cell surface</source>
        <translation>Surface des cellules de la ligne temporelle</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="526"/>
        <source>Duration</source>
        <translation>Durée</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="528"/>
        <source> ms</source>
        <translation> ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="529"/>
        <source>Frame duration</source>
        <translation>Durée de l&apos;image</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="531"/>
        <source>Display time of the active frame, in milliseconds</source>
        <translation>Durée d&apos;affichage de l&apos;image active, en millisecondes</translation>
    </message>
</context>
<context>
    <name>User_Guide_Dialog</name>
    <message>
        <location filename="../ui/user_guide.py" line="499"/>
        <source>Could not load this topic:

%1</source>
        <extracomment>Qt roles that would resolve an anchor to the network or the local filesystem; the viewer is fully offline (REQ-UG-UI-007), so a click on such a link is a no-op — it is never fetched. The UserRole slot carrying a topic id on a ToC / results item. The in-guide markdown image URL the mark resolves against. The guide pages reference the mark as ``![PixelArt Creator](pac-logo.png)`` under this EXACT string -- it is the contract between the content and this widget&apos;s document-resource registration; do not change it here. A reader callable: a bundle-relative content ref -&gt; the Markdown text. Defaults to the defensive ``data`` reader; injectable so headless tests can substitute a fixture reader without touching the real bundle. A locale provider: returns the active UI locale code (e.g. ``&quot;en&quot;``). Defaults to the guide&apos;s default locale; the main window passes the LanguageManager&apos;s ``current_language`` so content follows the UI language (REQ-UG-UI-011 / CL-3). Qt&apos;s scale for a char format&apos;s font-size adjustment (``+1`` is 1.2 times the base size, ``+2`` 1.5, ``+3`` 2.0); the markdown importer gives a heading the adjustment ``4 - level``. Used to find the size a heading would be drawn at, so it can be rounded to a whole multiple of the pixel font&apos;s em. Emitted when the hidden logo switch is toggled (the new on/off state), so the owner can remember it (``REQ-VI-UI-017``).</extracomment>
        <translation>Impossible de charger cette rubrique :

%1</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="553"/>
        <source>The User Guide content could not be loaded:

%1</source>
        <translation>Le contenu du guide de l&apos;utilisateur n&apos;a pas pu être chargé :

%1</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="556"/>
        <source>The User Guide content could not be loaded.</source>
        <translation>Le contenu du guide de l&apos;utilisateur n&apos;a pas pu être chargé.</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="649"/>
        <location filename="../ui/user_guide.py" line="650"/>
        <source>User Guide</source>
        <translation>Guide de l&apos;utilisateur</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="651"/>
        <source>Search the guide…</source>
        <translation>Rechercher dans le guide…</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="652"/>
        <source>Search the guide</source>
        <translation>Rechercher dans le guide</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="653"/>
        <source>Guide contents</source>
        <translation>Sommaire du guide</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="654"/>
        <source>Search results</source>
        <translation>Résultats de la recherche</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="655"/>
        <source>Guide content</source>
        <translation>Contenu du guide</translation>
    </message>
</context>
<context>
    <name>Vanishing_Point_Dialog</name>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="152"/>
        <source>1-point</source>
        <translation>1 point</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="153"/>
        <source>2-point</source>
        <translation>2 points</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="154"/>
        <source>3-point</source>
        <translation>3 points</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="158"/>
        <source>Configure Perspective</source>
        <translation>Configurer la perspective</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="159"/>
        <source>Vanishing points</source>
        <translation>Points de fuite</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="160"/>
        <source>Horizon Y</source>
        <translation>Horizon Y</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="161"/>
        <source>Vanishing-point mode</source>
        <translation>Mode de points de fuite</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="162"/>
        <source>Horizon Y position</source>
        <translation>Position Y de l&apos;horizon</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="166"/>
        <source>Vanishing point {n}</source>
        <translation>Point de fuite {n}</translation>
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
        <translation>Point de fuite {n} X</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="174"/>
        <source>Vanishing point {n} Y</source>
        <translation>Point de fuite {n} Y</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="178"/>
        <source>OK</source>
        <translation>OK</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="181"/>
        <source>Cancel</source>
        <translation>Annuler</translation>
    </message>
</context>
<context>
    <name>Version_History_Browser</name>
    <message>
        <location filename="../ui/version_history_browser.py" line="169"/>
        <source>Select a version to restore.</source>
        <extracomment>Column order of the version tree (presentation-only layout, not a domain value). QSS role-selector property (never a hard-coded colour): the status label carries the computed :class:`SyncState` as a dynamic property so BOTH themes can style it by role (``QLabel[syncState=&quot;diverged&quot;]`` etc.) — see D-13.</extracomment>
        <translation>Sélectionnez une version à restaurer.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/version_history_browser.py" line="174"/>
        <source>Version %1 — %n bytes (created marker %3).</source>
        <translation>
            <numerusform>Version %1 — %n octet (marqueur de création %3).</numerusform>
            <numerusform>Version %1 — %n octets (marqueur de création %3).</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="185"/>
        <source>Up to date with the cloud.</source>
        <translation>À jour avec le cloud.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="187"/>
        <source>Local changes have not been saved to the cloud yet.</source>
        <translation>Les modifications locales n&apos;ont pas encore été enregistrées dans le cloud.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="189"/>
        <source>A newer version exists in the cloud.</source>
        <translation>Une version plus récente existe dans le cloud.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="190"/>
        <source>Local and cloud history have diverged.</source>
        <translation>L&apos;historique local et celui du cloud ont divergé.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="195"/>
        <source>Cloud Version History</source>
        <translation>Historique des versions du cloud</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="198"/>
        <source>Prior cloud saves, oldest first. Restoring opens the chosen version in a new tab — your current work is not overwritten.</source>
        <translation>Enregistrements précédents dans le cloud, du plus ancien au plus récent. La restauration ouvre la version choisie dans un nouvel onglet — votre travail actuel n&apos;est pas écrasé.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="203"/>
        <source>Cloud sync status</source>
        <translation>État de synchronisation avec le cloud</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="206"/>
        <source>Version</source>
        <translation>Version</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="207"/>
        <source>Marker</source>
        <translation>Marqueur</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="208"/>
        <source>Size (bytes)</source>
        <translation>Taille (octets)</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="209"/>
        <source>Pinned</source>
        <translation>Épinglée</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="210"/>
        <source>Parent</source>
        <translation>Parent</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="213"/>
        <source>Yes</source>
        <translation>Oui</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="214"/>
        <source>No</source>
        <translation>Non</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="222"/>
        <source>Restore</source>
        <translation>Restaurer</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="223"/>
        <source>Cloud version list</source>
        <translation>Liste des versions du cloud</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="224"/>
        <source>Restore selected version</source>
        <translation>Restaurer la version sélectionnée</translation>
    </message>
</context>
<context>
    <name>_Node_Row</name>
    <message>
        <location filename="../ui/layer_panel.py" line="180"/>
        <source>Ref</source>
        <extracomment>A node address in the frame tree — the logic index path used by the document layer ops (top-level index, then indices descending through nested groups). A fully-shown mask (opaque alpha everywhere ⇒ no modulation, LOGIC-012).</extracomment>
        <translation>Réf.</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="182"/>
        <source>Mask</source>
        <translation>Masque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="184"/>
        <source>Smart</source>
        <translation>Intelligent</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="196"/>
        <source>Toggle Visibility</source>
        <translation>Basculer la visibilité</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="205"/>
        <source>Toggle Lock</source>
        <translation>Basculer le verrouillage</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="217"/>
        <source>Set Blend Mode</source>
        <translation>Définir le mode de fusion</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="251"/>
        <source>Set Opacity</source>
        <translation>Définir l&apos;opacité</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="257"/>
        <source>V</source>
        <translation>V</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="258"/>
        <source>Toggle layer visibility</source>
        <translation>Basculer la visibilité du calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="259"/>
        <source>Visibility</source>
        <translation>Visibilité</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="260"/>
        <source>L</source>
        <translation>L</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="261"/>
        <source>Lock layer against painting</source>
        <translation>Verrouiller le calque pour empêcher de peindre dessus</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="262"/>
        <source>Lock</source>
        <translation>Verrouillage</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="263"/>
        <source>Layer name</source>
        <translation>Nom du calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="264"/>
        <source>Layer flags</source>
        <translation>Indicateurs du calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="265"/>
        <source>Layer opacity</source>
        <translation>Opacité du calque</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="266"/>
        <source>Opacity</source>
        <translation>Opacité</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="267"/>
        <location filename="../ui/layer_panel.py" line="268"/>
        <source>Blend mode</source>
        <translation>Mode de fusion</translation>
    </message>
</context>
<context>
    <name>_Project_Prefs_Menu</name>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="71"/>
        <source>Ask me every time</source>
        <extracomment>A domain wider than this renders as a nested exclusive submenu rather than a single checkable action (plan §3.4) — a plain boolean-shaped preference (ask / suppressed) keeps the shipped single-checkbox rendering. Menu-rendering strings share one translation context with the class below so :func:`value_label_for` — a free function, exported for a future renderer (phase-6&apos;s settings dialog) — is caught by the same ``tr()`` extraction pass as the class&apos;s own strings.</extracomment>
        <translation>Me demander à chaque fois</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="74"/>
        <source>Always pick up the library change</source>
        <translation>Toujours récupérer la modification de la bibliothèque</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="77"/>
        <source>Always keep the referenced version</source>
        <translation>Toujours conserver la version référencée</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="83"/>
        <source>Set to: %1</source>
        <translation>Défini sur : %1</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="218"/>
        <source>Confirm before overwriting a cel</source>
        <extracomment>The provider the caller supplies: returns the active document, or ``None`` when no document is open.</extracomment>
        <translation>Confirmer avant d&apos;écraser un cel</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="220"/>
        <source>When a referenced library asset changes</source>
        <translation>Lorsqu&apos;une ressource de bibliothèque référencée change</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="221"/>
        <source>Confirm: %1</source>
        <translation>Confirmer : %1</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="224"/>
        <location filename="../ui/project_prefs_actions.py" line="225"/>
        <source>Project confirmations</source>
        <translation>Confirmations du projet</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="230"/>
        <source>Restore this confirmation so it asks again</source>
        <translation>Rétablir cette confirmation pour qu&apos;elle soit de nouveau demandée</translation>
    </message>
</context>
<context>
    <name>_Tile_Pixel_Editor</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="111"/>
        <location filename="../ui/tileset_editor_panel.py" line="155"/>
        <source>Tile pixel editor</source>
        <extracomment>Thumbnail edge (px) for a tile swatch in the grid list (presentation-only, not a domain tuning value — cf. Palette_Panel&apos;s swatch size). On-screen pixel size of one tile pixel in the tile editor dialog.</extracomment>
        <translation>Éditeur de pixels de tuile</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="113"/>
        <location filename="../ui/tileset_editor_panel.py" line="157"/>
        <source>Left-click to paint, right-click to erase</source>
        <translation>Clic gauche pour peindre, clic droit pour effacer</translation>
    </message>
</context>
<context>
    <name>_Track_Table_Model</name>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="239"/>
        <source>Frame %1</source>
        <extracomment>Longest edge (px) of a cached per-cell thumbnail. Mirrors ``timeline_panel._THUMBNAIL_EDGE`` exactly (visual consistency between the two cell surfaces the toggle swaps between); a presentation-only sizing literal, not a domain tuning value (Article II does not reach it, like its strip twin). Custom data roles carried on every cell, alongside the standard Qt roles.</extracomment>
        <translation>Image %1</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="256"/>
        <source>%1, %2</source>
        <translation>%1, %2</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="261"/>
        <source>%1, %2 — empty</source>
        <translation>%1, %2 — vide</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="268"/>
        <source>%1, track %2</source>
        <translation>%1, piste %2</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="273"/>
        <source>%1, track %2, empty</source>
        <translation>%1, piste %2, vide</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="278"/>
        <source>Occupied cell</source>
        <translation>Cellule occupée</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="278"/>
        <source>Empty cell</source>
        <translation>Cellule vide</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="326"/>
        <source>%1
%2 ms</source>
        <translation>%1
%2 ms</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/timeline_grid_view.py" line="331"/>
        <source>Frame %1, %n milliseconds</source>
        <translation>
            <numerusform>Image %1, %n milliseconde</numerusform>
            <numerusform>Image %1, %n millisecondes</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="341"/>
        <source>Track %1</source>
        <translation>Piste %1</translation>
    </message>
</context>
<context>
    <name>_WheelPad</name>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="308"/>
        <source>Colour wheel</source>
        <extracomment>Hue at the top of the circle, in degrees (achromatic fallback keeps this hue). Number of conical-gradient stops sweeping the hue circle (six primaries + wrap). Edge of a harmony/preview swatch button, px (presentation-only sizing). Minimum wheel diameter, px (presentation-only sizing). Marker radius drawn at the current hue/saturation, px. Keyboard nudge steps for the wheel (hue degrees / saturation fraction). Single left click — paint this swatch&apos;s colour, leave the wheel alone. Double left click / Space / Return — adopt this swatch&apos;s colour into the wheel, paint nothing. Emitted with ``(hue_degrees, saturation)`` when the user picks on the wheel.</extracomment>
        <translation>Roue chromatique</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="311"/>
        <source>Hue and saturation wheel; use the arrow keys or the numeric fields to pick a colour without a mouse</source>
        <translation>Roue de teinte et de saturation ; utilisez les touches fléchées ou les champs numériques pour choisir une couleur sans souris</translation>
    </message>
</context>
<context>
    <name>export</name>
    <message>
        <location filename="../ui/export_actions.py" line="98"/>
        <location filename="../ui/export_actions.py" line="109"/>
        <source>Export</source>
        <extracomment>The source document that was submitted for export (never the exported file&apos;s own bytes — REQ-P11-UI-014). The export settings as used for this run (JSON-scalar values only — bounded by ``logic.constants.MAX_METADATA_BYTES`` at ingress).</extracomment>
        <translation>Exporter</translation>
    </message>
    <message>
        <location filename="../ui/export_actions.py" line="99"/>
        <source>Open a document before exporting.</source>
        <translation>Ouvrez un document avant d&apos;exporter.</translation>
    </message>
    <message>
        <location filename="../ui/export_actions.py" line="110"/>
        <source>Choose a destination path before exporting.</source>
        <translation>Choisissez un chemin de destination avant d&apos;exporter.</translation>
    </message>
</context>
<context>
    <name>theme</name>
    <message>
        <location filename="../ui/theme.py" line="155"/>
        <source>unknown style: %1</source>
        <extracomment>%1 is the internal style name that could not be found.</extracomment>
        <translation>style inconnu : %1</translation>
    </message>
    <message>
        <location filename="../ui/theme.py" line="160"/>
        <source>unknown theme: %1</source>
        <translation>thème inconnu : %1</translation>
    </message>
</context>
<context>
    <name>tilemap_io</name>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="38"/>
        <source>Export Tiled Map</source>
        <extracomment>Tiled JSON file filter (format identifier, not a translated string).</extracomment>
        <translation>Exporter une carte Tiled</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="49"/>
        <source>Export failed</source>
        <translation>Échec de l&apos;exportation</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="50"/>
        <source>Could not export the map: %1</source>
        <translation>Impossible d&apos;exporter la carte : %1</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="67"/>
        <source>Import Tiled Map</source>
        <translation>Importer une carte Tiled</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="78"/>
        <source>Import failed</source>
        <translation>Échec de l&apos;importation</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="79"/>
        <source>Could not import the map: %1</source>
        <translation>Impossible d&apos;importer la carte : %1</translation>
    </message>
</context>
<context>
    <name>tool_icons</name>
    <message>
        <location filename="../ui/tool_icons.py" line="129"/>
        <source>unknown tool glyph id: %1</source>
        <extracomment>The importable package the glyph bundle is shipped inside (package data), matching ``data/guide_content.py``&apos;s ``BUNDLE_PACKAGE`` convention. Package-data subdirectory holding the eleven glyphs, relative to :data:`_ICON_PACKAGE` (``pixelart_creator/icons/tools/``). SVG file extension for a glyph resource. Square render size, in device-independent pixels, for the rasterised glyph and its tinted pixmap. One named constant, referenced everywhere a size is needed in this module (S12) — this module owns no other size. The theme role whose colour tints every glyph (`ui/theme.py`&apos;s role palette; `text` exists in both themes, QT-D1). The eleven shipped `tool_id`s, one per authored glyph stem (`pixelart_creator/icons/tools/&lt;id&gt;.svg`) — the exact `tool_id` class attributes carried by `ui/tools/*.py` (pencil, eraser, fill, line, picker, rectangle, ellipse, select_rect, select_lasso, select_wand, dither). Kept as a literal tuple here (not imported from each tool class) so this module has no dependency on the tool-strategy classes themselves — only on the glyph *ids* they happen to share.</extracomment>
        <translation>identifiant de glyphe d&apos;outil inconnu : %1</translation>
    </message>
    <message>
        <location filename="../ui/tool_icons.py" line="136"/>
        <source>missing tool glyph asset for: %1</source>
        <translation>ressource de glyphe d&apos;outil manquante pour : %1</translation>
    </message>
    <message>
        <location filename="../ui/tool_icons.py" line="153"/>
        <source>unknown theme: %1</source>
        <translation>thème inconnu : %1</translation>
    </message>
</context>
<context>
    <name>tools</name>
    <message>
        <location filename="../ui/tools/dither_tool.py" line="65"/>
        <source>Dither</source>
        <extracomment>The two dither modes accepted by ``logic.dither.make_dither_command``.</extracomment>
        <translation>Tramage</translation>
    </message>
    <message>
        <location filename="../ui/tools/ellipse_tool.py" line="29"/>
        <source>Ellipse</source>
        <translation>Ellipse</translation>
    </message>
    <message>
        <location filename="../ui/tools/eraser.py" line="25"/>
        <source>Eraser</source>
        <extracomment>Indexed buffers erase to palette index 0 (the buffer&apos;s own default value).</extracomment>
        <translation>Gomme</translation>
    </message>
    <message>
        <location filename="../ui/tools/fill.py" line="23"/>
        <source>Fill</source>
        <translation>Pot de peinture</translation>
    </message>
    <message>
        <location filename="../ui/tools/lasso_tool.py" line="30"/>
        <source>Lasso Select</source>
        <translation>Sélection au lasso</translation>
    </message>
    <message>
        <location filename="../ui/tools/line.py" line="29"/>
        <source>Line</source>
        <translation>Ligne</translation>
    </message>
    <message>
        <location filename="../ui/tools/magic_wand_tool.py" line="36"/>
        <source>Magic Wand</source>
        <extracomment>A wand click always (re)selects; it never starts a floating move. Colour tolerance; default exact match (CL-1). Set by the shell control.</extracomment>
        <translation>Baguette magique</translation>
    </message>
    <message>
        <location filename="../ui/tools/pencil.py" line="49"/>
        <source>Pencil</source>
        <translation>Crayon</translation>
    </message>
    <message>
        <location filename="../ui/tools/rect_select_tool.py" line="23"/>
        <source>Rectangle Select</source>
        <translation>Sélection rectangulaire</translation>
    </message>
    <message>
        <location filename="../ui/tools/rectangle_tool.py" line="29"/>
        <source>Rectangle</source>
        <translation>Rectangle</translation>
    </message>
</context>
<context>
    <name>widget</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="60"/>
        <source>Loop</source>
        <translation>Boucle</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="61"/>
        <source>Once</source>
        <translation>Une fois</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="62"/>
        <source>Ping-Pong</source>
        <translation>Ping-pong</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="63"/>
        <source>Reverse</source>
        <translation>Inverse</translation>
    </message>
</context>
</TS>
