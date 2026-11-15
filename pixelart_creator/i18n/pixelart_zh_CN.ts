<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN" sourcelanguage="en">
<context>
    <name>About_Dialog</name>
    <message>
        <location filename="../ui/about_dialog.py" line="280"/>
        <source>About PixelArt Creator</source>
        <extracomment>The dialog&apos;s fixed links, in the order shown (REQ-AV-UI-005).</extracomment>
        <translation>关于 PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="281"/>
        <source>About PixelArt Creator dialog</source>
        <translation>关于 PixelArt Creator 对话框</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="283"/>
        <source>PixelArt Creator icon</source>
        <translation>PixelArt Creator 图标</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="284"/>
        <source>Application name</source>
        <translation>应用程序名称</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="285"/>
        <source>Version:</source>
        <translation>版本:</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="286"/>
        <source>Application version</source>
        <translation>应用程序版本</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="287"/>
        <source>Licence:</source>
        <translation>许可证:</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="288"/>
        <source>Licence name</source>
        <translation>许可证名称</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="289"/>
        <source>Environment:</source>
        <translation>环境:</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="290"/>
        <source>Environment summary</source>
        <translation>环境摘要</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="294"/>
        <source>Repository</source>
        <translation>代码仓库</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="295"/>
        <source>Documentation</source>
        <translation>文档</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="296"/>
        <source>Releases</source>
        <translation>发行版</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="307"/>
        <source>&amp;Copy</source>
        <translation>复制</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="308"/>
        <source>Copy environment summary</source>
        <translation>复制环境摘要</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="309"/>
        <source>C&amp;lose</source>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="310"/>
        <source>Close the About dialog</source>
        <translation>关闭“关于”对话框</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="314"/>
        <source>unknown</source>
        <translation>未知</translation>
    </message>
</context>
<context>
    <name>Asset_Library_Panel</name>
    <message>
        <location filename="../ui/asset_library_panel.py" line="162"/>
        <source>Broken reference</source>
        <extracomment>Emitted with the selected entry&apos;s ``asset_id`` (``&quot;&quot;`` when cleared). The active filter driven by the search panel (empty = full catalog).</extracomment>
        <translation>失效引用</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="186"/>
        <source>Sprite</source>
        <translation>精灵</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="187"/>
        <source>Animation</source>
        <translation>动画</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="188"/>
        <source>Tileset</source>
        <translation>瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="189"/>
        <source>Tilemap</source>
        <translation>瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="190"/>
        <source>Palette</source>
        <translation>调色板</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="195"/>
        <source>Asset library</source>
        <translation>素材库</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Name</source>
        <translation>名称</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Kind</source>
        <translation>类型</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Tags</source>
        <translation>标签</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Status</source>
        <translation>状态</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="199"/>
        <source>Catalog assets</source>
        <translation>素材目录</translation>
    </message>
</context>
<context>
    <name>Asset_Library_Session</name>
    <message>
        <location filename="../ui/asset_library_actions.py" line="507"/>
        <source>Import asset artifact</source>
        <extracomment>Emitted after any change to the catalog (add / remove / tag do-undo) so the bound panels re-read and repaint. No payload — panels pull the fresh catalog. Emitted after the dependency graph is replaced so the dependency-graph view and the passive break surface re-read and repaint. No payload. Emitted after a registration action commits — carries the :class:`RegistrationOutcome` (REQ-P11-UI-017). Emitted when a registration action cannot commit — carries a translatable message; the catalog, store and revision history are all left unchanged (REQ-P11-UI-017). Emitted when the user cancels the registration prompt — cancelling is not a failure (REQ-P11-UI-017; RP-4). Emitted after a successful registration&apos;s derived dependency edges are computed (ruling P11-R6, REQ-P11-LOGIC-010 / REQ-P11-UI-018) — carries the **accumulated** edge set (this session&apos;s current graph edges plus the newly derived ones), because the bound consumer (:meth:`~pixelart_creator.ui.dependency_graph_view.Dependency_Graph_View. show_edges`) *replaces* the graph it is handed rather than merging into it. This session never calls :meth:`set_graph` itself and never imports the view — ``show_edges`` alone decides whether the accumulated set is accepted (and, on a closed cycle, rejected passively, the prior graph kept) — see ``main_window.py``&apos;s connection of this signal. Emitted after a single library artifact (``.pixasset``) is imported and merged + committed into the already-open library (ruling P11-R5, REQ-P11-UI-015/-016) — carries the imported ``Tuple[AssetDescriptor, ...]``. Emitted when a library-artifact import cannot commit — a translatable message; the catalog and store are unchanged. Emitted when the user cancels the &quot;Import asset artifact&quot; file dialog. Emitted after a chosen catalog subset is written to a library artifact file (REQ-P11-UI-016) — carries the destination path as ``str``. Emitted when a library-subset export cannot complete — a translatable message; no file is written. Emitted when the user cancels the &quot;Export asset artifact&quot; file dialog. Emitted after a project + its whole reference set is written to a ``.pixbundle`` file (the shipped :func:`~pixelart_creator.data.asset_export.export_project_bundle`, unchanged) — carries the destination path as ``str``. Emitted when a project-bundle export cannot complete — a translatable message; no file is written. Emitted when the user cancels the &quot;Export project bundle&quot; file dialog. Emitted after a ``.pixbundle`` is reconstructed into a new project directory (the shipped :func:`~pixelart_creator.data.asset_export.import_project_bundle`, unchanged) — carries the ``(Document, AssetCatalog)`` tuple. This session&apos;s own catalog is untouched: the bundle reconstructs a **new** project, never merging into the open library (plan Section 3.7). Emitted when a project-bundle import cannot complete — a translatable message; ``target_dir`` is left exactly as it was (the shipped function&apos;s own atomic-move guarantee). Emitted when the user cancels the &quot;Import project bundle&quot; file dialog. The shared undo stack the tag commands push onto (REQ-P11-UI-002). The durable catalog root once bound (REQ-P11-DATA-008); ``None`` until :meth:`bind_root` is called, so an unbound session stays purely in-memory. The content-addressable store the registration actions write blobs through, once bound; ``None`` until :meth:`bind_content_store`. The revision store the registration actions record through, once bound; ``None`` until :meth:`bind_revision_store`.</extracomment>
        <translation>导入素材文件</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="508"/>
        <location filename="../ui/asset_library_actions.py" line="571"/>
        <source>Asset artifact (*%1)</source>
        <translation>素材文件(*%1)</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="519"/>
        <source>&quot;%1&quot; is a project bundle, not a single asset. Use &quot;Import project bundle…&quot; instead.</source>
        <translation>“%1”是项目包，而不是单个素材。请改用“导入项目包…”。</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="524"/>
        <location filename="../ui/asset_library_actions.py" line="728"/>
        <source>Import asset</source>
        <translation>导入素材</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="570"/>
        <source>Export asset artifact</source>
        <translation>导出素材文件</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="625"/>
        <location filename="../ui/asset_library_actions.py" line="752"/>
        <source>Export project bundle</source>
        <translation>导出项目包</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="626"/>
        <location filename="../ui/asset_library_actions.py" line="677"/>
        <source>Project bundle (*%1)</source>
        <translation>项目包(*%1)</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="676"/>
        <location filename="../ui/asset_library_actions.py" line="765"/>
        <source>Import project bundle</source>
        <translation>导入项目包</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="722"/>
        <source>Could not import the asset: %1</source>
        <translation>无法导入素材: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="733"/>
        <source>Could not export the asset: %1</source>
        <translation>无法导出素材: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="739"/>
        <source>Export asset</source>
        <translation>导出素材</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="746"/>
        <source>Could not export the project bundle: %1</source>
        <translation>无法导出项目包: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="759"/>
        <source>Could not import the project bundle: %1</source>
        <translation>无法导入项目包: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="830"/>
        <source>There is no active selection to register.</source>
        <translation>没有可登记的当前选区</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="1151"/>
        <source>Could not register the asset: %1</source>
        <translation>无法登记素材: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="1157"/>
        <source>Asset registration</source>
        <translation>素材登记</translation>
    </message>
</context>
<context>
    <name>Asset_Register_Dialog</name>
    <message numerus="yes">
        <location filename="../ui/asset_register_dialog.py" line="165"/>
        <source>Too many tags: %n given, %2 allowed.</source>
        <extracomment>Combo order = the five shipped kinds, in the vocabulary&apos;s own declaration order (``logic/asset_catalog.AssetKind`` — RP-1&apos;s &quot;five shipped kinds&quot;).</extracomment>
        <translation>
            <numerusform>标签过多: 已给出 %n 个，最多允许 %2 个</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_register_dialog.py" line="170"/>
        <source>Tag &quot;%1&quot; is too long (%n bytes allowed).</source>
        <translation>
            <numerusform>标签“%1”过长(最多 %n 字节)</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="178"/>
        <source>Enter a name for this asset.</source>
        <translation>请输入此素材的名称</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="190"/>
        <source>Register Asset</source>
        <translation>登记素材</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="191"/>
        <source>Asset registration prompt</source>
        <translation>素材登记提示</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="193"/>
        <source>Name</source>
        <translation>名称</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="194"/>
        <source>Asset display name</source>
        <translation>素材显示名称</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="195"/>
        <source>Display name</source>
        <translation>显示名称</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="197"/>
        <source>Kind</source>
        <translation>类型</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="198"/>
        <source>Asset kind</source>
        <translation>素材类型</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="199"/>
        <source>Sprite</source>
        <translation>精灵</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="200"/>
        <source>Animation</source>
        <translation>动画</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="201"/>
        <source>Tileset</source>
        <translation>瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="202"/>
        <source>Tilemap</source>
        <translation>瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="203"/>
        <source>Palette</source>
        <translation>调色板</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="205"/>
        <source>Tags</source>
        <translation>标签</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="206"/>
        <source>Asset tags, comma-separated</source>
        <translation>素材标签，用逗号分隔</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="207"/>
        <source>Optional tags, comma-separated</source>
        <translation>可选标签，用逗号分隔</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="209"/>
        <source>Registration validation message</source>
        <translation>登记验证消息</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="213"/>
        <source>Register</source>
        <translation>登记</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="214"/>
        <source>Register asset</source>
        <translation>登记素材</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="217"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="218"/>
        <source>Cancel registration</source>
        <translation>取消登记</translation>
    </message>
</context>
<context>
    <name>Asset_Reuse_Panel</name>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="254"/>
        <source>The selected asset is not available.</source>
        <extracomment>Columns of the in-project reference list (REQ-P11-UI-021 indicators). The selected asset row&apos;s ``asset_id`` is stashed on the name column (both trees). Column of the in-project reference list that shows the resolve state. Emitted with ``(asset_id, project)`` after a successful reference. Each open project&apos;s real, durable reference set (REQ-P11-UI-021), bound through :meth:`set_project_reference_set` or created empty by :meth:`add_project`. Never a predicate&apos;s own scratch state. In-project reference list — the resolve-state / shared-state indicators (REQ-P11-UI-021), over the *current* project&apos;s real reference set.</extracomment>
        <translation>所选素材不可用</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="261"/>
        <source>Shared content for %1 is not available.</source>
        <translation>%1 的共享内容不可用</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="276"/>
        <source>%1 is already referenced in %2.</source>
        <translation>%1 已在 %2 中引用</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="282"/>
        <source>Referenced %1 into %2.</source>
        <translation>已将 %1 引用到 %2</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="345"/>
        <location filename="../ui/asset_reuse_panel.py" line="408"/>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <location filename="../ui/asset_reuse_panel.py" line="484"/>
        <source>Shared</source>
        <translation>共享</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="357"/>
        <location filename="../ui/asset_reuse_panel.py" line="425"/>
        <source>Referenced by another open project</source>
        <translation>已被其他打开的项目引用</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="404"/>
        <source>In library</source>
        <translation>在库中</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="406"/>
        <source>Not found in library</source>
        <translation>未在库中找到</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="421"/>
        <source>This reference could not be found in the local library.</source>
        <translation>在本地库中找不到此引用</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_reuse_panel.py" line="431"/>
        <source>%n unresolved reference(s) in this project.</source>
        <translation>
            <numerusform>此项目中有 %n 个未解析的引用</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="436"/>
        <source>All references resolve in the local library.</source>
        <translation>所有引用均可在本地库中解析</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="452"/>
        <source>Sprite</source>
        <translation>精灵</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="453"/>
        <source>Animation</source>
        <translation>动画</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="454"/>
        <source>Tileset</source>
        <translation>瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="455"/>
        <source>Tilemap</source>
        <translation>瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="456"/>
        <source>Palette</source>
        <translation>调色板</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="462"/>
        <source>Cross-project reuse</source>
        <translation>跨项目复用</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="463"/>
        <source>Project:</source>
        <translation>项目:</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="464"/>
        <source>Target project</source>
        <translation>目标项目</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <location filename="../ui/asset_reuse_panel.py" line="466"/>
        <source>New project name</source>
        <translation>新项目名称</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="467"/>
        <source>Add Project</source>
        <translation>添加项目</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="468"/>
        <source>Add a project</source>
        <translation>添加一个项目</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <location filename="../ui/asset_reuse_panel.py" line="481"/>
        <source>Name</source>
        <translation>名称</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <location filename="../ui/asset_reuse_panel.py" line="482"/>
        <source>Kind</source>
        <translation>类型</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <source>Projects</source>
        <translation>项目</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="472"/>
        <source>Shared assets</source>
        <translation>共享素材</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="473"/>
        <source>Reference into Project</source>
        <translation>引用到项目</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="475"/>
        <source>Reference the selected asset into the project</source>
        <translation>将所选素材引用到项目中</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="477"/>
        <source>Reuse status</source>
        <translation>复用状态</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="478"/>
        <source>References in this project:</source>
        <translation>此项目中的引用:</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="483"/>
        <source>Resolve state</source>
        <translation>解析状态</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="488"/>
        <source>References in the current project</source>
        <translation>当前项目中的引用</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="490"/>
        <source>Missing reference count</source>
        <translation>缺失引用数</translation>
    </message>
</context>
<context>
    <name>Asset_Search_Panel</name>
    <message>
        <location filename="../ui/asset_search_panel.py" line="133"/>
        <source>Sprite</source>
        <extracomment>The fixed display order of the kind combo (after the &quot;All kinds&quot; entry). Emitted with ``(name, tags, kind)`` whenever a control changes. ``name`` is a possibly-empty str, ``tags`` a list of str, ``kind`` an ``AssetKind`` or ``None``. The library panel consumes it via ``set_query``.</extracomment>
        <translation>精灵</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="134"/>
        <source>Animation</source>
        <translation>动画</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="135"/>
        <source>Tileset</source>
        <translation>瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="136"/>
        <source>Tilemap</source>
        <translation>瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="137"/>
        <source>Palette</source>
        <translation>调色板</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="142"/>
        <source>Asset search and filter</source>
        <translation>素材搜索与筛选</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="143"/>
        <source>Name:</source>
        <translation>名称:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="144"/>
        <location filename="../ui/asset_search_panel.py" line="145"/>
        <source>Search by name</source>
        <translation>按名称搜索</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="146"/>
        <source>Tags:</source>
        <translation>标签:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="147"/>
        <source>Filter by tags (comma-separated)</source>
        <translation>按标签筛选(用逗号分隔)</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="148"/>
        <source>Filter by tags</source>
        <translation>按标签筛选</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="149"/>
        <source>Kind:</source>
        <translation>类型:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="150"/>
        <source>Filter by kind</source>
        <translation>按类型筛选</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="151"/>
        <source>All kinds</source>
        <translation>所有类型</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="154"/>
        <source>Clear</source>
        <translation>清除</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="155"/>
        <source>Clear the search and filters</source>
        <translation>清除搜索和筛选条件</translation>
    </message>
</context>
<context>
    <name>Asset_Tagging_Panel</name>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="124"/>
        <location filename="../ui/asset_tagging_panel.py" line="154"/>
        <source>Tagging</source>
        <extracomment>The asset whose tags are being edited (``&quot;&quot;`` when none is selected).</extracomment>
        <translation>标记</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="133"/>
        <source>Add tag &quot;%1&quot;</source>
        <translation>添加标签“%1”</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="163"/>
        <source>Remove tag &quot;%1&quot;</source>
        <translation>移除标签“%1”</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="198"/>
        <source>No asset selected</source>
        <translation>未选择素材</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="201"/>
        <source>Tags for: %1</source>
        <translation>素材标签: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="205"/>
        <source>Asset tagging</source>
        <translation>素材标记</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="206"/>
        <source>Asset tags</source>
        <translation>素材标签</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="207"/>
        <location filename="../ui/asset_tagging_panel.py" line="208"/>
        <source>New tag</source>
        <translation>新标签</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="209"/>
        <source>Add Tag</source>
        <translation>添加标签</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="210"/>
        <source>Add tag to asset</source>
        <translation>为素材添加标签</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="211"/>
        <source>Remove Tag</source>
        <translation>移除标签</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="212"/>
        <source>Remove selected tag</source>
        <translation>移除所选标签</translation>
    </message>
</context>
<context>
    <name>Asset_Update_Prompt_Dialog</name>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="491"/>
        <source>Library Asset Updated</source>
        <extracomment>This dialog&apos;s own outcome vocabulary — distinct from the *persisted* three-value preference domain (``&quot;ask&quot;`` / ``&quot;always_pick_up&quot;`` / ``&quot;always_keep_referenced&quot;``, declared in ``logic/asset_references.ASSET_LIBRARY_EDIT``): an outcome is what THIS prompt resolved to for ONE edit; the preference is what to do about FUTURE edits without asking. **Promoted aliases (ADR-0062, ruling P11-R13 — same &quot;one definition of a control, aliases kept so no call site moves&quot; move ruling P11-R11 made for ``data/asset_catalog_io.py``&apos;s ``_safe_asset_id`` / ``_resolve_within``, applied here in the other direction):** the canonical outcome domain now lives in the logic layer, :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_PICK_UP` / :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_KEEP`, at byte-identical values — these two names are retained, unchanged, as aliases so every existing reference in this module and its callers still resolves without moving. The two non-default members of ``ASSET_LIBRARY_EDIT.domain`` this prompt writes through :func:`~pixelart_creator.logic.project_prefs.with_value` (the registered seam validates membership; nothing here re-derives the domain). One session-memory entry key: ``(asset_id, edit_token)``. ``edit_token`` is ``None`` when the caller has no content-hash identity to hand yet (see :meth:`Asset_Update_Prompt_Dialog.decide`) — two ``None``-token calls with the same ``asset_id`` are therefore treated as the SAME edit, which is the exact, disclosed limit of this session memory absent a real per-edit identity (module docstring boundary note). Emitted once a button is clicked, before the dialog closes: ``(outcome, dont_ask_again)``. For a caller driving the dialog non-modally (``open()``); :meth:`decide` does not need it. **Per-edit session memory** (extended by plan §3.11 (2b)): &quot;the same edit does not ask again&quot; for :meth:`decide` (``REQ-P11-UI-022``&apos;s own acceptance clause), scoped to one project&apos;s session bucket so a different project (:data:`ProjectPrefs`, ``SC-P11-UI-023-3``) is never affected by another project&apos;s session memory. Keyed by ``id(prefs)`` -&gt; ``(prefs, {edit_key: outcome})`` when no ``project_key`` is supplied (today&apos;s byte-for-byte behaviour — the snapshot itself is held strongly alongside its id so a *live* entry&apos;s id can never be reused by an unrelated, later ``ProjectPrefs`` object, an ``is`` check on lookup is the defensive second line); keyed by the caller-supplied ``project_key`` (a ``str``) instead when one is given — the production route (``ui/main_window.py``, plan §3.11 (2b)), because ``document.prefs`` is *replaced* on any confirmation-preference toggle (``ui/project_prefs_actions.py:165/175``), which would silently orphan an ``id(prefs)``-keyed bucket. This dict itself is still in-memory, per-process runtime state — it is never itself written to disk, and it is never written through ``logic/project_prefs.py`` (that seam is reserved for the &quot;Don&apos;t ask again&quot; preference, ``REQ-P11-UI-023``, a materially different, explicit, durable choice). **Corrected (ADR-0062, ruling P11-R13):** this bucket is no longer the *only* record of an unticked decision — it can be **hydrated** at the start of a session from the durable, per-edit ledger (:class:`~pixelart_creator.logic.asset_edit_decisions.AssetEditDecisions`) via :meth:`prime_session`, and every fresh decision made through :meth:`decide` is handed to that method&apos;s optional ``on_decided`` callback so the caller can persist it (the write-ahead journal / the project-file save) — this module performs no I/O of its own; it only calls out. Disclosed cost, unchanged: a decided ``ProjectPrefs`` snapshot (or a live ``project_key`` bucket) is retained for the life of the process; call :meth:`forget_session` when a project closes to release it.</extracomment>
        <translation>素材库中的素材已更新</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="492"/>
        <source>Library asset updated confirmation</source>
        <translation>素材库素材更新确认</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="493"/>
        <source>this asset</source>
        <translation>此素材</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="496"/>
        <source>The library asset &quot;%1&quot; has changed since your project last referenced it. Pick up the change, or keep the version your project already references?</source>
        <translation>自项目上次引用以来，素材库中的素材“%1”已发生更改。要采用此更改，还是保留项目已引用的版本?</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="501"/>
        <source>Library edit notice</source>
        <translation>素材库编辑通知</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="502"/>
        <source>Don&apos;t ask again</source>
        <translation>不再询问</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="504"/>
        <source>Remember this choice for future edits of this asset</source>
        <translation>记住此选择，用于此素材以后的编辑</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="506"/>
        <source>Pick Up the Change</source>
        <translation>采用更改</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="508"/>
        <source>Pick up the library asset&apos;s change</source>
        <translation>采用素材库中素材的更改</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="510"/>
        <source>Keep the Referenced Version</source>
        <translation>保留已引用的版本</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="512"/>
        <source>Keep the version this project already references</source>
        <translation>保留此项目已引用的版本</translation>
    </message>
</context>
<context>
    <name>Asset_Version_Browser</name>
    <message>
        <location filename="../ui/asset_version_browser.py" line="194"/>
        <source>%1 (current)</source>
        <extracomment>The selected row&apos;s revision ``content_hash`` is stashed on the order column. How many leading characters of a content hash the browser shows (the full hash is kept on the tooltip / item data — this is display abbreviation only, not identity). Emitted with the new head&apos;s ``content_hash`` after a successful restore (so a caller / test can react); no payload semantics beyond the reinstated head hash. The asset whose revisions are shown (``&quot;&quot;`` when none is selected).</extracomment>
        <translation>%1(当前)</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="195"/>
        <location filename="../ui/asset_version_browser.py" line="240"/>
        <source>(unknown)</source>
        <translation>(未知)</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="234"/>
        <location filename="../ui/asset_version_browser.py" line="260"/>
        <location filename="../ui/asset_version_browser.py" line="276"/>
        <source>Version history</source>
        <translation>版本历史记录</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_version_browser.py" line="242"/>
        <source>Revision %1 — %n bytes, marker %3, author %4</source>
        <translation>
            <numerusform>修订 %1，%n 字节，标记 %3，作者 %4</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="332"/>
        <location filename="../ui/asset_version_browser.py" line="337"/>
        <source>Revisions of: %1</source>
        <translation>素材修订: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="340"/>
        <source>No asset selected</source>
        <translation>未选择素材</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="344"/>
        <source>Asset version browser</source>
        <translation>素材版本浏览器</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="346"/>
        <source>#</source>
        <translation>#</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="346"/>
        <source>Created</source>
        <translation>创建时间</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="346"/>
        <source>Author</source>
        <translation>作者</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="346"/>
        <source>Content</source>
        <translation>内容</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="348"/>
        <source>Asset revisions</source>
        <translation>素材修订</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="349"/>
        <source>Revision details</source>
        <translation>修订详情</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="350"/>
        <source>Inspect</source>
        <translation>查看</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="351"/>
        <source>Inspect selected revision</source>
        <translation>查看所选修订</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="352"/>
        <source>Restore</source>
        <translation>还原</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="354"/>
        <source>Restore selected revision as a new head</source>
        <translation>将所选修订还原为新的最新版本</translation>
    </message>
</context>
<context>
    <name>Assistant_Dock</name>
    <message>
        <location filename="../ui/assistant_dock.py" line="160"/>
        <source>No AI provider is configured. Use Configure… to set an endpoint and API key.</source>
        <extracomment>Provider of the active document (``None`` when no document tab is open). Provider of the current chat backend (a configured ``data/llm`` adapter, or ``None`` when the user has not configured a provider). Probed fresh on each send so a config change takes effect immediately; ``ui/`` never sees a provider/HTTP type. ``(commands, label)`` — the turn&apos;s ordered, unapplied reversible commands and a translatable undo label; the host wraps them in one ``AssistantCommand``. How many transcript messages have already been rendered (render the tail).</extracomment>
        <translation>尚未配置 AI 服务商。请使用“配置…”设置端点和 API 密钥。</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="168"/>
        <source>Open a document before chatting with the assistant.</source>
        <translation>请先打开文档，再与助手对话</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="185"/>
        <source>Assistant edit</source>
        <translation>助手编辑</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="191"/>
        <source>Assistant error: {0}</source>
        <translation>助手出错: {0}</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="211"/>
        <source>Confirm assistant action</source>
        <translation>确认助手操作</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="214"/>
        <source>The assistant wants to run &quot;{0}&quot;, which cannot be reliably undone. Allow it?</source>
        <translation>助手想要运行“{0}”，此操作无法可靠撤销。是否允许?</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="231"/>
        <source>Provider configuration saved.</source>
        <translation>AI 服务商配置已保存</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="240"/>
        <source>Working…</source>
        <translation>正在处理…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="253"/>
        <source>You</source>
        <translation>你</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="256"/>
        <source>Assistant</source>
        <translation>助手</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="257"/>
        <source>(taking an action…)</source>
        <translation>(正在执行操作…)</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="259"/>
        <source>Action</source>
        <translation>操作</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="289"/>
        <source>AI Assistant</source>
        <translation>AI 助手</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="290"/>
        <source>AI assistant chat</source>
        <translation>AI 助手聊天</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="291"/>
        <source>Assistant conversation</source>
        <translation>助手对话</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="292"/>
        <source>Message to the assistant</source>
        <translation>发给助手的消息</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="293"/>
        <source>Ask the assistant to edit…</source>
        <translation>请助手进行编辑…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="294"/>
        <source>Send</source>
        <translation>发送</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="295"/>
        <source>Send message</source>
        <translation>发送消息</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="296"/>
        <source>Configure…</source>
        <translation>配置…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="297"/>
        <source>Configure AI provider</source>
        <translation>配置 AI 服务商</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="298"/>
        <source>Assistant working indicator</source>
        <translation>助手工作指示器</translation>
    </message>
</context>
<context>
    <name>Batch_Export_Panel</name>
    <message>
        <location filename="../ui/batch_export_panel.py" line="160"/>
        <source>%1 — done</source>
        <extracomment>Optional provider returning the document to export against (the active tab).</extracomment>
        <translation>%1 — 完成</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="167"/>
        <source>%1 — failed: %2</source>
        <translation>%1 — 失败: %2</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="190"/>
        <source>Add Target…</source>
        <translation>添加目标…</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="191"/>
        <source>Remove</source>
        <translation>移除</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="192"/>
        <source>Export All</source>
        <translation>全部导出</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="193"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="194"/>
        <source>Batch export</source>
        <translation>批量导出</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="195"/>
        <source>Batch export targets</source>
        <translation>批量导出目标</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="196"/>
        <source>Batch export progress</source>
        <translation>批量导出进度</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="197"/>
        <source>Add export target</source>
        <translation>添加导出目标</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="198"/>
        <source>Remove export target</source>
        <translation>移除导出目标</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="199"/>
        <source>Export all targets</source>
        <translation>导出所有目标</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="200"/>
        <source>Cancel batch export</source>
        <translation>取消批量导出</translation>
    </message>
</context>
<context>
    <name>Batch_Recolour_Panel</name>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="172"/>
        <source>Running…</source>
        <extracomment>Combo indices for the mapping mode (module-local UI enumeration). Upper bound for the index spin boxes — the widest palette a buffer can address (a display range for the spin control, not a domain tuning value). ``(ops, label)`` — the host should dispatch the ``batch_recolour`` op on the worker as one undoable grouped command (REQ-P8-UI-006/-009). Each pair is ``(src, dst)`` — ints for index mode, RGBA tuples for colour mode. Kept parallel to the visible list.</extracomment>
        <translation>正在运行…</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="174"/>
        <source>Done</source>
        <translation>完成</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="175"/>
        <source>Idle</source>
        <translation>空闲</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="213"/>
        <source>Pick a colour</source>
        <translation>选取颜色</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="222"/>
        <source>From: %1</source>
        <translation>源: %1</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="225"/>
        <source>To: %1</source>
        <translation>目标: %1</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="238"/>
        <source>%1 → %2</source>
        <translation>%1 → %2</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="268"/>
        <source>Batch Recolour</source>
        <translation>批量重新着色</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="289"/>
        <source>Mapping:</source>
        <translation>映射:</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="290"/>
        <source>Index remap</source>
        <translation>索引重映射</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="291"/>
        <source>Colour remap</source>
        <translation>颜色重映射</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="292"/>
        <source>Frame:</source>
        <translation>帧:</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="293"/>
        <source>Add Pair</source>
        <translation>添加配对</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="294"/>
        <source>Remove</source>
        <translation>移除</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="295"/>
        <source>Apply Batch Recolour</source>
        <translation>应用批量重新着色</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="297"/>
        <source>Batch recolour</source>
        <translation>批量重新着色</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="298"/>
        <source>Recolour mapping mode</source>
        <translation>重新着色映射模式</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="299"/>
        <source>Target frame index</source>
        <translation>目标帧索引</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="300"/>
        <source>Source palette index</source>
        <translation>源调色板索引</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="301"/>
        <source>Destination palette index</source>
        <translation>目标调色板索引</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="302"/>
        <source>Pick source colour</source>
        <translation>选取源颜色</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="303"/>
        <source>Pick destination colour</source>
        <translation>选取目标颜色</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="304"/>
        <source>Recolour mapping pairs</source>
        <translation>重新着色映射配对</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="305"/>
        <source>Add a recolour pair</source>
        <translation>添加重新着色配对</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="306"/>
        <source>Remove the selected pair</source>
        <translation>移除所选配对</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="307"/>
        <source>Apply the batch recolour</source>
        <translation>应用批量重新着色</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="308"/>
        <source>Progress</source>
        <translation>进度</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="309"/>
        <source>Batch recolour progress</source>
        <translation>批量重新着色进度</translation>
    </message>
</context>
<context>
    <name>Branch_Diff_Dialog</name>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="214"/>
        <source>Metadata changes</source>
        <extracomment>The four op-tier groups, fixed display order (``REQ-P10-UI-016``) — matches ``branch_diff._CLASS_RANK``&apos;s declaration order (metadata, layer_attr, layer_order, raster; ``convergence.py:228``). Emitted with ``source_name`` when the user activates *Continue to merge*. This view performs **no** merge itself (``REQ-P10-UI-018``) — the caller runs the unchanged ``Branching_Session.merge_to_mainline`` (the same shipped path the panel&apos;s own Merge button uses, ``REQ-P10-UI-019``).</extracomment>
        <translation>元数据更改</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="215"/>
        <source>Layer attribute changes</source>
        <translation>图层属性更改</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="216"/>
        <source>Layer order changes</source>
        <translation>图层顺序更改</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="217"/>
        <source>Raster (pixel) changes</source>
        <translation>栅格(像素)更改</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="229"/>
        <source>Metadata &apos;{key}&apos; set to &apos;{value}&apos;</source>
        <translation>元数据“{key}”已设为“{value}”</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="233"/>
        <source>Frame {frame}, layer {layer}: {attr} = {value}</source>
        <translation>第 {frame} 帧，图层 {layer}: {attr} = {value}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="237"/>
        <source>Frame {frame}: layer order changed</source>
        <translation>第 {frame} 帧: 图层顺序已更改</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="242"/>
        <source>Frame {frame}, layer {layer}: tile ({tile_x}, {tile_y})</source>
        <translation>第 {frame} 帧，图层 {layer}: 瓦片({tile_x}, {tile_y})</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="277"/>
        <source>Frame {frame}, layer {layer}: ({x}, {y}) {width}×{height}</source>
        <translation>第 {frame} 帧，图层 {layer}: ({x}, {y}) {width}×{height}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="304"/>
        <source>Diff: &apos;{source}&apos; vs &apos;{target}&apos;</source>
        <translation>差异: “{source}”对比“{target}”</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="308"/>
        <location filename="../ui/branch_diff_dialog.py" line="309"/>
        <source>Branch diff</source>
        <translation>分支差异</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="312"/>
        <source>Comparing branch &apos;{source}&apos; (source) against &apos;{target}&apos; (target). This is a snapshot taken now — the merge has not happened yet.</source>
        <translation>正在将分支“{source}”(源)与“{target}”(目标)进行比较。这是此刻生成的快照，合并尚未进行。</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="317"/>
        <source>Diff basis</source>
        <translation>差异基准</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="322"/>
        <source>Checked: the recorded changes account for everything on this branch.</source>
        <translation>已检查: 已记录的更改涵盖了此分支上的全部内容</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="329"/>
        <source>Warning: some changes on this branch are not recorded and will not be merged. {detail}</source>
        <translation>警告: 此分支上有些更改未被记录，不会被合并。{detail}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="333"/>
        <source>Supervision result</source>
        <translation>监督结果</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="336"/>
        <source>States whether the recorded operation log explains every change on this branch&apos;s live document.</source>
        <translation>说明已记录的操作日志能否解释此分支当前文档中的每一处更改</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="343"/>
        <source>This branch has no changes to merge.</source>
        <translation>此分支没有可合并的更改</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="355"/>
        <source>No changes.</source>
        <translation>无更改</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="357"/>
        <source>%n change(s).</source>
        <translation>
            <numerusform>%n 项更改</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="359"/>
        <source>{title} list</source>
        <translation>{title} 列表</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="361"/>
        <source>%n entries.</source>
        <translation>
            <numerusform>%n 个条目</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="363"/>
        <source>Affected regions</source>
        <translation>受影响的区域</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="366"/>
        <source>Each region is reported at the whole {tile}×{tile} pixel tile granularity — a one-pixel change still covers a full tile here.</source>
        <translation>每个区域均按完整的 {tile}×{tile} 像素瓦片粒度报告，因此这里即使只更改一个像素，也会覆盖整个瓦片</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="371"/>
        <source>Affected regions list</source>
        <translation>受影响的区域列表</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="373"/>
        <source>%n regions.</source>
        <translation>
            <numerusform>%n 个区域</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="378"/>
        <source>%n operation(s) total, across %2 distinct target(s).</source>
        <translation>
            <numerusform>共 %n 项操作，涉及 %2 个不同的目标</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="383"/>
        <source>Divergence total</source>
        <translation>分歧总数</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="385"/>
        <source>Continue to Merge</source>
        <translation>继续合并</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="386"/>
        <source>Continue to merge</source>
        <translation>继续合并</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="389"/>
        <source>Performs the same conflict-free merge as the branching panel&apos;s Merge control.</source>
        <translation>执行与分支面板中“合并”控件相同的无冲突合并</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="393"/>
        <location filename="../ui/branch_diff_dialog.py" line="394"/>
        <source>Close</source>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="396"/>
        <source>Closes this view without merging or changing anything.</source>
        <translation>关闭此视图，不进行合并，也不更改任何内容</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="408"/>
        <source>frames {frames}</source>
        <translation>帧 {frames}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="414"/>
        <source>layers {layers}</source>
        <translation>图层 {layers}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="422"/>
        <source>attributes {attrs}</source>
        <translation>属性 {attrs}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="431"/>
        <source>metadata keys {keys}</source>
        <translation>元数据键 {keys}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="437"/>
        <source>tiles {tiles}</source>
        <translation>瓦片 {tiles}</translation>
    </message>
</context>
<context>
    <name>Branching_Panel</name>
    <message>
        <location filename="../ui/branching_panel.py" line="364"/>
        <location filename="../ui/branching_panel.py" line="378"/>
        <location filename="../ui/branching_panel.py" line="395"/>
        <source>Branch</source>
        <extracomment>The reserved name of the always-present mainline branch. emitted when the set of branches changed (create / merge). ``(name,)`` — the active branch changed. ``(document,)`` — a branch was materialised/merged; the caller loads it into the active tab (a whole Qt-free :class:`~pixelart_creator.logic.document.Document`). ``(summary,)`` — a merge completed conflict-free; carries a translatable-ready outcome summary the panel surfaces (REQ-P10-UI-012). The Document object the active branch&apos;s edits actually land on — the same instance the caller (``ui/main_window.py``) mutates in place, so a raster trace&apos;s tile bytes are always read post-edit (plan §8.2). ``None`` until a base document is set. ``(name,)`` — the user activated the open-diff affordance for the selected feature branch (REQ-P10-UI-014). The caller (``ui/main_window.py``) supplies the active tab&apos;s live ``Document`` to ``logic/branch_diff.supervise`` and, once ``ui/branch_diff_dialog.py`` exists, opens the pre-merge diff view from it.</extracomment>
        <translation>分支</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="365"/>
        <source>Open a project first.</source>
        <translation>请先打开项目</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="369"/>
        <location filename="../ui/branching_panel.py" line="499"/>
        <source>New Branch</source>
        <translation>新建分支</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="369"/>
        <source>Branch name:</source>
        <translation>分支名称:</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="412"/>
        <location filename="../ui/branching_panel.py" line="503"/>
        <source>Merge</source>
        <translation>合并</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branching_panel.py" line="442"/>
        <source>Merged branch &apos;{name}&apos; (%n edits) into mainline — conflict-free.</source>
        <translation>
            <numerusform>已将分支“{name}”(%n 处编辑)合并到主线，无冲突</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="456"/>
        <source>{name} (active)</source>
        <translation>{name}(当前)</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="475"/>
        <source>Open the pre-merge diff for the selected branch.</source>
        <translation>打开所选分支的合并前差异</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="479"/>
        <source>Disabled: open a project first.</source>
        <translation>已禁用: 请先打开项目</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="484"/>
        <source>Disabled: select a feature branch, not mainline, to view its diff.</source>
        <translation>已禁用: 请选择功能分支(而非主线)以查看其差异</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="491"/>
        <source>Branching</source>
        <translation>分支</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="494"/>
        <source>Branch the project to edit a variation independently, then merge it back. Merges are conflict-free.</source>
        <translation>为项目创建分支，独立编辑某个变体，再合并回来。合并不会产生冲突。</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="498"/>
        <source>Branches</source>
        <translation>分支</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="500"/>
        <source>Create a new branch</source>
        <translation>创建新分支</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="501"/>
        <source>Switch</source>
        <translation>切换</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="502"/>
        <source>Switch to the selected branch</source>
        <translation>切换到所选分支</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="505"/>
        <source>Merge the selected branch into mainline</source>
        <translation>将所选分支合并到主线</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="507"/>
        <source>Open Diff</source>
        <translation>打开差异</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="509"/>
        <source>Open the pre-merge diff for the selected branch</source>
        <translation>打开所选分支的合并前差异</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="511"/>
        <source>Merge outcome</source>
        <translation>合并结果</translation>
    </message>
</context>
<context>
    <name>Canvas_Size_Dialog</name>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="79"/>
        <source>Canvas Size</source>
        <translation>画布大小</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="80"/>
        <source>Canvas size dialog</source>
        <translation>画布大小对话框</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="81"/>
        <source>Target canvas width in pixels</source>
        <translation>目标画布宽度(像素)</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="82"/>
        <source>Target canvas height in pixels</source>
        <translation>目标画布高度(像素)</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="83"/>
        <source>Width (px)</source>
        <translation>宽度(px)</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="84"/>
        <source>Height (px)</source>
        <translation>高度(px)</translation>
    </message>
</context>
<context>
    <name>Canvas_View</name>
    <message>
        <location filename="../ui/canvas_view.py" line="318"/>
        <location filename="../ui/canvas_view.py" line="1443"/>
        <source>Canvas</source>
        <extracomment>Platform name reported by Qt when running without a windowing system. Emitted with the current zoom scale after any zoom change. Emitted with the buffer ``(x, y)`` when the canvas is right-clicked (seam). Emitted with the picked RGBA tuple when the colour-picker sets a colour. Emitted ``(is_active, is_copy)`` when a floating move/copy state changes (drives the shell&apos;s copy-mode status hint, REQ-P2-UI-032/-036). Emitted when a paint/mask-edit stroke is refused because the active layer is locked (D-05); the shell surfaces a &quot;layer is locked&quot; notice. Emitted when a left-click lands outside the active document&apos;s bounds (FIX 5, 2026-08-24 field defect): a click there must not arm a stroke, and must not fail silently — the shell surfaces a notice, following the ``lockedLayerEditRejected`` precedent exactly. Emitted when a paint/mask-edit is refused because the active layer is a REFERENCE or SMART layer (REQ-P3-UI-006 clause 5: non-editable targets are three classes, not two — locked, reference, and smart — and every one of them must be surfaced, never silently swallowed). Distinct from ``lockedLayerEditRejected`` so the shell can show the right notice; ``is_active_editable()`` returns ``False`` for all three classes, and this signal covers the two this view previously dropped on the floor. Emitted when a tool ran (the guards passed) but produced no pixel change — e.g. a flood fill on a region that already holds the picked colour (REQ-P1-UI-014), or a pencil placed on a pixel that already holds it — so no undo entry was pushed. An explicit, deliberate gesture (a completed colour-hub pick, REQ-P3-UI-006 clause 6) must never answer with silence even when it changed nothing. Emitted with the target frame index a ``Ctrl``+wheel / ``Ctrl``+middle- click frame gesture resolved to (REQ-IS-UI-010/-014); the shell routes it through the shipped frame-selection path. Pushes no command — frame navigation is view state (CL-13). Emitted when a confirmed ``Ctrl``+left-click (no floating move live) should add a frame after the active one (REQ-IS-UI-016); the shell builds and pushes the shipped undoable ``make_add_frame_command``. The three selection tools whose Shift/Alt modifiers stay the shipped add/subtract combine gesture (REQ-IS-UI-015) — Shift+drag pans for every other tool. Mirrors ``Main_Window._SELECTION_ENTRY_TOOL_IDS``. The wrapper every :class:`~pixelart_creator.ui.tools.base.ToolContext` is actually built with (see :class:`_RecordingUndoStack`); reads ``self._undo_stack``/``self._record_trace``/``self._recording_document`` live at each push, so `set_undo_stack`/`set_recording` need not rebuild it. A middle press awaiting the click/drag verdict (REQ-IS-UI-011): ``True`` between a middle press and either its release under ``CLICK_DRAG_THRESHOLD_PX`` (a click) or its promotion to ``_panning`` once the cursor travels past the threshold (a drag). A ``Ctrl``+left press awaiting the click/drag verdict (REQ-IS-UI-016, mirrors ``_middle_pending``): ``True`` between the press and either its release under ``CLICK_DRAG_THRESHOLD_PX`` (adds a frame) or its promotion to an ordinary paint/floating-move drag once the cursor travels past the threshold. The persisted Favourites model a plain wheel notch / unmodified middle click travel (REQ-IS-UI-008/-012); ``None`` until the shell binds one via :meth:`set_favourites_model`. The ``timestamp()`` of the RightButton press currently being dispatched through ``_menu_hook``, ``None`` for the keyboard (Menu key / Shift+F10) trigger. Consumed once via :meth:`pop_pending_right_press_timestamp` — deliberately NOT threaded as a third positional argument to ``_menu_hook`` itself, so the hook&apos;s signature (``Callable[[int, int], None]``) and every existing 2-argument hook (tests included) stay unchanged. Live mirror-centre override fed to ``logic.symmetry.mirror`` via each stroke&apos;s :class:`ToolContext` (D-28/CF-93); ``None`` keeps the shipped canvas-centre default. Fed by the shell&apos;s Symmetry_Panel. The guide currently being dragged (D-11), or ``None``. Raw (pre-snap) scene point at the start of the current stroke — the perspective direction-lock anchor (``logic.grids.perspective_snap``).</extracomment>
        <translation>画布</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="320"/>
        <location filename="../ui/canvas_view.py" line="1445"/>
        <source>Pixel canvas: left-click to paint, middle-drag to pan</source>
        <translation>像素画布: 左键单击绘制，中键拖动平移</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="1335"/>
        <source>Remove guide</source>
        <translation>移除参考线</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="1346"/>
        <source>No canvas actions yet</source>
        <translation>暂无画布操作</translation>
    </message>
</context>
<context>
    <name>Cel_Overwrite_Dialog</name>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="69"/>
        <source>Overwrite Existing Cel?</source>
        <translation>覆盖现有画格?</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="70"/>
        <source>Overwrite existing cel confirmation</source>
        <translation>覆盖现有画格确认</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="73"/>
        <source>The destination cell already has a drawing on it. Proceeding replaces that drawing. This can be undone.</source>
        <translation>目标单元格上已有绘图。继续将替换该绘图。此操作可以撤销。</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="77"/>
        <source>Overwrite warning</source>
        <translation>覆盖警告</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="78"/>
        <source>Don&apos;t ask again for this project</source>
        <translation>此项目不再询问</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="80"/>
        <source>Suppress this confirmation for the current project</source>
        <translation>对当前项目不再显示此确认</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="84"/>
        <location filename="../ui/cel_overwrite_dialog.py" line="85"/>
        <source>Overwrite</source>
        <translation>覆盖</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="88"/>
        <location filename="../ui/cel_overwrite_dialog.py" line="89"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
</context>
<context>
    <name>Colour_Cycling_Panel</name>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="156"/>
        <source>Colour Cycling</source>
        <extracomment>Milliseconds per cycling tick, derived from the tuning FPS (S12). Emitted with a list of display colours to preview (rotated palette). Emitted with ``(start, end, step)`` when Apply commits the cycle state.</extracomment>
        <translation>颜色循环</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="157"/>
        <source>Colour cycling panel</source>
        <translation>颜色循环面板</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="158"/>
        <source>Start</source>
        <translation>起点</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="159"/>
        <source>End</source>
        <translation>终点</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="160"/>
        <source>Step</source>
        <translation>步长</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="161"/>
        <source>Cycle range start index</source>
        <translation>循环范围起点索引</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="162"/>
        <source>Cycle range end index</source>
        <translation>循环范围终点索引</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="163"/>
        <source>Cycle step</source>
        <translation>循环步长</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="164"/>
        <source>Play / Stop</source>
        <translation>播放 / 停止</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="165"/>
        <source>Apply</source>
        <translation>应用</translation>
    </message>
</context>
<context>
    <name>Colour_Hub_Menu</name>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="642"/>
        <source>Colour Hub</source>
        <extracomment>Emitted with an RGBA tuple whenever a colour is picked (apply immediately, leg 1 — the live preview stream; never refused, REQ-P3-UI-006 clause 1). Emitted with an RGBA tuple on a COMPLETED pick only — one emission per discrete gesture (a wheel-drag release, a keyboard nudge release, a numeric spin&apos;s editingFinished, a single click on a harmony/shade/tint swatch, or a single click on a Favourites entry). A DOUBLE click / a keyboard activation on either swatch surface adopts instead and never reaches this signal (REQ-IS-UI-019/-020/-022, D-11). The shell (``ui/main_window.py``) uses this to run the active tool at the hub&apos;s anchor pixel as leg 2 (REQ-P3-UI-006 clauses 2-6). Re-emitted when the Favourites model changes (so the shell persists it). Set by the app-wide dismiss filter (below) to the ``timestamp()`` of the RightButton press that just hid this hub, and consumed once by :meth:`consume_dismiss_timestamp`. ``None`` when no dismissal is pending recognition.</extracomment>
        <translation>颜色中心</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="643"/>
        <source>Colour hub</source>
        <translation>颜色中心</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="644"/>
        <source>Add to Favourites</source>
        <translation>添加到收藏夹</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="647"/>
        <source>This tool does not paint the active colour, so the colour wheel is hidden here.</source>
        <translation>此工具不使用当前颜色绘制，因此这里隐藏了色轮</translation>
    </message>
</context>
<context>
    <name>Colour_Wheel_Widget</name>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="354"/>
        <location filename="../ui/colour_wheel_widget.py" line="637"/>
        <source>Red channel</source>
        <extracomment>Emitted with the picked :class:`QColor` on any user-initiated change that ADOPTS into the wheel (wheel-pad drag, value slider, numeric entries, and a harmony/shade/tint swatch&apos;s double-click/keyboard activation — never a swatch&apos;s single click). Emitted with a harmony/shade/tint swatch&apos;s own RGBA tuple on a single left click (REQ-IS-UI-020). PAINT-only: the wheel&apos;s own selection is deliberately left unchanged, unlike :attr:`colorPicked`.</extracomment>
        <translation>红色通道</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="357"/>
        <location filename="../ui/colour_wheel_widget.py" line="638"/>
        <source>Green channel</source>
        <translation>绿色通道</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="360"/>
        <location filename="../ui/colour_wheel_widget.py" line="639"/>
        <source>Blue channel</source>
        <translation>蓝色通道</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="363"/>
        <location filename="../ui/colour_wheel_widget.py" line="640"/>
        <source>Hue</source>
        <translation>色相</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="366"/>
        <location filename="../ui/colour_wheel_widget.py" line="641"/>
        <source>Saturation</source>
        <translation>饱和度</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="369"/>
        <location filename="../ui/colour_wheel_widget.py" line="629"/>
        <location filename="../ui/colour_wheel_widget.py" line="642"/>
        <source>Value</source>
        <translation>明度</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="564"/>
        <source>Current colour %1</source>
        <translation>当前颜色 %1</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="627"/>
        <source>Colour wheel picker</source>
        <translation>色轮取色器</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="630"/>
        <source>Brightness value</source>
        <translation>明度值</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="631"/>
        <source>R</source>
        <translation>R</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="632"/>
        <source>G</source>
        <translation>G</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="633"/>
        <source>B</source>
        <translation>B</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="634"/>
        <source>H</source>
        <translation>H</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="635"/>
        <source>S</source>
        <translation>S</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="636"/>
        <source>V</source>
        <translation>V</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="643"/>
        <source>Hex colour</source>
        <translation>十六进制颜色</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="644"/>
        <source>Complementary</source>
        <translation>互补色</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="645"/>
        <source>Analogous</source>
        <translation>邻近色</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="646"/>
        <source>Triadic</source>
        <translation>三角配色</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="647"/>
        <source>Tetradic</source>
        <translation>四角配色</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="648"/>
        <source>Split-complementary</source>
        <translation>分裂互补色</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="649"/>
        <source>Shades</source>
        <translation>暗色调</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="650"/>
        <source>Tints</source>
        <translation>亮色调</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="661"/>
        <source>harmony</source>
        <translation>配色</translation>
    </message>
</context>
<context>
    <name>Comments_Panel</name>
    <message>
        <location filename="../ui/comments_panel.py" line="117"/>
        <location filename="../ui/comments_panel.py" line="125"/>
        <location filename="../ui/comments_panel.py" line="135"/>
        <location filename="../ui/comments_panel.py" line="147"/>
        <location filename="../ui/comments_panel.py" line="169"/>
        <location filename="../ui/comments_panel.py" line="233"/>
        <source>Comments</source>
        <translation>评论</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="118"/>
        <source>Open a shared project before commenting.</source>
        <translation>请先打开共享项目，再发表评论</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="126"/>
        <source>Enter your member id before commenting.</source>
        <translation>请先输入你的成员 ID，再发表评论</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/comments_panel.py" line="136"/>
        <source>A comment may be at most %n bytes.</source>
        <translation>
            <numerusform>评论最多 %n 字节</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="207"/>
        <source>Resolved</source>
        <translation>已解决</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="207"/>
        <source>Open</source>
        <translation>未解决</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/comments_panel.py" line="222"/>
        <source>%1 / %n bytes</source>
        <translation>
            <numerusform>%1 / %n 字节</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="234"/>
        <source>Your member id:</source>
        <translation>你的成员 ID:</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="235"/>
        <source>e.g. alice</source>
        <translation>例如 alice</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="236"/>
        <source>Comment author id</source>
        <translation>评论作者 ID</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="238"/>
        <source>Author</source>
        <translation>作者</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="238"/>
        <source>Comment</source>
        <translation>评论</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="238"/>
        <source>Status</source>
        <translation>状态</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="240"/>
        <source>Comment thread</source>
        <translation>评论线程</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="241"/>
        <source>Write a comment…</source>
        <translation>撰写评论…</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="242"/>
        <source>New comment text</source>
        <translation>新评论文本</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="243"/>
        <source>Reply to selected</source>
        <translation>回复所选</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="244"/>
        <source>Reply to the selected comment</source>
        <translation>回复所选的评论</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="245"/>
        <source>Add Comment</source>
        <translation>添加评论</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="246"/>
        <source>Add the comment</source>
        <translation>添加此评论</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="247"/>
        <source>Resolve</source>
        <translation>解决</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="248"/>
        <source>Resolve the selected comment</source>
        <translation>解决所选评论</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="249"/>
        <source>Comment byte count</source>
        <translation>评论字节数</translation>
    </message>
</context>
<context>
    <name>Cursor_Feedback_Overlay</name>
    <message>
        <location filename="../ui/cursor_feedback_overlay.py" line="103"/>
        <location filename="../ui/cursor_feedback_overlay.py" line="160"/>
        <source>Cursor feedback</source>
        <extracomment>Progress fraction (0..1 of FEEDBACK_DURATION_MS) at which the fall to zero begins.</extracomment>
        <translation>光标反馈</translation>
    </message>
</context>
<context>
    <name>Dependency_Graph_View</name>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="169"/>
        <source>Dependency cycle detected (graph unchanged): %1</source>
        <extracomment>Item roles: whether a row is a broken edge, and the edge it stands for. The asset in scope (``&quot;&quot;`` = the whole catalog). The kind of the last cycle failure at :meth:`show_edges` (``None`` = none).</extracomment>
        <translation>检测到依赖循环(依赖关系图未更改): %1</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="202"/>
        <source>Dependencies (depends on)</source>
        <translation>依赖项(依赖于)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="208"/>
        <source>Dependents (referenced by)</source>
        <translation>依赖方(被引用于)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="238"/>
        <source>Broken (%1)</source>
        <translation>失效(%1)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="262"/>
        <source>%1 (%2)</source>
        <translation>%1 (%2)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="270"/>
        <source>Sprite</source>
        <translation>精灵</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="271"/>
        <source>Animation</source>
        <translation>动画</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="272"/>
        <source>Tileset</source>
        <translation>瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="273"/>
        <source>Tilemap</source>
        <translation>瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="274"/>
        <source>Palette</source>
        <translation>调色板</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="281"/>
        <source>missing target</source>
        <translation>目标缺失</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="283"/>
        <source>changed target</source>
        <translation>目标已更改</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="290"/>
        <source>No broken references</source>
        <translation>没有失效引用</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="293"/>
        <source>Broken references: %1</source>
        <translation>失效引用: %1</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="295"/>
        <source>Broken reference summary</source>
        <translation>失效引用摘要</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="299"/>
        <source>Dependency graph</source>
        <translation>依赖关系图</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="300"/>
        <source>Asset</source>
        <translation>素材</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="300"/>
        <source>Status</source>
        <translation>状态</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="301"/>
        <source>Dependency relations</source>
        <translation>依赖关系</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="302"/>
        <source>Dependency cycle notice</source>
        <translation>依赖循环通知</translation>
    </message>
</context>
<context>
    <name>Document_Transform_Confirm_Dialog</name>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="92"/>
        <source>Confirm Large Transform</source>
        <translation>确认大型变换</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="93"/>
        <source>Confirm large document transform dialog</source>
        <translation>确认大型文档变换对话框</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="99"/>
        <source>%1 will resample every layer and mask of this document to %2 × %3 px, using up to %4 of memory at once. Proceed?</source>
        <translation>%1 将把此文档的所有图层和蒙版重采样为 %2 × %3 px，同时最多占用 %4 内存。是否继续?</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="107"/>
        <source>Transform cost summary</source>
        <translation>变换资源占用摘要</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="108"/>
        <source>Proceed</source>
        <translation>继续</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="109"/>
        <source>Proceed with the transform</source>
        <translation>继续变换</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="110"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="111"/>
        <source>Cancel the transform</source>
        <translation>取消变换</translation>
    </message>
</context>
<context>
    <name>Document_Transform_Progress_Dialog</name>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="197"/>
        <source>Transforming Document</source>
        <extracomment>Emitted when the user asks to stop — via the button, Escape, or the window&apos;s close control. The caller (the runner) decides what &quot;stop&quot; means; this dialog only reports the request.</extracomment>
        <translation>正在变换文档</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="198"/>
        <source>Document transform progress dialog</source>
        <translation>文档变换进度对话框</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="199"/>
        <source>%1…</source>
        <translation>%1…</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="200"/>
        <source>Transform operation in progress</source>
        <translation>变换操作进行中</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="201"/>
        <source>Transform progress</source>
        <translation>变换进度</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="202"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="203"/>
        <source>Cancel the transform</source>
        <translation>取消变换</translation>
    </message>
</context>
<context>
    <name>Document_View</name>
    <message>
        <location filename="../ui/multi_view.py" line="119"/>
        <source>Document view {0}</source>
        <extracomment>Per-wheel-notch zoom step for an extra view (independent of the primary view). Emitted with the picked RGBA tuple when a plain wheel notch travels the shared Favourites cursor (REQ-IS-UI-008, D-16 — this surface is a navigate-only view of the SAME live document scene as the primary Canvas_View, so the active colour it sets is real document context). The persisted Favourites model bound via :meth:`set_favourites_model`; ``None`` until the shell binds one.</extracomment>
        <translation>文档视图 {0}</translation>
    </message>
    <message>
        <location filename="../ui/multi_view.py" line="123"/>
        <source>An extra synced view of the same document (independent zoom/pan)</source>
        <translation>同一文档的额外同步视图(独立缩放/平移)</translation>
    </message>
</context>
<context>
    <name>Export_Dialog</name>
    <message>
        <location filename="../ui/export_dialog.py" line="265"/>
        <source>%1 → %2</source>
        <extracomment>Presentation-only spin bounds (UI clamps; the logic layer re-validates, S12).</extracomment>
        <translation>%1 → %2</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="293"/>
        <source>Whole document</source>
        <translation>整个文档</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="301"/>
        <source>Animated GIF (*.gif)</source>
        <translation>动画 GIF(*.gif)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="303"/>
        <source>PNG image (*.png)</source>
        <translation>PNG 图像(*.png)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="305"/>
        <source>Export To</source>
        <translation>导出到</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="313"/>
        <source>Export</source>
        <translation>导出</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="314"/>
        <source>Format</source>
        <translation>格式</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="315"/>
        <location filename="../ui/export_dialog.py" line="343"/>
        <source>Engine preset</source>
        <translation>引擎预设</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="316"/>
        <source>Destination</source>
        <translation>目标位置</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="317"/>
        <source>Browse…</source>
        <translation>浏览…</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="318"/>
        <source>Also add to the asset library</source>
        <translation>同时添加到素材库</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="320"/>
        <source>PNG image</source>
        <translation>PNG 图像</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="321"/>
        <source>Animated GIF</source>
        <translation>动画 GIF</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="322"/>
        <source>Sprite sheet</source>
        <translation>精灵表</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="323"/>
        <source>Texture atlas</source>
        <translation>纹理图集</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="324"/>
        <source>None</source>
        <translation>无</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="325"/>
        <source>Unity</source>
        <translation>Unity</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="326"/>
        <source>Godot</source>
        <translation>Godot</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="329"/>
        <source>Exports the first frame as a flattened PNG image.</source>
        <translation>将第一帧导出为拼合后的 PNG 图像</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="331"/>
        <source>Frames</source>
        <translation>帧</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="332"/>
        <source>Loop count</source>
        <translation>循环次数</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="333"/>
        <source>Loop count (0 = loop forever).</source>
        <translation>循环次数(0 = 永久循环)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="334"/>
        <source>Columns</source>
        <translation>列数</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="335"/>
        <location filename="../ui/export_dialog.py" line="337"/>
        <source>Padding (px)</source>
        <translation>内边距(px)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="336"/>
        <location filename="../ui/export_dialog.py" line="339"/>
        <source>Write JSON metadata</source>
        <translation>写入 JSON 元数据</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="338"/>
        <source>Max dimension (px)</source>
        <translation>最大尺寸(px)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="342"/>
        <source>Export format</source>
        <translation>导出格式</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="344"/>
        <source>Destination path</source>
        <translation>目标路径</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="345"/>
        <source>Browse for destination</source>
        <translation>浏览目标位置</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="347"/>
        <source>Also add this export to the asset library</source>
        <translation>同时将此导出添加到素材库</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="349"/>
        <source>GIF frame source</source>
        <translation>GIF 帧来源</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="350"/>
        <source>GIF loop count</source>
        <translation>GIF 循环次数</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="351"/>
        <source>Sprite-sheet columns</source>
        <translation>精灵表列数</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="352"/>
        <source>Sprite-sheet padding</source>
        <translation>精灵表内边距</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="353"/>
        <source>Write sprite-sheet JSON</source>
        <translation>写入精灵表 JSON</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="354"/>
        <source>Atlas padding</source>
        <translation>图集内边距</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="355"/>
        <source>Atlas max dimension</source>
        <translation>图集最大尺寸</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="356"/>
        <source>Write atlas JSON</source>
        <translation>写入图集 JSON</translation>
    </message>
</context>
<context>
    <name>Extract_Palette_Dialog</name>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="130"/>
        <source>Choose Image</source>
        <extracomment>Extraction method tokens carried in the method combo&apos;s item data.</extracomment>
        <translation>选择图像</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="132"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>图像(*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="139"/>
        <location filename="../ui/extract_palette_dialog.py" line="158"/>
        <source>Extract Palette</source>
        <translation>提取调色板</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="139"/>
        <source>Could not load the image.</source>
        <translation>无法加载图像</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="169"/>
        <source>Extract Palette from Image</source>
        <translation>从图像提取调色板</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="170"/>
        <source>Extract palette dialog</source>
        <translation>提取调色板对话框</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="171"/>
        <source>Choose Image…</source>
        <translation>选择图像…</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="172"/>
        <source>No image chosen</source>
        <translation>未选择图像</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="173"/>
        <source>Colours (N)</source>
        <translation>颜色数(N)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="174"/>
        <source>Method</source>
        <translation>方法</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="175"/>
        <source>Number of colours</source>
        <translation>颜色数量</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="176"/>
        <source>Extraction method</source>
        <translation>提取方法</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="177"/>
        <source>Median cut (fast)</source>
        <translation>中位切分(快速)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="178"/>
        <source>K-means (higher quality)</source>
        <translation>K-means(质量更高)</translation>
    </message>
</context>
<context>
    <name>Failure_Messages</name>
    <message>
        <location filename="../ui/failure_messages.py" line="151"/>
        <source>The operation timed out.</source>
        <extracomment>The most links of a chain read; a longer chain is read only this far.</extracomment>
        <translation>操作超时</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="155"/>
        <source>The connection failed.</source>
        <translation>连接失败</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="157"/>
        <source>The file or folder could not be found.</source>
        <translation>无法找到文件或文件夹</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="161"/>
        <source>Access to the file or folder was denied.</source>
        <translation>访问文件或文件夹被拒绝</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="165"/>
        <source>A value was not valid for this operation.</source>
        <translation>某个值对此操作无效</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="168"/>
        <source>The operation could not be completed.</source>
        <translation>无法完成操作</translation>
    </message>
</context>
<context>
    <name>Favourites_Panel</name>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="279"/>
        <source>Favourites</source>
        <extracomment>Edge of a Favourites swatch icon, px (presentation-only sizing). Keys that nudge the wheel pad&apos;s hue/saturation (``_WheelPad.keyPressEvent``); a KeyRelease for one of these is a discrete, already-completed pick (REQ-P3- UI-006 leg 2), unlike Tab/other keys the pad never acts on. Single left click on a favourite — paint that colour, leave the wheel alone. Double left click / Enter / Return on a favourite — adopt that colour into the wheel, paint nothing. Deprecated alias of :attr:`favouriteActivated`, kept for pre-2026-08-31 callers of the pre-split single ``favouriteChosen`` signal. Emitted alongside :attr:`favouriteActivated` ONLY — never alongside :attr:`favouritePicked`, so it never resurrects the fused-gesture defect this split fixes (REQ-IS-UI-019). New code should connect :attr:`favouritePicked` / :attr:`favouriteActivated` directly. Emitted whenever the underlying model is mutated (so the shell persists it).</extracomment>
        <translation>收藏夹</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="280"/>
        <source>Favourites panel</source>
        <translation>收藏夹面板</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="281"/>
        <source>Favourite colours</source>
        <translation>收藏的颜色</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="282"/>
        <source>Remove</source>
        <translation>移除</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="283"/>
        <source>Move Up</source>
        <translation>上移</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="284"/>
        <source>Move Down</source>
        <translation>下移</translation>
    </message>
</context>
<context>
    <name>Frame_Tags_Panel</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="266"/>
        <source>%1  [%2–%3]  %4</source>
        <extracomment>Emitted with the :class:`FrameTag` to play as a named animation (UI-014).</extracomment>
        <translation>%1  [%2–%3]  %4</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="267"/>
        <source>(unnamed)</source>
        <translation>(未命名)</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="317"/>
        <location filename="../ui/frame_tags_panel.py" line="323"/>
        <location filename="../ui/frame_tags_panel.py" line="394"/>
        <source>Add Tag</source>
        <translation>添加标签</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="346"/>
        <location filename="../ui/frame_tags_panel.py" line="352"/>
        <location filename="../ui/frame_tags_panel.py" line="395"/>
        <source>Edit Tag</source>
        <translation>编辑标签</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="363"/>
        <location filename="../ui/frame_tags_panel.py" line="396"/>
        <source>Remove Tag</source>
        <translation>移除标签</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="388"/>
        <source>Frame tags panel</source>
        <translation>帧标签面板</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="389"/>
        <source>Tag actions</source>
        <translation>标签操作</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="390"/>
        <source>Frame tags</source>
        <translation>帧标签</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="392"/>
        <source>Named animations; double-click to edit</source>
        <translation>命名动画；双击可编辑</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="397"/>
        <source>Play Tag</source>
        <translation>播放标签</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="399"/>
        <source>Play the selected tag as its own animation</source>
        <translation>将所选标签作为独立动画播放</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="401"/>
        <source>Play tag</source>
        <translation>播放标签</translation>
    </message>
</context>
<context>
    <name>Guide_Logo_Switch_Widget</name>
    <message>
        <location filename="../ui/guide_logo_switch.py" line="121"/>
        <source>Switch the pixel font for the guide&apos;s pages</source>
        <extracomment>Accessible name of the switch; screen readers announce it.</extracomment>
        <translation>切换指南页面的像素字体</translation>
    </message>
</context>
<context>
    <name>Iso_Grid_Dialog</name>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="122"/>
        <source>Configure Isometric Grid</source>
        <extracomment>Sane bounds for the ``W:H`` tile ratio field (2:1 dimetric default is 2.0; true-iso is ~1.732). Not a lattice geometry decision — just a widget bound keeping the field away from non-finite/degenerate input before it ever reaches ``IsoGridConfig`` validation (S12).</extracomment>
        <translation>配置等距网格</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="123"/>
        <source>Tile width</source>
        <translation>瓦片宽度</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="124"/>
        <source>Tile ratio (W:H)</source>
        <translation>瓦片比例(W:H)</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="125"/>
        <source>Origin X</source>
        <translation>原点 X</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="126"/>
        <source>Origin Y</source>
        <translation>原点 Y</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="127"/>
        <source>Isometric tile width</source>
        <translation>等距瓦片宽度</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="128"/>
        <source>Isometric tile ratio</source>
        <translation>等距瓦片比例</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="129"/>
        <source>Isometric grid origin X</source>
        <translation>等距网格原点 X</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="130"/>
        <source>Isometric grid origin Y</source>
        <translation>等距网格原点 Y</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="133"/>
        <source>OK</source>
        <translation>确定</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="136"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
</context>
<context>
    <name>Layer_Panel</name>
    <message>
        <location filename="../ui/layer_panel.py" line="443"/>
        <source>Normal</source>
        <extracomment>Emitted with the selected node (``Layer`` / ``LayerGroup`` / ``None``). Emitted when the &quot;edit mask&quot; toggle flips (route paint to the mask buffer). Emitted when a mask attach/remove/edit is refused because the target node is locked (D-05); the shell surfaces a &quot;layer is locked&quot; notice.</extracomment>
        <translation>正常</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="444"/>
        <source>Multiply</source>
        <translation>正片叠底</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="445"/>
        <source>Screen</source>
        <translation>滤色</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="446"/>
        <source>Overlay</source>
        <translation>叠加</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="447"/>
        <source>Darken</source>
        <translation>变暗</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="448"/>
        <source>Lighten</source>
        <translation>变亮</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="449"/>
        <source>Colour Dodge</source>
        <translation>颜色减淡</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="450"/>
        <source>Colour Burn</source>
        <translation>颜色加深</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="451"/>
        <source>Hard Light</source>
        <translation>强光</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="452"/>
        <source>Soft Light</source>
        <translation>柔光</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="453"/>
        <source>Difference</source>
        <translation>差值</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="454"/>
        <source>Exclusion</source>
        <translation>排除</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="650"/>
        <source>Layer</source>
        <translation>图层</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="654"/>
        <location filename="../ui/layer_panel.py" line="883"/>
        <source>Add Layer</source>
        <translation>添加图层</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="667"/>
        <location filename="../ui/layer_panel.py" line="884"/>
        <source>Remove Layer</source>
        <translation>移除图层</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="680"/>
        <location filename="../ui/layer_panel.py" line="885"/>
        <source>Duplicate Layer</source>
        <translation>复制图层</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="689"/>
        <location filename="../ui/layer_panel.py" line="886"/>
        <source>Group</source>
        <translation>组</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="693"/>
        <source>Group Layers</source>
        <translation>将图层编组</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="705"/>
        <source>Ungroup Layers</source>
        <translation>取消图层编组</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="726"/>
        <location filename="../ui/layer_panel.py" line="871"/>
        <location filename="../ui/layer_panel.py" line="891"/>
        <source>Add Mask</source>
        <translation>添加蒙版</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="733"/>
        <location filename="../ui/layer_panel.py" line="871"/>
        <source>Remove Mask</source>
        <translation>移除蒙版</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="757"/>
        <source>Toggle Reference</source>
        <translation>切换参考</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="767"/>
        <source>Smart</source>
        <translation>智能</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="771"/>
        <source>Create Smart Layer</source>
        <translation>创建智能图层</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="828"/>
        <source>Move Layer</source>
        <translation>移动图层</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="877"/>
        <source>Layers panel</source>
        <translation>图层面板</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="878"/>
        <source>Layer actions</source>
        <translation>图层操作</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="879"/>
        <source>Layer tree</source>
        <translation>图层树</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="881"/>
        <source>Layers top-to-bottom; drag to reorder or re-parent</source>
        <translation>图层自上而下排列；拖动可重新排序或更改父级</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="887"/>
        <source>Ungroup</source>
        <translation>取消编组</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="888"/>
        <source>Edit Mask</source>
        <translation>编辑蒙版</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="889"/>
        <source>Reference</source>
        <translation>参考</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="890"/>
        <source>Smart Layer</source>
        <translation>智能图层</translation>
    </message>
</context>
<context>
    <name>Macro_Controls</name>
    <message>
        <location filename="../ui/macro_controls.py" line="144"/>
        <source>Running…</source>
        <extracomment>``(Macro, label)`` — the host should replay this macro on the active document (as one undoable grouped command, REQ-P8-UI-002). ``(recording,)`` — recording started / stopped (view state, not undoable). The user asked to cancel the in-flight automation run (C-07); the host relays this to ``Automation_Controller.cancel()``.</extracomment>
        <translation>正在运行…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="146"/>
        <source>Done</source>
        <translation>完成</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="147"/>
        <source>Idle</source>
        <translation>空闲</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="187"/>
        <source>Macro Error</source>
        <translation>宏错误</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/macro_controls.py" line="195"/>
        <source>Recording %1 (%n steps)</source>
        <translation>
            <numerusform>正在录制 %1 (%n 步)</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="217"/>
        <source>Macro</source>
        <translation>宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="235"/>
        <source>Save Macro</source>
        <translation>保存宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="237"/>
        <location filename="../ui/macro_controls.py" line="263"/>
        <source>Macro files (*%1)</source>
        <translation>宏文件(*%1)</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="246"/>
        <source>Save Macro Failed</source>
        <translation>保存宏失败</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="261"/>
        <source>Load Macro</source>
        <translation>加载宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="272"/>
        <source>Load Macro Failed</source>
        <translation>加载宏失败</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/macro_controls.py" line="307"/>
        <source>Recording… %n steps captured</source>
        <translation>
            <numerusform>正在录制… 已捕获 %n 步</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="310"/>
        <source>Not recording</source>
        <translation>未在录制</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="314"/>
        <source>Stop Recording</source>
        <translation>停止录制</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="314"/>
        <source>Record Macro</source>
        <translation>录制宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="316"/>
        <source>Replay</source>
        <translation>重放</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="317"/>
        <source>Save…</source>
        <translation>保存…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="318"/>
        <source>Load…</source>
        <translation>加载…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="319"/>
        <source>Remove</source>
        <translation>移除</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="320"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="321"/>
        <source>Macro controls</source>
        <translation>宏控件</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="322"/>
        <source>Record or stop a macro</source>
        <translation>开始或停止录制宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="323"/>
        <source>Macro recording status</source>
        <translation>宏录制状态</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="324"/>
        <source>Recorded and loaded macros</source>
        <translation>已录制和已加载的宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="325"/>
        <source>Replay the selected macro</source>
        <translation>重放所选宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="326"/>
        <source>Save the selected macro</source>
        <translation>保存所选宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="327"/>
        <source>Load a macro from a file</source>
        <translation>从文件加载宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="328"/>
        <source>Remove the selected macro</source>
        <translation>移除所选宏</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="329"/>
        <source>Cancel the running automation</source>
        <translation>取消正在运行的自动化</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="331"/>
        <source>Stops the in-flight automation run; enabled only while busy.</source>
        <translation>停止正在进行的自动化运行；仅在忙碌时可用</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="333"/>
        <source>Progress</source>
        <translation>进度</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="334"/>
        <source>Macro replay progress</source>
        <translation>宏重放进度</translation>
    </message>
</context>
<context>
    <name>Main_Window</name>
    <message>
        <location filename="../ui/main_window.py" line="1309"/>
        <location filename="../ui/main_window.py" line="5770"/>
        <source>&amp;Undo</source>
        <extracomment>Emitted when &quot;Use system font&quot; changes (stored here; the font itself is switched by the listener that owns it). Emitted when &quot;Pixel-perfect interface&quot; changes (stored here; it takes effect at the next launch). Live mirror-centre override from the Symmetry_Panel (D-28/CF-93); ``None`` keeps the shipped canvas-centre default. The DSL ops of the in-flight automation run (recorded into a macro on success if recording is active); ``None`` for a macro replay (a replay is not itself re-recorded). True while an in-session timelapse playback holds the active tab&apos;s canvas + the shared undo/redo actions read-only (REQ-P9-UI-016); see ``_on_timelapse_playback_lock_changed``. The cloud project id last saved to / opened from (drives version browse). D-13: the most recently fetched remote version list (cached from the last &quot;open_list&quot;/&quot;versions&quot;/&quot;save&quot; result) — feeds the read-only ``compute_sync_state`` for the Cloud menu status line and the version browser, without a network round trip on every tab switch. D-13: the version id of a restore/recover in flight, consumed once the reconstructed document lands in its new tab (see ``_on_cloud_succeeded``). Live-cursor overlays are per-tab (attached in _create_tab_aids); toggled on connect. The local member id broadcast with presence (never a token).</extracomment>
        <translation>撤销</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="1311"/>
        <location filename="../ui/main_window.py" line="5771"/>
        <source>&amp;Redo</source>
        <translation>重做</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2244"/>
        <source>Untitled</source>
        <translation>未命名</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2819"/>
        <source>Add Frame</source>
        <translation>添加帧</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3172"/>
        <source>Unsaved Changes</source>
        <translation>未保存的更改</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3175"/>
        <source>The current document has unsaved changes. Save it before opening the dropped project?</source>
        <translation>当前文档有未保存的更改。是否在打开拖入的项目之前先保存?</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3180"/>
        <source>Save</source>
        <translation>保存</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3182"/>
        <source>Discard</source>
        <translation>放弃</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3184"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3217"/>
        <source>Load Palette</source>
        <translation>加载调色板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3245"/>
        <location filename="../ui/main_window.py" line="4307"/>
        <source>Save Project</source>
        <translation>保存项目</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3247"/>
        <location filename="../ui/main_window.py" line="4293"/>
        <location filename="../ui/main_window.py" line="4309"/>
        <source>Pixel projects (*%1)</source>
        <translation>像素项目(*%1)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3257"/>
        <source>Unsupported file type: %1</source>
        <translation>不支持的文件类型: %1</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3268"/>
        <source>Layer is locked.</source>
        <translation>图层已锁定</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3283"/>
        <source>This is the last remaining frame; a document must keep at least one.</source>
        <translation>这是剩下的最后一帧，文档至少须保留一帧</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3296"/>
        <source>Click was outside the document.</source>
        <translation>所选位置在文档之外</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3309"/>
        <source>This layer cannot be edited directly.</source>
        <translation>无法直接编辑此图层</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3322"/>
        <source>No change: the colour already matched.</source>
        <translation>无更改: 颜色已一致</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3335"/>
        <source>No tileset bound to this tilemap yet.</source>
        <translation>此瓦片地图尚未绑定瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3347"/>
        <source>Select a tile first.</source>
        <translation>请先选择一个瓦片</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3354"/>
        <source>Open a document before loading a palette.</source>
        <translation>请先打开文档，再加载调色板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3362"/>
        <source>Import Failed</source>
        <translation>导入失败</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3363"/>
        <source>Could not import %1:
%2</source>
        <translation>无法导入 %1:
%2</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3487"/>
        <source>Copying selection — release, Enter to commit, Esc to cancel</source>
        <extracomment>Incoming tool ids that discard the active selection on entry (REQ-IS-UI-029). Re-activating an already-active selection tool is included deliberately, so it doubles as a start-fresh gesture — an assumption, flagged and cheap to reverse. Every other incoming tool leaves the selection untouched, so mask-constrained drawing (REQ-P2-LOGIC-006) survives a tool switch.</extracomment>
        <translation>正在复制选区，松开后按 Enter 确认，按 Esc 取消</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3492"/>
        <source>Moving selection — hold Ctrl to copy; Enter to commit, Esc to cancel</source>
        <translation>正在移动选区，按住 Ctrl 可复制；按 Enter 确认，按 Esc 取消</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3603"/>
        <source>Add Shade Ramp</source>
        <translation>添加明暗色阶</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3623"/>
        <location filename="../ui/main_window.py" line="3633"/>
        <source>Constrain to Palette</source>
        <translation>限制到调色板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3654"/>
        <location filename="../ui/main_window.py" line="3665"/>
        <location filename="../ui/main_window.py" line="5794"/>
        <source>Colour Cycling</source>
        <translation>颜色循环</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3655"/>
        <source>Colour cycling applies to indexed documents.</source>
        <translation>颜色循环适用于索引文档</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3675"/>
        <source>Colour Cycle</source>
        <translation>颜色循环</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3693"/>
        <source>Extract Palette</source>
        <translation>提取调色板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3704"/>
        <location filename="../ui/main_window.py" line="3724"/>
        <location filename="../ui/main_window.py" line="3734"/>
        <source>Palette Swap</source>
        <translation>调色板交换</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3705"/>
        <source>Palette swap applies to indexed documents.</source>
        <translation>调色板交换适用于索引文档</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3759"/>
        <location filename="../ui/main_window.py" line="3769"/>
        <source>Convert to Indexed</source>
        <translation>转换为索引色</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3791"/>
        <location filename="../ui/main_window.py" line="3801"/>
        <source>Convert to RGBA</source>
        <translation>转换为 RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3929"/>
        <source>Register Selection</source>
        <translation>登记选区</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4022"/>
        <source>Choose a new folder for the imported project</source>
        <translation>为导入的项目选择新文件夹</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4031"/>
        <source>&quot;%1&quot; already exists. Choose a name for a new folder.</source>
        <translation>“%1”已存在。请为新文件夹指定一个名称。</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4050"/>
        <source>Imported Project</source>
        <translation>已导入的项目</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4291"/>
        <source>Open Project</source>
        <translation>打开项目</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4318"/>
        <source>Cloud project name:</source>
        <translation>云项目名称:</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4323"/>
        <source>Enter a project name.</source>
        <translation>请输入项目名称</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4332"/>
        <source>Connect to a cloud provider first.</source>
        <translation>请先连接到云服务商</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4366"/>
        <source>Cloud status: —</source>
        <translation>云端状态: —</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4374"/>
        <source>Cloud status: Up to date</source>
        <translation>云端状态: 已是最新</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4376"/>
        <source>Cloud status: Not yet saved to cloud</source>
        <translation>云端状态: 尚未保存到云端</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4378"/>
        <source>Cloud status: Newer version in cloud</source>
        <translation>云端状态: 云端有较新的版本</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4379"/>
        <source>Cloud status: Diverged</source>
        <translation>云端状态: 已出现分歧</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4385"/>
        <source>Real-time</source>
        <translation>实时协作</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4388"/>
        <location filename="../ui/main_window.py" line="4552"/>
        <source>Open a document first.</source>
        <translation>请先打开文档</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4390"/>
        <source>Your member id:</source>
        <translation>你的成员 ID:</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4427"/>
        <source>Real-time. {msg}</source>
        <translation>实时协作。{msg}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4429"/>
        <source>Real-time: {msg}</source>
        <translation>实时协作: {msg}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4536"/>
        <source>Merge</source>
        <translation>合并</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4547"/>
        <source>Save to Cloud</source>
        <translation>保存到云端</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4569"/>
        <source>Open from Cloud</source>
        <translation>从云端打开</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4587"/>
        <location filename="../ui/main_window.py" line="4704"/>
        <source>Cloud Version History</source>
        <translation>云端版本历史记录</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4674"/>
        <source>Saved to cloud.</source>
        <translation>已保存到云端</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4681"/>
        <source>Cloud Project</source>
        <translation>云项目</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4683"/>
        <source>Recovered</source>
        <translation>已找回</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4691"/>
        <source>Restored from cloud.</source>
        <translation>已从云端还原</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4705"/>
        <source>No versions found for this project.</source>
        <translation>找不到此项目的版本</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4732"/>
        <source>Cloud</source>
        <translation>云端</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4858"/>
        <source>Clear Selection</source>
        <translation>清除选区</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4973"/>
        <source>Flip Horizontal</source>
        <translation>水平翻转</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4976"/>
        <source>Flip Vertical</source>
        <translation>垂直翻转</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4980"/>
        <source>Rotate 90° CW</source>
        <translation>顺时针旋转 90°</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4985"/>
        <source>Rotate 90° CCW</source>
        <translation>逆时针旋转 90°</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5006"/>
        <location filename="../ui/main_window.py" line="5011"/>
        <location filename="../ui/main_window.py" line="5019"/>
        <location filename="../ui/main_window.py" line="5030"/>
        <location filename="../ui/main_window.py" line="5037"/>
        <source>Scale Canvas</source>
        <translation>缩放画布</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5066"/>
        <location filename="../ui/main_window.py" line="5071"/>
        <source>Canvas Size</source>
        <translation>画布大小</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5093"/>
        <source>Rotate (RotSprite)</source>
        <translation>旋转(RotSprite)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5268"/>
        <source>Pixel-perfect interface: the change applies the next time the application starts.</source>
        <translation>像素完美界面: 更改将在下次启动应用程序时生效</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5396"/>
        <location filename="../ui/main_window.py" line="5407"/>
        <source>Open Tileset Image</source>
        <translation>打开瓦片集图像</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5398"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>图像(*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5422"/>
        <source>New Tileset</source>
        <translation>新建瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5432"/>
        <source>Add Tileset</source>
        <translation>添加瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5442"/>
        <location filename="../ui/main_window.py" line="5493"/>
        <source>Attach Tileset</source>
        <translation>附加瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5455"/>
        <source>Tilemap</source>
        <translation>瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5458"/>
        <source>Layer 1</source>
        <translation>图层 1</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5465"/>
        <source>Add Tilemap</source>
        <translation>添加瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5485"/>
        <source>Import Tilemap</source>
        <translation>导入瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5517"/>
        <source>Export Tiled Map</source>
        <translation>导出 Tiled 地图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5518"/>
        <source>There is no tilemap to export.</source>
        <translation>没有可导出的瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5546"/>
        <source>Exporting…</source>
        <translation>正在导出…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5551"/>
        <source>Exporting %1 of %2…</source>
        <translation>正在导出第 %1 项，共 %2 项…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5594"/>
        <source>Export Failed</source>
        <translation>导出失败</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/main_window.py" line="5596"/>
        <source>%n export target(s) failed:
%2</source>
        <translation>
            <numerusform>%n 个导出目标失败:
%2</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/main_window.py" line="5604"/>
        <source>Export complete (%n file(s)).</source>
        <translation>
            <numerusform>导出完成(%n 个文件)</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5654"/>
        <source>Automation</source>
        <translation>自动化</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5676"/>
        <source>Automation Error</source>
        <translation>自动化错误</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5694"/>
        <source>Running automation…</source>
        <translation>正在运行自动化…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5740"/>
        <source>Assistant edit</source>
        <translation>助手编辑</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5782"/>
        <source>PixelArt Creator</source>
        <translation>PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5784"/>
        <source>Tools</source>
        <translation>工具</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5785"/>
        <source>Palette</source>
        <translation>调色板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5786"/>
        <source>Symmetry</source>
        <translation>对称</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5787"/>
        <source>Layers</source>
        <translation>图层</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5788"/>
        <source>Timeline</source>
        <translation>时间轴</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5789"/>
        <source>Onion Skin</source>
        <translation>洋葱皮</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5790"/>
        <source>Frame Tags</source>
        <translation>帧标签</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5791"/>
        <source>Palette Editor</source>
        <translation>调色板编辑器</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5792"/>
        <source>Constraints</source>
        <translation>约束</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5793"/>
        <source>Shade Ramps</source>
        <translation>明暗色阶</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5795"/>
        <source>Analytics</source>
        <translation>分析</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5796"/>
        <source>Tileset Editor</source>
        <translation>瓦片集编辑器</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5797"/>
        <source>Tilemap Layers</source>
        <translation>瓦片地图图层</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5798"/>
        <source>Tilemap Canvas</source>
        <translation>瓦片地图画布</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5799"/>
        <source>Batch Export</source>
        <translation>批量导出</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5800"/>
        <source>Macros</source>
        <translation>宏</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5801"/>
        <source>Script Runner</source>
        <translation>脚本运行器</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5802"/>
        <source>Plugins</source>
        <translation>插件</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5803"/>
        <source>Batch Recolour</source>
        <translation>批量重新着色</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5804"/>
        <source>Procedural Generation</source>
        <translation>程序化生成</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5805"/>
        <source>Shared Projects</source>
        <translation>共享项目</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5806"/>
        <source>Comments</source>
        <translation>评论</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5807"/>
        <source>Presence</source>
        <translation>在线状态</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5808"/>
        <source>Branching</source>
        <translation>分支</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5809"/>
        <source>Asset Library</source>
        <translation>素材库</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5810"/>
        <source>Asset Search</source>
        <translation>素材搜索</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5811"/>
        <source>Asset Tagging</source>
        <translation>素材标记</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5812"/>
        <source>Dependency Graph</source>
        <translation>依赖关系图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5813"/>
        <source>Asset Versions</source>
        <translation>素材版本</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5814"/>
        <source>Asset Reuse</source>
        <translation>素材复用</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5818"/>
        <source>Real-Size Preview</source>
        <translation>实际尺寸预览</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5819"/>
        <source>Timelapse</source>
        <translation>延时回放</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5820"/>
        <source>Reopened Recording</source>
        <translation>已重新打开的录制</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5821"/>
        <source>Open documents</source>
        <translation>已打开的文档</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5822"/>
        <source>Floating selection status</source>
        <translation>浮动选区状态</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5826"/>
        <source>Pencil</source>
        <translation>铅笔</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5827"/>
        <source>Eraser</source>
        <translation>橡皮擦</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5828"/>
        <source>Fill</source>
        <translation>填充</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5829"/>
        <source>Line</source>
        <translation>直线</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5830"/>
        <source>Colour picker</source>
        <translation>取色器</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5831"/>
        <source>Rectangle</source>
        <translation>矩形</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5832"/>
        <source>Ellipse</source>
        <translation>椭圆</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5833"/>
        <source>Rectangle select</source>
        <translation>矩形选框</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5834"/>
        <source>Lasso select</source>
        <translation>套索选择</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5835"/>
        <source>Magic wand</source>
        <translation>魔棒</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5836"/>
        <location filename="../ui/main_window.py" line="5895"/>
        <source>Dither</source>
        <translation>抖动</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5845"/>
        <source>&amp;New</source>
        <translation>新建</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5846"/>
        <source>&amp;Open…</source>
        <translation>打开…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5847"/>
        <source>&amp;Save</source>
        <translation>保存</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5848"/>
        <source>Save &amp;As…</source>
        <translation>另存为…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5849"/>
        <source>&amp;Export…</source>
        <translation>导出…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5850"/>
        <source>&amp;Close</source>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5852"/>
        <source>&amp;Connect…</source>
        <translation>连接…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5853"/>
        <source>&amp;Disconnect</source>
        <translation>断开连接</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5854"/>
        <source>&amp;Save to Cloud…</source>
        <translation>保存到云端…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5855"/>
        <source>&amp;Open from Cloud…</source>
        <translation>从云端打开…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5856"/>
        <source>&amp;Version History…</source>
        <translation>版本历史记录…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5858"/>
        <source>Start &amp;Real-time…</source>
        <translation>开始实时协作…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5859"/>
        <source>Stop Real-&amp;time</source>
        <translation>停止实时协作</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5860"/>
        <source>Show &amp;Live Cursors</source>
        <translation>显示实时光标</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5861"/>
        <source>Zoom &amp;In</source>
        <translation>放大</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5862"/>
        <source>Zoom &amp;Out</source>
        <translation>缩小</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5863"/>
        <source>&amp;Fit to View</source>
        <translation>适应视图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5864"/>
        <source>Fit to &amp;Content</source>
        <translation>适应内容</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5865"/>
        <source>Show &amp;Grid</source>
        <translation>显示网格</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5866"/>
        <source>&amp;Snap to Grid</source>
        <translation>对齐到网格</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5867"/>
        <source>&amp;Anti-aliasing Off</source>
        <translation>关闭抗锯齿</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5868"/>
        <source>&amp;Tiled Mode</source>
        <translation>平铺模式</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5869"/>
        <source>Light</source>
        <translation>浅色</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5870"/>
        <source>Dark</source>
        <translation>深色</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5873"/>
        <source>New Tileset from Image…</source>
        <translation>从图像新建瓦片集…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5874"/>
        <source>New Tilemap</source>
        <translation>新建瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5875"/>
        <source>Import Tiled JSON…</source>
        <translation>导入 Tiled JSON…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5876"/>
        <source>Export Tiled JSON…</source>
        <translation>导出 Tiled JSON…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5877"/>
        <source>Stamp Tool</source>
        <translation>图章工具</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5878"/>
        <source>Place the selected tile</source>
        <translation>放置所选瓦片</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5879"/>
        <source>Tile Eraser</source>
        <translation>瓦片橡皮擦</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5880"/>
        <source>Clear the target cell</source>
        <translation>清除目标单元格</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5881"/>
        <source>Rectangle Fill</source>
        <translation>矩形填充</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5883"/>
        <source>Fill a dragged rectangle with the selected tile</source>
        <translation>用所选瓦片填充拖出的矩形</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5885"/>
        <source>Flip Stamp Horizontal</source>
        <translation>水平翻转图章</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5886"/>
        <source>Flip Stamp Vertical</source>
        <translation>垂直翻转图章</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5887"/>
        <source>Rotate Stamp 90° CW</source>
        <translation>顺时针旋转图章 90°</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5891"/>
        <source>Fille&amp;d Shapes</source>
        <translation>填充形状</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5892"/>
        <source>&amp;Pixel Perfect</source>
        <translation>像素完美</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5893"/>
        <source>Tolerance</source>
        <translation>容差</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5894"/>
        <source>Magic-wand tolerance</source>
        <translation>魔棒容差</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5896"/>
        <source>Dither mode</source>
        <translation>抖动模式</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5897"/>
        <source>Ordered (Bayer)</source>
        <translation>有序(Bayer)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5898"/>
        <source>Floyd–Steinberg</source>
        <translation>Floyd–Steinberg</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5899"/>
        <source>&amp;Extract from Image…</source>
        <translation>从图像提取…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5900"/>
        <source>Palette &amp;Swap…</source>
        <translation>调色板交换…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5902"/>
        <source>Convert to Inde&amp;xed</source>
        <translation>转换为索引色</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5903"/>
        <source>&amp;Convert to RGBA</source>
        <translation>转换为 RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5905"/>
        <source>Select &amp;All</source>
        <translation>全选</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5906"/>
        <source>&amp;Deselect</source>
        <translation>取消选择</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5907"/>
        <source>&amp;Invert Selection</source>
        <translation>反转选区</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5908"/>
        <source>&amp;Clear Selection</source>
        <translation>清除选区</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5910"/>
        <source>Flip &amp;Horizontal</source>
        <translation>水平翻转</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5911"/>
        <source>Flip &amp;Vertical</source>
        <translation>垂直翻转</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5912"/>
        <source>Rotate 90° C&amp;W</source>
        <translation>顺时针旋转 90°</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5913"/>
        <source>Rotate 90° &amp;CCW</source>
        <translation>逆时针旋转 90°</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5914"/>
        <source>&amp;Scale…</source>
        <translation>缩放…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5915"/>
        <source>Canvas S&amp;ize…</source>
        <translation>画布大小…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5916"/>
        <source>&amp;Rotate (RotSprite)…</source>
        <translation>旋转(RotSprite)…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5918"/>
        <source>Guides &amp;&amp; &amp;Rulers</source>
        <translation>参考线 &amp;&amp; 标尺</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5919"/>
        <source>&amp;Isometric Grid</source>
        <translation>等距网格</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5920"/>
        <source>&amp;Configure Isometric Grid…</source>
        <translation>配置等距网格…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5921"/>
        <source>&amp;Perspective Grid</source>
        <translation>透视网格</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5922"/>
        <source>Confi&amp;gure Perspective…</source>
        <translation>配置透视…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5923"/>
        <source>&amp;New View</source>
        <translation>新建视图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5924"/>
        <source>Reference &amp;Board</source>
        <translation>参考板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5926"/>
        <source>&amp;File</source>
        <translation>文件</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5927"/>
        <source>&amp;Edit</source>
        <translation>编辑</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5928"/>
        <source>&amp;Select</source>
        <translation>选择</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5929"/>
        <source>&amp;Image</source>
        <translation>图像</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5930"/>
        <source>&amp;View</source>
        <translation>视图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5931"/>
        <source>Visual Ai&amp;ds</source>
        <translation>视觉辅助</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5932"/>
        <source>&amp;Palette</source>
        <translation>调色板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5933"/>
        <source>Tile&amp;map</source>
        <translation>瓦片地图</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5934"/>
        <source>&amp;Automation</source>
        <translation>自动化</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5935"/>
        <source>&amp;Cloud</source>
        <translation>云端</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5936"/>
        <source>&amp;Library</source>
        <translation>素材库</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5938"/>
        <source>&amp;Register Active Document…</source>
        <translation>登记当前文档…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5940"/>
        <source>Register &amp;Selection…</source>
        <translation>登记选区…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5941"/>
        <source>&amp;Import Asset…</source>
        <translation>导入素材…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5942"/>
        <source>&amp;Export Asset…</source>
        <translation>导出素材…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5943"/>
        <source>Export Project &amp;Bundle…</source>
        <translation>导出项目包…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5944"/>
        <source>I&amp;mport Project Bundle…</source>
        <translation>导入项目包…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5945"/>
        <source>&amp;Theme</source>
        <translation>主题</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5946"/>
        <source>La&amp;nguage</source>
        <translation>语言</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5947"/>
        <source>&amp;Help</source>
        <translation>帮助</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5948"/>
        <source>&amp;User Guide</source>
        <translation>用户指南</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5949"/>
        <source>&amp;About PixelArt Creator</source>
        <translation>关于 PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5954"/>
        <source>Washi &amp;&amp; Kintsugi</source>
        <translation>Washi &amp;&amp; Kintsugi</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5955"/>
        <source>Edo Night</source>
        <translation>Edo Night</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5956"/>
        <source>Arcade Kikko</source>
        <translation>Arcade Kikko</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5962"/>
        <source>&amp;Style</source>
        <translation>样式</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5963"/>
        <source>Choose the visual style</source>
        <translation>选择视觉样式</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5966"/>
        <source>Use system &amp;font</source>
        <translation>使用系统字体</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5968"/>
        <source>Use the operating system&apos;s interface font instead of Nifen Art</source>
        <translation>使用操作系统的界面字体，而不是 Nifen Art</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5971"/>
        <source>Pixel-perfect &amp;interface</source>
        <translation>像素完美界面</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5974"/>
        <source>Scale the interface by whole numbers only (next launch)</source>
        <translation>仅按整数倍缩放界面(下次启动时生效)</translation>
    </message>
</context>
<context>
    <name>New_Document_Dialog</name>
    <message>
        <location filename="../ui/new_document_dialog.py" line="81"/>
        <source>New Document</source>
        <translation>新建文档</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="82"/>
        <source>New document dialog</source>
        <translation>新建文档对话框</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="83"/>
        <source>Document width in pixels</source>
        <translation>文档宽度(像素)</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="84"/>
        <source>Document height in pixels</source>
        <translation>文档高度(像素)</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="85"/>
        <source>Width (px)</source>
        <translation>宽度(px)</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="86"/>
        <source>Height (px)</source>
        <translation>高度(px)</translation>
    </message>
</context>
<context>
    <name>Onion_Skin_Controls</name>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="108"/>
        <location filename="../ui/onion_skin_controls.py" line="176"/>
        <source>Previous frames</source>
        <extracomment>Emitted with the current :class:`OnionSettings` on any change (live update).</extracomment>
        <translation>前面的帧</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="109"/>
        <location filename="../ui/onion_skin_controls.py" line="177"/>
        <source>Next frames</source>
        <translation>后面的帧</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="135"/>
        <location filename="../ui/onion_skin_controls.py" line="183"/>
        <source>Previous-frame tint</source>
        <translation>前帧色调</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="142"/>
        <location filename="../ui/onion_skin_controls.py" line="185"/>
        <source>Next-frame tint</source>
        <translation>后帧色调</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="173"/>
        <source>Onion skin controls</source>
        <translation>洋葱皮控件</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="174"/>
        <source>Enable onion skinning</source>
        <translation>启用洋葱皮</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="175"/>
        <source>Onion skin toggle</source>
        <translation>洋葱皮开关</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="178"/>
        <source>Previous onion frame count</source>
        <translation>前面的洋葱皮帧数</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="179"/>
        <source>How many earlier frames to ghost</source>
        <translation>显示虚影的较早帧数</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="180"/>
        <source>Next onion frame count</source>
        <translation>后面的洋葱皮帧数</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="181"/>
        <source>How many later frames to ghost</source>
        <translation>显示虚影的较晚帧数</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="182"/>
        <location filename="../ui/onion_skin_controls.py" line="184"/>
        <source>Tint…</source>
        <translation>色调…</translation>
    </message>
</context>
<context>
    <name>Overwrite_Confirm_Dialog</name>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="76"/>
        <source>Overwrite Existing Pixels?</source>
        <translation>覆盖现有像素?</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="77"/>
        <location filename="../ui/project_prefs_actions.py" line="223"/>
        <source>Overwrite existing pixels confirmation</source>
        <translation>覆盖现有像素确认</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="80"/>
        <source>The destination already has pixels on it. Continuing replaces that content. This can be undone.</source>
        <translation>目标位置已有像素。继续将替换这些内容。此操作可以撤销。</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="84"/>
        <source>Overwrite warning</source>
        <translation>覆盖警告</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="85"/>
        <source>Don&apos;t ask again for this project</source>
        <translation>此项目不再询问</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="87"/>
        <source>Suppress this confirmation for the current project</source>
        <translation>对当前项目不再显示此确认</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="91"/>
        <location filename="../ui/overwrite_confirm_dialog.py" line="92"/>
        <source>Continue</source>
        <translation>继续</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="95"/>
        <location filename="../ui/overwrite_confirm_dialog.py" line="96"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
</context>
<context>
    <name>Palette_Analytics_View</name>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="171"/>
        <source>Palette Analytics</source>
        <extracomment>Edge of a colour-swatch icon in the table, px (presentation-only sizing). Debounce window (ms) coalescing a burst of deferred refresh requests into a single buffer scan (presentation-only timing, not a domain tuning value — cf. _SWATCH_PX). Short enough to feel instant when the dock becomes visible.</extracomment>
        <translation>调色板分析</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="172"/>
        <source>Palette analytics view</source>
        <translation>调色板分析视图</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="173"/>
        <source>Colour usage counts</source>
        <translation>颜色使用次数</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="175"/>
        <source>Colour / Index</source>
        <translation>颜色 / 索引</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="175"/>
        <source>Usage count</source>
        <translation>使用次数</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="177"/>
        <source>Refresh</source>
        <translation>刷新</translation>
    </message>
</context>
<context>
    <name>Palette_Constraint_Panel</name>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="60"/>
        <source>Constrain to Hardware Palette</source>
        <extracomment>Preset identifiers routed back to the shell (which owns the logic call). Emitted with a preset id (``PRESET_NES`` / ``PRESET_GAME_BOY``) on click.</extracomment>
        <translation>限制到硬件调色板</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="61"/>
        <source>Palette constraint presets</source>
        <translation>调色板限制预设</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="62"/>
        <source>Constrain to NES</source>
        <translation>限制到 NES</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="63"/>
        <source>Constrain to Game Boy</source>
        <translation>限制到 Game Boy</translation>
    </message>
</context>
<context>
    <name>Palette_Editor_Panel</name>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="226"/>
        <location filename="../ui/palette_editor_panel.py" line="230"/>
        <source>Add Colour</source>
        <extracomment>Edge of an editor swatch icon, px (presentation-only sizing). Maps a save/open dialog filter label to the ``palette_io`` format token. Emitted with an RGBA tuple when a swatch is selected (sets active colour).</extracomment>
        <translation>添加颜色</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="226"/>
        <source>The palette is full.</source>
        <translation>调色板已满</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="245"/>
        <source>Remove Colour</source>
        <translation>移除颜色</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="257"/>
        <location filename="../ui/palette_editor_panel.py" line="271"/>
        <source>Reorder Palette</source>
        <translation>重新排序调色板</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="280"/>
        <location filename="../ui/palette_editor_panel.py" line="291"/>
        <source>Export Palette</source>
        <translation>导出调色板</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="302"/>
        <location filename="../ui/palette_editor_panel.py" line="314"/>
        <location filename="../ui/palette_editor_panel.py" line="320"/>
        <source>Import Palette</source>
        <translation>导入调色板</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="334"/>
        <source>Palette Editor</source>
        <translation>调色板编辑器</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="335"/>
        <source>Palette editor panel</source>
        <translation>调色板编辑器面板</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="336"/>
        <source>Editable colour palette</source>
        <translation>可编辑的调色板</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="337"/>
        <source>Add</source>
        <translation>添加</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="338"/>
        <source>Add the active colour</source>
        <translation>添加当前颜色</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="339"/>
        <source>Remove</source>
        <translation>移除</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="340"/>
        <source>Move Up</source>
        <translation>上移</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="341"/>
        <source>Move Down</source>
        <translation>下移</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="342"/>
        <source>Import…</source>
        <translation>导入…</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="343"/>
        <source>Export…</source>
        <translation>导出…</translation>
    </message>
</context>
<context>
    <name>Palette_Panel</name>
    <message>
        <location filename="../ui/main_window.py" line="555"/>
        <source>Colour palette</source>
        <extracomment>Stable cloud recovery-slot key for the working document when no named cloud project is active (presentation-only identifier, not a domain tuning value). A sensible starter palette for a new document (usability, not a spec value). Swatch icon edge, px (presentation-only sizing, not a domain tuning value). Filename of the app-level Favourites store under AppConfigLocation (ADR-0004). Longest edge of a RotSprite preview thumbnail, px (presentation-only sizing, not a domain tuning value — cf. _SWATCH_PX). Tool ids whose stroke WRITES the active colour to the buffer: the value written is ``ctx.paint_value()`` / ``ctx.active_color`` itself, not merely a live-preview tint. These five run under REQ-P3-UI-006 leg (2) from a completed colour-hub pick; the other six tool ids (eraser, the three selection tools, picker, dither) hide the hub&apos;s wheel/value/numeric/harmony pick surface (``set_pick_surface_visible``) and never run from a hub pick, even a Favourites activation (SC-U006-13). Tool identifiers, not numeric tuning values, so this stays a set of the tools&apos; own ``tool_id`` class attributes rather than a `constants.py` entry. FIX 3 (2026-08-24 field defect, RC-1 follow-up). Every right-hand &quot;workflow&quot; panel is tabified into ONE dock group (``_add_workflow_dock``), and a Qt tab group&apos;s minimum width is the MAXIMUM over its members&apos; own content-derived ``minimumSizeHint()`` — verified up to 766 px for one panel (probe-runtime-canvas-20260824.py). That floor overrides FIX 1&apos;s ``CANVAS_PANE_WIDTH_RATIO`` split regardless of window width, so no per-panel edit can fix it: the override has to happen once, here, at the single place every workflow dock is created. Overriding ``QWidget.setMinimumWidth()`` on the panel (verified empirically to lower ``QDockWidget.minimumSizeHint()`` even though the panel&apos;s own ``minimumSizeHint()`` is unchanged and content can clip below it — Qt&apos;s dock layout consults the explicit minimum, not the generic ``QLayoutItem.minimumSize()`` ``expandedTo`` rule) is presentation sizing, not a domain tuning value, so it stays local exactly like _SWATCH_PX / _PREVIEW_MAX_EDGE_PX above — see the FIX-3 report note requesting this be promoted to logic/constants.py (a logic-layer surface) as e.g. ``WORKFLOW_DOCK_MIN_WIDTH_PX`` rather than reached into from here. FIX 3 (2026-08-24 field defect). Bound on ``Main_Window._settle_width()``&apos;s event-flush loop (presentation-only startup timing, not a domain tuning value — cf. _SWATCH_PX / _PREVIEW_MAX_EDGE_PX above). Observed settling in 2 passes on the probe&apos;s offscreen run; this leaves generous headroom without risking an unbounded/hanging wait on a layout that never settles. FIX 1 (2026-08-24 field defect, RC-1 follow-up on the earlier FIX 1). The window was never given an explicit default size; Qt sized it to its layout hint, which on a real desktop happened to land the canvas at only ~10% of the window even after the FIX 1/FIX 3 dock-splitting work above, because that split is a RATIO of whatever width the window already has -- a window with no deliberate width defeats a width RATIO. Fraction of the primary screen&apos;s *available* geometry (excludes taskbars/docks) the window claims on first launch, absent any saved geometry restore (presentation-only startup sizing, not a domain tuning value -- cf. _WORKFLOW_DOCK_MIN_WIDTH_PX / _SWATCH_PX above). Report note: a candidate for promotion to logic/constants.py as e.g. DEFAULT_LAUNCH_SIZE_RATIO, exactly like that floor&apos;s own promotion note -- left local here on the same precedent.</extracomment>
        <translation>调色板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="556"/>
        <source>Palette panel</source>
        <translation>调色板面板</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="557"/>
        <source>Colour mode</source>
        <translation>颜色模式</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="562"/>
        <source>Mode: Indexed</source>
        <translation>模式: 索引</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="564"/>
        <source>Mode: RGBA</source>
        <translation>模式: RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="566"/>
        <source>Mode: —</source>
        <translation>模式: —</translation>
    </message>
</context>
<context>
    <name>Palette_Swap_Dialog</name>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="106"/>
        <source>Palette Swap</source>
        <translation>调色板交换</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="107"/>
        <source>Palette swap dialog</source>
        <translation>调色板交换对话框</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="108"/>
        <source>From index</source>
        <translation>从索引</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="109"/>
        <source>To index</source>
        <translation>到索引</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="110"/>
        <source>Source index</source>
        <translation>源索引</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="111"/>
        <source>Target index</source>
        <translation>目标索引</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="112"/>
        <source>Add</source>
        <translation>添加</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="113"/>
        <source>Remove</source>
        <translation>移除</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="114"/>
        <source>Index remap entries</source>
        <translation>索引重映射条目</translation>
    </message>
</context>
<context>
    <name>Playback_Controls</name>
    <message>
        <location filename="../ui/playback_controls.py" line="364"/>
        <source>Loop</source>
        <extracomment>Type of the per-tick step yielded by the sequencing engine: (index, ms). Emitted with the frame index to display on each playback tick (scrub-like). Emitted ``True`` when playback becomes active, ``False`` when it halts. The shell suppresses onion skinning while active (CL-11).</extracomment>
        <translation>循环</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="365"/>
        <source>Once</source>
        <translation>单次</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="366"/>
        <source>Ping-Pong</source>
        <translation>往返</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="367"/>
        <source>Reverse</source>
        <translation>反向</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="372"/>
        <source>Playback controls</source>
        <translation>播放控件</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="373"/>
        <location filename="../ui/playback_controls.py" line="375"/>
        <source>Play</source>
        <translation>播放</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="374"/>
        <source>Play (Space)</source>
        <translation>播放(Space)</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="376"/>
        <location filename="../ui/playback_controls.py" line="378"/>
        <source>Pause</source>
        <translation>暂停</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="377"/>
        <source>Pause (Space)</source>
        <translation>暂停(Space)</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="379"/>
        <location filename="../ui/playback_controls.py" line="381"/>
        <source>Stop</source>
        <translation>停止</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="380"/>
        <source>Stop and return to the start frame</source>
        <translation>停止并返回起始帧</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="382"/>
        <source>Playback mode</source>
        <translation>播放模式</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="383"/>
        <source>Global playback mode</source>
        <translation>全局播放模式</translation>
    </message>
</context>
<context>
    <name>Plugin_Manager_Panel</name>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="138"/>
        <source>Add Plugin Manifest</source>
        <extracomment>Enabled plugin handles keyed by plugin name (view/session state).</extracomment>
        <translation>添加插件清单</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="140"/>
        <source>Manifest files (*.json)</source>
        <translation>清单文件(*.json)</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="149"/>
        <source>Install Failed</source>
        <translation>安装失败</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="176"/>
        <source>No Manifest</source>
        <translation>无清单</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="178"/>
        <source>This plugin has no loaded manifest. Use Add Manifest to load its declared permissions before enabling it.</source>
        <translation>此插件尚未加载清单。请在启用之前使用“添加清单”加载其声明的权限。</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="185"/>
        <source>Enable Plugin</source>
        <translation>启用插件</translation>
    </message>
    <message>
        <source>Enable %1 and grant it these permissions?

%2

The plugin runs sandboxed and can only edit through reversible commands. It cannot reach the UI, filesystem, or network.</source>
        <translation type="vanished">启用 %1 并授予它以下权限?

%2

该插件在沙盒中运行，只能通过可撤销的命令进行编辑，无法访问界面、文件系统或网络。</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="187"/>
        <source>Enable %1 and approve these permissions?

%2

Plugins are not isolated from your computer. Only enable plugins you trust. These permissions are checked only on requests made through the app&apos;s permission object, not on what the plugin&apos;s own code can do.</source>
        <translation>启用 %1 并批准以下权限?

%2

插件并没有与你的计算机隔离开。请只启用你信任的插件。这些权限只在请求通过应用的权限对象发出时才会被检查，插件本身的代码能做什么则不在检查之列。</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="203"/>
        <source>Enable Failed</source>
        <translation>启用失败</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="234"/>
        <source>enabled</source>
        <translation>已启用</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="234"/>
        <source>disabled</source>
        <translation>已禁用</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="235"/>
        <source>%1 v%2 — %3</source>
        <translation>%1 v%2 — %3</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="264"/>
        <source>(no manifest loaded — permissions unknown)</source>
        <translation>(未加载清单，权限未知)</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="278"/>
        <source>Read the open document</source>
        <translation>读取当前打开的文档</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="280"/>
        <source>Change the document through the app&apos;s commands</source>
        <translation>通过应用的命令更改文档</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="282"/>
        <source>Add new script commands</source>
        <translation>添加新的脚本命令</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="284"/>
        <source>Add new procedural generation commands</source>
        <translation>添加新的程序化生成命令</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="299"/>
        <source>Select a plugin to view its permissions.</source>
        <translation>选择一个插件以查看其权限</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="309"/>
        <source>Refresh</source>
        <translation>刷新</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="310"/>
        <source>Add Manifest…</source>
        <translation>添加清单…</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="311"/>
        <source>Enable</source>
        <translation>启用</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="312"/>
        <source>Disable</source>
        <translation>禁用</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="313"/>
        <source>Declared permissions:</source>
        <translation>声明的权限:</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="314"/>
        <source>Plugin manager</source>
        <translation>插件管理器</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="315"/>
        <source>Discovered and installed plugins</source>
        <translation>已发现和已安装的插件</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="316"/>
        <source>Selected plugin permissions</source>
        <translation>所选插件的权限</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="317"/>
        <source>Refresh the plugin list</source>
        <translation>刷新插件列表</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="318"/>
        <source>Add a plugin manifest</source>
        <translation>添加插件清单</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="319"/>
        <source>Enable the selected plugin</source>
        <translation>启用所选插件</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="320"/>
        <source>Disable the selected plugin</source>
        <translation>禁用所选插件</translation>
    </message>
</context>
<context>
    <name>Presence_Panel</name>
    <message>
        <location filename="../ui/presence_panel.py" line="101"/>
        <location filename="../ui/presence_panel.py" line="109"/>
        <location filename="../ui/presence_panel.py" line="118"/>
        <location filename="../ui/presence_panel.py" line="161"/>
        <source>Presence</source>
        <translation>在线状态</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="102"/>
        <source>Open a shared project first.</source>
        <translation>请先打开共享项目</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="110"/>
        <source>Enter your member id to announce presence.</source>
        <translation>输入你的成员 ID 以公布在线状态</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="164"/>
        <source>Members currently present in the shared project. Presence is ephemeral and is never saved into the project file.</source>
        <translation>当前在共享项目中的成员。在线状态是临时的，绝不会保存到项目文件中。</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="168"/>
        <location filename="../ui/presence_panel.py" line="169"/>
        <source>Your member id</source>
        <translation>你的成员 ID</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="170"/>
        <source>Join</source>
        <translation>加入</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="171"/>
        <source>Announce your presence</source>
        <translation>公布在线状态</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="172"/>
        <source>Leave</source>
        <translation>离开</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="173"/>
        <source>Clear your presence</source>
        <translation>清除在线状态</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="174"/>
        <source>Present members</source>
        <translation>在线成员</translation>
    </message>
</context>
<context>
    <name>Prewarm_Indicator</name>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="81"/>
        <source>Playback preparation progress</source>
        <extracomment>Emitted when the user cancels the pre-warm (wired to Stop by the shell).</extracomment>
        <translation>播放准备进度</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="82"/>
        <source>Preparing playback…</source>
        <translation>正在准备播放…</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="83"/>
        <source>Frames prepared</source>
        <translation>已准备的帧</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="84"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="85"/>
        <location filename="../ui/prewarm_indicator.py" line="86"/>
        <source>Cancel playback preparation</source>
        <translation>取消播放准备</translation>
    </message>
</context>
<context>
    <name>Procgen_Panel</name>
    <message>
        <location filename="../ui/procgen_panel.py" line="82"/>
        <location filename="../ui/procgen_panel.py" line="87"/>
        <location filename="../ui/procgen_panel.py" line="213"/>
        <location filename="../ui/procgen_panel.py" line="214"/>
        <source> px</source>
        <extracomment>Largest seed the spin box offers (a display range for the control; the engine accepts any int seed). 2**31 - 1 keeps the value in the Qt spin box&apos;s int range. ``(ops, label)`` — the host should dispatch the ``procgen`` op on the worker as one undoable grouped command (REQ-P8-UI-007/-009).</extracomment>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="156"/>
        <source>Running…</source>
        <translation>正在运行…</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="158"/>
        <source>Done</source>
        <translation>完成</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="159"/>
        <source>Idle</source>
        <translation>空闲</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="174"/>
        <source>Procedural Generation</source>
        <translation>程序化生成</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="197"/>
        <source>Value noise</source>
        <translation>值噪声</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="198"/>
        <source>Gradient noise</source>
        <translation>梯度噪声</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="199"/>
        <source>OpenSimplex noise</source>
        <translation>OpenSimplex 噪声</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="200"/>
        <source>Cellular automata</source>
        <translation>元胞自动机</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="201"/>
        <source>Dithered gradient</source>
        <translation>抖动渐变</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="207"/>
        <source>Algorithm</source>
        <translation>算法</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="208"/>
        <source>Seed</source>
        <translation>种子</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="209"/>
        <source>Width</source>
        <translation>宽度</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="210"/>
        <source>Height</source>
        <translation>高度</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="211"/>
        <source>Frequency</source>
        <translation>频率</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="212"/>
        <source>Octaves</source>
        <translation>倍频数</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="215"/>
        <source>Generate</source>
        <translation>生成</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="217"/>
        <source>Procedural generation</source>
        <translation>程序化生成</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="218"/>
        <source>Generation algorithm</source>
        <translation>生成算法</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="219"/>
        <source>Random seed</source>
        <translation>随机种子</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="220"/>
        <source>Output width in pixels</source>
        <translation>输出宽度(像素)</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="221"/>
        <source>Output height in pixels</source>
        <translation>输出高度(像素)</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="222"/>
        <source>Noise base frequency</source>
        <translation>噪声基础频率</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="223"/>
        <source>Noise octaves</source>
        <translation>噪声倍频数</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="224"/>
        <source>Generate content</source>
        <translation>生成内容</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="225"/>
        <source>Progress</source>
        <translation>进度</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="226"/>
        <source>Generation progress</source>
        <translation>生成进度</translation>
    </message>
</context>
<context>
    <name>Provider_Config_Dialog</name>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="258"/>
        <source>The OS keyring is unavailable; install the &apos;assistant_live&apos; extra to store an API key. The provider settings were saved.</source>
        <extracomment>Provider-kind identifiers. These double as the keyring service namespace segment (``pixelart-creator:assistant:{provider}``) and the adapter&apos;s ``provider`` arg, so the key stored here is the key the adapter loads. Module-local vocabulary (ADR-0001), not a numeric constant. The keyring account the single-user key is stored under (matches ``data/llm``&apos;s ``_DEFAULT_ACCOUNT`` so the adapter loads the same credential). :class:`QSettings` group + keys for the NON-SECRET configuration only. Sensible default endpoints per provider kind (the user may override).</extracomment>
        <translation>操作系统密钥环不可用；请安装“assistant_live”扩展以存储 API 密钥。服务商设置已保存。</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="269"/>
        <source>Could not store the API key: {0}</source>
        <translation>无法存储 API 密钥: {0}</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="282"/>
        <source>Configure AI Assistant Provider</source>
        <translation>配置 AI 助手服务商</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="283"/>
        <source>AI assistant provider configuration</source>
        <translation>AI 助手服务商配置</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="284"/>
        <source>OpenAI-compatible</source>
        <translation>兼容 OpenAI</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="285"/>
        <source>Anthropic (Claude)</source>
        <translation>Anthropic (Claude)</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="286"/>
        <location filename="../ui/provider_config_dialog.py" line="287"/>
        <source>Provider</source>
        <translation>服务商</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="288"/>
        <source>Endpoint URL</source>
        <translation>端点 URL</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="289"/>
        <source>Provider endpoint URL</source>
        <translation>服务商端点 URL</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="290"/>
        <source>https://…</source>
        <translation>https://…</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="291"/>
        <source>Model</source>
        <translation>模型</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="292"/>
        <source>Model name</source>
        <translation>模型名称</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="293"/>
        <source>e.g. gpt-4o-mini</source>
        <translation>例如 gpt-4o-mini</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="294"/>
        <source>API key</source>
        <translation>API 密钥</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="295"/>
        <source>API key (stored in the OS keyring)</source>
        <translation>API 密钥(存储在操作系统密钥环中)</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="297"/>
        <source>Leave blank to keep the existing key</source>
        <translation>留空则保留现有密钥</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="301"/>
        <source>The API key is stored only in your OS keyring — never in a project file or a log.</source>
        <translation>API 密钥仅存储在操作系统密钥环中，绝不会存入项目文件或日志</translation>
    </message>
</context>
<context>
    <name>Real_Size_Calibration_Dialog</name>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="85"/>
        <source> mm</source>
        <extracomment>On-screen calibration bar length in device-independent px (a known ruler the user matches against a real ruler / credit card to derive the true DPI). Millimetres per inch (calibration converts a measured mm length to DPI).</extracomment>
        <translation> mm</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="112"/>
        <source>Calibrate Real Size</source>
        <translation>校准实际尺寸</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="115"/>
        <source>Hold a ruler against the bar below and enter its measured length so real size matches your screen.</source>
        <translation>将尺子贴近下方的校准条，并输入测得的长度，使实际尺寸与屏幕相符</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="119"/>
        <source>Measured length</source>
        <translation>测量长度</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="121"/>
        <source>Measured calibration bar length in millimetres</source>
        <translation>校准条的测量长度(毫米)</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="123"/>
        <source>Calibration bar</source>
        <translation>校准条</translation>
    </message>
</context>
<context>
    <name>Real_Size_Preview_Window</name>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="258"/>
        <source>calibrated</source>
        <extracomment>A user-calibrated DPI override (``None`` =&gt; use the queried physical DPI).</extracomment>
        <translation>已校准</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="258"/>
        <source>screen</source>
        <translation>屏幕</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="261"/>
        <source>Real size: {0:.0f} PPI ({1}), scale {2:.2f}×</source>
        <translation>实际尺寸: {0:.0f} PPI({1})，缩放 {2:.2f}×</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="269"/>
        <source>Real-Size Preview</source>
        <translation>实际尺寸预览</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="270"/>
        <source>Real-size preview</source>
        <translation>实际尺寸预览</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="271"/>
        <source>Real-size document preview</source>
        <translation>实际尺寸文档预览</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="272"/>
        <source>Calibrate…</source>
        <translation>校准…</translation>
    </message>
</context>
<context>
    <name>Realtime_Client</name>
    <message>
        <location filename="../ui/realtime_worker.py" line="255"/>
        <source>no real-time transport configured</source>
        <extracomment>Builds a fresh :class:`TransportPort` on connect, called **on the worker thread**. Injectable so a test (or the out-of-CI WebSocket path) swaps the loopback transport with no UI change — the port is the provider-agnostic seam (REQ-P10-DATA-007). Poll cadence, seconds — how often the worker drains inbound frames when idle. A presentation-loop timing (not a domain tuning value, so module-local): outbound sends wake the loop immediately via the queue, so this only bounds inbound latency. Bounded wait for the worker thread to join on teardown, ms (presentation-only timing, mirrors ``cloud_worker._CLOUD_SHUTDOWN_WAIT_MS``). Past this the daemon backstop guarantees the thread cannot block interpreter exit. Sentinel pushed to the outbound queue to wake a blocking ``get`` on stop. ``(document_id, raw_frame_bytes)`` — one inbound, transport-validated framed message; the consumer routes it with ``sync_protocol.decode_message``. ``(connected,)`` — the worker joined (``True``) the document&apos;s relay. ``(kind,)`` — the worker hit a transport error (surfaced, never a crash); the payload is a ``FailureKind`` value, translated on the GUI thread. emitted once when the worker loop has fully exited (thread is ending). ``(document_id, raw_frame_bytes)`` — one inbound framed message (GUI thread). ``(connected,)`` — the real-time connection state changed. ``(message, is_failure)`` — a transport error occurred (surfaced to the user). ``is_failure`` is ``True`` for a failure sentence and ``False`` for a reason that is not one (no transport configured); the status bar frames the two differently.</extracomment>
        <translation>未配置实时传输</translation>
    </message>
</context>
<context>
    <name>Recovery_Prompt</name>
    <message>
        <location filename="../ui/recovery_prompt.py" line="74"/>
        <source>Recover Unsaved Work</source>
        <translation>找回未保存的工作</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="77"/>
        <source>Unsaved work from a previous session was found. Recover it into a new tab? Your last explicit save is not affected.</source>
        <translation>发现上一次会话中未保存的工作。要在新标签页中找回吗? 上次手动保存的内容不受影响。</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="81"/>
        <source>Recover</source>
        <translation>找回</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="82"/>
        <source>Discard</source>
        <translation>放弃</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="83"/>
        <source>Recover unsaved work</source>
        <translation>找回未保存的工作</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="84"/>
        <source>Discard unsaved work</source>
        <translation>放弃未保存的工作</translation>
    </message>
</context>
<context>
    <name>Reference_Board</name>
    <message>
        <location filename="../ui/reference_board.py" line="320"/>
        <source>Reference board full</source>
        <extracomment>Emitted with the picked RGBA tuple when a plain wheel notch travels the shared Favourites cursor (REQ-IS-UI-008, D-16). The board never touches the document/buffers/undo stack (REQ-P9-UI-010); this only sets the app-wide active colour/palette state, same as every other surface. The persisted Favourites model bound via :meth:`set_favourites_model` (D-16); ``None`` until the shell binds one.</extracomment>
        <translation>参考板已满</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/reference_board.py" line="322"/>
        <source>The board already holds the maximum of %n images.</source>
        <translation>
            <numerusform>参考板已达上限，最多容纳 %n 张图像</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="332"/>
        <source>Cannot load image</source>
        <translation>无法加载图像</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="333"/>
        <source>The file could not be read as an image: {0}</source>
        <translation>无法将此文件作为图像读取: {0}</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="404"/>
        <source>Save Reference Board</source>
        <translation>保存参考板</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="406"/>
        <location filename="../ui/reference_board.py" line="426"/>
        <source>Reference board (*.pixboard)</source>
        <translation>参考板(*.pixboard)</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="415"/>
        <source>Save failed</source>
        <translation>保存失败</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="424"/>
        <source>Open Reference Board</source>
        <translation>打开参考板</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="436"/>
        <source>Open failed</source>
        <translation>打开失败</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="447"/>
        <source>Add Reference Image</source>
        <translation>添加参考图像</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="449"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>图像(*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="515"/>
        <source>Reference Board</source>
        <translation>参考板</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="516"/>
        <source>Reference board</source>
        <translation>参考板</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="517"/>
        <source>Reference board canvas</source>
        <translation>参考板画布</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="518"/>
        <source>Add Image…</source>
        <translation>添加图像…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="519"/>
        <source>Save…</source>
        <translation>保存…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="520"/>
        <source>Open…</source>
        <translation>打开…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="521"/>
        <source>Always on Top</source>
        <translation>始终置顶</translation>
    </message>
</context>
<context>
    <name>Reference_Item</name>
    <message>
        <location filename="../ui/reference_board.py" line="247"/>
        <source>Raise</source>
        <extracomment>Per-wheel-notch board zoom step. Corner grab-handle edge, in item-local px (REQ-P9-UI-006 resize gesture). No matching UI-metric constant exists in ``logic/constants.py`` today (gap reported in this task&apos;s EXIT_STATUS); this module already keeps its own UI-only metrics locally (see ``_BOARD_ZOOM_STEP`` above), so the same convention is followed here rather than inlining a literal (S12). Minimum absolute scale factor a corner-drag resize may reach (guards against a degenerate/zero-size or inverted reference item). Opposite-corner anchor used while resizing (the anchor stays fixed).</extracomment>
        <translation>置于顶层</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="250"/>
        <source>Lower</source>
        <translation>置于底层</translation>
    </message>
</context>
<context>
    <name>RotSprite_Dialog</name>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="93"/>
        <source>No preview</source>
        <extracomment>Angle input bounds, degrees (a full turn either way; not a domain tuning value). Preview label edge, px (presentation-only sizing). Renders a preview :class:`QImage` for a candidate angle (or ``None``).</extracomment>
        <translation>无预览</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="106"/>
        <source>Rotate (RotSprite)</source>
        <translation>旋转(RotSprite)</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="107"/>
        <source>RotSprite rotation dialog</source>
        <translation>RotSprite 旋转对话框</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="108"/>
        <source>Rotation angle in degrees</source>
        <translation>旋转角度(度)</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="109"/>
        <source>Rotation preview</source>
        <translation>旋转预览</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="110"/>
        <source>Angle (deg)</source>
        <translation>角度(度)</translation>
    </message>
</context>
<context>
    <name>Ruler_Strip</name>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="347"/>
        <source>Horizontal ruler</source>
        <extracomment>z-order in the aid band, just below the grid overlays so guides read under grids. Ruler strip thickness in device-independent px (presentation sizing). Default overlay/ruler colours (overridden by the theme&apos;s role colours, 025). Emitted ``(orientation, doc_position)`` when a guide is dragged out.</extracomment>
        <translation>水平标尺</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="349"/>
        <source>Drag down to create a horizontal guide</source>
        <translation>向下拖动可创建水平参考线</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="352"/>
        <source>Vertical ruler</source>
        <translation>垂直标尺</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="354"/>
        <source>Drag right to create a vertical guide</source>
        <translation>向右拖动可创建垂直参考线</translation>
    </message>
</context>
<context>
    <name>Scale_Dialog</name>
    <message>
        <location filename="../ui/transform_dialog.py" line="111"/>
        <source>Scale Canvas</source>
        <translation>缩放画布</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="112"/>
        <source>Scale canvas dialog</source>
        <translation>缩放画布对话框</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="113"/>
        <source>Scale factor</source>
        <translation>缩放系数</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="114"/>
        <source>Target width in pixels</source>
        <translation>目标宽度(像素)</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="115"/>
        <source>Target height in pixels</source>
        <translation>目标高度(像素)</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="116"/>
        <source>Factor</source>
        <translation>系数</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="117"/>
        <source>Width (px)</source>
        <translation>宽度(px)</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="118"/>
        <source>Height (px)</source>
        <translation>高度(px)</translation>
    </message>
</context>
<context>
    <name>Script_Runner_Panel</name>
    <message>
        <location filename="../ui/script_runner_panel.py" line="114"/>
        <source>Running…</source>
        <extracomment>A compact, copy-pasteable example so the empty editor is self-documenting. ``(ops, label)`` — the host should dispatch these DSL ops on the worker as one undoable grouped command (REQ-P8-UI-004/-009).</extracomment>
        <translation>正在运行…</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="116"/>
        <source>Done</source>
        <translation>完成</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="117"/>
        <source>Idle</source>
        <translation>空闲</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="134"/>
        <source>Invalid JSON: %1</source>
        <translation>JSON 无效: %1</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="141"/>
        <source>A script must be a JSON array of steps.</source>
        <translation>脚本必须是由步骤组成的 JSON 数组</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="146"/>
        <source>Each step needs a &apos;name&apos; and optional &apos;params&apos;/&apos;seed&apos;.</source>
        <translation>每个步骤都需要“name”，并可选用“params”/“seed”</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="152"/>
        <source>Step &apos;name&apos; must be a string.</source>
        <translation>步骤的“name”必须是字符串</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="154"/>
        <source>Step &apos;params&apos; must be an object.</source>
        <translation>步骤的“params”必须是对象</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="165"/>
        <source>Script Error</source>
        <translation>脚本错误</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="169"/>
        <location filename="../ui/script_runner_panel.py" line="191"/>
        <source>Run Script</source>
        <translation>运行脚本</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="190"/>
        <source>DSL script (JSON list of steps):</source>
        <translation>DSL 脚本(步骤的 JSON 列表):</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="192"/>
        <source>Script runner</source>
        <translation>脚本运行器</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="193"/>
        <source>Script source</source>
        <translation>脚本源码</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="194"/>
        <source>Run the script</source>
        <translation>运行脚本</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="195"/>
        <source>Progress</source>
        <translation>进度</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="196"/>
        <source>Script run progress</source>
        <translation>脚本运行进度</translation>
    </message>
</context>
<context>
    <name>Shade_Ramp_Picker</name>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="150"/>
        <source>Shade Ramps</source>
        <extracomment>Edge of a ramp swatch button, px (presentation-only sizing). Emitted with an RGBA tuple when a ramp swatch is activated. Emitted with a list of RGBA colours when a whole ramp is added.</extracomment>
        <translation>明暗色阶</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="151"/>
        <source>Shade ramp picker</source>
        <translation>明暗色阶选择器</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="152"/>
        <source>Shades (toward black)</source>
        <translation>暗色调(趋向黑色)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="153"/>
        <source>Tints (toward white)</source>
        <translation>亮色调(趋向白色)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="154"/>
        <source>Tones (toward grey)</source>
        <translation>灰色调(趋向灰色)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="156"/>
        <source>Add to Palette</source>
        <translation>添加到调色板</translation>
    </message>
</context>
<context>
    <name>Shared_Projects_Panel</name>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="144"/>
        <location filename="../ui/shared_projects_panel.py" line="151"/>
        <location filename="../ui/shared_projects_panel.py" line="183"/>
        <location filename="../ui/shared_projects_panel.py" line="190"/>
        <location filename="../ui/shared_projects_panel.py" line="199"/>
        <source>Shared Project</source>
        <extracomment>Fixed display order for the role combo (a stable subset of the module-local :data:`MEMBER_ROLES` vocabulary; presentation ordering, not a domain value). The roster being edited before it is committed via Share/Update.</extracomment>
        <translation>共享项目</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="145"/>
        <source>Member %1 is already in the roster.</source>
        <translation>成员 %1 已在名单中</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/shared_projects_panel.py" line="153"/>
        <source>A shared project may have at most %n members.</source>
        <translation>
            <numerusform>共享项目最多可有 %n 名成员</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="184"/>
        <source>Enter a shared-project name first.</source>
        <translation>请先输入共享项目名称</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="191"/>
        <source>Add at least one member before sharing.</source>
        <translation>共享之前请至少添加一名成员</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="245"/>
        <source>Owner</source>
        <translation>所有者</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="246"/>
        <source>Editor</source>
        <translation>编辑者</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="247"/>
        <source>Viewer</source>
        <translation>查看者</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="252"/>
        <source>Shared projects</source>
        <translation>共享项目</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="253"/>
        <source>Shared-project name:</source>
        <translation>共享项目名称:</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="254"/>
        <source>e.g. team-sprite</source>
        <translation>例如 team-sprite</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="255"/>
        <source>Shared-project name</source>
        <translation>共享项目名称</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="256"/>
        <location filename="../ui/shared_projects_panel.py" line="257"/>
        <source>Member id to invite</source>
        <translation>要邀请的成员 ID</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="258"/>
        <source>Member role</source>
        <translation>成员角色</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="261"/>
        <source>Add Member</source>
        <translation>添加成员</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="262"/>
        <source>Add member to roster</source>
        <translation>将成员添加到名单</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="263"/>
        <source>Roster to share</source>
        <translation>要共享的成员名单</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="264"/>
        <source>Current members</source>
        <translation>当前成员</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="265"/>
        <source>Remove</source>
        <translation>移除</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="266"/>
        <source>Remove selected member</source>
        <translation>移除所选成员</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="267"/>
        <source>Share / Update</source>
        <translation>共享 / 更新</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="268"/>
        <source>Share or update the project</source>
        <translation>共享或更新项目</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="269"/>
        <source>Member</source>
        <translation>成员</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="269"/>
        <source>Role</source>
        <translation>角色</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="272"/>
        <source>Editable member roster</source>
        <translation>可编辑的成员名单</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="273"/>
        <source>Shared member list</source>
        <translation>共享成员列表</translation>
    </message>
</context>
<context>
    <name>Symmetry_Panel</name>
    <message>
        <location filename="../ui/symmetry_panel.py" line="158"/>
        <source>Off</source>
        <extracomment>Emitted with the newly selected :class:`SymmetryAxis`. Emitted with the mirror centre as ``Optional[Tuple[int, int]]`` once the user edits a position spinbox (``None`` = unset, ``mirror`` defaults to the canvas centre itself, CL-9). Never emitted from programmatic :meth:`set_canvas_size` calls, so a resize alone never fabricates a user-authored position. Axis order shown in the combo (value stored in the item&apos;s user data).</extracomment>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="159"/>
        <source>Vertical</source>
        <translation>垂直</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="160"/>
        <source>Horizontal</source>
        <translation>水平</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="161"/>
        <source>Both</source>
        <translation>双向</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="162"/>
        <source>Diagonal</source>
        <translation>对角</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="166"/>
        <source>Symmetry</source>
        <translation>对称</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="167"/>
        <source>Axis position</source>
        <translation>轴位置</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="168"/>
        <source>X</source>
        <translation>X</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="169"/>
        <source>Y</source>
        <translation>Y</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="170"/>
        <source>Reset to centre</source>
        <translation>重置到中心</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="171"/>
        <source>Symmetry axis panel</source>
        <translation>对称轴面板</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="172"/>
        <source>Symmetry axis</source>
        <translation>对称轴</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="173"/>
        <source>Symmetry axis position X</source>
        <translation>对称轴位置 X</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="174"/>
        <source>Symmetry axis position Y</source>
        <translation>对称轴位置 Y</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="176"/>
        <source>Reset symmetry axis position to centre</source>
        <translation>将对称轴位置重置到中心</translation>
    </message>
</context>
<context>
    <name>Tag_Dialog</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="150"/>
        <location filename="../ui/frame_tags_panel.py" line="192"/>
        <source>Tag colour</source>
        <translation>标签颜色</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="179"/>
        <source>Frame Tag</source>
        <translation>帧标签</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="180"/>
        <source>Name</source>
        <translation>名称</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="181"/>
        <source>From frame</source>
        <translation>起始帧</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="182"/>
        <source>To frame</source>
        <translation>结束帧</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="183"/>
        <source>Mode</source>
        <translation>模式</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="184"/>
        <source>Repeat (0 = infinite)</source>
        <translation>重复次数(0 = 无限)</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="185"/>
        <source>Colour</source>
        <translation>颜色</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="186"/>
        <source>Tag name</source>
        <translation>标签名称</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="187"/>
        <source>Tag start frame</source>
        <translation>标签起始帧</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="188"/>
        <source>Tag end frame</source>
        <translation>标签结束帧</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="189"/>
        <source>Tag playback mode</source>
        <translation>标签播放模式</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="190"/>
        <source>Tag repeat count</source>
        <translation>标签重复次数</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="191"/>
        <source>Colour…</source>
        <translation>颜色…</translation>
    </message>
</context>
<context>
    <name>Tile_Edit_Dialog</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="193"/>
        <source>Edit Tile</source>
        <translation>编辑瓦片</translation>
    </message>
</context>
<context>
    <name>Tilemap_Canvas</name>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="734"/>
        <source>Auto-tile</source>
        <extracomment>Initial scene window (px) for a fresh infinite map; grows to include stamps. Edge (px) of one checker square drawn behind the map (presentation-only). Platform name Qt reports with no windowing system (keep the raster viewport). MiB budget of the chunk pixmap LRU (D1). A 16x16 chunk at 16 px tiles is a 256x256 RGBA pixmap (~256 KiB), so ~128 MiB keeps a large working set resident while staying bounded on an infinite / fully filled map. Presentation/resource sizing (like frame_cache&apos;s budget), so it lives here in ui/, not logic/constants. Max cold chunks rendered *inline* per paint before the rest stream off-thread (D4). A cold chunk is ~0.84 ms (measured), so a handful stays well under the 16 ms budget and keeps a stamp / small pan instant; a full cold viewport streams. Bounded wait (ms) for an in-flight off-thread chunk render to finish on rebind / window close before the pool is torn down (mirrors canvas_scene&apos;s shutdown wait). Emitted after a layer&apos;s auto-tile mode changes (drives the panel checkbox). Emitted when a stamp/fill is refused because the tilemap has no tileset bound yet (CI-red field defect, 2026-08-24: the original FIX 5 routed this refusal through a blocking ``QMessageBox.warning``, which hangs a headless parallel worker with nothing to dismiss it). Follows the ``Canvas_View.lockedLayerEditRejected`` precedent exactly -- a signal the shell surfaces non-blockingly, never a modal, for a refusal reachable from a plain mouse gesture. Emitted when a stamp/fill is refused because no tile is selected as the active brush (a tileset IS bound; the brush gid is 0). Kept distinct from ``noTilesetBoundRejected`` so the shell shows the honest message for each case, exactly as the two ``_warn_no_active_brush`` branches already did. Emitted with the picked RGBA tuple when a plain wheel notch / an unmodified middle click travels the shared Favourites cursor (REQ-IS-UI-008/-012). Mirrors ``Canvas_View.colorPicked`` — the tilemap has no colour of its own to paint with, but the app-wide active colour/palette state is shared across every surface. A middle press awaiting the click/drag verdict — see ``Canvas_View._middle_pending`` (REQ-IS-UI-011); same behaviour here. The persisted Favourites model bound via :meth:`set_favourites_model` ``None`` until the shell binds one.</extracomment>
        <translation>自动拼贴</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="997"/>
        <source>Stamp</source>
        <translation>盖章</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1003"/>
        <source>Stamp Tile</source>
        <translation>盖章瓦片</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1013"/>
        <source>Erase</source>
        <translation>擦除</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1019"/>
        <source>Erase Tile</source>
        <translation>擦除瓦片</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1038"/>
        <source>Fill</source>
        <translation>填充</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1044"/>
        <source>Fill Rectangle</source>
        <translation>填充矩形</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1102"/>
        <source>Tilemap canvas</source>
        <translation>瓦片地图画布</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1105"/>
        <source>Tilemap: left-click to stamp/erase/fill, middle-drag to pan, H/V flip, R rotate</source>
        <translation>瓦片地图: 左键单击可盖章/擦除/填充，中键拖动平移，H/V 翻转，R 旋转</translation>
    </message>
</context>
<context>
    <name>Tilemap_Layer_Panel</name>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="175"/>
        <source>Layer %1</source>
        <extracomment>Emitted with the active layer index (view state, no undo). Emitted when the auto-tile checkbox is toggled (canvas builds the ruleset).</extracomment>
        <translation>图层 %1</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="180"/>
        <location filename="../ui/tilemap_layer_panel.py" line="186"/>
        <location filename="../ui/tilemap_layer_panel.py" line="297"/>
        <source>Add Layer</source>
        <translation>添加图层</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="197"/>
        <location filename="../ui/tilemap_layer_panel.py" line="203"/>
        <location filename="../ui/tilemap_layer_panel.py" line="298"/>
        <source>Remove Layer</source>
        <translation>移除图层</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="236"/>
        <location filename="../ui/tilemap_layer_panel.py" line="242"/>
        <source>Reorder Layer</source>
        <translation>重新排序图层</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="259"/>
        <source>Layer Visibility</source>
        <translation>图层可见性</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="265"/>
        <source>Toggle Layer Visibility</source>
        <translation>切换图层可见性</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="291"/>
        <source>Tilemap layers panel</source>
        <translation>瓦片地图图层面板</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="292"/>
        <source>Layer actions</source>
        <translation>图层操作</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="293"/>
        <source>Tilemap layers</source>
        <translation>瓦片地图图层</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="295"/>
        <source>Ordered map layers; tick to show/hide, top layer first</source>
        <translation>有序的地图图层；勾选可显示/隐藏，顶层在前</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="299"/>
        <source>Move Up</source>
        <translation>上移</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="300"/>
        <source>Move Down</source>
        <translation>下移</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="301"/>
        <source>Auto-tile (Blob-47)</source>
        <translation>自动拼贴(Blob-47)</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="303"/>
        <source>Resolve tile edges automatically from neighbours</source>
        <translation>根据相邻瓦片自动处理瓦片边缘</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="305"/>
        <source>Auto-tile toggle</source>
        <translation>自动拼贴开关</translation>
    </message>
</context>
<context>
    <name>Tileset_Editor_Panel</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="218"/>
        <location filename="../ui/tileset_editor_panel.py" line="429"/>
        <location filename="../ui/tileset_editor_panel.py" line="437"/>
        <source>Tile width</source>
        <extracomment>Emitted with the selected tile&apos;s **global gid** (view state, no undo).</extracomment>
        <translation>瓦片宽度</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="221"/>
        <location filename="../ui/tileset_editor_panel.py" line="430"/>
        <location filename="../ui/tileset_editor_panel.py" line="438"/>
        <source>Tile height</source>
        <translation>瓦片高度</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="224"/>
        <location filename="../ui/tileset_editor_panel.py" line="439"/>
        <source>Tile margin</source>
        <translation>瓦片边距</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="227"/>
        <location filename="../ui/tileset_editor_panel.py" line="440"/>
        <source>Tile spacing</source>
        <translation>瓦片间距</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="318"/>
        <source>Tile %1</source>
        <translation>瓦片 %1</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="371"/>
        <location filename="../ui/tileset_editor_panel.py" line="377"/>
        <source>Re-slice Tileset</source>
        <translation>重新切分瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="395"/>
        <location filename="../ui/tileset_editor_panel.py" line="401"/>
        <source>Edit Tile</source>
        <translation>编辑瓦片</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="428"/>
        <source>Tileset editor panel</source>
        <translation>瓦片集编辑器面板</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="431"/>
        <source>Margin</source>
        <translation>边距</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="432"/>
        <source>Spacing</source>
        <translation>间距</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="433"/>
        <location filename="../ui/tileset_editor_panel.py" line="434"/>
        <location filename="../ui/tileset_editor_panel.py" line="435"/>
        <location filename="../ui/tileset_editor_panel.py" line="436"/>
        <source> px</source>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="441"/>
        <source>Re-slice</source>
        <translation>重新切分</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="442"/>
        <source>Re-slice the source image</source>
        <translation>重新切分源图像</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="443"/>
        <source>Re-slice tileset</source>
        <translation>重新切分瓦片集</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="444"/>
        <source>Edit Tile…</source>
        <translation>编辑瓦片…</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="445"/>
        <source>Paint into the selected source tile</source>
        <translation>在所选源瓦片中绘制</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="446"/>
        <source>Edit selected tile</source>
        <translation>编辑所选瓦片</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="447"/>
        <source>Tileset tiles</source>
        <translation>瓦片集中的瓦片</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="449"/>
        <source>Sliced tiles in row-major order; click to select for stamping</source>
        <translation>按行优先顺序排列的已切分瓦片；单击可选中以盖章</translation>
    </message>
</context>
<context>
    <name>Timelapse_Controls</name>
    <message numerus="yes">
        <location filename="../ui/timelapse_controls.py" line="435"/>
        <source>%n frame(s) were dropped because the edits they recorded were undone and replaced.</source>
        <extracomment>A Document -&gt; RGBA ``ndarray`` renderer (e.g. wrapping ``blend.composite_stack``), injected by the host rather than authored here (S11 — no domain/composite maths in this widget). Returns the currently active document for a bound ``QUndoStack`` (S11 — this widget reads it, it never derives it). Emitted with the current frame count after a record / load / reset. Emitted with one reconstructed RGBA ``ndarray`` per displayed frame, whichever substrate served it (in-session or a loaded payload). Emitted ``True`` while document edits must be refused (playing or paused mid-sequence), ``False`` once playback stops or completes. Emitted with the number of frames dropped by a discarded branch (REQ-P9-UI-021), once per occurrence. The per-recording identity half (REQ-P9-LOGIC-022; plan §10.1) — one :mod:`secrets` draw, minted once per recording (here, and again on every :meth:`reset`). Never an adversarial-strength token (``TIMELAPSE_RECORDING_ID_BYTES``&apos; own docstring): it only has to not collide, and it is paid for on every frame. The monotone ordinal half — only ever ``+= 1``, never reset, rewound, or derived from ``len(session.frames)``: every rewrite path rebuilds the frames *tuple*, and a counter living inside it would rewind with it (plan §10.1). The id of the document this session was recorded against (REQ-P9-UI-020) — ``None`` until the first frame is recorded. The id of the document currently bound (the active tab). stack index -&gt; the FrameId minted the last time that index was reached forward (plan §10.2). On every forward index change to ``i``, every entry with key ``&gt;= i`` is evicted **before** any new mint — an event-time observation, exact because nothing has been reused yet, never a resolution-time inference from a count. Its value set is both the surviving-identity set passed to :func:`~pixelart_creator.logic.timelapse.drop_discarded` and the live HISTORY extent handed to :class:`~pixelart_creator.ui.timelapse_playback.History_Document_Provider`. Set by :meth:`load_reopened_recording` when reviewing a loaded, cross-session payload rather than the live in-session history. ``True`` only while this widget is itself driving the bound ``QUndoStack`` through a provider (a historical render or a save&apos;s payload snapshot pass) — every ``indexChanged`` this causes is this widget&apos;s own bookkeeping, never a user commit, and must not be recorded or misread as a discard boundary (D1 fix; see ``_render_all``/``_build_payload_tables``).</extracomment>
        <translation>
            <numerusform>有 %n 帧已被丢弃，因为它们所记录的编辑已被撤销并被替换</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="469"/>
        <source>Recording stopped</source>
        <translation>录制已停止</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="471"/>
        <source>Recording was stopped because it reached the maximum number of frames. The frames already recorded are kept. Save this recording, or reset it to start a new one.</source>
        <translation>录制因达到帧数上限而停止。已录制的帧会保留。请保存此录制，或将其重置以开始新的录制。</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="543"/>
        <source>Different document</source>
        <translation>不同的文档</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="545"/>
        <source>This recording belongs to a different document. Switch to that document to resume it, or reset first to start a new one here.</source>
        <translation>此录制属于另一个文档。请切换到该文档以继续录制，或先重置以在此处开始新的录制。</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="562"/>
        <source>Save Timelapse</source>
        <translation>保存延时回放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="564"/>
        <location filename="../ui/timelapse_controls.py" line="678"/>
        <source>Timelapse (*.pixtimelapse)</source>
        <translation>延时回放(*.pixtimelapse)</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="573"/>
        <location filename="../ui/timelapse_controls.py" line="591"/>
        <location filename="../ui/timelapse_controls.py" line="608"/>
        <source>Save failed</source>
        <translation>保存失败</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="575"/>
        <source>This recording could not be saved because a recorded state could not be reconstructed from the current history.</source>
        <translation>此录制无法保存，因为无法从当前历史记录重建某个已录制的状态</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="593"/>
        <source>This recording was not saved because it is too large. Nothing was written. Discard some frames and try again.</source>
        <translation>此录制因过大而未保存，未写入任何内容。请丢弃部分帧后重试。</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="610"/>
        <source>This recording could not be saved. The file could not be written, or its data could not be encoded.</source>
        <translation>无法保存此录制。无法写入文件，或无法对其数据进行编码。</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="676"/>
        <source>Open Timelapse</source>
        <translation>打开延时回放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="693"/>
        <source>Open failed</source>
        <translation>打开失败</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="695"/>
        <source>This file could not be opened. It is missing, unreadable, or not a valid timelapse recording.</source>
        <translation>无法打开此文件。文件缺失、无法读取，或不是有效的延时回放录制。</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="754"/>
        <source>There is nothing recorded to play yet.</source>
        <translation>还没有可播放的录制内容</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="761"/>
        <source>This recording belongs to a different document. Switch to that document to play it.</source>
        <translation>此录制属于另一个文档。请切换到该文档以播放它。</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="766"/>
        <source>Playback is not available yet.</source>
        <translation>播放尚不可用</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="782"/>
        <source>This recording was saved in a form that cannot be replayed.</source>
        <translation>此录制的保存形式无法重新播放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="787"/>
        <source>This recording&apos;s saved data is incomplete and cannot be fully replayed.</source>
        <translation>此录制的已保存数据不完整，无法完整重新播放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="793"/>
        <source>Some recorded frames are no longer reachable in the current history and cannot be played.</source>
        <translation>部分已录制的帧在当前历史记录中已无法访问，因此无法播放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="798"/>
        <source>This recording&apos;s history no longer matches; it cannot be replayed from here.</source>
        <translation>此录制的历史记录已不再匹配，无法从此处重新播放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="812"/>
        <source>This recording was saved in an earlier form whose frames cannot be told apart reliably, so it will not be replayed.</source>
        <translation>此录制是以较早的形式保存的，其帧无法可靠地区分，因此不会重新播放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="815"/>
        <source>This recording cannot be played.</source>
        <translation>无法播放此录制</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="845"/>
        <source>Cannot play</source>
        <translation>无法播放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="853"/>
        <source>Playback failed</source>
        <translation>播放失败</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="854"/>
        <source>This recording could not be replayed.</source>
        <translation>无法重新播放此录制</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="941"/>
        <source>Frame {0} of {1}</source>
        <translation>第 {0} 帧，共 {1} 帧</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="946"/>
        <source>Recorded frames: {0}</source>
        <translation>已录制的帧: {0}</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="978"/>
        <source>Stop Recording</source>
        <translation>停止录制</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="978"/>
        <source>Record</source>
        <translation>录制</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="983"/>
        <source>Pause</source>
        <translation>暂停</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="983"/>
        <source>Play</source>
        <translation>播放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="987"/>
        <source>Timelapse</source>
        <translation>延时回放</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="988"/>
        <source>Timelapse controls</source>
        <translation>延时回放控件</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="989"/>
        <source>Save…</source>
        <translation>保存…</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="990"/>
        <source>Open…</source>
        <translation>打开…</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="991"/>
        <source>Stop</source>
        <translation>停止</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="992"/>
        <source>Timelapse position</source>
        <translation>延时回放位置</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="993"/>
        <source>Playback speed</source>
        <translation>播放速度</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="998"/>
        <source>Playback refusal reason</source>
        <translation>播放被拒绝的原因</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="999"/>
        <source>Recorded frame count</source>
        <translation>已录制的帧数</translation>
    </message>
</context>
<context>
    <name>Timelapse_Frame_View</name>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="52"/>
        <location filename="../ui/timelapse_frame_view.py" line="116"/>
        <source>Reopened recording — not the current document</source>
        <translation>已重新打开的录制，并非当前文档</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="110"/>
        <source>Reopened Recording</source>
        <translation>已重新打开的录制</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="111"/>
        <source>Reopened timelapse recording</source>
        <translation>已重新打开的延时回放录制</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="113"/>
        <source>Reopened recording — this is not your current document</source>
        <translation>已重新打开的录制，这不是当前文档</translation>
    </message>
</context>
<context>
    <name>Timeline_Grid_View</name>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="553"/>
        <source>Toggle Cel Visibility</source>
        <extracomment>Emitted with the frame index a selection (of any kind) settled on (REQ-P5-UI-023). Pushes no command. Emitted with the ``layer_id`` a cell/row-header selection settled on (REQ-P5-UI-023). Pushes no command. Emitted with the frame index the cursor is scrubbing over during a body drag away from any occupied cell (REQ-P5-UI-025). Pushes no command. Emitted when a Ctrl+right-click removal was refused because the target document has only one frame left (D-22). ``Document._ensure_frame_removable`` is the single, unconditional owner of that invariant; this view asks the bound document itself (``len(document.frames)``) rather than keeping a second, independently-maintained notion of &quot;removable&quot; — so the two can never drift apart. Pushes no command; the gesture stays inert.</extracomment>
        <translation>切换画格可见性</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="589"/>
        <source>Create Cel Here</source>
        <translation>在此创建画格</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="591"/>
        <source>Create a new drawing on this track in this frame</source>
        <translation>在此帧的此轨道上创建新绘图</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="609"/>
        <source>Create Cel</source>
        <translation>创建画格</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="642"/>
        <source>Remove Frame</source>
        <translation>移除帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="666"/>
        <source>Reorder Frame</source>
        <translation>重新排序帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="816"/>
        <source>Copy Cel</source>
        <translation>复制画格</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="824"/>
        <source>Move Cel</source>
        <translation>移动画格</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="851"/>
        <source>Timeline grid</source>
        <translation>时间轴网格</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="854"/>
        <source>Frames as columns, layer tracks as rows; drag a header to reorder, drag a drawing to move it (hold Ctrl to copy), or open the context menu on an empty cell to create a cel there</source>
        <translation>帧为列，图层轨道为行；拖动表头可重新排序，拖动绘图可移动它(按住 Ctrl 可复制)，或在空单元格上打开右键菜单以在此创建画格</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="859"/>
        <source>Frame headers</source>
        <translation>帧表头</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="860"/>
        <source>Layer track headers</source>
        <translation>图层轨道表头</translation>
    </message>
</context>
<context>
    <name>Timeline_Panel</name>
    <message>
        <location filename="../ui/timeline_panel.py" line="274"/>
        <source>Frame %1</source>
        <extracomment>Index of the strip surface in the cell-surface QStackedWidget — the default (REQ-P5-UI-020: &quot;the strip is the default&quot;). Not a domain constant (Article II does not reach a fixed widget-stack index); grouped with the other presentation literals this module already carries. Longest edge (px) of a cached per-cell frame thumbnail. Presentation-only sizing (like ``_SWATCH_PX`` in ``main_window``); the resident buffer is never culled — only the small display thumbnail is downscaled (F7). Ceiling for the per-frame duration spin box (ms). A presentation-only cap on how high the editor spins (like ``_THUMBNAIL_EDGE``); it is NOT a domain tuning value — the authoritative bound is the logic ``make_set_frame_duration_command`` positive-int guard, which alone validates. Emitted with the frame index a click/keyboard selected (settled — onion on). Emitted with the frame index the cursor is dragging over (scrub — onion off). Emitted with a ``layer_id`` the grid cell surface&apos;s selection settled on (REQ-P5-UI-023, BF-G1); the strip has no layer axis and never emits this.</extracomment>
        <translation>第 %1 帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="282"/>
        <source>Frame %1 — %2 ms</source>
        <translation>第 %1 帧，%2 ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="396"/>
        <location filename="../ui/timeline_panel.py" line="515"/>
        <source>Add Frame</source>
        <translation>添加帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="408"/>
        <location filename="../ui/timeline_panel.py" line="517"/>
        <source>Remove Frame</source>
        <translation>移除帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="419"/>
        <location filename="../ui/timeline_panel.py" line="519"/>
        <source>Duplicate Frame</source>
        <translation>复制帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="452"/>
        <source>Reorder Frame</source>
        <translation>重新排序帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="468"/>
        <source>Set Frame Duration</source>
        <translation>设置帧时长</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="509"/>
        <source>Timeline panel</source>
        <translation>时间轴面板</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="510"/>
        <source>Frame actions</source>
        <translation>帧操作</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="511"/>
        <source>Frame strip</source>
        <translation>帧条</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="513"/>
        <source>Frames left-to-right in playback order; drag to reorder</source>
        <translation>帧按播放顺序从左到右排列；拖动可重新排序</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="516"/>
        <source>Insert a new frame after the active one</source>
        <translation>在当前帧之后插入新帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="518"/>
        <source>Delete the active frame</source>
        <translation>删除当前帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="521"/>
        <source>Insert a copy of the active frame after it</source>
        <translation>在当前帧之后插入其副本</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="523"/>
        <source>Grid View</source>
        <translation>网格视图</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="525"/>
        <source>Show frames and layer tracks as a grid instead of a strip</source>
        <translation>以网格而非条带显示帧和图层轨道</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="527"/>
        <source>Timeline cell surface</source>
        <translation>时间轴单元格区域</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="528"/>
        <source>Duration</source>
        <translation>时长</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="530"/>
        <source> ms</source>
        <translation> ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="531"/>
        <source>Frame duration</source>
        <translation>帧时长</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="533"/>
        <source>Display time of the active frame, in milliseconds</source>
        <translation>当前帧的显示时间(毫秒)</translation>
    </message>
</context>
<context>
    <name>User_Guide_Dialog</name>
    <message>
        <location filename="../ui/user_guide.py" line="509"/>
        <source>Could not load this topic:

%1</source>
        <extracomment>Qt roles that would resolve an anchor to the network or the local filesystem; the viewer is fully offline (REQ-UG-UI-007), so a click on such a link is a no-op — it is never fetched. The UserRole slot carrying a topic id on a ToC / results item. The in-guide markdown image URL the mark resolves against. The guide pages reference the mark as ``![PixelArt Creator](pac-logo.png)`` under this EXACT string -- it is the contract between the content and this widget&apos;s document-resource registration; do not change it here. A reader callable: a bundle-relative content ref -&gt; the Markdown text. Defaults to the defensive ``data`` reader; injectable so headless tests can substitute a fixture reader without touching the real bundle. A locale provider: returns the active UI locale code (e.g. ``&quot;en&quot;``). Defaults to the guide&apos;s default locale; the main window passes the LanguageManager&apos;s ``current_language`` so content follows the UI language (REQ-UG-UI-011 / CL-3). Qt&apos;s scale for a char format&apos;s font-size adjustment (``+1`` is 1.2 times the base size, ``+2`` 1.5, ``+3`` 2.0); the markdown importer gives a heading the adjustment ``4 - level``. Used to find the size a heading would be drawn at, so it can be rounded to a whole multiple of the pixel font&apos;s em. Emitted when the hidden logo switch is toggled (the new on/off state), so the owner can remember it (``REQ-VI-UI-017``).</extracomment>
        <translation>无法加载此主题:

%1</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="568"/>
        <source>The User Guide content could not be loaded:

%1</source>
        <translation>无法加载用户指南内容:

%1</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="571"/>
        <source>The User Guide content could not be loaded.</source>
        <translation>无法加载用户指南内容</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="711"/>
        <location filename="../ui/user_guide.py" line="712"/>
        <source>User Guide</source>
        <translation>用户指南</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="713"/>
        <source>Search the guide…</source>
        <translation>搜索指南…</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="714"/>
        <source>Search the guide</source>
        <translation>搜索指南</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="715"/>
        <source>Guide contents</source>
        <translation>指南目录</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="716"/>
        <source>Search results</source>
        <translation>搜索结果</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="717"/>
        <source>Guide content</source>
        <translation>指南内容</translation>
    </message>
</context>
<context>
    <name>Vanishing_Point_Dialog</name>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="156"/>
        <source>1-point</source>
        <translation>一点透视</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="157"/>
        <source>2-point</source>
        <translation>两点透视</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="158"/>
        <source>3-point</source>
        <translation>三点透视</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="162"/>
        <source>Configure Perspective</source>
        <translation>配置透视</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="163"/>
        <source>Vanishing points</source>
        <translation>灭点</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="164"/>
        <source>Horizon Y</source>
        <translation>地平线 Y</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="165"/>
        <source>Vanishing-point mode</source>
        <translation>灭点模式</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="166"/>
        <source>Horizon Y position</source>
        <translation>地平线 Y 位置</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="170"/>
        <source>Vanishing point {n}</source>
        <translation>灭点 {n}</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="172"/>
        <source>X</source>
        <translation>X</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="173"/>
        <source>Y</source>
        <translation>Y</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="175"/>
        <source>Vanishing point {n} X</source>
        <translation>灭点 {n} X</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="178"/>
        <source>Vanishing point {n} Y</source>
        <translation>灭点 {n} Y</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="182"/>
        <source>OK</source>
        <translation>确定</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="185"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
</context>
<context>
    <name>Version_History_Browser</name>
    <message>
        <location filename="../ui/version_history_browser.py" line="169"/>
        <source>Select a version to restore.</source>
        <extracomment>Column order of the version tree (presentation-only layout, not a domain value). QSS role-selector property (never a hard-coded colour): the status label carries the computed :class:`SyncState` as a dynamic property so BOTH themes can style it by role (``QLabel[syncState=&quot;diverged&quot;]`` etc.) — see D-13.</extracomment>
        <translation>请选择要还原的版本</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/version_history_browser.py" line="174"/>
        <source>Version %1 — %n bytes (created marker %3).</source>
        <translation>
            <numerusform>版本 %1，%n 字节(创建标记 %3)</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="185"/>
        <source>Up to date with the cloud.</source>
        <translation>已与云端同步</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="187"/>
        <source>Local changes have not been saved to the cloud yet.</source>
        <translation>本地更改尚未保存到云端</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="189"/>
        <source>A newer version exists in the cloud.</source>
        <translation>云端存在较新的版本</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="190"/>
        <source>Local and cloud history have diverged.</source>
        <translation>本地与云端的历史记录已出现分歧</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="195"/>
        <source>Cloud Version History</source>
        <translation>云端版本历史记录</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="198"/>
        <source>Prior cloud saves, oldest first. Restoring opens the chosen version in a new tab — your current work is not overwritten.</source>
        <translation>以往的云端保存记录，最早的在前。还原时会在新标签页中打开所选版本，当前工作不会被覆盖。</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="203"/>
        <source>Cloud sync status</source>
        <translation>云端同步状态</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="206"/>
        <source>Version</source>
        <translation>版本</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="207"/>
        <source>Marker</source>
        <translation>标记</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="208"/>
        <source>Size (bytes)</source>
        <translation>大小(字节)</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="209"/>
        <source>Pinned</source>
        <translation>已固定</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="210"/>
        <source>Parent</source>
        <translation>父版本</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="213"/>
        <source>Yes</source>
        <translation>是</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="214"/>
        <source>No</source>
        <translation>否</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="222"/>
        <source>Restore</source>
        <translation>还原</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="223"/>
        <source>Cloud version list</source>
        <translation>云端版本列表</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="224"/>
        <source>Restore selected version</source>
        <translation>还原所选版本</translation>
    </message>
</context>
<context>
    <name>_Node_Row</name>
    <message>
        <location filename="../ui/layer_panel.py" line="180"/>
        <source>Ref</source>
        <extracomment>A node address in the frame tree — the logic index path used by the document layer ops (top-level index, then indices descending through nested groups). A fully-shown mask (opaque alpha everywhere ⇒ no modulation, LOGIC-012).</extracomment>
        <translation>参考</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="182"/>
        <source>Mask</source>
        <translation>蒙版</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="184"/>
        <source>Smart</source>
        <translation>智能</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="196"/>
        <source>Toggle Visibility</source>
        <translation>切换可见性</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="205"/>
        <source>Toggle Lock</source>
        <translation>切换锁定</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="217"/>
        <source>Set Blend Mode</source>
        <translation>设置混合模式</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="251"/>
        <source>Set Opacity</source>
        <translation>设置不透明度</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="257"/>
        <source>V</source>
        <translation>显</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="258"/>
        <source>Toggle layer visibility</source>
        <translation>切换图层可见性</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="259"/>
        <source>Visibility</source>
        <translation>可见性</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="260"/>
        <source>L</source>
        <translation>锁</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="261"/>
        <source>Lock layer against painting</source>
        <translation>锁定图层以防绘制</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="262"/>
        <source>Lock</source>
        <translation>锁定</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="263"/>
        <source>Layer name</source>
        <translation>图层名称</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="264"/>
        <source>Layer flags</source>
        <translation>图层标志</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="265"/>
        <source>Layer opacity</source>
        <translation>图层不透明度</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="266"/>
        <source>Opacity</source>
        <translation>不透明度</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="267"/>
        <location filename="../ui/layer_panel.py" line="268"/>
        <source>Blend mode</source>
        <translation>混合模式</translation>
    </message>
</context>
<context>
    <name>_Project_Prefs_Menu</name>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="72"/>
        <source>Ask me every time</source>
        <extracomment>A domain wider than this renders as a nested exclusive submenu rather than a single checkable action (plan §3.4) — a plain boolean-shaped preference (ask / suppressed) keeps the shipped single-checkbox rendering. Menu-rendering strings share one translation context with the class below so :func:`value_label_for` — a free function, exported for a future renderer (phase-6&apos;s settings dialog) — is caught by the same ``tr()`` extraction pass as the class&apos;s own strings.</extracomment>
        <translation>每次都询问</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="75"/>
        <source>Always pick up the library change</source>
        <translation>始终采用素材库中的更改</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="78"/>
        <source>Always keep the referenced version</source>
        <translation>始终保留已引用的版本</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="84"/>
        <source>Set to: %1</source>
        <translation>设为: %1</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="219"/>
        <source>Confirm before overwriting a cel</source>
        <extracomment>The provider the caller supplies: returns the active document, or ``None`` when no document is open.</extracomment>
        <translation>覆盖画格前确认</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="221"/>
        <source>When a referenced library asset changes</source>
        <translation>当引用的素材库素材更改时</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="227"/>
        <source>Confirm: %1</source>
        <translation>确认: %1</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="230"/>
        <location filename="../ui/project_prefs_actions.py" line="231"/>
        <source>Project confirmations</source>
        <translation>项目确认</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="236"/>
        <source>Restore this confirmation so it asks again</source>
        <translation>恢复此确认，使其再次询问</translation>
    </message>
</context>
<context>
    <name>_Tile_Pixel_Editor</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="113"/>
        <location filename="../ui/tileset_editor_panel.py" line="157"/>
        <source>Tile pixel editor</source>
        <extracomment>Thumbnail edge (px) for a tile swatch in the grid list (presentation-only, not a domain tuning value — cf. Palette_Panel&apos;s swatch size). On-screen pixel size of one tile pixel in the tile editor dialog.</extracomment>
        <translation>瓦片像素编辑器</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="115"/>
        <location filename="../ui/tileset_editor_panel.py" line="159"/>
        <source>Left-click to paint, right-click to erase</source>
        <translation>左键单击绘制，右键单击擦除</translation>
    </message>
</context>
<context>
    <name>_Track_Table_Model</name>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="239"/>
        <source>Frame %1</source>
        <extracomment>Longest edge (px) of a cached per-cell thumbnail. Mirrors ``timeline_panel._THUMBNAIL_EDGE`` exactly (visual consistency between the two cell surfaces the toggle swaps between); a presentation-only sizing literal, not a domain tuning value (Article II does not reach it, like its strip twin). Custom data roles carried on every cell, alongside the standard Qt roles.</extracomment>
        <translation>第 %1 帧</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="256"/>
        <source>%1, %2</source>
        <translation>%1，%2</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="261"/>
        <source>%1, %2 — empty</source>
        <translation>%1，%2，空</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="268"/>
        <source>%1, track %2</source>
        <translation>%1，轨道 %2</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="273"/>
        <source>%1, track %2, empty</source>
        <translation>%1，轨道 %2，空</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="278"/>
        <source>Occupied cell</source>
        <translation>有内容的单元格</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="278"/>
        <source>Empty cell</source>
        <translation>空单元格</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="326"/>
        <source>%1
%2 ms</source>
        <translation>%1
%2 ms</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/timeline_grid_view.py" line="331"/>
        <source>Frame %1, %n milliseconds</source>
        <translation>
            <numerusform>第 %1 帧，%n 毫秒</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="341"/>
        <source>Track %1</source>
        <translation>轨道 %1</translation>
    </message>
</context>
<context>
    <name>_WheelPad</name>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="309"/>
        <source>Colour wheel</source>
        <extracomment>Hue at the top of the circle, in degrees (achromatic fallback keeps this hue). Number of conical-gradient stops sweeping the hue circle (six primaries + wrap). Edge of a harmony/preview swatch button, px (presentation-only sizing). Minimum wheel diameter, px (presentation-only sizing). Marker radius drawn at the current hue/saturation, px. Keyboard nudge steps for the wheel (hue degrees / saturation fraction). Single left click — paint this swatch&apos;s colour, leave the wheel alone. Double left click / Space / Return — adopt this swatch&apos;s colour into the wheel, paint nothing. Emitted with ``(hue_degrees, saturation)`` when the user picks on the wheel.</extracomment>
        <translation>色轮</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="312"/>
        <source>Hue and saturation wheel; use the arrow keys or the numeric fields to pick a colour without a mouse</source>
        <translation>色相和饱和度色轮；无需鼠标，可使用方向键或数值字段来选取颜色</translation>
    </message>
</context>
<context>
    <name>export</name>
    <message>
        <location filename="../ui/export_actions.py" line="98"/>
        <location filename="../ui/export_actions.py" line="109"/>
        <source>Export</source>
        <extracomment>The source document that was submitted for export (never the exported file&apos;s own bytes — REQ-P11-UI-014). The export settings as used for this run (JSON-scalar values only — bounded by ``logic.constants.MAX_METADATA_BYTES`` at ingress).</extracomment>
        <translation>导出</translation>
    </message>
    <message>
        <location filename="../ui/export_actions.py" line="99"/>
        <source>Open a document before exporting.</source>
        <translation>导出前请先打开文档</translation>
    </message>
    <message>
        <location filename="../ui/export_actions.py" line="110"/>
        <source>Choose a destination path before exporting.</source>
        <translation>导出前请先选择目标路径</translation>
    </message>
</context>
<context>
    <name>theme</name>
    <message>
        <location filename="../ui/theme.py" line="161"/>
        <source>unknown style: %1</source>
        <extracomment>%1 is the internal style name that could not be found.</extracomment>
        <translation>未知样式: %1</translation>
    </message>
    <message>
        <location filename="../ui/theme.py" line="166"/>
        <source>unknown theme: %1</source>
        <translation>未知主题: %1</translation>
    </message>
</context>
<context>
    <name>tilemap_io</name>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="39"/>
        <source>Export Tiled Map</source>
        <extracomment>Tiled JSON file filter (format identifier, not a translated string).</extracomment>
        <translation>导出 Tiled 地图</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="50"/>
        <source>Export failed</source>
        <translation>导出失败</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="52"/>
        <source>Could not export the map: %1</source>
        <translation>无法导出地图: %1</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="74"/>
        <source>Import Tiled Map</source>
        <translation>导入 Tiled 地图</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="85"/>
        <source>Import failed</source>
        <translation>导入失败</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="87"/>
        <source>Could not import the map: %1</source>
        <translation>无法导入地图: %1</translation>
    </message>
</context>
<context>
    <name>tool_icons</name>
    <message>
        <location filename="../ui/tool_icons.py" line="129"/>
        <source>unknown tool glyph id: %1</source>
        <extracomment>The importable package the glyph bundle is shipped inside (package data), matching ``data/guide_content.py``&apos;s ``BUNDLE_PACKAGE`` convention. Package-data subdirectory holding the eleven glyphs, relative to :data:`_ICON_PACKAGE` (``pixelart_creator/icons/tools/``). SVG file extension for a glyph resource. Square render size, in device-independent pixels, for the rasterised glyph and its tinted pixmap. One named constant, referenced everywhere a size is needed in this module (S12) — this module owns no other size. The theme role whose colour tints every glyph (`ui/theme.py`&apos;s role palette; `text` exists in both themes, QT-D1). The eleven shipped `tool_id`s, one per authored glyph stem (`pixelart_creator/icons/tools/&lt;id&gt;.svg`) — the exact `tool_id` class attributes carried by `ui/tools/*.py` (pencil, eraser, fill, line, picker, rectangle, ellipse, select_rect, select_lasso, select_wand, dither). Kept as a literal tuple here (not imported from each tool class) so this module has no dependency on the tool-strategy classes themselves — only on the glyph *ids* they happen to share.</extracomment>
        <translation>未知工具图标 ID: %1</translation>
    </message>
    <message>
        <location filename="../ui/tool_icons.py" line="136"/>
        <source>missing tool glyph asset for: %1</source>
        <translation>缺少该工具的图标资源: %1</translation>
    </message>
    <message>
        <location filename="../ui/tool_icons.py" line="153"/>
        <source>unknown theme: %1</source>
        <translation>未知主题: %1</translation>
    </message>
</context>
<context>
    <name>tools</name>
    <message>
        <location filename="../ui/tools/dither_tool.py" line="65"/>
        <source>Dither</source>
        <extracomment>The two dither modes accepted by ``logic.dither.make_dither_command``.</extracomment>
        <translation>抖动</translation>
    </message>
    <message>
        <location filename="../ui/tools/ellipse_tool.py" line="29"/>
        <source>Ellipse</source>
        <translation>椭圆</translation>
    </message>
    <message>
        <location filename="../ui/tools/eraser.py" line="25"/>
        <source>Eraser</source>
        <extracomment>Indexed buffers erase to palette index 0 (the buffer&apos;s own default value).</extracomment>
        <translation>橡皮擦</translation>
    </message>
    <message>
        <location filename="../ui/tools/fill.py" line="23"/>
        <source>Fill</source>
        <translation>填充</translation>
    </message>
    <message>
        <location filename="../ui/tools/lasso_tool.py" line="30"/>
        <source>Lasso Select</source>
        <translation>套索选择</translation>
    </message>
    <message>
        <location filename="../ui/tools/line.py" line="29"/>
        <source>Line</source>
        <translation>直线</translation>
    </message>
    <message>
        <location filename="../ui/tools/magic_wand_tool.py" line="36"/>
        <source>Magic Wand</source>
        <extracomment>A wand click always (re)selects; it never starts a floating move. Colour tolerance; default exact match (CL-1). Set by the shell control.</extracomment>
        <translation>魔棒</translation>
    </message>
    <message>
        <location filename="../ui/tools/pencil.py" line="49"/>
        <source>Pencil</source>
        <translation>铅笔</translation>
    </message>
    <message>
        <location filename="../ui/tools/rect_select_tool.py" line="23"/>
        <source>Rectangle Select</source>
        <translation>矩形选框</translation>
    </message>
    <message>
        <location filename="../ui/tools/rectangle_tool.py" line="29"/>
        <source>Rectangle</source>
        <translation>矩形</translation>
    </message>
</context>
<context>
    <name>widget</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="62"/>
        <source>Loop</source>
        <translation>循环</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="63"/>
        <source>Once</source>
        <translation>单次</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="64"/>
        <source>Ping-Pong</source>
        <translation>往返</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="65"/>
        <source>Reverse</source>
        <translation>反向</translation>
    </message>
</context>
</TS>
