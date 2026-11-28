<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="ko" sourcelanguage="en">
<context>
    <name>About_Dialog</name>
    <message>
        <location filename="../ui/about_dialog.py" line="280"/>
        <source>About PixelArt Creator</source>
        <extracomment>The dialog&apos;s fixed links, in the order shown (REQ-AV-UI-005).</extracomment>
        <translation>PixelArt Creator 정보</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="281"/>
        <source>About PixelArt Creator dialog</source>
        <translation>PixelArt Creator 정보 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="283"/>
        <source>PixelArt Creator icon</source>
        <translation>PixelArt Creator 아이콘</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="284"/>
        <source>Application name</source>
        <translation>애플리케이션 이름</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="285"/>
        <source>Version:</source>
        <translation>버전:</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="286"/>
        <source>Application version</source>
        <translation>애플리케이션 버전</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="287"/>
        <source>Licence:</source>
        <translation>라이선스:</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="288"/>
        <source>Licence name</source>
        <translation>라이선스 이름</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="289"/>
        <source>Environment:</source>
        <translation>환경:</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="290"/>
        <source>Environment summary</source>
        <translation>환경 요약</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="294"/>
        <source>Repository</source>
        <translation>저장소</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="295"/>
        <source>Documentation</source>
        <translation>설명서</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="296"/>
        <source>Releases</source>
        <translation>릴리스</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="307"/>
        <source>&amp;Copy</source>
        <translation>복사</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="308"/>
        <source>Copy environment summary</source>
        <translation>환경 요약 복사</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="309"/>
        <source>C&amp;lose</source>
        <translation>닫기</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="310"/>
        <source>Close the About dialog</source>
        <translation>정보 대화 상자 닫기</translation>
    </message>
    <message>
        <location filename="../ui/about_dialog.py" line="314"/>
        <source>unknown</source>
        <translation>알 수 없음</translation>
    </message>
</context>
<context>
    <name>Asset_Library_Panel</name>
    <message>
        <location filename="../ui/asset_library_panel.py" line="162"/>
        <source>Broken reference</source>
        <extracomment>Emitted with the selected entry&apos;s ``asset_id`` (``&quot;&quot;`` when cleared). The active filter driven by the search panel (empty = full catalog).</extracomment>
        <translation>끊어진 참조</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="186"/>
        <source>Sprite</source>
        <translation>스프라이트</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="187"/>
        <source>Animation</source>
        <translation>애니메이션</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="188"/>
        <source>Tileset</source>
        <translation>타일셋</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="189"/>
        <source>Tilemap</source>
        <translation>타일맵</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="190"/>
        <source>Palette</source>
        <translation>팔레트</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="195"/>
        <source>Asset library</source>
        <translation>에셋 라이브러리</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Name</source>
        <translation>이름</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Kind</source>
        <translation>종류</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Tags</source>
        <translation>태그</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="197"/>
        <source>Status</source>
        <translation>상태</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_panel.py" line="199"/>
        <source>Catalog assets</source>
        <translation>카탈로그 에셋</translation>
    </message>
</context>
<context>
    <name>Asset_Library_Session</name>
    <message>
        <location filename="../ui/asset_library_actions.py" line="507"/>
        <source>Import asset artifact</source>
        <extracomment>Emitted after any change to the catalog (add / remove / tag do-undo) so the bound panels re-read and repaint. No payload — panels pull the fresh catalog. Emitted after the dependency graph is replaced so the dependency-graph view and the passive break surface re-read and repaint. No payload. Emitted after a registration action commits — carries the :class:`RegistrationOutcome` (REQ-P11-UI-017). Emitted when a registration action cannot commit — carries a translatable message; the catalog, store and revision history are all left unchanged (REQ-P11-UI-017). Emitted when the user cancels the registration prompt — cancelling is not a failure (REQ-P11-UI-017; RP-4). Emitted after a successful registration&apos;s derived dependency edges are computed (ruling P11-R6, REQ-P11-LOGIC-010 / REQ-P11-UI-018) — carries the **accumulated** edge set (this session&apos;s current graph edges plus the newly derived ones), because the bound consumer (:meth:`~pixelart_creator.ui.dependency_graph_view.Dependency_Graph_View. show_edges`) *replaces* the graph it is handed rather than merging into it. This session never calls :meth:`set_graph` itself and never imports the view — ``show_edges`` alone decides whether the accumulated set is accepted (and, on a closed cycle, rejected passively, the prior graph kept) — see ``main_window.py``&apos;s connection of this signal. Emitted after a single library artifact (``.pixasset``) is imported and merged + committed into the already-open library (ruling P11-R5, REQ-P11-UI-015/-016) — carries the imported ``Tuple[AssetDescriptor, ...]``. Emitted when a library-artifact import cannot commit — a translatable message; the catalog and store are unchanged. Emitted when the user cancels the &quot;Import asset artifact&quot; file dialog. Emitted after a chosen catalog subset is written to a library artifact file (REQ-P11-UI-016) — carries the destination path as ``str``. Emitted when a library-subset export cannot complete — a translatable message; no file is written. Emitted when the user cancels the &quot;Export asset artifact&quot; file dialog. Emitted after a project + its whole reference set is written to a ``.pixbundle`` file (the shipped :func:`~pixelart_creator.data.asset_export.export_project_bundle`, unchanged) — carries the destination path as ``str``. Emitted when a project-bundle export cannot complete — a translatable message; no file is written. Emitted when the user cancels the &quot;Export project bundle&quot; file dialog. Emitted after a ``.pixbundle`` is reconstructed into a new project directory (the shipped :func:`~pixelart_creator.data.asset_export.import_project_bundle`, unchanged) — carries the ``(Document, AssetCatalog)`` tuple. This session&apos;s own catalog is untouched: the bundle reconstructs a **new** project, never merging into the open library (plan Section 3.7). Emitted when a project-bundle import cannot complete — a translatable message; ``target_dir`` is left exactly as it was (the shipped function&apos;s own atomic-move guarantee). Emitted when the user cancels the &quot;Import project bundle&quot; file dialog. The shared undo stack the tag commands push onto (REQ-P11-UI-002). The durable catalog root once bound (REQ-P11-DATA-008); ``None`` until :meth:`bind_root` is called, so an unbound session stays purely in-memory. The content-addressable store the registration actions write blobs through, once bound; ``None`` until :meth:`bind_content_store`. The revision store the registration actions record through, once bound; ``None`` until :meth:`bind_revision_store`.</extracomment>
        <translation>에셋 파일 가져오기</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="508"/>
        <location filename="../ui/asset_library_actions.py" line="571"/>
        <source>Asset artifact (*%1)</source>
        <translation>에셋 파일 (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="519"/>
        <source>&quot;%1&quot; is a project bundle, not a single asset. Use &quot;Import project bundle…&quot; instead.</source>
        <translation>프로젝트 번들이며 단일 에셋이 아닙니다: &quot;%1&quot;. 대신 &quot;프로젝트 번들 가져오기…&quot; 항목을 사용하세요.</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="524"/>
        <location filename="../ui/asset_library_actions.py" line="728"/>
        <source>Import asset</source>
        <translation>에셋 가져오기</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="570"/>
        <source>Export asset artifact</source>
        <translation>에셋 파일 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="625"/>
        <location filename="../ui/asset_library_actions.py" line="752"/>
        <source>Export project bundle</source>
        <translation>프로젝트 번들 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="626"/>
        <location filename="../ui/asset_library_actions.py" line="677"/>
        <source>Project bundle (*%1)</source>
        <translation>프로젝트 번들 (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="676"/>
        <location filename="../ui/asset_library_actions.py" line="765"/>
        <source>Import project bundle</source>
        <translation>프로젝트 번들 가져오기</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="722"/>
        <source>Could not import the asset: %1</source>
        <translation>에셋을 가져올 수 없습니다: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="733"/>
        <source>Could not export the asset: %1</source>
        <translation>에셋을 내보낼 수 없습니다: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="739"/>
        <source>Export asset</source>
        <translation>에셋 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="746"/>
        <source>Could not export the project bundle: %1</source>
        <translation>프로젝트 번들을 내보낼 수 없습니다: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="759"/>
        <source>Could not import the project bundle: %1</source>
        <translation>프로젝트 번들을 가져올 수 없습니다: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="830"/>
        <source>There is no active selection to register.</source>
        <translation>등록할 활성 선택 영역이 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="1151"/>
        <source>Could not register the asset: %1</source>
        <translation>에셋을 등록할 수 없습니다: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_library_actions.py" line="1157"/>
        <source>Asset registration</source>
        <translation>에셋 등록</translation>
    </message>
</context>
<context>
    <name>Asset_Register_Dialog</name>
    <message numerus="yes">
        <location filename="../ui/asset_register_dialog.py" line="165"/>
        <source>Too many tags: %n given, %2 allowed.</source>
        <extracomment>Combo order = the five shipped kinds, in the vocabulary&apos;s own declaration order (``logic/asset_catalog.AssetKind`` — RP-1&apos;s &quot;five shipped kinds&quot;).</extracomment>
        <translation>
            <numerusform>태그가 너무 많습니다. %n개가 지정되었으며 최대 %2개까지 허용됩니다.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_register_dialog.py" line="170"/>
        <source>Tag &quot;%1&quot; is too long (%n bytes allowed).</source>
        <translation>
            <numerusform>태그 &quot;%1&quot;의 길이가 너무 깁니다. 최대 %n바이트까지 허용됩니다.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="178"/>
        <source>Enter a name for this asset.</source>
        <translation>이 에셋의 이름을 입력하세요.</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="190"/>
        <source>Register Asset</source>
        <translation>에셋 등록</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="191"/>
        <source>Asset registration prompt</source>
        <translation>에셋 등록 안내</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="193"/>
        <source>Name</source>
        <translation>이름</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="194"/>
        <source>Asset display name</source>
        <translation>에셋 표시 이름</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="195"/>
        <source>Display name</source>
        <translation>표시 이름</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="197"/>
        <source>Kind</source>
        <translation>종류</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="198"/>
        <source>Asset kind</source>
        <translation>에셋 종류</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="199"/>
        <source>Sprite</source>
        <translation>스프라이트</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="200"/>
        <source>Animation</source>
        <translation>애니메이션</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="201"/>
        <source>Tileset</source>
        <translation>타일셋</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="202"/>
        <source>Tilemap</source>
        <translation>타일맵</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="203"/>
        <source>Palette</source>
        <translation>팔레트</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="205"/>
        <source>Tags</source>
        <translation>태그</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="206"/>
        <source>Asset tags, comma-separated</source>
        <translation>에셋 태그, 쉼표로 구분</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="207"/>
        <source>Optional tags, comma-separated</source>
        <translation>태그(선택 사항), 쉼표로 구분</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="209"/>
        <source>Registration validation message</source>
        <translation>등록 검증 메시지</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="213"/>
        <source>Register</source>
        <translation>등록</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="214"/>
        <source>Register asset</source>
        <translation>에셋 등록</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="217"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
    <message>
        <location filename="../ui/asset_register_dialog.py" line="218"/>
        <source>Cancel registration</source>
        <translation>등록 취소</translation>
    </message>
</context>
<context>
    <name>Asset_Reuse_Panel</name>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="254"/>
        <source>The selected asset is not available.</source>
        <extracomment>Columns of the in-project reference list (REQ-P11-UI-021 indicators). The selected asset row&apos;s ``asset_id`` is stashed on the name column (both trees). Column of the in-project reference list that shows the resolve state. Emitted with ``(asset_id, project)`` after a successful reference. Each open project&apos;s real, durable reference set (REQ-P11-UI-021), bound through :meth:`set_project_reference_set` or created empty by :meth:`add_project`. Never a predicate&apos;s own scratch state. In-project reference list — the resolve-state / shared-state indicators (REQ-P11-UI-021), over the *current* project&apos;s real reference set.</extracomment>
        <translation>선택한 에셋을 사용할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="261"/>
        <source>Shared content for %1 is not available.</source>
        <translation>%1의 공유 콘텐츠를 사용할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="276"/>
        <source>%1 is already referenced in %2.</source>
        <translation>%2에 %1 참조가 이미 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="282"/>
        <source>Referenced %1 into %2.</source>
        <translation>%2에 %1 참조를 추가했습니다.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="345"/>
        <location filename="../ui/asset_reuse_panel.py" line="408"/>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <location filename="../ui/asset_reuse_panel.py" line="484"/>
        <source>Shared</source>
        <translation>공유됨</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="357"/>
        <location filename="../ui/asset_reuse_panel.py" line="425"/>
        <source>Referenced by another open project</source>
        <translation>다른 열린 프로젝트에서 참조 중</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="404"/>
        <source>In library</source>
        <translation>라이브러리에 있음</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="406"/>
        <source>Not found in library</source>
        <translation>라이브러리에 없음</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="421"/>
        <source>This reference could not be found in the local library.</source>
        <translation>이 참조를 로컬 라이브러리에서 찾을 수 없습니다.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_reuse_panel.py" line="431"/>
        <source>%n unresolved reference(s) in this project.</source>
        <translation>
            <numerusform>이 프로젝트에 확인되지 않은 참조가 %n개 있습니다.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="436"/>
        <source>All references resolve in the local library.</source>
        <translation>모든 참조가 로컬 라이브러리에서 확인되었습니다.</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="452"/>
        <source>Sprite</source>
        <translation>스프라이트</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="453"/>
        <source>Animation</source>
        <translation>애니메이션</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="454"/>
        <source>Tileset</source>
        <translation>타일셋</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="455"/>
        <source>Tilemap</source>
        <translation>타일맵</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="456"/>
        <source>Palette</source>
        <translation>팔레트</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="462"/>
        <source>Cross-project reuse</source>
        <translation>프로젝트 간 재사용</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="463"/>
        <source>Project:</source>
        <translation>프로젝트:</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="464"/>
        <source>Target project</source>
        <translation>대상 프로젝트</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="465"/>
        <location filename="../ui/asset_reuse_panel.py" line="466"/>
        <source>New project name</source>
        <translation>새 프로젝트 이름</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="467"/>
        <source>Add Project</source>
        <translation>프로젝트 추가</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="468"/>
        <source>Add a project</source>
        <translation>프로젝트 추가</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <location filename="../ui/asset_reuse_panel.py" line="481"/>
        <source>Name</source>
        <translation>이름</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <location filename="../ui/asset_reuse_panel.py" line="482"/>
        <source>Kind</source>
        <translation>종류</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="470"/>
        <source>Projects</source>
        <translation>프로젝트</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="472"/>
        <source>Shared assets</source>
        <translation>공유 에셋</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="473"/>
        <source>Reference into Project</source>
        <translation>프로젝트에 참조 추가</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="475"/>
        <source>Reference the selected asset into the project</source>
        <translation>선택한 에셋을 프로젝트에 참조로 추가</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="477"/>
        <source>Reuse status</source>
        <translation>재사용 상태</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="478"/>
        <source>References in this project:</source>
        <translation>이 프로젝트의 참조:</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="483"/>
        <source>Resolve state</source>
        <translation>확인 상태</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="488"/>
        <source>References in the current project</source>
        <translation>현재 프로젝트의 참조</translation>
    </message>
    <message>
        <location filename="../ui/asset_reuse_panel.py" line="490"/>
        <source>Missing reference count</source>
        <translation>누락된 참조 수</translation>
    </message>
</context>
<context>
    <name>Asset_Search_Panel</name>
    <message>
        <location filename="../ui/asset_search_panel.py" line="133"/>
        <source>Sprite</source>
        <extracomment>The fixed display order of the kind combo (after the &quot;All kinds&quot; entry). Emitted with ``(name, tags, kind)`` whenever a control changes. ``name`` is a possibly-empty str, ``tags`` a list of str, ``kind`` an ``AssetKind`` or ``None``. The library panel consumes it via ``set_query``.</extracomment>
        <translation>스프라이트</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="134"/>
        <source>Animation</source>
        <translation>애니메이션</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="135"/>
        <source>Tileset</source>
        <translation>타일셋</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="136"/>
        <source>Tilemap</source>
        <translation>타일맵</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="137"/>
        <source>Palette</source>
        <translation>팔레트</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="142"/>
        <source>Asset search and filter</source>
        <translation>에셋 검색 및 필터</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="143"/>
        <source>Name:</source>
        <translation>이름:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="144"/>
        <location filename="../ui/asset_search_panel.py" line="145"/>
        <source>Search by name</source>
        <translation>이름으로 검색</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="146"/>
        <source>Tags:</source>
        <translation>태그:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="147"/>
        <source>Filter by tags (comma-separated)</source>
        <translation>태그로 필터링 (쉼표로 구분)</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="148"/>
        <source>Filter by tags</source>
        <translation>태그로 필터링</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="149"/>
        <source>Kind:</source>
        <translation>종류:</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="150"/>
        <source>Filter by kind</source>
        <translation>종류로 필터링</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="151"/>
        <source>All kinds</source>
        <translation>모든 종류</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="154"/>
        <source>Clear</source>
        <translation>지우기</translation>
    </message>
    <message>
        <location filename="../ui/asset_search_panel.py" line="155"/>
        <source>Clear the search and filters</source>
        <translation>검색 및 필터 지우기</translation>
    </message>
</context>
<context>
    <name>Asset_Tagging_Panel</name>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="124"/>
        <location filename="../ui/asset_tagging_panel.py" line="154"/>
        <source>Tagging</source>
        <extracomment>The asset whose tags are being edited (``&quot;&quot;`` when none is selected).</extracomment>
        <translation>태그 지정</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="133"/>
        <source>Add tag &quot;%1&quot;</source>
        <translation>태그 &quot;%1&quot; 추가</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="163"/>
        <source>Remove tag &quot;%1&quot;</source>
        <translation>태그 &quot;%1&quot; 제거</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="198"/>
        <source>No asset selected</source>
        <translation>선택한 에셋 없음</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="201"/>
        <source>Tags for: %1</source>
        <translation>다음 에셋의 태그: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="205"/>
        <source>Asset tagging</source>
        <translation>에셋 태그 지정</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="206"/>
        <source>Asset tags</source>
        <translation>에셋 태그</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="207"/>
        <location filename="../ui/asset_tagging_panel.py" line="208"/>
        <source>New tag</source>
        <translation>새 태그</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="209"/>
        <source>Add Tag</source>
        <translation>태그 추가</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="210"/>
        <source>Add tag to asset</source>
        <translation>에셋에 태그 추가</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="211"/>
        <source>Remove Tag</source>
        <translation>태그 제거</translation>
    </message>
    <message>
        <location filename="../ui/asset_tagging_panel.py" line="212"/>
        <source>Remove selected tag</source>
        <translation>선택한 태그 제거</translation>
    </message>
</context>
<context>
    <name>Asset_Update_Prompt_Dialog</name>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="491"/>
        <source>Library Asset Updated</source>
        <extracomment>This dialog&apos;s own outcome vocabulary — distinct from the *persisted* three-value preference domain (``&quot;ask&quot;`` / ``&quot;always_pick_up&quot;`` / ``&quot;always_keep_referenced&quot;``, declared in ``logic/asset_references.ASSET_LIBRARY_EDIT``): an outcome is what THIS prompt resolved to for ONE edit; the preference is what to do about FUTURE edits without asking. **Promoted aliases (ADR-0062, ruling P11-R13 — same &quot;one definition of a control, aliases kept so no call site moves&quot; move ruling P11-R11 made for ``data/asset_catalog_io.py``&apos;s ``_safe_asset_id`` / ``_resolve_within``, applied here in the other direction):** the canonical outcome domain now lives in the logic layer, :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_PICK_UP` / :data:`~pixelart_creator.logic.asset_edit_decisions.DECISION_KEEP`, at byte-identical values — these two names are retained, unchanged, as aliases so every existing reference in this module and its callers still resolves without moving. The two non-default members of ``ASSET_LIBRARY_EDIT.domain`` this prompt writes through :func:`~pixelart_creator.logic.project_prefs.with_value` (the registered seam validates membership; nothing here re-derives the domain). One session-memory entry key: ``(asset_id, edit_token)``. ``edit_token`` is ``None`` when the caller has no content-hash identity to hand yet (see :meth:`Asset_Update_Prompt_Dialog.decide`) — two ``None``-token calls with the same ``asset_id`` are therefore treated as the SAME edit, which is the exact, disclosed limit of this session memory absent a real per-edit identity (module docstring boundary note). Emitted once a button is clicked, before the dialog closes: ``(outcome, dont_ask_again)``. For a caller driving the dialog non-modally (``open()``); :meth:`decide` does not need it. **Per-edit session memory** (extended by plan §3.11 (2b)): &quot;the same edit does not ask again&quot; for :meth:`decide` (``REQ-P11-UI-022``&apos;s own acceptance clause), scoped to one project&apos;s session bucket so a different project (:data:`ProjectPrefs`, ``SC-P11-UI-023-3``) is never affected by another project&apos;s session memory. Keyed by ``id(prefs)`` -&gt; ``(prefs, {edit_key: outcome})`` when no ``project_key`` is supplied (today&apos;s byte-for-byte behaviour — the snapshot itself is held strongly alongside its id so a *live* entry&apos;s id can never be reused by an unrelated, later ``ProjectPrefs`` object, an ``is`` check on lookup is the defensive second line); keyed by the caller-supplied ``project_key`` (a ``str``) instead when one is given — the production route (``ui/main_window.py``, plan §3.11 (2b)), because ``document.prefs`` is *replaced* on any confirmation-preference toggle (``ui/project_prefs_actions.py:165/175``), which would silently orphan an ``id(prefs)``-keyed bucket. This dict itself is still in-memory, per-process runtime state — it is never itself written to disk, and it is never written through ``logic/project_prefs.py`` (that seam is reserved for the &quot;Don&apos;t ask again&quot; preference, ``REQ-P11-UI-023``, a materially different, explicit, durable choice). **Corrected (ADR-0062, ruling P11-R13):** this bucket is no longer the *only* record of an unticked decision — it can be **hydrated** at the start of a session from the durable, per-edit ledger (:class:`~pixelart_creator.logic.asset_edit_decisions.AssetEditDecisions`) via :meth:`prime_session`, and every fresh decision made through :meth:`decide` is handed to that method&apos;s optional ``on_decided`` callback so the caller can persist it (the write-ahead journal / the project-file save) — this module performs no I/O of its own; it only calls out. Disclosed cost, unchanged: a decided ``ProjectPrefs`` snapshot (or a live ``project_key`` bucket) is retained for the life of the process; call :meth:`forget_session` when a project closes to release it.</extracomment>
        <translation>라이브러리 에셋 업데이트됨</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="492"/>
        <source>Library asset updated confirmation</source>
        <translation>라이브러리 에셋 업데이트 확인</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="493"/>
        <source>this asset</source>
        <translation>이 에셋</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="496"/>
        <source>The library asset &quot;%1&quot; has changed since your project last referenced it. Pick up the change, or keep the version your project already references?</source>
        <translation>라이브러리 에셋 &quot;%1&quot;의 내용이 프로젝트에서 마지막으로 참조한 이후 변경되었습니다. 변경 내용을 반영하시겠습니까, 아니면 프로젝트가 이미 참조하는 버전을 유지하시겠습니까?</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="501"/>
        <source>Library edit notice</source>
        <translation>라이브러리 편집 알림</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="502"/>
        <source>Don&apos;t ask again</source>
        <translation>다시 묻지 않음</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="504"/>
        <source>Remember this choice for future edits of this asset</source>
        <translation>이 에셋을 이후 편집할 때도 이 선택 기억</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="506"/>
        <source>Pick Up the Change</source>
        <translation>변경 내용 반영</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="508"/>
        <source>Pick up the library asset&apos;s change</source>
        <translation>라이브러리 에셋의 변경 내용 반영</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="510"/>
        <source>Keep the Referenced Version</source>
        <translation>참조된 버전 유지</translation>
    </message>
    <message>
        <location filename="../ui/asset_update_prompt.py" line="512"/>
        <source>Keep the version this project already references</source>
        <translation>이 프로젝트가 이미 참조하는 버전 유지</translation>
    </message>
</context>
<context>
    <name>Asset_Version_Browser</name>
    <message>
        <location filename="../ui/asset_version_browser.py" line="194"/>
        <source>%1 (current)</source>
        <extracomment>The selected row&apos;s revision ``content_hash`` is stashed on the order column. How many leading characters of a content hash the browser shows (the full hash is kept on the tooltip / item data — this is display abbreviation only, not identity). Emitted with the new head&apos;s ``content_hash`` after a successful restore (so a caller / test can react); no payload semantics beyond the reinstated head hash. The asset whose revisions are shown (``&quot;&quot;`` when none is selected).</extracomment>
        <translation>%1 (현재)</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="195"/>
        <location filename="../ui/asset_version_browser.py" line="240"/>
        <source>(unknown)</source>
        <translation>(알 수 없음)</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="234"/>
        <location filename="../ui/asset_version_browser.py" line="260"/>
        <location filename="../ui/asset_version_browser.py" line="276"/>
        <source>Version history</source>
        <translation>버전 내역</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/asset_version_browser.py" line="242"/>
        <source>Revision %1 — %n bytes, marker %3, author %4</source>
        <translation>
            <numerusform>리비전 %1 — %n바이트, 마커 %3, 작성자 %4</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="332"/>
        <location filename="../ui/asset_version_browser.py" line="337"/>
        <source>Revisions of: %1</source>
        <translation>다음 에셋의 리비전: %1</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="340"/>
        <source>No asset selected</source>
        <translation>선택한 에셋 없음</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="344"/>
        <source>Asset version browser</source>
        <translation>에셋 버전 브라우저</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="346"/>
        <source>#</source>
        <translation>#</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="346"/>
        <source>Created</source>
        <translation>생성됨</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="346"/>
        <source>Author</source>
        <translation>작성자</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="346"/>
        <source>Content</source>
        <translation>콘텐츠</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="348"/>
        <source>Asset revisions</source>
        <translation>에셋 리비전</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="349"/>
        <source>Revision details</source>
        <translation>리비전 세부 정보</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="350"/>
        <source>Inspect</source>
        <translation>살펴보기</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="351"/>
        <source>Inspect selected revision</source>
        <translation>선택한 리비전 살펴보기</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="352"/>
        <source>Restore</source>
        <translation>복원</translation>
    </message>
    <message>
        <location filename="../ui/asset_version_browser.py" line="354"/>
        <source>Restore selected revision as a new head</source>
        <translation>선택한 리비전을 새 최신본으로 복원</translation>
    </message>
</context>
<context>
    <name>Assistant_Dock</name>
    <message>
        <location filename="../ui/assistant_dock.py" line="160"/>
        <source>No AI provider is configured. Use Configure… to set an endpoint and API key.</source>
        <extracomment>Provider of the active document (``None`` when no document tab is open). Provider of the current chat backend (a configured ``data/llm`` adapter, or ``None`` when the user has not configured a provider). Probed fresh on each send so a config change takes effect immediately; ``ui/`` never sees a provider/HTTP type. ``(commands, label)`` — the turn&apos;s ordered, unapplied reversible commands and a translatable undo label; the host wraps them in one ``AssistantCommand``. How many transcript messages have already been rendered (render the tail).</extracomment>
        <translation>구성된 AI 제공자가 없습니다. 구성… 버튼으로 엔드포인트와 API 키를 설정하세요.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="168"/>
        <source>Open a document before chatting with the assistant.</source>
        <translation>어시스턴트와 대화하기 전에 문서를 여세요.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="185"/>
        <source>Assistant edit</source>
        <translation>어시스턴트 편집</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="191"/>
        <source>Assistant error: {0}</source>
        <translation>어시스턴트 오류: {0}</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="211"/>
        <source>Confirm assistant action</source>
        <translation>어시스턴트 동작 확인</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="214"/>
        <source>The assistant wants to run &quot;{0}&quot;, which cannot be reliably undone. Allow it?</source>
        <translation>어시스턴트가 &quot;{0}&quot; 작업을 시작하려고 합니다. 이 작업은 제대로 되돌리지 못할 수 있습니다. 허용하시겠습니까?</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="231"/>
        <source>Provider configuration saved.</source>
        <translation>제공자 구성을 저장했습니다.</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="240"/>
        <source>Working…</source>
        <translation>작업 중…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="253"/>
        <source>You</source>
        <translation>나</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="256"/>
        <source>Assistant</source>
        <translation>어시스턴트</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="257"/>
        <source>(taking an action…)</source>
        <translation>(동작을 처리하는 중…)</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="259"/>
        <source>Action</source>
        <translation>동작</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="289"/>
        <source>AI Assistant</source>
        <translation>AI 어시스턴트</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="290"/>
        <source>AI assistant chat</source>
        <translation>AI 어시스턴트 대화</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="291"/>
        <source>Assistant conversation</source>
        <translation>어시스턴트 대화</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="292"/>
        <source>Message to the assistant</source>
        <translation>어시스턴트에게 보낼 메시지</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="293"/>
        <source>Ask the assistant to edit…</source>
        <translation>어시스턴트에게 편집을 요청하세요…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="294"/>
        <source>Send</source>
        <translation>보내기</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="295"/>
        <source>Send message</source>
        <translation>메시지 보내기</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="296"/>
        <source>Configure…</source>
        <translation>구성…</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="297"/>
        <source>Configure AI provider</source>
        <translation>AI 제공자 구성</translation>
    </message>
    <message>
        <location filename="../ui/assistant_dock.py" line="298"/>
        <source>Assistant working indicator</source>
        <translation>어시스턴트 작업 표시기</translation>
    </message>
</context>
<context>
    <name>Batch_Export_Panel</name>
    <message>
        <location filename="../ui/batch_export_panel.py" line="160"/>
        <source>%1 — done</source>
        <extracomment>Optional provider returning the document to export against (the active tab).</extracomment>
        <translation>%1 — 완료</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="167"/>
        <source>%1 — failed: %2</source>
        <translation>%1 — 실패: %2</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="190"/>
        <source>Add Target…</source>
        <translation>대상 추가…</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="191"/>
        <source>Remove</source>
        <translation>제거</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="192"/>
        <source>Export All</source>
        <translation>모두 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="193"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="194"/>
        <source>Batch export</source>
        <translation>일괄 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="195"/>
        <source>Batch export targets</source>
        <translation>일괄 내보내기 대상</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="196"/>
        <source>Batch export progress</source>
        <translation>일괄 내보내기 진행률</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="197"/>
        <source>Add export target</source>
        <translation>내보내기 대상 추가</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="198"/>
        <source>Remove export target</source>
        <translation>내보내기 대상 제거</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="199"/>
        <source>Export all targets</source>
        <translation>모든 대상 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/batch_export_panel.py" line="200"/>
        <source>Cancel batch export</source>
        <translation>일괄 내보내기 취소</translation>
    </message>
</context>
<context>
    <name>Batch_Recolour_Panel</name>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="172"/>
        <source>Running…</source>
        <extracomment>Combo indices for the mapping mode (module-local UI enumeration). Upper bound for the index spin boxes — the widest palette a buffer can address (a display range for the spin control, not a domain tuning value). ``(ops, label)`` — the host should dispatch the ``batch_recolour`` op on the worker as one undoable grouped command (REQ-P8-UI-006/-009). Each pair is ``(src, dst)`` — ints for index mode, RGBA tuples for colour mode. Kept parallel to the visible list.</extracomment>
        <translation>실행 중…</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="174"/>
        <source>Done</source>
        <translation>완료</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="175"/>
        <source>Idle</source>
        <translation>대기 중</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="213"/>
        <source>Pick a colour</source>
        <translation>색상 선택</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="222"/>
        <source>From: %1</source>
        <translation>원본: %1</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="225"/>
        <source>To: %1</source>
        <translation>대상: %1</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="238"/>
        <source>%1 → %2</source>
        <translation>%1 → %2</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="268"/>
        <source>Batch Recolour</source>
        <translation>일괄 색상 변경</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="289"/>
        <source>Mapping:</source>
        <translation>매핑:</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="290"/>
        <source>Index remap</source>
        <translation>인덱스 재매핑</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="291"/>
        <source>Colour remap</source>
        <translation>색상 재매핑</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="292"/>
        <source>Frame:</source>
        <translation>프레임:</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="293"/>
        <source>Add Pair</source>
        <translation>쌍 추가</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="294"/>
        <source>Remove</source>
        <translation>제거</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="295"/>
        <source>Apply Batch Recolour</source>
        <translation>일괄 색상 변경 적용</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="297"/>
        <source>Batch recolour</source>
        <translation>일괄 색상 변경</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="298"/>
        <source>Recolour mapping mode</source>
        <translation>색상 변경 매핑 모드</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="299"/>
        <source>Target frame index</source>
        <translation>대상 프레임 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="300"/>
        <source>Source palette index</source>
        <translation>원본 팔레트 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="301"/>
        <source>Destination palette index</source>
        <translation>대상 팔레트 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="302"/>
        <source>Pick source colour</source>
        <translation>원본 색상 선택</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="303"/>
        <source>Pick destination colour</source>
        <translation>대상 색상 선택</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="304"/>
        <source>Recolour mapping pairs</source>
        <translation>색상 변경 매핑 쌍</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="305"/>
        <source>Add a recolour pair</source>
        <translation>색상 변경 쌍 추가</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="306"/>
        <source>Remove the selected pair</source>
        <translation>선택한 쌍 제거</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="307"/>
        <source>Apply the batch recolour</source>
        <translation>일괄 색상 변경 적용</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="308"/>
        <source>Progress</source>
        <translation>진행률</translation>
    </message>
    <message>
        <location filename="../ui/batch_recolour_panel.py" line="309"/>
        <source>Batch recolour progress</source>
        <translation>일괄 색상 변경 진행률</translation>
    </message>
</context>
<context>
    <name>Branch_Diff_Dialog</name>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="214"/>
        <source>Metadata changes</source>
        <extracomment>The four op-tier groups, fixed display order (``REQ-P10-UI-016``) — matches ``branch_diff._CLASS_RANK``&apos;s declaration order (metadata, layer_attr, layer_order, raster; ``convergence.py:228``). Emitted with ``source_name`` when the user activates *Continue to merge*. This view performs **no** merge itself (``REQ-P10-UI-018``) — the caller runs the unchanged ``Branching_Session.merge_to_mainline`` (the same shipped path the panel&apos;s own Merge button uses, ``REQ-P10-UI-019``).</extracomment>
        <translation>메타데이터 변경</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="215"/>
        <source>Layer attribute changes</source>
        <translation>레이어 속성 변경</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="216"/>
        <source>Layer order changes</source>
        <translation>레이어 순서 변경</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="217"/>
        <source>Raster (pixel) changes</source>
        <translation>래스터(픽셀) 변경</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="229"/>
        <source>Metadata &apos;{key}&apos; set to &apos;{value}&apos;</source>
        <translation>메타데이터 &apos;{key}&apos; 설정값: &apos;{value}&apos;</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="233"/>
        <source>Frame {frame}, layer {layer}: {attr} = {value}</source>
        <translation>프레임 {frame}, 레이어 {layer}: {attr} = {value}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="237"/>
        <source>Frame {frame}: layer order changed</source>
        <translation>프레임 {frame}: 레이어 순서 변경됨</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="242"/>
        <source>Frame {frame}, layer {layer}: tile ({tile_x}, {tile_y})</source>
        <translation>프레임 {frame}, 레이어 {layer}: 타일 ({tile_x}, {tile_y})</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="277"/>
        <source>Frame {frame}, layer {layer}: ({x}, {y}) {width}×{height}</source>
        <translation>프레임 {frame}, 레이어 {layer}: ({x}, {y}) {width}×{height}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="304"/>
        <source>Diff: &apos;{source}&apos; vs &apos;{target}&apos;</source>
        <translation>차이: &apos;{source}&apos; 대 &apos;{target}&apos;</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="308"/>
        <location filename="../ui/branch_diff_dialog.py" line="309"/>
        <source>Branch diff</source>
        <translation>브랜치 차이</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="312"/>
        <source>Comparing branch &apos;{source}&apos; (source) against &apos;{target}&apos; (target). This is a snapshot taken now — the merge has not happened yet.</source>
        <translation>브랜치 &apos;{source}&apos;(원본)을 &apos;{target}&apos;(대상)과 비교합니다. 지금 시점의 스냅샷이며 병합은 아직 이루어지지 않았습니다.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="317"/>
        <source>Diff basis</source>
        <translation>비교 기준</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="322"/>
        <source>Checked: the recorded changes account for everything on this branch.</source>
        <translation>확인됨: 기록된 변경 사항이 이 브랜치의 모든 변경을 설명합니다.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="329"/>
        <source>Warning: some changes on this branch are not recorded and will not be merged. {detail}</source>
        <translation>경고: 이 브랜치의 일부 변경 사항이 기록되지 않았으며 병합되지 않습니다. {detail}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="333"/>
        <source>Supervision result</source>
        <translation>검증 결과</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="336"/>
        <source>States whether the recorded operation log explains every change on this branch&apos;s live document.</source>
        <translation>기록된 작업 로그가 이 브랜치의 라이브 문서에서 발생한 모든 변경을 설명하는지 여부를 나타냅니다.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="343"/>
        <source>This branch has no changes to merge.</source>
        <translation>이 브랜치에는 병합할 변경 사항이 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="355"/>
        <source>No changes.</source>
        <translation>변경 사항이 없습니다.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="357"/>
        <source>%n change(s).</source>
        <translation>
            <numerusform>변경 사항 %n건.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="359"/>
        <source>{title} list</source>
        <translation>{title} 목록</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="361"/>
        <source>%n entries.</source>
        <translation>
            <numerusform>항목 %n개.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="363"/>
        <source>Affected regions</source>
        <translation>영향받는 영역</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="366"/>
        <source>Each region is reported at the whole {tile}×{tile} pixel tile granularity — a one-pixel change still covers a full tile here.</source>
        <translation>각 영역은 {tile}×{tile} 픽셀 타일 단위로 보고되므로, 1픽셀만 바뀌어도 여기서는 타일 전체가 포함됩니다.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="371"/>
        <source>Affected regions list</source>
        <translation>영향받는 영역 목록</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="373"/>
        <source>%n regions.</source>
        <translation>
            <numerusform>영역 %n개.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branch_diff_dialog.py" line="378"/>
        <source>%n operation(s) total, across %2 distinct target(s).</source>
        <translation>
            <numerusform>총 작업 %n건, 서로 다른 대상 %2개에 걸쳐 있습니다.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="383"/>
        <source>Divergence total</source>
        <translation>차이 합계</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="385"/>
        <source>Continue to Merge</source>
        <translation>병합 계속</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="386"/>
        <source>Continue to merge</source>
        <translation>병합 계속</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="389"/>
        <source>Performs the same conflict-free merge as the branching panel&apos;s Merge control.</source>
        <translation>브랜치 패널의 병합 컨트롤과 동일하게 충돌 없이 병합합니다.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="393"/>
        <location filename="../ui/branch_diff_dialog.py" line="394"/>
        <source>Close</source>
        <translation>닫기</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="396"/>
        <source>Closes this view without merging or changing anything.</source>
        <translation>병합하거나 변경하지 않고 이 보기를 닫습니다.</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="408"/>
        <source>frames {frames}</source>
        <translation>프레임 {frames}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="414"/>
        <source>layers {layers}</source>
        <translation>레이어 {layers}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="422"/>
        <source>attributes {attrs}</source>
        <translation>속성 {attrs}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="431"/>
        <source>metadata keys {keys}</source>
        <translation>메타데이터 키 {keys}</translation>
    </message>
    <message>
        <location filename="../ui/branch_diff_dialog.py" line="437"/>
        <source>tiles {tiles}</source>
        <translation>타일 {tiles}</translation>
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
        <translation>브랜치</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="365"/>
        <source>Open a project first.</source>
        <translation>먼저 프로젝트를 여세요.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="369"/>
        <location filename="../ui/branching_panel.py" line="499"/>
        <source>New Branch</source>
        <translation>새 브랜치</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="369"/>
        <source>Branch name:</source>
        <translation>브랜치 이름:</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="412"/>
        <location filename="../ui/branching_panel.py" line="503"/>
        <source>Merge</source>
        <translation>병합</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/branching_panel.py" line="442"/>
        <source>Merged branch &apos;{name}&apos; (%n edits) into mainline — conflict-free.</source>
        <translation>
            <numerusform>브랜치 &apos;{name}&apos; 병합 완료: 편집 %n건을 메인라인에 반영했으며 충돌이 없습니다.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="456"/>
        <source>{name} (active)</source>
        <translation>{name} (활성)</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="475"/>
        <source>Open the pre-merge diff for the selected branch.</source>
        <translation>선택한 브랜치의 병합 전 차이를 엽니다.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="479"/>
        <source>Disabled: open a project first.</source>
        <translation>사용할 수 없음: 먼저 프로젝트를 여세요.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="484"/>
        <source>Disabled: select a feature branch, not mainline, to view its diff.</source>
        <translation>사용할 수 없음: 차이를 보려면 메인라인이 아닌 기능 브랜치를 선택하세요.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="491"/>
        <source>Branching</source>
        <translation>브랜칭</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="494"/>
        <source>Branch the project to edit a variation independently, then merge it back. Merges are conflict-free.</source>
        <translation>프로젝트를 브랜치로 나누어 변형본을 독립적으로 편집한 뒤 다시 병합할 수 있습니다. 병합 시 충돌이 발생하지 않습니다.</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="498"/>
        <source>Branches</source>
        <translation>브랜치</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="500"/>
        <source>Create a new branch</source>
        <translation>새 브랜치 만들기</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="501"/>
        <source>Switch</source>
        <translation>전환</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="502"/>
        <source>Switch to the selected branch</source>
        <translation>선택한 브랜치로 전환</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="505"/>
        <source>Merge the selected branch into mainline</source>
        <translation>선택한 브랜치를 메인라인에 병합</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="507"/>
        <source>Open Diff</source>
        <translation>차이 열기</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="509"/>
        <source>Open the pre-merge diff for the selected branch</source>
        <translation>선택한 브랜치의 병합 전 차이 열기</translation>
    </message>
    <message>
        <location filename="../ui/branching_panel.py" line="511"/>
        <source>Merge outcome</source>
        <translation>병합 결과</translation>
    </message>
</context>
<context>
    <name>Canvas_Size_Dialog</name>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="79"/>
        <source>Canvas Size</source>
        <translation>캔버스 크기</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="80"/>
        <source>Canvas size dialog</source>
        <translation>캔버스 크기 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="81"/>
        <source>Target canvas width in pixels</source>
        <translation>대상 캔버스 너비(픽셀)</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="82"/>
        <source>Target canvas height in pixels</source>
        <translation>대상 캔버스 높이(픽셀)</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="83"/>
        <source>Width (px)</source>
        <translation>너비 (px)</translation>
    </message>
    <message>
        <location filename="../ui/canvas_size_dialog.py" line="84"/>
        <source>Height (px)</source>
        <translation>높이 (px)</translation>
    </message>
</context>
<context>
    <name>Canvas_View</name>
    <message>
        <location filename="../ui/canvas_view.py" line="318"/>
        <location filename="../ui/canvas_view.py" line="1443"/>
        <source>Canvas</source>
        <extracomment>Platform name reported by Qt when running without a windowing system. Emitted with the current zoom scale after any zoom change. Emitted with the buffer ``(x, y)`` when the canvas is right-clicked (seam). Emitted with the picked RGBA tuple when the colour-picker sets a colour. Emitted ``(is_active, is_copy)`` when a floating move/copy state changes (drives the shell&apos;s copy-mode status hint, REQ-P2-UI-032/-036). Emitted when a paint/mask-edit stroke is refused because the active layer is locked (D-05); the shell surfaces a &quot;layer is locked&quot; notice. Emitted when a left-click lands outside the active document&apos;s bounds (FIX 5, 2026-08-24 field defect): a click there must not arm a stroke, and must not fail silently — the shell surfaces a notice, following the ``lockedLayerEditRejected`` precedent exactly. Emitted when a paint/mask-edit is refused because the active layer is a REFERENCE or SMART layer (REQ-P3-UI-006 clause 5: non-editable targets are three classes, not two — locked, reference, and smart — and every one of them must be surfaced, never silently swallowed). Distinct from ``lockedLayerEditRejected`` so the shell can show the right notice; ``is_active_editable()`` returns ``False`` for all three classes, and this signal covers the two this view previously dropped on the floor. Emitted when a tool ran (the guards passed) but produced no pixel change — e.g. a flood fill on a region that already holds the picked colour (REQ-P1-UI-014), or a pencil placed on a pixel that already holds it — so no undo entry was pushed. An explicit, deliberate gesture (a completed colour-hub pick, REQ-P3-UI-006 clause 6) must never answer with silence even when it changed nothing. Emitted with the target frame index a ``Ctrl``+wheel / ``Ctrl``+middle- click frame gesture resolved to (REQ-IS-UI-010/-014); the shell routes it through the shipped frame-selection path. Pushes no command — frame navigation is view state (CL-13). Emitted when a confirmed ``Ctrl``+left-click (no floating move live) should add a frame after the active one (REQ-IS-UI-016); the shell builds and pushes the shipped undoable ``make_add_frame_command``. The three selection tools whose Shift/Alt modifiers stay the shipped add/subtract combine gesture (REQ-IS-UI-015) — Shift+drag pans for every other tool. Mirrors ``Main_Window._SELECTION_ENTRY_TOOL_IDS``. The wrapper every :class:`~pixelart_creator.ui.tools.base.ToolContext` is actually built with (see :class:`_RecordingUndoStack`); reads ``self._undo_stack``/``self._record_trace``/``self._recording_document`` live at each push, so `set_undo_stack`/`set_recording` need not rebuild it. A middle press awaiting the click/drag verdict (REQ-IS-UI-011): ``True`` between a middle press and either its release under ``CLICK_DRAG_THRESHOLD_PX`` (a click) or its promotion to ``_panning`` once the cursor travels past the threshold (a drag). A ``Ctrl``+left press awaiting the click/drag verdict (REQ-IS-UI-016, mirrors ``_middle_pending``): ``True`` between the press and either its release under ``CLICK_DRAG_THRESHOLD_PX`` (adds a frame) or its promotion to an ordinary paint/floating-move drag once the cursor travels past the threshold. The persisted Favourites model a plain wheel notch / unmodified middle click travel (REQ-IS-UI-008/-012); ``None`` until the shell binds one via :meth:`set_favourites_model`. The ``timestamp()`` of the RightButton press currently being dispatched through ``_menu_hook``, ``None`` for the keyboard (Menu key / Shift+F10) trigger. Consumed once via :meth:`pop_pending_right_press_timestamp` — deliberately NOT threaded as a third positional argument to ``_menu_hook`` itself, so the hook&apos;s signature (``Callable[[int, int], None]``) and every existing 2-argument hook (tests included) stay unchanged. Live mirror-centre override fed to ``logic.symmetry.mirror`` via each stroke&apos;s :class:`ToolContext` (D-28/CF-93); ``None`` keeps the shipped canvas-centre default. Fed by the shell&apos;s Symmetry_Panel. The guide currently being dragged (D-11), or ``None``. Raw (pre-snap) scene point at the start of the current stroke — the perspective direction-lock anchor (``logic.grids.perspective_snap``).</extracomment>
        <translation>캔버스</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="320"/>
        <location filename="../ui/canvas_view.py" line="1445"/>
        <source>Pixel canvas: left-click to paint, middle-drag to pan</source>
        <translation>픽셀 캔버스: 왼쪽 버튼으로 그리기, 가운데 버튼을 끌어 이동</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="1335"/>
        <source>Remove guide</source>
        <translation>안내선 제거</translation>
    </message>
    <message>
        <location filename="../ui/canvas_view.py" line="1346"/>
        <source>No canvas actions yet</source>
        <translation>아직 캔버스 작업이 없습니다.</translation>
    </message>
</context>
<context>
    <name>Cel_Overwrite_Dialog</name>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="69"/>
        <source>Overwrite Existing Cel?</source>
        <translation>기존 셀을 덮어쓰시겠습니까?</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="70"/>
        <source>Overwrite existing cel confirmation</source>
        <translation>기존 셀 덮어쓰기 확인</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="73"/>
        <source>The destination cell already has a drawing on it. Proceeding replaces that drawing. This can be undone.</source>
        <translation>대상 셀에 이미 그림이 있습니다. 계속하면 해당 그림이 교체됩니다. 이 작업은 실행 취소할 수 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="77"/>
        <source>Overwrite warning</source>
        <translation>덮어쓰기 경고</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="78"/>
        <source>Don&apos;t ask again for this project</source>
        <translation>이 프로젝트에서는 다시 묻지 않음</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="80"/>
        <source>Suppress this confirmation for the current project</source>
        <translation>현재 프로젝트에서 이 확인 창 표시 안 함</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="84"/>
        <location filename="../ui/cel_overwrite_dialog.py" line="85"/>
        <source>Overwrite</source>
        <translation>덮어쓰기</translation>
    </message>
    <message>
        <location filename="../ui/cel_overwrite_dialog.py" line="88"/>
        <location filename="../ui/cel_overwrite_dialog.py" line="89"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
</context>
<context>
    <name>Colour_Cycling_Panel</name>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="156"/>
        <source>Colour Cycling</source>
        <extracomment>Milliseconds per cycling tick, derived from the tuning FPS (S12). Emitted with a list of display colours to preview (rotated palette). Emitted with ``(start, end, step)`` when Apply commits the cycle state.</extracomment>
        <translation>색상 순환</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="157"/>
        <source>Colour cycling panel</source>
        <translation>색상 순환 패널</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="158"/>
        <source>Start</source>
        <translation>시작</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="159"/>
        <source>End</source>
        <translation>끝</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="160"/>
        <source>Step</source>
        <translation>단계</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="161"/>
        <source>Cycle range start index</source>
        <translation>순환 범위 시작 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="162"/>
        <source>Cycle range end index</source>
        <translation>순환 범위 끝 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="163"/>
        <source>Cycle step</source>
        <translation>순환 단계</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="164"/>
        <source>Play / Stop</source>
        <translation>재생 / 중지</translation>
    </message>
    <message>
        <location filename="../ui/colour_cycling_panel.py" line="165"/>
        <source>Apply</source>
        <translation>적용</translation>
    </message>
</context>
<context>
    <name>Colour_Hub_Menu</name>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="642"/>
        <source>Colour Hub</source>
        <extracomment>Emitted with an RGBA tuple whenever a colour is picked (apply immediately, leg 1 — the live preview stream; never refused, REQ-P3-UI-006 clause 1). Emitted with an RGBA tuple on a COMPLETED pick only — one emission per discrete gesture (a wheel-drag release, a keyboard nudge release, a numeric spin&apos;s editingFinished, a single click on a harmony/shade/tint swatch, or a single click on a Favourites entry). A DOUBLE click / a keyboard activation on either swatch surface adopts instead and never reaches this signal (REQ-IS-UI-019/-020/-022, D-11). The shell (``ui/main_window.py``) uses this to run the active tool at the hub&apos;s anchor pixel as leg 2 (REQ-P3-UI-006 clauses 2-6). Re-emitted when the Favourites model changes (so the shell persists it). Set by the app-wide dismiss filter (below) to the ``timestamp()`` of the RightButton press that just hid this hub, and consumed once by :meth:`consume_dismiss_timestamp`. ``None`` when no dismissal is pending recognition.</extracomment>
        <translation>색상 허브</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="643"/>
        <source>Colour hub</source>
        <translation>색상 허브</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="644"/>
        <source>Add to Favourites</source>
        <translation>즐겨찾기에 추가</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="647"/>
        <source>This tool does not paint the active colour, so the colour wheel is hidden here.</source>
        <translation>이 도구는 활성 색상으로 칠하지 않으므로 여기서는 색상환이 숨겨집니다.</translation>
    </message>
</context>
<context>
    <name>Colour_Wheel_Widget</name>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="354"/>
        <location filename="../ui/colour_wheel_widget.py" line="637"/>
        <source>Red channel</source>
        <extracomment>Emitted with the picked :class:`QColor` on any user-initiated change that ADOPTS into the wheel (wheel-pad drag, value slider, numeric entries, and a harmony/shade/tint swatch&apos;s double-click/keyboard activation — never a swatch&apos;s single click). Emitted with a harmony/shade/tint swatch&apos;s own RGBA tuple on a single left click (REQ-IS-UI-020). PAINT-only: the wheel&apos;s own selection is deliberately left unchanged, unlike :attr:`colorPicked`.</extracomment>
        <translation>빨강 채널</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="357"/>
        <location filename="../ui/colour_wheel_widget.py" line="638"/>
        <source>Green channel</source>
        <translation>초록 채널</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="360"/>
        <location filename="../ui/colour_wheel_widget.py" line="639"/>
        <source>Blue channel</source>
        <translation>파랑 채널</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="363"/>
        <location filename="../ui/colour_wheel_widget.py" line="640"/>
        <source>Hue</source>
        <translation>색조</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="366"/>
        <location filename="../ui/colour_wheel_widget.py" line="641"/>
        <source>Saturation</source>
        <translation>채도</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="369"/>
        <location filename="../ui/colour_wheel_widget.py" line="629"/>
        <location filename="../ui/colour_wheel_widget.py" line="642"/>
        <source>Value</source>
        <translation>명도</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="564"/>
        <source>Current colour %1</source>
        <translation>현재 색상 %1</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="627"/>
        <source>Colour wheel picker</source>
        <translation>색상환 선택기</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="630"/>
        <source>Brightness value</source>
        <translation>명도 값</translation>
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
        <translation>16진수 색상</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="644"/>
        <source>Complementary</source>
        <translation>보색</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="645"/>
        <source>Analogous</source>
        <translation>유사색</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="646"/>
        <source>Triadic</source>
        <translation>삼각 배색</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="647"/>
        <source>Tetradic</source>
        <translation>사각 배색</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="648"/>
        <source>Split-complementary</source>
        <translation>분할 보색</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="649"/>
        <source>Shades</source>
        <translation>셰이드</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="650"/>
        <source>Tints</source>
        <translation>틴트</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="661"/>
        <source>harmony</source>
        <translation>배색</translation>
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
        <translation>댓글</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="118"/>
        <source>Open a shared project before commenting.</source>
        <translation>댓글을 작성하기 전에 공유 프로젝트를 여세요.</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="126"/>
        <source>Enter your member id before commenting.</source>
        <translation>댓글을 작성하기 전에 멤버 ID를 입력하세요.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/comments_panel.py" line="136"/>
        <source>A comment may be at most %n bytes.</source>
        <translation>
            <numerusform>댓글은 최대 %n바이트까지 입력할 수 있습니다.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="207"/>
        <source>Resolved</source>
        <translation>해결됨</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="207"/>
        <source>Open</source>
        <translation>열림</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/comments_panel.py" line="222"/>
        <source>%1 / %n bytes</source>
        <translation>
            <numerusform>%1 / %n바이트</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="234"/>
        <source>Your member id:</source>
        <translation>내 멤버 ID:</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="235"/>
        <source>e.g. alice</source>
        <translation>예: alice</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="236"/>
        <source>Comment author id</source>
        <translation>댓글 작성자 ID</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="238"/>
        <source>Author</source>
        <translation>작성자</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="238"/>
        <source>Comment</source>
        <translation>댓글</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="238"/>
        <source>Status</source>
        <translation>상태</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="240"/>
        <source>Comment thread</source>
        <translation>댓글 스레드</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="241"/>
        <source>Write a comment…</source>
        <translation>댓글을 입력하세요…</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="242"/>
        <source>New comment text</source>
        <translation>새 댓글 내용</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="243"/>
        <source>Reply to selected</source>
        <translation>선택 항목에 답글</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="244"/>
        <source>Reply to the selected comment</source>
        <translation>선택한 댓글에 답글 달기</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="245"/>
        <source>Add Comment</source>
        <translation>댓글 추가</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="246"/>
        <source>Add the comment</source>
        <translation>댓글 추가</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="247"/>
        <source>Resolve</source>
        <translation>해결</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="248"/>
        <source>Resolve the selected comment</source>
        <translation>선택한 댓글을 해결됨으로 표시</translation>
    </message>
    <message>
        <location filename="../ui/comments_panel.py" line="249"/>
        <source>Comment byte count</source>
        <translation>댓글 바이트 수</translation>
    </message>
</context>
<context>
    <name>Cursor_Feedback_Overlay</name>
    <message>
        <location filename="../ui/cursor_feedback_overlay.py" line="103"/>
        <location filename="../ui/cursor_feedback_overlay.py" line="160"/>
        <source>Cursor feedback</source>
        <extracomment>Progress fraction (0..1 of FEEDBACK_DURATION_MS) at which the fall to zero begins.</extracomment>
        <translation>커서 피드백</translation>
    </message>
</context>
<context>
    <name>Dependency_Graph_View</name>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="169"/>
        <source>Dependency cycle detected (graph unchanged): %1</source>
        <extracomment>Item roles: whether a row is a broken edge, and the edge it stands for. The asset in scope (``&quot;&quot;`` = the whole catalog). The kind of the last cycle failure at :meth:`show_edges` (``None`` = none).</extracomment>
        <translation>종속성 순환이 감지되었습니다(그래프는 변경되지 않음): %1</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="202"/>
        <source>Dependencies (depends on)</source>
        <translation>종속성 (의존 대상)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="208"/>
        <source>Dependents (referenced by)</source>
        <translation>참조하는 항목</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="238"/>
        <source>Broken (%1)</source>
        <translation>끊어짐 (%1)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="262"/>
        <source>%1 (%2)</source>
        <translation>%1 (%2)</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="270"/>
        <source>Sprite</source>
        <translation>스프라이트</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="271"/>
        <source>Animation</source>
        <translation>애니메이션</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="272"/>
        <source>Tileset</source>
        <translation>타일셋</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="273"/>
        <source>Tilemap</source>
        <translation>타일맵</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="274"/>
        <source>Palette</source>
        <translation>팔레트</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="281"/>
        <source>missing target</source>
        <translation>대상 없음</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="283"/>
        <source>changed target</source>
        <translation>대상 변경됨</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="290"/>
        <source>No broken references</source>
        <translation>끊어진 참조 없음</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="293"/>
        <source>Broken references: %1</source>
        <translation>끊어진 참조: %1</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="295"/>
        <source>Broken reference summary</source>
        <translation>끊어진 참조 요약</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="299"/>
        <source>Dependency graph</source>
        <translation>종속성 그래프</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="300"/>
        <source>Asset</source>
        <translation>에셋</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="300"/>
        <source>Status</source>
        <translation>상태</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="301"/>
        <source>Dependency relations</source>
        <translation>종속 관계</translation>
    </message>
    <message>
        <location filename="../ui/dependency_graph_view.py" line="302"/>
        <source>Dependency cycle notice</source>
        <translation>종속성 순환 알림</translation>
    </message>
</context>
<context>
    <name>Document_Transform_Confirm_Dialog</name>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="92"/>
        <source>Confirm Large Transform</source>
        <translation>대규모 변형 확인</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="93"/>
        <source>Confirm large document transform dialog</source>
        <translation>대규모 문서 변형 확인 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="99"/>
        <source>%1 will resample every layer and mask of this document to %2 × %3 px, using up to %4 of memory at once. Proceed?</source>
        <translation>%1 작업은 이 문서의 모든 레이어와 마스크를 %2 × %3 px로 리샘플링하며, 최대 %4의 메모리를 한 번에 사용합니다. 계속하시겠습니까?</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="107"/>
        <source>Transform cost summary</source>
        <translation>변형 비용 요약</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="108"/>
        <source>Proceed</source>
        <translation>계속</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="109"/>
        <source>Proceed with the transform</source>
        <translation>변형 계속</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="110"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="111"/>
        <source>Cancel the transform</source>
        <translation>변형 취소</translation>
    </message>
</context>
<context>
    <name>Document_Transform_Progress_Dialog</name>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="197"/>
        <source>Transforming Document</source>
        <extracomment>Emitted when the user asks to stop — via the button, Escape, or the window&apos;s close control. The caller (the runner) decides what &quot;stop&quot; means; this dialog only reports the request.</extracomment>
        <translation>문서 변형 중</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="198"/>
        <source>Document transform progress dialog</source>
        <translation>문서 변형 진행 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="199"/>
        <source>%1…</source>
        <translation>%1…</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="200"/>
        <source>Transform operation in progress</source>
        <translation>변형 작업 진행 중</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="201"/>
        <source>Transform progress</source>
        <translation>변형 진행률</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="202"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
    <message>
        <location filename="../ui/document_transform_dialogs.py" line="203"/>
        <source>Cancel the transform</source>
        <translation>변형 취소</translation>
    </message>
</context>
<context>
    <name>Document_View</name>
    <message>
        <location filename="../ui/multi_view.py" line="119"/>
        <source>Document view {0}</source>
        <extracomment>Per-wheel-notch zoom step for an extra view (independent of the primary view). Emitted with the picked RGBA tuple when a plain wheel notch travels the shared Favourites cursor (REQ-IS-UI-008, D-16 — this surface is a navigate-only view of the SAME live document scene as the primary Canvas_View, so the active colour it sets is real document context). The persisted Favourites model bound via :meth:`set_favourites_model`; ``None`` until the shell binds one.</extracomment>
        <translation>문서 보기 {0}</translation>
    </message>
    <message>
        <location filename="../ui/multi_view.py" line="123"/>
        <source>An extra synced view of the same document (independent zoom/pan)</source>
        <translation>같은 문서의 추가 동기화 보기 (확대/축소와 이동은 독립적)</translation>
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
        <translation>문서 전체</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="301"/>
        <source>Animated GIF (*.gif)</source>
        <translation>애니메이션 GIF (*.gif)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="303"/>
        <source>PNG image (*.png)</source>
        <translation>PNG 이미지 (*.png)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="305"/>
        <source>Export To</source>
        <translation>내보내기 위치</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="313"/>
        <source>Export</source>
        <translation>내보내기</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="314"/>
        <source>Format</source>
        <translation>형식</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="315"/>
        <location filename="../ui/export_dialog.py" line="343"/>
        <source>Engine preset</source>
        <translation>엔진 프리셋</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="316"/>
        <source>Destination</source>
        <translation>대상</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="317"/>
        <source>Browse…</source>
        <translation>찾아보기…</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="318"/>
        <source>Also add to the asset library</source>
        <translation>에셋 라이브러리에도 추가</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="320"/>
        <source>PNG image</source>
        <translation>PNG 이미지</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="321"/>
        <source>Animated GIF</source>
        <translation>애니메이션 GIF</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="322"/>
        <source>Sprite sheet</source>
        <translation>스프라이트시트</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="323"/>
        <source>Texture atlas</source>
        <translation>텍스처 아틀라스</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="324"/>
        <source>None</source>
        <translation>없음</translation>
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
        <translation>첫 번째 프레임을 하나로 합쳐 PNG 이미지로 내보냅니다.</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="331"/>
        <source>Frames</source>
        <translation>프레임</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="332"/>
        <source>Loop count</source>
        <translation>반복 횟수</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="333"/>
        <source>Loop count (0 = loop forever).</source>
        <translation>반복 횟수(0 = 무한 반복).</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="334"/>
        <source>Columns</source>
        <translation>열</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="335"/>
        <location filename="../ui/export_dialog.py" line="337"/>
        <source>Padding (px)</source>
        <translation>여백 (px)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="336"/>
        <location filename="../ui/export_dialog.py" line="339"/>
        <source>Write JSON metadata</source>
        <translation>JSON 메타데이터 쓰기</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="338"/>
        <source>Max dimension (px)</source>
        <translation>최대 크기 (px)</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="342"/>
        <source>Export format</source>
        <translation>내보내기 형식</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="344"/>
        <source>Destination path</source>
        <translation>대상 경로</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="345"/>
        <source>Browse for destination</source>
        <translation>대상 찾아보기</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="347"/>
        <source>Also add this export to the asset library</source>
        <translation>이 내보내기 결과를 에셋 라이브러리에도 추가</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="349"/>
        <source>GIF frame source</source>
        <translation>GIF 프레임 원본</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="350"/>
        <source>GIF loop count</source>
        <translation>GIF 반복 횟수</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="351"/>
        <source>Sprite-sheet columns</source>
        <translation>스프라이트시트 열 수</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="352"/>
        <source>Sprite-sheet padding</source>
        <translation>스프라이트시트 여백</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="353"/>
        <source>Write sprite-sheet JSON</source>
        <translation>스프라이트시트 JSON 쓰기</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="354"/>
        <source>Atlas padding</source>
        <translation>아틀라스 여백</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="355"/>
        <source>Atlas max dimension</source>
        <translation>아틀라스 최대 크기</translation>
    </message>
    <message>
        <location filename="../ui/export_dialog.py" line="356"/>
        <source>Write atlas JSON</source>
        <translation>아틀라스 JSON 쓰기</translation>
    </message>
</context>
<context>
    <name>Extract_Palette_Dialog</name>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="130"/>
        <source>Choose Image</source>
        <extracomment>Extraction method tokens carried in the method combo&apos;s item data.</extracomment>
        <translation>이미지 선택</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="132"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>이미지 (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="139"/>
        <location filename="../ui/extract_palette_dialog.py" line="158"/>
        <source>Extract Palette</source>
        <translation>팔레트 추출</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="139"/>
        <source>Could not load the image.</source>
        <translation>이미지를 불러올 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="169"/>
        <source>Extract Palette from Image</source>
        <translation>이미지에서 팔레트 추출</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="170"/>
        <source>Extract palette dialog</source>
        <translation>팔레트 추출 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="171"/>
        <source>Choose Image…</source>
        <translation>이미지 선택…</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="172"/>
        <source>No image chosen</source>
        <translation>선택한 이미지 없음</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="173"/>
        <source>Colours (N)</source>
        <translation>색상 수 (N)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="174"/>
        <source>Method</source>
        <translation>방식</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="175"/>
        <source>Number of colours</source>
        <translation>색상 수</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="176"/>
        <source>Extraction method</source>
        <translation>추출 방식</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="177"/>
        <source>Median cut (fast)</source>
        <translation>미디언 컷 (빠름)</translation>
    </message>
    <message>
        <location filename="../ui/extract_palette_dialog.py" line="178"/>
        <source>K-means (higher quality)</source>
        <translation>K-평균 (더 높은 품질)</translation>
    </message>
</context>
<context>
    <name>Failure_Messages</name>
    <message>
        <location filename="../ui/failure_messages.py" line="151"/>
        <source>The operation timed out.</source>
        <extracomment>The most links of a chain read; a longer chain is read only this far.</extracomment>
        <translation>작업 시간이 초과되었습니다.</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="155"/>
        <source>The connection failed.</source>
        <translation>연결에 실패했습니다.</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="157"/>
        <source>The file or folder could not be found.</source>
        <translation>파일 또는 폴더를 찾을 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="161"/>
        <source>Access to the file or folder was denied.</source>
        <translation>파일 또는 폴더에 대한 접근이 거부되었습니다.</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="165"/>
        <source>A value was not valid for this operation.</source>
        <translation>이 작업에 유효하지 않은 값이 있었습니다.</translation>
    </message>
    <message>
        <location filename="../ui/failure_messages.py" line="168"/>
        <source>The operation could not be completed.</source>
        <translation>작업을 완료하지 못했습니다.</translation>
    </message>
</context>
<context>
    <name>Favourites_Panel</name>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="279"/>
        <source>Favourites</source>
        <extracomment>Edge of a Favourites swatch icon, px (presentation-only sizing). Keys that nudge the wheel pad&apos;s hue/saturation (``_WheelPad.keyPressEvent``); a KeyRelease for one of these is a discrete, already-completed pick (REQ-P3- UI-006 leg 2), unlike Tab/other keys the pad never acts on. Single left click on a favourite — paint that colour, leave the wheel alone. Double left click / Enter / Return on a favourite — adopt that colour into the wheel, paint nothing. Deprecated alias of :attr:`favouriteActivated`, kept for pre-2026-08-31 callers of the pre-split single ``favouriteChosen`` signal. Emitted alongside :attr:`favouriteActivated` ONLY — never alongside :attr:`favouritePicked`, so it never resurrects the fused-gesture defect this split fixes (REQ-IS-UI-019). New code should connect :attr:`favouritePicked` / :attr:`favouriteActivated` directly. Emitted whenever the underlying model is mutated (so the shell persists it).</extracomment>
        <translation>즐겨찾기</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="280"/>
        <source>Favourites panel</source>
        <translation>즐겨찾기 패널</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="281"/>
        <source>Favourite colours</source>
        <translation>즐겨찾는 색상</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="282"/>
        <source>Remove</source>
        <translation>제거</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="283"/>
        <source>Move Up</source>
        <translation>위로 이동</translation>
    </message>
    <message>
        <location filename="../ui/colour_hub_menu.py" line="284"/>
        <source>Move Down</source>
        <translation>아래로 이동</translation>
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
        <translation>(이름 없음)</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="317"/>
        <location filename="../ui/frame_tags_panel.py" line="323"/>
        <location filename="../ui/frame_tags_panel.py" line="394"/>
        <source>Add Tag</source>
        <translation>태그 추가</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="346"/>
        <location filename="../ui/frame_tags_panel.py" line="352"/>
        <location filename="../ui/frame_tags_panel.py" line="395"/>
        <source>Edit Tag</source>
        <translation>태그 편집</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="363"/>
        <location filename="../ui/frame_tags_panel.py" line="396"/>
        <source>Remove Tag</source>
        <translation>태그 제거</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="388"/>
        <source>Frame tags panel</source>
        <translation>프레임 태그 패널</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="389"/>
        <source>Tag actions</source>
        <translation>태그 작업</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="390"/>
        <source>Frame tags</source>
        <translation>프레임 태그</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="392"/>
        <source>Named animations; double-click to edit</source>
        <translation>이름이 지정된 애니메이션입니다. 두 번 눌러 편집합니다.</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="397"/>
        <source>Play Tag</source>
        <translation>태그 재생</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="399"/>
        <source>Play the selected tag as its own animation</source>
        <translation>선택한 태그를 별도의 애니메이션으로 재생</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="401"/>
        <source>Play tag</source>
        <translation>태그 재생</translation>
    </message>
</context>
<context>
    <name>Guide_Logo_Switch_Widget</name>
    <message>
        <location filename="../ui/guide_logo_switch.py" line="121"/>
        <source>Switch the pixel font for the guide&apos;s pages</source>
        <extracomment>Accessible name of the switch; screen readers announce it.</extracomment>
        <translation>가이드 페이지의 픽셀 글꼴 전환</translation>
    </message>
</context>
<context>
    <name>Iso_Grid_Dialog</name>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="122"/>
        <source>Configure Isometric Grid</source>
        <extracomment>Sane bounds for the ``W:H`` tile ratio field (2:1 dimetric default is 2.0; true-iso is ~1.732). Not a lattice geometry decision — just a widget bound keeping the field away from non-finite/degenerate input before it ever reaches ``IsoGridConfig`` validation (S12).</extracomment>
        <translation>등각 격자 설정</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="123"/>
        <source>Tile width</source>
        <translation>타일 너비</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="124"/>
        <source>Tile ratio (W:H)</source>
        <translation>타일 비율 (W:H)</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="125"/>
        <source>Origin X</source>
        <translation>원점 X</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="126"/>
        <source>Origin Y</source>
        <translation>원점 Y</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="127"/>
        <source>Isometric tile width</source>
        <translation>등각 타일 너비</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="128"/>
        <source>Isometric tile ratio</source>
        <translation>등각 타일 비율</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="129"/>
        <source>Isometric grid origin X</source>
        <translation>등각 격자 원점 X</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="130"/>
        <source>Isometric grid origin Y</source>
        <translation>등각 격자 원점 Y</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="133"/>
        <source>OK</source>
        <translation>확인</translation>
    </message>
    <message>
        <location filename="../ui/iso_grid_dialog.py" line="136"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
</context>
<context>
    <name>Layer_Panel</name>
    <message>
        <location filename="../ui/layer_panel.py" line="443"/>
        <source>Normal</source>
        <extracomment>Emitted with the selected node (``Layer`` / ``LayerGroup`` / ``None``). Emitted when the &quot;edit mask&quot; toggle flips (route paint to the mask buffer). Emitted when a mask attach/remove/edit is refused because the target node is locked (D-05); the shell surfaces a &quot;layer is locked&quot; notice.</extracomment>
        <translation>표준</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="444"/>
        <source>Multiply</source>
        <translation>곱하기</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="445"/>
        <source>Screen</source>
        <translation>스크린</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="446"/>
        <source>Overlay</source>
        <translation>오버레이</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="447"/>
        <source>Darken</source>
        <translation>어둡게</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="448"/>
        <source>Lighten</source>
        <translation>밝게</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="449"/>
        <source>Colour Dodge</source>
        <translation>색상 닷지</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="450"/>
        <source>Colour Burn</source>
        <translation>색상 번</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="451"/>
        <source>Hard Light</source>
        <translation>하드 라이트</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="452"/>
        <source>Soft Light</source>
        <translation>소프트 라이트</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="453"/>
        <source>Difference</source>
        <translation>차이</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="454"/>
        <source>Exclusion</source>
        <translation>제외</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="650"/>
        <source>Layer</source>
        <translation>레이어</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="654"/>
        <location filename="../ui/layer_panel.py" line="883"/>
        <source>Add Layer</source>
        <translation>레이어 추가</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="667"/>
        <location filename="../ui/layer_panel.py" line="884"/>
        <source>Remove Layer</source>
        <translation>레이어 제거</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="680"/>
        <location filename="../ui/layer_panel.py" line="885"/>
        <source>Duplicate Layer</source>
        <translation>레이어 복제</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="689"/>
        <location filename="../ui/layer_panel.py" line="886"/>
        <source>Group</source>
        <translation>그룹</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="693"/>
        <source>Group Layers</source>
        <translation>레이어 그룹화</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="705"/>
        <source>Ungroup Layers</source>
        <translation>레이어 그룹 해제</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="726"/>
        <location filename="../ui/layer_panel.py" line="871"/>
        <location filename="../ui/layer_panel.py" line="891"/>
        <source>Add Mask</source>
        <translation>마스크 추가</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="733"/>
        <location filename="../ui/layer_panel.py" line="871"/>
        <source>Remove Mask</source>
        <translation>마스크 제거</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="757"/>
        <source>Toggle Reference</source>
        <translation>참조 전환</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="767"/>
        <source>Smart</source>
        <translation>스마트</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="771"/>
        <source>Create Smart Layer</source>
        <translation>스마트 레이어 만들기</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="828"/>
        <source>Move Layer</source>
        <translation>레이어 이동</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="877"/>
        <source>Layers panel</source>
        <translation>레이어 패널</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="878"/>
        <source>Layer actions</source>
        <translation>레이어 작업</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="879"/>
        <source>Layer tree</source>
        <translation>레이어 트리</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="881"/>
        <source>Layers top-to-bottom; drag to reorder or re-parent</source>
        <translation>레이어가 위에서 아래 순서로 나열됩니다. 끌어서 순서나 상위 그룹을 변경하세요.</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="887"/>
        <source>Ungroup</source>
        <translation>그룹 해제</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="888"/>
        <source>Edit Mask</source>
        <translation>마스크 편집</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="889"/>
        <source>Reference</source>
        <translation>참조</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="890"/>
        <source>Smart Layer</source>
        <translation>스마트 레이어</translation>
    </message>
</context>
<context>
    <name>Macro_Controls</name>
    <message>
        <location filename="../ui/macro_controls.py" line="144"/>
        <source>Running…</source>
        <extracomment>``(Macro, label)`` — the host should replay this macro on the active document (as one undoable grouped command, REQ-P8-UI-002). ``(recording,)`` — recording started / stopped (view state, not undoable). The user asked to cancel the in-flight automation run (C-07); the host relays this to ``Automation_Controller.cancel()``.</extracomment>
        <translation>실행 중…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="146"/>
        <source>Done</source>
        <translation>완료</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="147"/>
        <source>Idle</source>
        <translation>대기 중</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="187"/>
        <source>Macro Error</source>
        <translation>매크로 오류</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/macro_controls.py" line="195"/>
        <source>Recording %1 (%n steps)</source>
        <translation>
            <numerusform>%1 기록 중 (%n단계)</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="217"/>
        <source>Macro</source>
        <translation>매크로</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="235"/>
        <source>Save Macro</source>
        <translation>매크로 저장</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="237"/>
        <location filename="../ui/macro_controls.py" line="263"/>
        <source>Macro files (*%1)</source>
        <translation>매크로 파일 (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="246"/>
        <source>Save Macro Failed</source>
        <translation>매크로 저장 실패</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="261"/>
        <source>Load Macro</source>
        <translation>매크로 불러오기</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="272"/>
        <source>Load Macro Failed</source>
        <translation>매크로 불러오기 실패</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/macro_controls.py" line="307"/>
        <source>Recording… %n steps captured</source>
        <translation>
            <numerusform>기록 중… %n단계 캡처됨</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="310"/>
        <source>Not recording</source>
        <translation>기록 중이 아님</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="314"/>
        <source>Stop Recording</source>
        <translation>기록 중지</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="314"/>
        <source>Record Macro</source>
        <translation>매크로 기록</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="316"/>
        <source>Replay</source>
        <translation>재생</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="317"/>
        <source>Save…</source>
        <translation>저장…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="318"/>
        <source>Load…</source>
        <translation>불러오기…</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="319"/>
        <source>Remove</source>
        <translation>제거</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="320"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="321"/>
        <source>Macro controls</source>
        <translation>매크로 컨트롤</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="322"/>
        <source>Record or stop a macro</source>
        <translation>매크로 기록 시작 또는 중지</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="323"/>
        <source>Macro recording status</source>
        <translation>매크로 기록 상태</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="324"/>
        <source>Recorded and loaded macros</source>
        <translation>기록했거나 불러온 매크로</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="325"/>
        <source>Replay the selected macro</source>
        <translation>선택한 매크로 재생</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="326"/>
        <source>Save the selected macro</source>
        <translation>선택한 매크로 저장</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="327"/>
        <source>Load a macro from a file</source>
        <translation>파일에서 매크로 불러오기</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="328"/>
        <source>Remove the selected macro</source>
        <translation>선택한 매크로 제거</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="329"/>
        <source>Cancel the running automation</source>
        <translation>실행 중인 자동화 취소</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="331"/>
        <source>Stops the in-flight automation run; enabled only while busy.</source>
        <translation>진행 중인 자동화를 중지합니다. 작업 중일 때만 사용할 수 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="333"/>
        <source>Progress</source>
        <translation>진행률</translation>
    </message>
    <message>
        <location filename="../ui/macro_controls.py" line="334"/>
        <source>Macro replay progress</source>
        <translation>매크로 재생 진행률</translation>
    </message>
</context>
<context>
    <name>Main_Window</name>
    <message>
        <location filename="../ui/main_window.py" line="1309"/>
        <location filename="../ui/main_window.py" line="5770"/>
        <source>&amp;Undo</source>
        <extracomment>Emitted when &quot;Use system font&quot; changes (stored here; the font itself is switched by the listener that owns it). Emitted when &quot;Pixel-perfect interface&quot; changes (stored here; it takes effect at the next launch). Live mirror-centre override from the Symmetry_Panel (D-28/CF-93); ``None`` keeps the shipped canvas-centre default. The DSL ops of the in-flight automation run (recorded into a macro on success if recording is active); ``None`` for a macro replay (a replay is not itself re-recorded). True while an in-session timelapse playback holds the active tab&apos;s canvas + the shared undo/redo actions read-only (REQ-P9-UI-016); see ``_on_timelapse_playback_lock_changed``. The cloud project id last saved to / opened from (drives version browse). D-13: the most recently fetched remote version list (cached from the last &quot;open_list&quot;/&quot;versions&quot;/&quot;save&quot; result) — feeds the read-only ``compute_sync_state`` for the Cloud menu status line and the version browser, without a network round trip on every tab switch. D-13: the version id of a restore/recover in flight, consumed once the reconstructed document lands in its new tab (see ``_on_cloud_succeeded``). Live-cursor overlays are per-tab (attached in _create_tab_aids); toggled on connect. The local member id broadcast with presence (never a token).</extracomment>
        <translation>실행 취소</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="1311"/>
        <location filename="../ui/main_window.py" line="5771"/>
        <source>&amp;Redo</source>
        <translation>다시 실행</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2244"/>
        <source>Untitled</source>
        <translation>제목 없음</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="2819"/>
        <source>Add Frame</source>
        <translation>프레임 추가</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3172"/>
        <source>Unsaved Changes</source>
        <translation>저장되지 않은 변경 사항</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3175"/>
        <source>The current document has unsaved changes. Save it before opening the dropped project?</source>
        <translation>현재 문서에 저장되지 않은 변경 사항이 있습니다. 끌어다 놓은 프로젝트를 열기 전에 저장하시겠습니까?</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3180"/>
        <source>Save</source>
        <translation>저장</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3182"/>
        <source>Discard</source>
        <translation>폐기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3184"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3217"/>
        <source>Load Palette</source>
        <translation>팔레트 불러오기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3245"/>
        <location filename="../ui/main_window.py" line="4307"/>
        <source>Save Project</source>
        <translation>프로젝트 저장</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3247"/>
        <location filename="../ui/main_window.py" line="4293"/>
        <location filename="../ui/main_window.py" line="4309"/>
        <source>Pixel projects (*%1)</source>
        <translation>픽셀 프로젝트 (*%1)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3257"/>
        <source>Unsupported file type: %1</source>
        <translation>지원되지 않는 파일 형식: %1</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3268"/>
        <source>Layer is locked.</source>
        <translation>레이어가 잠겨 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3283"/>
        <source>This is the last remaining frame; a document must keep at least one.</source>
        <translation>마지막 남은 프레임입니다. 문서에는 프레임이 하나 이상 있어야 합니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3296"/>
        <source>Click was outside the document.</source>
        <translation>선택한 위치가 문서 밖에 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3309"/>
        <source>This layer cannot be edited directly.</source>
        <translation>이 레이어는 직접 편집할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3322"/>
        <source>No change: the colour already matched.</source>
        <translation>변경 없음: 색상이 이미 일치합니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3335"/>
        <source>No tileset bound to this tilemap yet.</source>
        <translation>이 타일맵에 연결된 타일셋이 아직 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3347"/>
        <source>Select a tile first.</source>
        <translation>먼저 타일을 선택하세요.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3354"/>
        <source>Open a document before loading a palette.</source>
        <translation>팔레트를 불러오기 전에 문서를 여세요.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3362"/>
        <source>Import Failed</source>
        <translation>가져오기 실패</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3363"/>
        <source>Could not import %1:
%2</source>
        <translation>가져올 수 없습니다: %1
%2</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3487"/>
        <source>Copying selection — release, Enter to commit, Esc to cancel</source>
        <extracomment>Incoming tool ids that discard the active selection on entry (REQ-IS-UI-029). Re-activating an already-active selection tool is included deliberately, so it doubles as a start-fresh gesture — an assumption, flagged and cheap to reverse. Every other incoming tool leaves the selection untouched, so mask-constrained drawing (REQ-P2-LOGIC-006) survives a tool switch.</extracomment>
        <translation>선택 영역 복사 중 — 놓은 뒤 Enter 키로 확정, Esc 키로 취소</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3492"/>
        <source>Moving selection — hold Ctrl to copy; Enter to commit, Esc to cancel</source>
        <translation>선택 영역 이동 중 — Ctrl 키를 누르면 복사, Enter 키로 확정, Esc 키로 취소</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3603"/>
        <source>Add Shade Ramp</source>
        <translation>셰이드 그라데이션 추가</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3623"/>
        <location filename="../ui/main_window.py" line="3633"/>
        <source>Constrain to Palette</source>
        <translation>팔레트로 제한</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3654"/>
        <location filename="../ui/main_window.py" line="3665"/>
        <location filename="../ui/main_window.py" line="5794"/>
        <source>Colour Cycling</source>
        <translation>색상 순환</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3655"/>
        <source>Colour cycling applies to indexed documents.</source>
        <translation>색상 순환은 인덱스 문서에만 적용됩니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3675"/>
        <source>Colour Cycle</source>
        <translation>색상 순환</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3693"/>
        <source>Extract Palette</source>
        <translation>팔레트 추출</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3704"/>
        <location filename="../ui/main_window.py" line="3724"/>
        <location filename="../ui/main_window.py" line="3734"/>
        <source>Palette Swap</source>
        <translation>팔레트 교체</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3705"/>
        <source>Palette swap applies to indexed documents.</source>
        <translation>팔레트 교체는 인덱스 문서에만 적용됩니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3759"/>
        <location filename="../ui/main_window.py" line="3769"/>
        <source>Convert to Indexed</source>
        <translation>인덱스로 변환</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3791"/>
        <location filename="../ui/main_window.py" line="3801"/>
        <source>Convert to RGBA</source>
        <translation>RGBA로 변환</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="3929"/>
        <source>Register Selection</source>
        <translation>선택 영역 등록</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4022"/>
        <source>Choose a new folder for the imported project</source>
        <translation>가져온 프로젝트를 저장할 새 폴더를 선택하세요.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4031"/>
        <source>&quot;%1&quot; already exists. Choose a name for a new folder.</source>
        <translation>이미 있는 이름입니다: &quot;%1&quot;. 새 폴더의 이름을 선택하세요.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4050"/>
        <source>Imported Project</source>
        <translation>가져온 프로젝트</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4291"/>
        <source>Open Project</source>
        <translation>프로젝트 열기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4318"/>
        <source>Cloud project name:</source>
        <translation>클라우드 프로젝트 이름:</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4323"/>
        <source>Enter a project name.</source>
        <translation>프로젝트 이름을 입력하세요.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4332"/>
        <source>Connect to a cloud provider first.</source>
        <translation>먼저 클라우드 제공자에 연결하세요.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4366"/>
        <source>Cloud status: —</source>
        <translation>클라우드 상태: —</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4374"/>
        <source>Cloud status: Up to date</source>
        <translation>클라우드 상태: 최신 상태</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4376"/>
        <source>Cloud status: Not yet saved to cloud</source>
        <translation>클라우드 상태: 아직 클라우드에 저장되지 않음</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4378"/>
        <source>Cloud status: Newer version in cloud</source>
        <translation>클라우드 상태: 클라우드에 더 최신 버전이 있음</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4379"/>
        <source>Cloud status: Diverged</source>
        <translation>클라우드 상태: 갈라짐</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4385"/>
        <source>Real-time</source>
        <translation>실시간</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4388"/>
        <location filename="../ui/main_window.py" line="4552"/>
        <source>Open a document first.</source>
        <translation>먼저 문서를 여세요.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4390"/>
        <source>Your member id:</source>
        <translation>내 멤버 ID:</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4427"/>
        <source>Real-time. {msg}</source>
        <translation>실시간. {msg}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4429"/>
        <source>Real-time: {msg}</source>
        <translation>실시간: {msg}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4536"/>
        <source>Merge</source>
        <translation>병합</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4547"/>
        <source>Save to Cloud</source>
        <translation>클라우드에 저장</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4569"/>
        <source>Open from Cloud</source>
        <translation>클라우드에서 열기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4587"/>
        <location filename="../ui/main_window.py" line="4704"/>
        <source>Cloud Version History</source>
        <translation>클라우드 버전 내역</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4674"/>
        <source>Saved to cloud.</source>
        <translation>클라우드에 저장했습니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4681"/>
        <source>Cloud Project</source>
        <translation>클라우드 프로젝트</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4683"/>
        <source>Recovered</source>
        <translation>복구됨</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4691"/>
        <source>Restored from cloud.</source>
        <translation>클라우드에서 복원했습니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4705"/>
        <source>No versions found for this project.</source>
        <translation>이 프로젝트의 버전을 찾을 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4732"/>
        <source>Cloud</source>
        <translation>클라우드</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4858"/>
        <source>Clear Selection</source>
        <translation>선택 영역 지우기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4973"/>
        <source>Flip Horizontal</source>
        <translation>가로로 뒤집기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4976"/>
        <source>Flip Vertical</source>
        <translation>세로로 뒤집기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4980"/>
        <source>Rotate 90° CW</source>
        <translation>시계 방향으로 90° 회전</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="4985"/>
        <source>Rotate 90° CCW</source>
        <translation>시계 반대 방향으로 90° 회전</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5006"/>
        <location filename="../ui/main_window.py" line="5011"/>
        <location filename="../ui/main_window.py" line="5019"/>
        <location filename="../ui/main_window.py" line="5030"/>
        <location filename="../ui/main_window.py" line="5037"/>
        <source>Scale Canvas</source>
        <translation>캔버스 배율 조정</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5066"/>
        <location filename="../ui/main_window.py" line="5071"/>
        <source>Canvas Size</source>
        <translation>캔버스 크기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5093"/>
        <source>Rotate (RotSprite)</source>
        <translation>회전 (RotSprite)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5268"/>
        <source>Pixel-perfect interface: the change applies the next time the application starts.</source>
        <translation>픽셀 퍼펙트 인터페이스: 변경 사항은 다음에 애플리케이션을 시작할 때 적용됩니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5396"/>
        <location filename="../ui/main_window.py" line="5407"/>
        <source>Open Tileset Image</source>
        <translation>타일셋 이미지 열기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5398"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>이미지 (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5422"/>
        <source>New Tileset</source>
        <translation>새 타일셋</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5432"/>
        <source>Add Tileset</source>
        <translation>타일셋 추가</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5442"/>
        <location filename="../ui/main_window.py" line="5493"/>
        <source>Attach Tileset</source>
        <translation>타일셋 연결</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5455"/>
        <source>Tilemap</source>
        <translation>타일맵</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5458"/>
        <source>Layer 1</source>
        <translation>레이어 1</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5465"/>
        <source>Add Tilemap</source>
        <translation>타일맵 추가</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5485"/>
        <source>Import Tilemap</source>
        <translation>타일맵 가져오기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5517"/>
        <source>Export Tiled Map</source>
        <translation>Tiled 맵 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5518"/>
        <source>There is no tilemap to export.</source>
        <translation>내보낼 타일맵이 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5546"/>
        <source>Exporting…</source>
        <translation>내보내는 중…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5551"/>
        <source>Exporting %1 of %2…</source>
        <translation>내보내는 중 (%1 / %2)…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5594"/>
        <source>Export Failed</source>
        <translation>내보내기 실패</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/main_window.py" line="5596"/>
        <source>%n export target(s) failed:
%2</source>
        <translation>
            <numerusform>내보내기 대상 %n개가 실패했습니다:
%2</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/main_window.py" line="5604"/>
        <source>Export complete (%n file(s)).</source>
        <translation>
            <numerusform>내보내기를 완료했습니다(파일 %n개).</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5654"/>
        <source>Automation</source>
        <translation>자동화</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5676"/>
        <source>Automation Error</source>
        <translation>자동화 오류</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5694"/>
        <source>Running automation…</source>
        <translation>자동화 실행 중…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5740"/>
        <source>Assistant edit</source>
        <translation>어시스턴트 편집</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5782"/>
        <source>PixelArt Creator</source>
        <translation>PixelArt Creator</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5784"/>
        <source>Tools</source>
        <translation>도구</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5785"/>
        <source>Palette</source>
        <translation>팔레트</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5786"/>
        <source>Symmetry</source>
        <translation>대칭</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5787"/>
        <source>Layers</source>
        <translation>레이어</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5788"/>
        <source>Timeline</source>
        <translation>타임라인</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5789"/>
        <source>Onion Skin</source>
        <translation>어니언 스킨</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5790"/>
        <source>Frame Tags</source>
        <translation>프레임 태그</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5791"/>
        <source>Palette Editor</source>
        <translation>팔레트 편집기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5792"/>
        <source>Constraints</source>
        <translation>제약 조건</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5793"/>
        <source>Shade Ramps</source>
        <translation>셰이드 그라데이션</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5795"/>
        <source>Analytics</source>
        <translation>분석</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5796"/>
        <source>Tileset Editor</source>
        <translation>타일셋 편집기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5797"/>
        <source>Tilemap Layers</source>
        <translation>타일맵 레이어</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5798"/>
        <source>Tilemap Canvas</source>
        <translation>타일맵 캔버스</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5799"/>
        <source>Batch Export</source>
        <translation>일괄 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5800"/>
        <source>Macros</source>
        <translation>매크로</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5801"/>
        <source>Script Runner</source>
        <translation>스크립트 실행기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5802"/>
        <source>Plugins</source>
        <translation>플러그인</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5803"/>
        <source>Batch Recolour</source>
        <translation>일괄 색상 변경</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5804"/>
        <source>Procedural Generation</source>
        <translation>절차적 생성</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5805"/>
        <source>Shared Projects</source>
        <translation>공유 프로젝트</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5806"/>
        <source>Comments</source>
        <translation>댓글</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5807"/>
        <source>Presence</source>
        <translation>접속 현황</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5808"/>
        <source>Branching</source>
        <translation>브랜칭</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5809"/>
        <source>Asset Library</source>
        <translation>에셋 라이브러리</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5810"/>
        <source>Asset Search</source>
        <translation>에셋 검색</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5811"/>
        <source>Asset Tagging</source>
        <translation>에셋 태그 지정</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5812"/>
        <source>Dependency Graph</source>
        <translation>종속성 그래프</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5813"/>
        <source>Asset Versions</source>
        <translation>에셋 버전</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5814"/>
        <source>Asset Reuse</source>
        <translation>에셋 재사용</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5818"/>
        <source>Real-Size Preview</source>
        <translation>실제 크기 미리 보기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5819"/>
        <source>Timelapse</source>
        <translation>타임랩스</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5820"/>
        <source>Reopened Recording</source>
        <translation>다시 연 기록</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5821"/>
        <source>Open documents</source>
        <translation>열린 문서</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5822"/>
        <source>Floating selection status</source>
        <translation>플로팅 선택 영역 상태</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5826"/>
        <source>Pencil</source>
        <translation>연필</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5827"/>
        <source>Eraser</source>
        <translation>지우개</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5828"/>
        <source>Fill</source>
        <translation>채우기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5829"/>
        <source>Line</source>
        <translation>선</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5830"/>
        <source>Colour picker</source>
        <translation>스포이드</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5831"/>
        <source>Rectangle</source>
        <translation>사각형</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5832"/>
        <source>Ellipse</source>
        <translation>타원</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5833"/>
        <source>Rectangle select</source>
        <translation>사각형 선택</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5834"/>
        <source>Lasso select</source>
        <translation>올가미 선택</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5835"/>
        <source>Magic wand</source>
        <translation>마술봉</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5836"/>
        <location filename="../ui/main_window.py" line="5895"/>
        <source>Dither</source>
        <translation>디더링</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5845"/>
        <source>&amp;New</source>
        <translation>새로 만들기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5846"/>
        <source>&amp;Open…</source>
        <translation>열기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5847"/>
        <source>&amp;Save</source>
        <translation>저장</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5848"/>
        <source>Save &amp;As…</source>
        <translation>다른 이름으로 저장…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5849"/>
        <source>&amp;Export…</source>
        <translation>내보내기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5850"/>
        <source>&amp;Close</source>
        <translation>닫기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5852"/>
        <source>&amp;Connect…</source>
        <translation>연결…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5853"/>
        <source>&amp;Disconnect</source>
        <translation>연결 끊기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5854"/>
        <source>&amp;Save to Cloud…</source>
        <translation>클라우드에 저장…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5855"/>
        <source>&amp;Open from Cloud…</source>
        <translation>클라우드에서 열기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5856"/>
        <source>&amp;Version History…</source>
        <translation>버전 내역…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5858"/>
        <source>Start &amp;Real-time…</source>
        <translation>실시간 시작…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5859"/>
        <source>Stop Real-&amp;time</source>
        <translation>실시간 중지</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5860"/>
        <source>Show &amp;Live Cursors</source>
        <translation>실시간 커서 표시</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5861"/>
        <source>Zoom &amp;In</source>
        <translation>확대</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5862"/>
        <source>Zoom &amp;Out</source>
        <translation>축소</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5863"/>
        <source>&amp;Fit to View</source>
        <translation>보기에 맞춤</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5864"/>
        <source>Fit to &amp;Content</source>
        <translation>내용에 맞춤</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5865"/>
        <source>Show &amp;Grid</source>
        <translation>격자 표시</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5866"/>
        <source>&amp;Snap to Grid</source>
        <translation>격자에 맞추기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5867"/>
        <source>&amp;Anti-aliasing Off</source>
        <translation>안티앨리어싱 끄기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5868"/>
        <source>&amp;Tiled Mode</source>
        <translation>타일 모드</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5869"/>
        <source>Light</source>
        <translation>라이트</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5870"/>
        <source>Dark</source>
        <translation>다크</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5873"/>
        <source>New Tileset from Image…</source>
        <translation>이미지에서 새 타일셋…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5874"/>
        <source>New Tilemap</source>
        <translation>새 타일맵</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5875"/>
        <source>Import Tiled JSON…</source>
        <translation>Tiled JSON 가져오기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5876"/>
        <source>Export Tiled JSON…</source>
        <translation>Tiled JSON 내보내기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5877"/>
        <source>Stamp Tool</source>
        <translation>스탬프 도구</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5878"/>
        <source>Place the selected tile</source>
        <translation>선택한 타일 배치</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5879"/>
        <source>Tile Eraser</source>
        <translation>타일 지우개</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5880"/>
        <source>Clear the target cell</source>
        <translation>대상 셀 비우기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5881"/>
        <source>Rectangle Fill</source>
        <translation>사각형 채우기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5883"/>
        <source>Fill a dragged rectangle with the selected tile</source>
        <translation>끌어서 지정한 사각형을 선택한 타일로 채우기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5885"/>
        <source>Flip Stamp Horizontal</source>
        <translation>스탬프 가로로 뒤집기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5886"/>
        <source>Flip Stamp Vertical</source>
        <translation>스탬프 세로로 뒤집기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5887"/>
        <source>Rotate Stamp 90° CW</source>
        <translation>스탬프를 시계 방향으로 90° 회전</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5891"/>
        <source>Fille&amp;d Shapes</source>
        <translation>채워진 도형</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5892"/>
        <source>&amp;Pixel Perfect</source>
        <translation>픽셀 퍼펙트</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5893"/>
        <source>Tolerance</source>
        <translation>허용 오차</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5894"/>
        <source>Magic-wand tolerance</source>
        <translation>마술봉 허용 오차</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5896"/>
        <source>Dither mode</source>
        <translation>디더링 모드</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5897"/>
        <source>Ordered (Bayer)</source>
        <translation>순서형 (Bayer)</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5898"/>
        <source>Floyd–Steinberg</source>
        <translation>Floyd–Steinberg</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5899"/>
        <source>&amp;Extract from Image…</source>
        <translation>이미지에서 추출…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5900"/>
        <source>Palette &amp;Swap…</source>
        <translation>팔레트 교체…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5902"/>
        <source>Convert to Inde&amp;xed</source>
        <translation>인덱스로 변환</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5903"/>
        <source>&amp;Convert to RGBA</source>
        <translation>RGBA로 변환</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5905"/>
        <source>Select &amp;All</source>
        <translation>모두 선택</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5906"/>
        <source>&amp;Deselect</source>
        <translation>선택 해제</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5907"/>
        <source>&amp;Invert Selection</source>
        <translation>선택 영역 반전</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5908"/>
        <source>&amp;Clear Selection</source>
        <translation>선택 영역 지우기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5910"/>
        <source>Flip &amp;Horizontal</source>
        <translation>가로로 뒤집기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5911"/>
        <source>Flip &amp;Vertical</source>
        <translation>세로로 뒤집기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5912"/>
        <source>Rotate 90° C&amp;W</source>
        <translation>시계 방향으로 90° 회전</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5913"/>
        <source>Rotate 90° &amp;CCW</source>
        <translation>시계 반대 방향으로 90° 회전</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5914"/>
        <source>&amp;Scale…</source>
        <translation>배율 조정…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5915"/>
        <source>Canvas S&amp;ize…</source>
        <translation>캔버스 크기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5916"/>
        <source>&amp;Rotate (RotSprite)…</source>
        <translation>회전 (RotSprite)…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5918"/>
        <source>Guides &amp;&amp; &amp;Rulers</source>
        <translation>안내선 &amp;&amp; 눈금자</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5919"/>
        <source>&amp;Isometric Grid</source>
        <translation>등각 격자</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5920"/>
        <source>&amp;Configure Isometric Grid…</source>
        <translation>등각 격자 설정…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5921"/>
        <source>&amp;Perspective Grid</source>
        <translation>원근 격자</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5922"/>
        <source>Confi&amp;gure Perspective…</source>
        <translation>원근 설정…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5923"/>
        <source>&amp;New View</source>
        <translation>새 보기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5924"/>
        <source>Reference &amp;Board</source>
        <translation>참조 보드</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5926"/>
        <source>&amp;File</source>
        <translation>파일</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5927"/>
        <source>&amp;Edit</source>
        <translation>편집</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5928"/>
        <source>&amp;Select</source>
        <translation>선택</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5929"/>
        <source>&amp;Image</source>
        <translation>이미지</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5930"/>
        <source>&amp;View</source>
        <translation>보기</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5931"/>
        <source>Visual Ai&amp;ds</source>
        <translation>시각 보조</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5932"/>
        <source>&amp;Palette</source>
        <translation>팔레트</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5933"/>
        <source>Tile&amp;map</source>
        <translation>타일맵</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5934"/>
        <source>&amp;Automation</source>
        <translation>자동화</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5935"/>
        <source>&amp;Cloud</source>
        <translation>클라우드</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5936"/>
        <source>&amp;Library</source>
        <translation>라이브러리</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5938"/>
        <source>&amp;Register Active Document…</source>
        <translation>활성 문서 등록…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5940"/>
        <source>Register &amp;Selection…</source>
        <translation>선택 영역 등록…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5941"/>
        <source>&amp;Import Asset…</source>
        <translation>에셋 가져오기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5942"/>
        <source>&amp;Export Asset…</source>
        <translation>에셋 내보내기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5943"/>
        <source>Export Project &amp;Bundle…</source>
        <translation>프로젝트 번들 내보내기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5944"/>
        <source>I&amp;mport Project Bundle…</source>
        <translation>프로젝트 번들 가져오기…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5945"/>
        <source>&amp;Theme</source>
        <translation>테마</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5946"/>
        <source>La&amp;nguage</source>
        <translation>언어</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5947"/>
        <source>&amp;Help</source>
        <translation>도움말</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5948"/>
        <source>&amp;User Guide</source>
        <translation>사용자 가이드</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5949"/>
        <source>&amp;About PixelArt Creator</source>
        <translation>PixelArt Creator 정보</translation>
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
        <translation>스타일</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5963"/>
        <source>Choose the visual style</source>
        <translation>시각 스타일 선택</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5966"/>
        <source>Use system &amp;font</source>
        <translation>시스템 글꼴 사용</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5968"/>
        <source>Use the operating system&apos;s interface font instead of Nifen Art</source>
        <translation>Nifen Art 대신 운영 체제의 인터페이스 글꼴 사용</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5971"/>
        <source>Pixel-perfect &amp;interface</source>
        <translation>픽셀 퍼펙트 인터페이스</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="5974"/>
        <source>Scale the interface by whole numbers only (next launch)</source>
        <translation>인터페이스를 정수 배율로만 조정 (다음 실행부터 적용)</translation>
    </message>
</context>
<context>
    <name>New_Document_Dialog</name>
    <message>
        <location filename="../ui/new_document_dialog.py" line="81"/>
        <source>New Document</source>
        <translation>새 문서</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="82"/>
        <source>New document dialog</source>
        <translation>새 문서 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="83"/>
        <source>Document width in pixels</source>
        <translation>문서 너비(픽셀)</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="84"/>
        <source>Document height in pixels</source>
        <translation>문서 높이(픽셀)</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="85"/>
        <source>Width (px)</source>
        <translation>너비 (px)</translation>
    </message>
    <message>
        <location filename="../ui/new_document_dialog.py" line="86"/>
        <source>Height (px)</source>
        <translation>높이 (px)</translation>
    </message>
</context>
<context>
    <name>Onion_Skin_Controls</name>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="108"/>
        <location filename="../ui/onion_skin_controls.py" line="176"/>
        <source>Previous frames</source>
        <extracomment>Emitted with the current :class:`OnionSettings` on any change (live update).</extracomment>
        <translation>이전 프레임</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="109"/>
        <location filename="../ui/onion_skin_controls.py" line="177"/>
        <source>Next frames</source>
        <translation>다음 프레임</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="135"/>
        <location filename="../ui/onion_skin_controls.py" line="183"/>
        <source>Previous-frame tint</source>
        <translation>이전 프레임 틴트</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="142"/>
        <location filename="../ui/onion_skin_controls.py" line="185"/>
        <source>Next-frame tint</source>
        <translation>다음 프레임 틴트</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="173"/>
        <source>Onion skin controls</source>
        <translation>어니언 스킨 컨트롤</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="174"/>
        <source>Enable onion skinning</source>
        <translation>어니언 스킨 사용</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="175"/>
        <source>Onion skin toggle</source>
        <translation>어니언 스킨 전환</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="178"/>
        <source>Previous onion frame count</source>
        <translation>이전 어니언 프레임 수</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="179"/>
        <source>How many earlier frames to ghost</source>
        <translation>흐리게 표시할 이전 프레임 수</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="180"/>
        <source>Next onion frame count</source>
        <translation>다음 어니언 프레임 수</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="181"/>
        <source>How many later frames to ghost</source>
        <translation>흐리게 표시할 이후 프레임 수</translation>
    </message>
    <message>
        <location filename="../ui/onion_skin_controls.py" line="182"/>
        <location filename="../ui/onion_skin_controls.py" line="184"/>
        <source>Tint…</source>
        <translation>틴트…</translation>
    </message>
</context>
<context>
    <name>Overwrite_Confirm_Dialog</name>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="76"/>
        <source>Overwrite Existing Pixels?</source>
        <translation>기존 픽셀을 덮어쓰시겠습니까?</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="77"/>
        <location filename="../ui/project_prefs_actions.py" line="223"/>
        <source>Overwrite existing pixels confirmation</source>
        <translation>기존 픽셀 덮어쓰기 확인</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="80"/>
        <source>The destination already has pixels on it. Continuing replaces that content. This can be undone.</source>
        <translation>대상에 이미 픽셀이 있습니다. 계속하면 해당 내용이 교체됩니다. 이 작업은 실행 취소할 수 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="84"/>
        <source>Overwrite warning</source>
        <translation>덮어쓰기 경고</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="85"/>
        <source>Don&apos;t ask again for this project</source>
        <translation>이 프로젝트에서는 다시 묻지 않음</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="87"/>
        <source>Suppress this confirmation for the current project</source>
        <translation>현재 프로젝트에서 이 확인 창 표시 안 함</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="91"/>
        <location filename="../ui/overwrite_confirm_dialog.py" line="92"/>
        <source>Continue</source>
        <translation>계속</translation>
    </message>
    <message>
        <location filename="../ui/overwrite_confirm_dialog.py" line="95"/>
        <location filename="../ui/overwrite_confirm_dialog.py" line="96"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
</context>
<context>
    <name>Palette_Analytics_View</name>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="171"/>
        <source>Palette Analytics</source>
        <extracomment>Edge of a colour-swatch icon in the table, px (presentation-only sizing). Debounce window (ms) coalescing a burst of deferred refresh requests into a single buffer scan (presentation-only timing, not a domain tuning value — cf. _SWATCH_PX). Short enough to feel instant when the dock becomes visible.</extracomment>
        <translation>팔레트 분석</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="172"/>
        <source>Palette analytics view</source>
        <translation>팔레트 분석 보기</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="173"/>
        <source>Colour usage counts</source>
        <translation>색상 사용 횟수</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="175"/>
        <source>Colour / Index</source>
        <translation>색상 / 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="175"/>
        <source>Usage count</source>
        <translation>사용 횟수</translation>
    </message>
    <message>
        <location filename="../ui/palette_analytics_view.py" line="177"/>
        <source>Refresh</source>
        <translation>새로 고침</translation>
    </message>
</context>
<context>
    <name>Palette_Constraint_Panel</name>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="60"/>
        <source>Constrain to Hardware Palette</source>
        <extracomment>Preset identifiers routed back to the shell (which owns the logic call). Emitted with a preset id (``PRESET_NES`` / ``PRESET_GAME_BOY``) on click.</extracomment>
        <translation>하드웨어 팔레트로 제한</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="61"/>
        <source>Palette constraint presets</source>
        <translation>팔레트 제한 프리셋</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="62"/>
        <source>Constrain to NES</source>
        <translation>NES로 제한</translation>
    </message>
    <message>
        <location filename="../ui/palette_constraint_panel.py" line="63"/>
        <source>Constrain to Game Boy</source>
        <translation>Game Boy로 제한</translation>
    </message>
</context>
<context>
    <name>Palette_Editor_Panel</name>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="226"/>
        <location filename="../ui/palette_editor_panel.py" line="230"/>
        <source>Add Colour</source>
        <extracomment>Edge of an editor swatch icon, px (presentation-only sizing). Maps a save/open dialog filter label to the ``palette_io`` format token. Emitted with an RGBA tuple when a swatch is selected (sets active colour).</extracomment>
        <translation>색상 추가</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="226"/>
        <source>The palette is full.</source>
        <translation>팔레트가 가득 찼습니다.</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="245"/>
        <source>Remove Colour</source>
        <translation>색상 제거</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="257"/>
        <location filename="../ui/palette_editor_panel.py" line="271"/>
        <source>Reorder Palette</source>
        <translation>팔레트 순서 변경</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="280"/>
        <location filename="../ui/palette_editor_panel.py" line="291"/>
        <source>Export Palette</source>
        <translation>팔레트 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="302"/>
        <location filename="../ui/palette_editor_panel.py" line="314"/>
        <location filename="../ui/palette_editor_panel.py" line="320"/>
        <source>Import Palette</source>
        <translation>팔레트 가져오기</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="334"/>
        <source>Palette Editor</source>
        <translation>팔레트 편집기</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="335"/>
        <source>Palette editor panel</source>
        <translation>팔레트 편집기 패널</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="336"/>
        <source>Editable colour palette</source>
        <translation>편집 가능한 색상 팔레트</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="337"/>
        <source>Add</source>
        <translation>추가</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="338"/>
        <source>Add the active colour</source>
        <translation>활성 색상 추가</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="339"/>
        <source>Remove</source>
        <translation>제거</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="340"/>
        <source>Move Up</source>
        <translation>위로 이동</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="341"/>
        <source>Move Down</source>
        <translation>아래로 이동</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="342"/>
        <source>Import…</source>
        <translation>가져오기…</translation>
    </message>
    <message>
        <location filename="../ui/palette_editor_panel.py" line="343"/>
        <source>Export…</source>
        <translation>내보내기…</translation>
    </message>
</context>
<context>
    <name>Palette_Panel</name>
    <message>
        <location filename="../ui/main_window.py" line="555"/>
        <source>Colour palette</source>
        <extracomment>Stable cloud recovery-slot key for the working document when no named cloud project is active (presentation-only identifier, not a domain tuning value). A sensible starter palette for a new document (usability, not a spec value). Swatch icon edge, px (presentation-only sizing, not a domain tuning value). Filename of the app-level Favourites store under AppConfigLocation (ADR-0004). Longest edge of a RotSprite preview thumbnail, px (presentation-only sizing, not a domain tuning value — cf. _SWATCH_PX). Tool ids whose stroke WRITES the active colour to the buffer: the value written is ``ctx.paint_value()`` / ``ctx.active_color`` itself, not merely a live-preview tint. These five run under REQ-P3-UI-006 leg (2) from a completed colour-hub pick; the other six tool ids (eraser, the three selection tools, picker, dither) hide the hub&apos;s wheel/value/numeric/harmony pick surface (``set_pick_surface_visible``) and never run from a hub pick, even a Favourites activation (SC-U006-13). Tool identifiers, not numeric tuning values, so this stays a set of the tools&apos; own ``tool_id`` class attributes rather than a `constants.py` entry. FIX 3 (2026-08-24 field defect, RC-1 follow-up). Every right-hand &quot;workflow&quot; panel is tabified into ONE dock group (``_add_workflow_dock``), and a Qt tab group&apos;s minimum width is the MAXIMUM over its members&apos; own content-derived ``minimumSizeHint()`` — verified up to 766 px for one panel (probe-runtime-canvas-20260824.py). That floor overrides FIX 1&apos;s ``CANVAS_PANE_WIDTH_RATIO`` split regardless of window width, so no per-panel edit can fix it: the override has to happen once, here, at the single place every workflow dock is created. Overriding ``QWidget.setMinimumWidth()`` on the panel (verified empirically to lower ``QDockWidget.minimumSizeHint()`` even though the panel&apos;s own ``minimumSizeHint()`` is unchanged and content can clip below it — Qt&apos;s dock layout consults the explicit minimum, not the generic ``QLayoutItem.minimumSize()`` ``expandedTo`` rule) is presentation sizing, not a domain tuning value, so it stays local exactly like _SWATCH_PX / _PREVIEW_MAX_EDGE_PX above — see the FIX-3 report note requesting this be promoted to logic/constants.py (a logic-layer surface) as e.g. ``WORKFLOW_DOCK_MIN_WIDTH_PX`` rather than reached into from here. FIX 3 (2026-08-24 field defect). Bound on ``Main_Window._settle_width()``&apos;s event-flush loop (presentation-only startup timing, not a domain tuning value — cf. _SWATCH_PX / _PREVIEW_MAX_EDGE_PX above). Observed settling in 2 passes on the probe&apos;s offscreen run; this leaves generous headroom without risking an unbounded/hanging wait on a layout that never settles. FIX 1 (2026-08-24 field defect, RC-1 follow-up on the earlier FIX 1). The window was never given an explicit default size; Qt sized it to its layout hint, which on a real desktop happened to land the canvas at only ~10% of the window even after the FIX 1/FIX 3 dock-splitting work above, because that split is a RATIO of whatever width the window already has -- a window with no deliberate width defeats a width RATIO. Fraction of the primary screen&apos;s *available* geometry (excludes taskbars/docks) the window claims on first launch, absent any saved geometry restore (presentation-only startup sizing, not a domain tuning value -- cf. _WORKFLOW_DOCK_MIN_WIDTH_PX / _SWATCH_PX above). Report note: a candidate for promotion to logic/constants.py as e.g. DEFAULT_LAUNCH_SIZE_RATIO, exactly like that floor&apos;s own promotion note -- left local here on the same precedent.</extracomment>
        <translation>색상 팔레트</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="556"/>
        <source>Palette panel</source>
        <translation>팔레트 패널</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="557"/>
        <source>Colour mode</source>
        <translation>색상 모드</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="562"/>
        <source>Mode: Indexed</source>
        <translation>모드: 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="564"/>
        <source>Mode: RGBA</source>
        <translation>모드: RGBA</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="566"/>
        <source>Mode: —</source>
        <translation>모드: —</translation>
    </message>
</context>
<context>
    <name>Palette_Swap_Dialog</name>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="106"/>
        <source>Palette Swap</source>
        <translation>팔레트 교체</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="107"/>
        <source>Palette swap dialog</source>
        <translation>팔레트 교체 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="108"/>
        <source>From index</source>
        <translation>원래 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="109"/>
        <source>To index</source>
        <translation>바꿀 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="110"/>
        <source>Source index</source>
        <translation>원본 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="111"/>
        <source>Target index</source>
        <translation>대상 인덱스</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="112"/>
        <source>Add</source>
        <translation>추가</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="113"/>
        <source>Remove</source>
        <translation>제거</translation>
    </message>
    <message>
        <location filename="../ui/palette_swap_dialog.py" line="114"/>
        <source>Index remap entries</source>
        <translation>인덱스 재매핑 항목</translation>
    </message>
</context>
<context>
    <name>Playback_Controls</name>
    <message>
        <location filename="../ui/playback_controls.py" line="364"/>
        <source>Loop</source>
        <extracomment>Type of the per-tick step yielded by the sequencing engine: (index, ms). Emitted with the frame index to display on each playback tick (scrub-like). Emitted ``True`` when playback becomes active, ``False`` when it halts. The shell suppresses onion skinning while active (CL-11).</extracomment>
        <translation>반복</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="365"/>
        <source>Once</source>
        <translation>한 번</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="366"/>
        <source>Ping-Pong</source>
        <translation>핑퐁</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="367"/>
        <source>Reverse</source>
        <translation>역방향</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="372"/>
        <source>Playback controls</source>
        <translation>재생 컨트롤</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="373"/>
        <location filename="../ui/playback_controls.py" line="375"/>
        <source>Play</source>
        <translation>재생</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="374"/>
        <source>Play (Space)</source>
        <translation>재생 (Space)</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="376"/>
        <location filename="../ui/playback_controls.py" line="378"/>
        <source>Pause</source>
        <translation>일시 중지</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="377"/>
        <source>Pause (Space)</source>
        <translation>일시 중지 (Space)</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="379"/>
        <location filename="../ui/playback_controls.py" line="381"/>
        <source>Stop</source>
        <translation>중지</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="380"/>
        <source>Stop and return to the start frame</source>
        <translation>중지하고 시작 프레임으로 돌아가기</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="382"/>
        <source>Playback mode</source>
        <translation>재생 모드</translation>
    </message>
    <message>
        <location filename="../ui/playback_controls.py" line="383"/>
        <source>Global playback mode</source>
        <translation>전체 재생 모드</translation>
    </message>
</context>
<context>
    <name>Plugin_Manager_Panel</name>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="138"/>
        <source>Add Plugin Manifest</source>
        <extracomment>Enabled plugin handles keyed by plugin name (view/session state).</extracomment>
        <translation>플러그인 매니페스트 추가</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="140"/>
        <source>Manifest files (*.json)</source>
        <translation>매니페스트 파일 (*.json)</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="149"/>
        <source>Install Failed</source>
        <translation>설치 실패</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="176"/>
        <source>No Manifest</source>
        <translation>매니페스트 없음</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="178"/>
        <source>This plugin has no loaded manifest. Use Add Manifest to load its declared permissions before enabling it.</source>
        <translation>이 플러그인에는 불러온 매니페스트가 없습니다. 사용하기 전에 매니페스트 추가를 선택하여 선언된 권한을 불러오세요.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="185"/>
        <source>Enable Plugin</source>
        <translation>플러그인 사용</translation>
    </message>
    <message>
        <source>Enable %1 and grant it these permissions?

%2

The plugin runs sandboxed and can only edit through reversible commands. It cannot reach the UI, filesystem, or network.</source>
        <translation type="vanished">%1 플러그인을 사용하고 다음 권한을 부여하시겠습니까?

%2

플러그인은 샌드박스에서 실행되며 되돌릴 수 있는 명령으로만 편집할 수 있습니다. UI, 파일 시스템, 네트워크에는 접근할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="187"/>
        <source>Enable %1 and approve these permissions?

%2

Plugins are not isolated from your computer. Only enable plugins you trust. These permissions are checked only on requests made through the app&apos;s permission object, not on what the plugin&apos;s own code can do.</source>
        <translation>%1 플러그인을 사용 설정하고 다음 권한을 승인하시겠습니까?

%2

플러그인은 사용자의 컴퓨터와 격리되어 있지 않습니다. 신뢰하는 플러그인만 사용 설정하세요. 이 권한은 앱의 권한 객체를 통한 요청에서만 확인되며, 플러그인 자체의 코드가 할 수 있는 일에는 해당하지 않습니다.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="203"/>
        <source>Enable Failed</source>
        <translation>사용 설정 실패</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="234"/>
        <source>enabled</source>
        <translation>사용 중</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="234"/>
        <source>disabled</source>
        <translation>사용 안 함</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="235"/>
        <source>%1 v%2 — %3</source>
        <translation>%1 v%2 — %3</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="264"/>
        <source>(no manifest loaded — permissions unknown)</source>
        <translation>(불러온 매니페스트 없음 — 권한을 알 수 없음)</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="278"/>
        <source>Read the open document</source>
        <translation>열린 문서 읽기</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="280"/>
        <source>Change the document through the app&apos;s commands</source>
        <translation>앱의 명령을 통해 문서 변경</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="282"/>
        <source>Add new script commands</source>
        <translation>새 스크립트 명령 추가</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="284"/>
        <source>Add new procedural generation commands</source>
        <translation>새 절차적 생성 명령 추가</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="299"/>
        <source>Select a plugin to view its permissions.</source>
        <translation>권한을 보려면 플러그인을 선택하세요.</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="309"/>
        <source>Refresh</source>
        <translation>새로 고침</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="310"/>
        <source>Add Manifest…</source>
        <translation>매니페스트 추가…</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="311"/>
        <source>Enable</source>
        <translation>사용</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="312"/>
        <source>Disable</source>
        <translation>사용 안 함</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="313"/>
        <source>Declared permissions:</source>
        <translation>선언된 권한:</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="314"/>
        <source>Plugin manager</source>
        <translation>플러그인 관리자</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="315"/>
        <source>Discovered and installed plugins</source>
        <translation>검색되었거나 설치된 플러그인</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="316"/>
        <source>Selected plugin permissions</source>
        <translation>선택한 플러그인의 권한</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="317"/>
        <source>Refresh the plugin list</source>
        <translation>플러그인 목록 새로 고침</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="318"/>
        <source>Add a plugin manifest</source>
        <translation>플러그인 매니페스트 추가</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="319"/>
        <source>Enable the selected plugin</source>
        <translation>선택한 플러그인 사용</translation>
    </message>
    <message>
        <location filename="../ui/plugin_manager_panel.py" line="320"/>
        <source>Disable the selected plugin</source>
        <translation>선택한 플러그인 사용 안 함</translation>
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
        <translation>접속 현황</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="102"/>
        <source>Open a shared project first.</source>
        <translation>먼저 공유 프로젝트를 여세요.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="110"/>
        <source>Enter your member id to announce presence.</source>
        <translation>접속 상태를 알리려면 멤버 ID를 입력하세요.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="164"/>
        <source>Members currently present in the shared project. Presence is ephemeral and is never saved into the project file.</source>
        <translation>공유 프로젝트에 현재 접속 중인 멤버입니다. 접속 현황은 일시적이며 프로젝트 파일에 저장되지 않습니다.</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="168"/>
        <location filename="../ui/presence_panel.py" line="169"/>
        <source>Your member id</source>
        <translation>내 멤버 ID</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="170"/>
        <source>Join</source>
        <translation>참여</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="171"/>
        <source>Announce your presence</source>
        <translation>내 접속 상태 알리기</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="172"/>
        <source>Leave</source>
        <translation>나가기</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="173"/>
        <source>Clear your presence</source>
        <translation>내 접속 상태 지우기</translation>
    </message>
    <message>
        <location filename="../ui/presence_panel.py" line="174"/>
        <source>Present members</source>
        <translation>접속 중인 멤버</translation>
    </message>
</context>
<context>
    <name>Prewarm_Indicator</name>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="81"/>
        <source>Playback preparation progress</source>
        <extracomment>Emitted when the user cancels the pre-warm (wired to Stop by the shell).</extracomment>
        <translation>재생 준비 진행률</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="82"/>
        <source>Preparing playback…</source>
        <translation>재생 준비 중…</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="83"/>
        <source>Frames prepared</source>
        <translation>준비된 프레임</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="84"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
    <message>
        <location filename="../ui/prewarm_indicator.py" line="85"/>
        <location filename="../ui/prewarm_indicator.py" line="86"/>
        <source>Cancel playback preparation</source>
        <translation>재생 준비 취소</translation>
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
        <translation>실행 중…</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="158"/>
        <source>Done</source>
        <translation>완료</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="159"/>
        <source>Idle</source>
        <translation>대기 중</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="174"/>
        <source>Procedural Generation</source>
        <translation>절차적 생성</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="197"/>
        <source>Value noise</source>
        <translation>값 노이즈</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="198"/>
        <source>Gradient noise</source>
        <translation>그라데이션 노이즈</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="199"/>
        <source>OpenSimplex noise</source>
        <translation>OpenSimplex 노이즈</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="200"/>
        <source>Cellular automata</source>
        <translation>셀룰러 오토마타</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="201"/>
        <source>Dithered gradient</source>
        <translation>디더링 그라데이션</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="207"/>
        <source>Algorithm</source>
        <translation>알고리즘</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="208"/>
        <source>Seed</source>
        <translation>시드</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="209"/>
        <source>Width</source>
        <translation>너비</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="210"/>
        <source>Height</source>
        <translation>높이</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="211"/>
        <source>Frequency</source>
        <translation>주파수</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="212"/>
        <source>Octaves</source>
        <translation>옥타브</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="215"/>
        <source>Generate</source>
        <translation>생성</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="217"/>
        <source>Procedural generation</source>
        <translation>절차적 생성</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="218"/>
        <source>Generation algorithm</source>
        <translation>생성 알고리즘</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="219"/>
        <source>Random seed</source>
        <translation>무작위 시드</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="220"/>
        <source>Output width in pixels</source>
        <translation>출력 너비(픽셀)</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="221"/>
        <source>Output height in pixels</source>
        <translation>출력 높이(픽셀)</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="222"/>
        <source>Noise base frequency</source>
        <translation>노이즈 기본 주파수</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="223"/>
        <source>Noise octaves</source>
        <translation>노이즈 옥타브</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="224"/>
        <source>Generate content</source>
        <translation>콘텐츠 생성</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="225"/>
        <source>Progress</source>
        <translation>진행률</translation>
    </message>
    <message>
        <location filename="../ui/procgen_panel.py" line="226"/>
        <source>Generation progress</source>
        <translation>생성 진행률</translation>
    </message>
</context>
<context>
    <name>Provider_Config_Dialog</name>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="258"/>
        <source>The OS keyring is unavailable; install the &apos;assistant_live&apos; extra to store an API key. The provider settings were saved.</source>
        <extracomment>Provider-kind identifiers. These double as the keyring service namespace segment (``pixelart-creator:assistant:{provider}``) and the adapter&apos;s ``provider`` arg, so the key stored here is the key the adapter loads. Module-local vocabulary (ADR-0001), not a numeric constant. The keyring account the single-user key is stored under (matches ``data/llm``&apos;s ``_DEFAULT_ACCOUNT`` so the adapter loads the same credential). :class:`QSettings` group + keys for the NON-SECRET configuration only. Sensible default endpoints per provider kind (the user may override).</extracomment>
        <translation>OS 키링을 사용할 수 없습니다. API 키를 저장하려면 &apos;assistant_live&apos; 추가 구성 요소를 설치하세요. 제공자 설정은 저장되었습니다.</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="269"/>
        <source>Could not store the API key: {0}</source>
        <translation>API 키를 저장할 수 없습니다: {0}</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="282"/>
        <source>Configure AI Assistant Provider</source>
        <translation>AI 어시스턴트 제공자 구성</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="283"/>
        <source>AI assistant provider configuration</source>
        <translation>AI 어시스턴트 제공자 구성 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="284"/>
        <source>OpenAI-compatible</source>
        <translation>OpenAI 호환</translation>
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
        <translation>제공자</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="288"/>
        <source>Endpoint URL</source>
        <translation>엔드포인트 URL</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="289"/>
        <source>Provider endpoint URL</source>
        <translation>제공자 엔드포인트 URL</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="290"/>
        <source>https://…</source>
        <translation>https://…</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="291"/>
        <source>Model</source>
        <translation>모델</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="292"/>
        <source>Model name</source>
        <translation>모델 이름</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="293"/>
        <source>e.g. gpt-4o-mini</source>
        <translation>예: gpt-4o-mini</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="294"/>
        <source>API key</source>
        <translation>API 키</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="295"/>
        <source>API key (stored in the OS keyring)</source>
        <translation>API 키 (OS 키링에 저장됨)</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="297"/>
        <source>Leave blank to keep the existing key</source>
        <translation>기존 키를 유지하려면 비워 두세요</translation>
    </message>
    <message>
        <location filename="../ui/provider_config_dialog.py" line="301"/>
        <source>The API key is stored only in your OS keyring — never in a project file or a log.</source>
        <translation>API 키는 OS 키링에만 저장되며 프로젝트 파일이나 로그에는 저장되지 않습니다.</translation>
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
        <translation>실제 크기 보정</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="115"/>
        <source>Hold a ruler against the bar below and enter its measured length so real size matches your screen.</source>
        <translation>아래 막대에 자를 대고 측정한 길이를 입력하면 실제 크기가 화면에 맞게 조정됩니다.</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="119"/>
        <source>Measured length</source>
        <translation>측정 길이</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="121"/>
        <source>Measured calibration bar length in millimetres</source>
        <translation>측정한 보정 막대 길이(밀리미터)</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="123"/>
        <source>Calibration bar</source>
        <translation>보정 막대</translation>
    </message>
</context>
<context>
    <name>Real_Size_Preview_Window</name>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="258"/>
        <source>calibrated</source>
        <extracomment>A user-calibrated DPI override (``None`` =&gt; use the queried physical DPI).</extracomment>
        <translation>보정됨</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="258"/>
        <source>screen</source>
        <translation>화면</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="261"/>
        <source>Real size: {0:.0f} PPI ({1}), scale {2:.2f}×</source>
        <translation>실제 크기: {0:.0f} PPI ({1}), 배율 {2:.2f}×</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="269"/>
        <source>Real-Size Preview</source>
        <translation>실제 크기 미리 보기</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="270"/>
        <source>Real-size preview</source>
        <translation>실제 크기 미리 보기</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="271"/>
        <source>Real-size document preview</source>
        <translation>실제 크기 문서 미리 보기</translation>
    </message>
    <message>
        <location filename="../ui/real_size_preview_window.py" line="272"/>
        <source>Calibrate…</source>
        <translation>보정…</translation>
    </message>
</context>
<context>
    <name>Realtime_Client</name>
    <message>
        <location filename="../ui/realtime_worker.py" line="255"/>
        <source>no real-time transport configured</source>
        <extracomment>Builds a fresh :class:`TransportPort` on connect, called **on the worker thread**. Injectable so a test (or the out-of-CI WebSocket path) swaps the loopback transport with no UI change — the port is the provider-agnostic seam (REQ-P10-DATA-007). Poll cadence, seconds — how often the worker drains inbound frames when idle. A presentation-loop timing (not a domain tuning value, so module-local): outbound sends wake the loop immediately via the queue, so this only bounds inbound latency. Bounded wait for the worker thread to join on teardown, ms (presentation-only timing, mirrors ``cloud_worker._CLOUD_SHUTDOWN_WAIT_MS``). Past this the daemon backstop guarantees the thread cannot block interpreter exit. Sentinel pushed to the outbound queue to wake a blocking ``get`` on stop. ``(document_id, raw_frame_bytes)`` — one inbound, transport-validated framed message; the consumer routes it with ``sync_protocol.decode_message``. ``(connected,)`` — the worker joined (``True``) the document&apos;s relay. ``(kind,)`` — the worker hit a transport error (surfaced, never a crash); the payload is a ``FailureKind`` value, translated on the GUI thread. emitted once when the worker loop has fully exited (thread is ending). ``(document_id, raw_frame_bytes)`` — one inbound framed message (GUI thread). ``(connected,)`` — the real-time connection state changed. ``(message, is_failure)`` — a transport error occurred (surfaced to the user). ``is_failure`` is ``True`` for a failure sentence and ``False`` for a reason that is not one (no transport configured); the status bar frames the two differently.</extracomment>
        <translation>구성된 실시간 전송 수단이 없습니다.</translation>
    </message>
</context>
<context>
    <name>Recovery_Prompt</name>
    <message>
        <location filename="../ui/recovery_prompt.py" line="74"/>
        <source>Recover Unsaved Work</source>
        <translation>저장하지 않은 작업 복구</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="77"/>
        <source>Unsaved work from a previous session was found. Recover it into a new tab? Your last explicit save is not affected.</source>
        <translation>이전 세션에서 저장하지 않은 작업을 찾았습니다. 새 탭으로 복구하시겠습니까? 마지막으로 직접 저장한 내용에는 영향이 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="81"/>
        <source>Recover</source>
        <translation>복구</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="82"/>
        <source>Discard</source>
        <translation>폐기</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="83"/>
        <source>Recover unsaved work</source>
        <translation>저장하지 않은 작업 복구</translation>
    </message>
    <message>
        <location filename="../ui/recovery_prompt.py" line="84"/>
        <source>Discard unsaved work</source>
        <translation>저장하지 않은 작업 폐기</translation>
    </message>
</context>
<context>
    <name>Reference_Board</name>
    <message>
        <location filename="../ui/reference_board.py" line="320"/>
        <source>Reference board full</source>
        <extracomment>Emitted with the picked RGBA tuple when a plain wheel notch travels the shared Favourites cursor (REQ-IS-UI-008, D-16). The board never touches the document/buffers/undo stack (REQ-P9-UI-010); this only sets the app-wide active colour/palette state, same as every other surface. The persisted Favourites model bound via :meth:`set_favourites_model` (D-16); ``None`` until the shell binds one.</extracomment>
        <translation>참조 보드가 가득 참</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/reference_board.py" line="322"/>
        <source>The board already holds the maximum of %n images.</source>
        <translation>
            <numerusform>보드에는 이미 최대 %n개의 이미지가 있습니다.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="332"/>
        <source>Cannot load image</source>
        <translation>이미지를 불러올 수 없음</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="333"/>
        <source>The file could not be read as an image: {0}</source>
        <translation>파일을 이미지로 읽을 수 없습니다: {0}</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="404"/>
        <source>Save Reference Board</source>
        <translation>참조 보드 저장</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="406"/>
        <location filename="../ui/reference_board.py" line="426"/>
        <source>Reference board (*.pixboard)</source>
        <translation>참조 보드 (*.pixboard)</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="415"/>
        <source>Save failed</source>
        <translation>저장 실패</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="424"/>
        <source>Open Reference Board</source>
        <translation>참조 보드 열기</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="436"/>
        <source>Open failed</source>
        <translation>열기 실패</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="447"/>
        <source>Add Reference Image</source>
        <translation>참조 이미지 추가</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="449"/>
        <source>Images (*.png *.jpg *.jpeg *.bmp *.gif)</source>
        <translation>이미지 (*.png *.jpg *.jpeg *.bmp *.gif)</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="515"/>
        <source>Reference Board</source>
        <translation>참조 보드</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="516"/>
        <source>Reference board</source>
        <translation>참조 보드</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="517"/>
        <source>Reference board canvas</source>
        <translation>참조 보드 캔버스</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="518"/>
        <source>Add Image…</source>
        <translation>이미지 추가…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="519"/>
        <source>Save…</source>
        <translation>저장…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="520"/>
        <source>Open…</source>
        <translation>열기…</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="521"/>
        <source>Always on Top</source>
        <translation>항상 위에 표시</translation>
    </message>
</context>
<context>
    <name>Reference_Item</name>
    <message>
        <location filename="../ui/reference_board.py" line="247"/>
        <source>Raise</source>
        <extracomment>Per-wheel-notch board zoom step. Corner grab-handle edge, in item-local px (REQ-P9-UI-006 resize gesture). No matching UI-metric constant exists in ``logic/constants.py`` today (gap reported in this task&apos;s EXIT_STATUS); this module already keeps its own UI-only metrics locally (see ``_BOARD_ZOOM_STEP`` above), so the same convention is followed here rather than inlining a literal (S12). Minimum absolute scale factor a corner-drag resize may reach (guards against a degenerate/zero-size or inverted reference item). Opposite-corner anchor used while resizing (the anchor stays fixed).</extracomment>
        <translation>앞으로 가져오기</translation>
    </message>
    <message>
        <location filename="../ui/reference_board.py" line="250"/>
        <source>Lower</source>
        <translation>뒤로 보내기</translation>
    </message>
</context>
<context>
    <name>RotSprite_Dialog</name>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="93"/>
        <source>No preview</source>
        <extracomment>Angle input bounds, degrees (a full turn either way; not a domain tuning value). Preview label edge, px (presentation-only sizing). Renders a preview :class:`QImage` for a candidate angle (or ``None``).</extracomment>
        <translation>미리 보기 없음</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="106"/>
        <source>Rotate (RotSprite)</source>
        <translation>회전 (RotSprite)</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="107"/>
        <source>RotSprite rotation dialog</source>
        <translation>RotSprite 회전 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="108"/>
        <source>Rotation angle in degrees</source>
        <translation>회전 각도(도)</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="109"/>
        <source>Rotation preview</source>
        <translation>회전 미리 보기</translation>
    </message>
    <message>
        <location filename="../ui/rotsprite_dialog.py" line="110"/>
        <source>Angle (deg)</source>
        <translation>각도 (도)</translation>
    </message>
</context>
<context>
    <name>Ruler_Strip</name>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="347"/>
        <source>Horizontal ruler</source>
        <extracomment>z-order in the aid band, just below the grid overlays so guides read under grids. Ruler strip thickness in device-independent px (presentation sizing). Default overlay/ruler colours (overridden by the theme&apos;s role colours, 025). Emitted ``(orientation, doc_position)`` when a guide is dragged out.</extracomment>
        <translation>가로 눈금자</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="349"/>
        <source>Drag down to create a horizontal guide</source>
        <translation>아래로 끌어 가로 안내선 만들기</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="352"/>
        <source>Vertical ruler</source>
        <translation>세로 눈금자</translation>
    </message>
    <message>
        <location filename="../ui/guides_rulers_overlay.py" line="354"/>
        <source>Drag right to create a vertical guide</source>
        <translation>오른쪽으로 끌어 세로 안내선 만들기</translation>
    </message>
</context>
<context>
    <name>Scale_Dialog</name>
    <message>
        <location filename="../ui/transform_dialog.py" line="111"/>
        <source>Scale Canvas</source>
        <translation>캔버스 배율 조정</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="112"/>
        <source>Scale canvas dialog</source>
        <translation>캔버스 배율 조정 대화 상자</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="113"/>
        <source>Scale factor</source>
        <translation>배율</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="114"/>
        <source>Target width in pixels</source>
        <translation>대상 너비(픽셀)</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="115"/>
        <source>Target height in pixels</source>
        <translation>대상 높이(픽셀)</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="116"/>
        <source>Factor</source>
        <translation>배율</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="117"/>
        <source>Width (px)</source>
        <translation>너비 (px)</translation>
    </message>
    <message>
        <location filename="../ui/transform_dialog.py" line="118"/>
        <source>Height (px)</source>
        <translation>높이 (px)</translation>
    </message>
</context>
<context>
    <name>Script_Runner_Panel</name>
    <message>
        <location filename="../ui/script_runner_panel.py" line="114"/>
        <source>Running…</source>
        <extracomment>A compact, copy-pasteable example so the empty editor is self-documenting. ``(ops, label)`` — the host should dispatch these DSL ops on the worker as one undoable grouped command (REQ-P8-UI-004/-009).</extracomment>
        <translation>실행 중…</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="116"/>
        <source>Done</source>
        <translation>완료</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="117"/>
        <source>Idle</source>
        <translation>대기 중</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="134"/>
        <source>Invalid JSON: %1</source>
        <translation>잘못된 JSON: %1</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="141"/>
        <source>A script must be a JSON array of steps.</source>
        <translation>스크립트는 단계로 이루어진 JSON 배열이어야 합니다.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="146"/>
        <source>Each step needs a &apos;name&apos; and optional &apos;params&apos;/&apos;seed&apos;.</source>
        <translation>각 단계에는 &apos;name&apos;이 필요하며 &apos;params&apos;와 &apos;seed&apos;는 선택 사항입니다.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="152"/>
        <source>Step &apos;name&apos; must be a string.</source>
        <translation>단계의 &apos;name&apos;은 문자열이어야 합니다.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="154"/>
        <source>Step &apos;params&apos; must be an object.</source>
        <translation>단계의 &apos;params&apos;는 객체여야 합니다.</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="165"/>
        <source>Script Error</source>
        <translation>스크립트 오류</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="169"/>
        <location filename="../ui/script_runner_panel.py" line="191"/>
        <source>Run Script</source>
        <translation>스크립트 실행</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="190"/>
        <source>DSL script (JSON list of steps):</source>
        <translation>DSL 스크립트 (단계의 JSON 목록):</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="192"/>
        <source>Script runner</source>
        <translation>스크립트 실행기</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="193"/>
        <source>Script source</source>
        <translation>스크립트 소스</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="194"/>
        <source>Run the script</source>
        <translation>스크립트 실행</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="195"/>
        <source>Progress</source>
        <translation>진행률</translation>
    </message>
    <message>
        <location filename="../ui/script_runner_panel.py" line="196"/>
        <source>Script run progress</source>
        <translation>스크립트 실행 진행률</translation>
    </message>
</context>
<context>
    <name>Shade_Ramp_Picker</name>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="150"/>
        <source>Shade Ramps</source>
        <extracomment>Edge of a ramp swatch button, px (presentation-only sizing). Emitted with an RGBA tuple when a ramp swatch is activated. Emitted with a list of RGBA colours when a whole ramp is added.</extracomment>
        <translation>셰이드 그라데이션</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="151"/>
        <source>Shade ramp picker</source>
        <translation>셰이드 그라데이션 선택기</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="152"/>
        <source>Shades (toward black)</source>
        <translation>셰이드 (검정 방향)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="153"/>
        <source>Tints (toward white)</source>
        <translation>틴트 (흰색 방향)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="154"/>
        <source>Tones (toward grey)</source>
        <translation>톤 (회색 방향)</translation>
    </message>
    <message>
        <location filename="../ui/shade_ramp_picker.py" line="156"/>
        <source>Add to Palette</source>
        <translation>팔레트에 추가</translation>
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
        <translation>공유 프로젝트</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="145"/>
        <source>Member %1 is already in the roster.</source>
        <translation>이미 명단에 있는 멤버입니다: %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/shared_projects_panel.py" line="153"/>
        <source>A shared project may have at most %n members.</source>
        <translation>
            <numerusform>공유 프로젝트의 멤버는 최대 %n명까지 가능합니다.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="184"/>
        <source>Enter a shared-project name first.</source>
        <translation>먼저 공유 프로젝트 이름을 입력하세요.</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="191"/>
        <source>Add at least one member before sharing.</source>
        <translation>공유하기 전에 멤버를 한 명 이상 추가하세요.</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="245"/>
        <source>Owner</source>
        <translation>소유자</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="246"/>
        <source>Editor</source>
        <translation>편집자</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="247"/>
        <source>Viewer</source>
        <translation>뷰어</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="252"/>
        <source>Shared projects</source>
        <translation>공유 프로젝트</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="253"/>
        <source>Shared-project name:</source>
        <translation>공유 프로젝트 이름:</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="254"/>
        <source>e.g. team-sprite</source>
        <translation>예: team-sprite</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="255"/>
        <source>Shared-project name</source>
        <translation>공유 프로젝트 이름</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="256"/>
        <location filename="../ui/shared_projects_panel.py" line="257"/>
        <source>Member id to invite</source>
        <translation>초대할 멤버 ID</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="258"/>
        <source>Member role</source>
        <translation>멤버 역할</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="261"/>
        <source>Add Member</source>
        <translation>멤버 추가</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="262"/>
        <source>Add member to roster</source>
        <translation>명단에 멤버 추가</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="263"/>
        <source>Roster to share</source>
        <translation>공유할 멤버 명단</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="264"/>
        <source>Current members</source>
        <translation>현재 멤버</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="265"/>
        <source>Remove</source>
        <translation>제거</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="266"/>
        <source>Remove selected member</source>
        <translation>선택한 멤버 제거</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="267"/>
        <source>Share / Update</source>
        <translation>공유 / 업데이트</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="268"/>
        <source>Share or update the project</source>
        <translation>프로젝트 공유 또는 업데이트</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="269"/>
        <source>Member</source>
        <translation>멤버</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="269"/>
        <source>Role</source>
        <translation>역할</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="272"/>
        <source>Editable member roster</source>
        <translation>편집 가능한 멤버 명단</translation>
    </message>
    <message>
        <location filename="../ui/shared_projects_panel.py" line="273"/>
        <source>Shared member list</source>
        <translation>공유 멤버 목록</translation>
    </message>
</context>
<context>
    <name>Symmetry_Panel</name>
    <message>
        <location filename="../ui/symmetry_panel.py" line="158"/>
        <source>Off</source>
        <extracomment>Emitted with the newly selected :class:`SymmetryAxis`. Emitted with the mirror centre as ``Optional[Tuple[int, int]]`` once the user edits a position spinbox (``None`` = unset, ``mirror`` defaults to the canvas centre itself, CL-9). Never emitted from programmatic :meth:`set_canvas_size` calls, so a resize alone never fabricates a user-authored position. Axis order shown in the combo (value stored in the item&apos;s user data).</extracomment>
        <translation>끔</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="159"/>
        <source>Vertical</source>
        <translation>세로</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="160"/>
        <source>Horizontal</source>
        <translation>가로</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="161"/>
        <source>Both</source>
        <translation>둘 다</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="162"/>
        <source>Diagonal</source>
        <translation>대각선</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="166"/>
        <source>Symmetry</source>
        <translation>대칭</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="167"/>
        <source>Axis position</source>
        <translation>축 위치</translation>
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
        <translation>중앙으로 재설정</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="171"/>
        <source>Symmetry axis panel</source>
        <translation>대칭축 패널</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="172"/>
        <source>Symmetry axis</source>
        <translation>대칭축</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="173"/>
        <source>Symmetry axis position X</source>
        <translation>대칭축 위치 X</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="174"/>
        <source>Symmetry axis position Y</source>
        <translation>대칭축 위치 Y</translation>
    </message>
    <message>
        <location filename="../ui/symmetry_panel.py" line="176"/>
        <source>Reset symmetry axis position to centre</source>
        <translation>대칭축 위치를 중앙으로 재설정</translation>
    </message>
</context>
<context>
    <name>Tag_Dialog</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="150"/>
        <location filename="../ui/frame_tags_panel.py" line="192"/>
        <source>Tag colour</source>
        <translation>태그 색상</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="179"/>
        <source>Frame Tag</source>
        <translation>프레임 태그</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="180"/>
        <source>Name</source>
        <translation>이름</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="181"/>
        <source>From frame</source>
        <translation>시작 프레임</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="182"/>
        <source>To frame</source>
        <translation>끝 프레임</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="183"/>
        <source>Mode</source>
        <translation>모드</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="184"/>
        <source>Repeat (0 = infinite)</source>
        <translation>반복 (0 = 무한)</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="185"/>
        <source>Colour</source>
        <translation>색상</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="186"/>
        <source>Tag name</source>
        <translation>태그 이름</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="187"/>
        <source>Tag start frame</source>
        <translation>태그 시작 프레임</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="188"/>
        <source>Tag end frame</source>
        <translation>태그 끝 프레임</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="189"/>
        <source>Tag playback mode</source>
        <translation>태그 재생 모드</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="190"/>
        <source>Tag repeat count</source>
        <translation>태그 반복 횟수</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="191"/>
        <source>Colour…</source>
        <translation>색상…</translation>
    </message>
</context>
<context>
    <name>Tile_Edit_Dialog</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="193"/>
        <source>Edit Tile</source>
        <translation>타일 편집</translation>
    </message>
</context>
<context>
    <name>Tilemap_Canvas</name>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="734"/>
        <source>Auto-tile</source>
        <extracomment>Initial scene window (px) for a fresh infinite map; grows to include stamps. Edge (px) of one checker square drawn behind the map (presentation-only). Platform name Qt reports with no windowing system (keep the raster viewport). MiB budget of the chunk pixmap LRU (D1). A 16x16 chunk at 16 px tiles is a 256x256 RGBA pixmap (~256 KiB), so ~128 MiB keeps a large working set resident while staying bounded on an infinite / fully filled map. Presentation/resource sizing (like frame_cache&apos;s budget), so it lives here in ui/, not logic/constants. Max cold chunks rendered *inline* per paint before the rest stream off-thread (D4). A cold chunk is ~0.84 ms (measured), so a handful stays well under the 16 ms budget and keeps a stamp / small pan instant; a full cold viewport streams. Bounded wait (ms) for an in-flight off-thread chunk render to finish on rebind / window close before the pool is torn down (mirrors canvas_scene&apos;s shutdown wait). Emitted after a layer&apos;s auto-tile mode changes (drives the panel checkbox). Emitted when a stamp/fill is refused because the tilemap has no tileset bound yet (CI-red field defect, 2026-08-24: the original FIX 5 routed this refusal through a blocking ``QMessageBox.warning``, which hangs a headless parallel worker with nothing to dismiss it). Follows the ``Canvas_View.lockedLayerEditRejected`` precedent exactly -- a signal the shell surfaces non-blockingly, never a modal, for a refusal reachable from a plain mouse gesture. Emitted when a stamp/fill is refused because no tile is selected as the active brush (a tileset IS bound; the brush gid is 0). Kept distinct from ``noTilesetBoundRejected`` so the shell shows the honest message for each case, exactly as the two ``_warn_no_active_brush`` branches already did. Emitted with the picked RGBA tuple when a plain wheel notch / an unmodified middle click travels the shared Favourites cursor (REQ-IS-UI-008/-012). Mirrors ``Canvas_View.colorPicked`` — the tilemap has no colour of its own to paint with, but the app-wide active colour/palette state is shared across every surface. A middle press awaiting the click/drag verdict — see ``Canvas_View._middle_pending`` (REQ-IS-UI-011); same behaviour here. The persisted Favourites model bound via :meth:`set_favourites_model` ``None`` until the shell binds one.</extracomment>
        <translation>자동 타일</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="997"/>
        <source>Stamp</source>
        <translation>스탬프</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1003"/>
        <source>Stamp Tile</source>
        <translation>타일 스탬프</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1013"/>
        <source>Erase</source>
        <translation>지우기</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1019"/>
        <source>Erase Tile</source>
        <translation>타일 지우기</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1038"/>
        <source>Fill</source>
        <translation>채우기</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1044"/>
        <source>Fill Rectangle</source>
        <translation>사각형 채우기</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1102"/>
        <source>Tilemap canvas</source>
        <translation>타일맵 캔버스</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_canvas.py" line="1105"/>
        <source>Tilemap: left-click to stamp/erase/fill, middle-drag to pan, H/V flip, R rotate</source>
        <translation>타일맵: 왼쪽 버튼으로 스탬프/지우기/채우기, 가운데 버튼을 끌어 이동, H/V 키로 뒤집기, R 키로 회전</translation>
    </message>
</context>
<context>
    <name>Tilemap_Layer_Panel</name>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="175"/>
        <source>Layer %1</source>
        <extracomment>Emitted with the active layer index (view state, no undo). Emitted when the auto-tile checkbox is toggled (canvas builds the ruleset).</extracomment>
        <translation>레이어 %1</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="180"/>
        <location filename="../ui/tilemap_layer_panel.py" line="186"/>
        <location filename="../ui/tilemap_layer_panel.py" line="297"/>
        <source>Add Layer</source>
        <translation>레이어 추가</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="197"/>
        <location filename="../ui/tilemap_layer_panel.py" line="203"/>
        <location filename="../ui/tilemap_layer_panel.py" line="298"/>
        <source>Remove Layer</source>
        <translation>레이어 제거</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="236"/>
        <location filename="../ui/tilemap_layer_panel.py" line="242"/>
        <source>Reorder Layer</source>
        <translation>레이어 순서 변경</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="259"/>
        <source>Layer Visibility</source>
        <translation>레이어 표시</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="265"/>
        <source>Toggle Layer Visibility</source>
        <translation>레이어 표시 전환</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="291"/>
        <source>Tilemap layers panel</source>
        <translation>타일맵 레이어 패널</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="292"/>
        <source>Layer actions</source>
        <translation>레이어 작업</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="293"/>
        <source>Tilemap layers</source>
        <translation>타일맵 레이어</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="295"/>
        <source>Ordered map layers; tick to show/hide, top layer first</source>
        <translation>순서대로 나열된 맵 레이어입니다. 확인란으로 표시 여부를 전환하며 맨 위 레이어가 먼저 나옵니다.</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="299"/>
        <source>Move Up</source>
        <translation>위로 이동</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="300"/>
        <source>Move Down</source>
        <translation>아래로 이동</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="301"/>
        <source>Auto-tile (Blob-47)</source>
        <translation>자동 타일 (Blob-47)</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="303"/>
        <source>Resolve tile edges automatically from neighbours</source>
        <translation>이웃 타일을 기준으로 타일 가장자리를 자동으로 결정</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_layer_panel.py" line="305"/>
        <source>Auto-tile toggle</source>
        <translation>자동 타일 전환</translation>
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
        <translation>타일 너비</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="221"/>
        <location filename="../ui/tileset_editor_panel.py" line="430"/>
        <location filename="../ui/tileset_editor_panel.py" line="438"/>
        <source>Tile height</source>
        <translation>타일 높이</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="224"/>
        <location filename="../ui/tileset_editor_panel.py" line="439"/>
        <source>Tile margin</source>
        <translation>타일 바깥 여백</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="227"/>
        <location filename="../ui/tileset_editor_panel.py" line="440"/>
        <source>Tile spacing</source>
        <translation>타일 간격</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="318"/>
        <source>Tile %1</source>
        <translation>타일 %1</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="371"/>
        <location filename="../ui/tileset_editor_panel.py" line="377"/>
        <source>Re-slice Tileset</source>
        <translation>타일셋 다시 자르기</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="395"/>
        <location filename="../ui/tileset_editor_panel.py" line="401"/>
        <source>Edit Tile</source>
        <translation>타일 편집</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="428"/>
        <source>Tileset editor panel</source>
        <translation>타일셋 편집기 패널</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="431"/>
        <source>Margin</source>
        <translation>바깥 여백</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="432"/>
        <source>Spacing</source>
        <translation>간격</translation>
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
        <translation>다시 자르기</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="442"/>
        <source>Re-slice the source image</source>
        <translation>원본 이미지 다시 자르기</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="443"/>
        <source>Re-slice tileset</source>
        <translation>타일셋 다시 자르기</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="444"/>
        <source>Edit Tile…</source>
        <translation>타일 편집…</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="445"/>
        <source>Paint into the selected source tile</source>
        <translation>선택한 원본 타일에 그리기</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="446"/>
        <source>Edit selected tile</source>
        <translation>선택한 타일 편집</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="447"/>
        <source>Tileset tiles</source>
        <translation>타일셋 타일</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="449"/>
        <source>Sliced tiles in row-major order; click to select for stamping</source>
        <translation>행 우선 순서로 잘라 낸 타일입니다. 스탬프로 사용하려면 선택하세요.</translation>
    </message>
</context>
<context>
    <name>Timelapse_Controls</name>
    <message numerus="yes">
        <location filename="../ui/timelapse_controls.py" line="435"/>
        <source>%n frame(s) were dropped because the edits they recorded were undone and replaced.</source>
        <extracomment>A Document -&gt; RGBA ``ndarray`` renderer (e.g. wrapping ``blend.composite_stack``), injected by the host rather than authored here (S11 — no domain/composite maths in this widget). Returns the currently active document for a bound ``QUndoStack`` (S11 — this widget reads it, it never derives it). Emitted with the current frame count after a record / load / reset. Emitted with one reconstructed RGBA ``ndarray`` per displayed frame, whichever substrate served it (in-session or a loaded payload). Emitted ``True`` while document edits must be refused (playing or paused mid-sequence), ``False`` once playback stops or completes. Emitted with the number of frames dropped by a discarded branch (REQ-P9-UI-021), once per occurrence. The per-recording identity half (REQ-P9-LOGIC-022; plan §10.1) — one :mod:`secrets` draw, minted once per recording (here, and again on every :meth:`reset`). Never an adversarial-strength token (``TIMELAPSE_RECORDING_ID_BYTES``&apos; own docstring): it only has to not collide, and it is paid for on every frame. The monotone ordinal half — only ever ``+= 1``, never reset, rewound, or derived from ``len(session.frames)``: every rewrite path rebuilds the frames *tuple*, and a counter living inside it would rewind with it (plan §10.1). The id of the document this session was recorded against (REQ-P9-UI-020) — ``None`` until the first frame is recorded. The id of the document currently bound (the active tab). stack index -&gt; the FrameId minted the last time that index was reached forward (plan §10.2). On every forward index change to ``i``, every entry with key ``&gt;= i`` is evicted **before** any new mint — an event-time observation, exact because nothing has been reused yet, never a resolution-time inference from a count. Its value set is both the surviving-identity set passed to :func:`~pixelart_creator.logic.timelapse.drop_discarded` and the live HISTORY extent handed to :class:`~pixelart_creator.ui.timelapse_playback.History_Document_Provider`. Set by :meth:`load_reopened_recording` when reviewing a loaded, cross-session payload rather than the live in-session history. ``True`` only while this widget is itself driving the bound ``QUndoStack`` through a provider (a historical render or a save&apos;s payload snapshot pass) — every ``indexChanged`` this causes is this widget&apos;s own bookkeeping, never a user commit, and must not be recorded or misread as a discard boundary (D1 fix; see ``_render_all``/``_build_payload_tables``).</extracomment>
        <translation>
            <numerusform>프레임 %n개가 삭제되었습니다. 해당 프레임에 기록된 편집이 실행 취소된 뒤 다른 편집으로 대체되었기 때문입니다.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="469"/>
        <source>Recording stopped</source>
        <translation>기록 중지됨</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="471"/>
        <source>Recording was stopped because it reached the maximum number of frames. The frames already recorded are kept. Save this recording, or reset it to start a new one.</source>
        <translation>최대 프레임 수에 도달하여 기록이 중지되었습니다. 이미 기록된 프레임은 유지됩니다. 이 기록을 저장하거나 초기화하여 새로 시작하세요.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="543"/>
        <source>Different document</source>
        <translation>다른 문서</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="545"/>
        <source>This recording belongs to a different document. Switch to that document to resume it, or reset first to start a new one here.</source>
        <translation>이 기록은 다른 문서에 속해 있습니다. 해당 문서로 전환하여 이어서 기록하거나, 먼저 초기화하여 여기에서 새로 시작하세요.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="562"/>
        <source>Save Timelapse</source>
        <translation>타임랩스 저장</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="564"/>
        <location filename="../ui/timelapse_controls.py" line="678"/>
        <source>Timelapse (*.pixtimelapse)</source>
        <translation>타임랩스 (*.pixtimelapse)</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="573"/>
        <location filename="../ui/timelapse_controls.py" line="591"/>
        <location filename="../ui/timelapse_controls.py" line="608"/>
        <source>Save failed</source>
        <translation>저장 실패</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="575"/>
        <source>This recording could not be saved because a recorded state could not be reconstructed from the current history.</source>
        <translation>기록된 상태를 현재 작업 내역에서 복원할 수 없어 이 기록을 저장할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="593"/>
        <source>This recording was not saved because it is too large. Nothing was written. Discard some frames and try again.</source>
        <translation>이 기록이 너무 커서 저장하지 못했습니다. 파일에 아무것도 쓰지 않았습니다. 일부 프레임을 삭제한 뒤 다시 시도하세요.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="610"/>
        <source>This recording could not be saved. The file could not be written, or its data could not be encoded.</source>
        <translation>이 기록을 저장할 수 없습니다. 파일에 쓸 수 없거나 데이터를 인코딩할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="676"/>
        <source>Open Timelapse</source>
        <translation>타임랩스 열기</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="693"/>
        <source>Open failed</source>
        <translation>열기 실패</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="695"/>
        <source>This file could not be opened. It is missing, unreadable, or not a valid timelapse recording.</source>
        <translation>이 파일을 열 수 없습니다. 파일이 없거나 읽을 수 없거나 올바른 타임랩스 기록이 아닙니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="754"/>
        <source>There is nothing recorded to play yet.</source>
        <translation>재생할 기록이 아직 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="761"/>
        <source>This recording belongs to a different document. Switch to that document to play it.</source>
        <translation>이 기록은 다른 문서에 속해 있습니다. 재생하려면 해당 문서로 전환하세요.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="766"/>
        <source>Playback is not available yet.</source>
        <translation>아직 재생할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="782"/>
        <source>This recording was saved in a form that cannot be replayed.</source>
        <translation>이 기록은 다시 재생할 수 없는 형식으로 저장되었습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="787"/>
        <source>This recording&apos;s saved data is incomplete and cannot be fully replayed.</source>
        <translation>이 기록의 저장된 데이터가 불완전하여 완전히 재생할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="793"/>
        <source>Some recorded frames are no longer reachable in the current history and cannot be played.</source>
        <translation>기록된 일부 프레임을 현재 작업 내역에서 더 이상 찾을 수 없어 재생할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="798"/>
        <source>This recording&apos;s history no longer matches; it cannot be replayed from here.</source>
        <translation>이 기록의 작업 내역이 더 이상 일치하지 않아 여기에서는 재생할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="812"/>
        <source>This recording was saved in an earlier form whose frames cannot be told apart reliably, so it will not be replayed.</source>
        <translation>이 기록은 프레임을 확실하게 구별할 수 없는 이전 형식으로 저장되어 재생되지 않습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="815"/>
        <source>This recording cannot be played.</source>
        <translation>이 기록은 재생할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="845"/>
        <source>Cannot play</source>
        <translation>재생할 수 없음</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="853"/>
        <source>Playback failed</source>
        <translation>재생 실패</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="854"/>
        <source>This recording could not be replayed.</source>
        <translation>이 기록을 재생할 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="941"/>
        <source>Frame {0} of {1}</source>
        <translation>프레임 {0} / {1}</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="946"/>
        <source>Recorded frames: {0}</source>
        <translation>기록된 프레임: {0}</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="978"/>
        <source>Stop Recording</source>
        <translation>기록 중지</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="978"/>
        <source>Record</source>
        <translation>기록 시작</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="983"/>
        <source>Pause</source>
        <translation>일시 중지</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="983"/>
        <source>Play</source>
        <translation>재생</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="987"/>
        <source>Timelapse</source>
        <translation>타임랩스</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="988"/>
        <source>Timelapse controls</source>
        <translation>타임랩스 컨트롤</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="989"/>
        <source>Save…</source>
        <translation>저장…</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="990"/>
        <source>Open…</source>
        <translation>열기…</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="991"/>
        <source>Stop</source>
        <translation>중지</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="992"/>
        <source>Timelapse position</source>
        <translation>타임랩스 위치</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="993"/>
        <source>Playback speed</source>
        <translation>재생 속도</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="998"/>
        <source>Playback refusal reason</source>
        <translation>재생 거부 사유</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_controls.py" line="999"/>
        <source>Recorded frame count</source>
        <translation>기록된 프레임 수</translation>
    </message>
</context>
<context>
    <name>Timelapse_Frame_View</name>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="52"/>
        <location filename="../ui/timelapse_frame_view.py" line="116"/>
        <source>Reopened recording — not the current document</source>
        <translation>다시 연 기록 — 현재 문서가 아님</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="110"/>
        <source>Reopened Recording</source>
        <translation>다시 연 기록</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="111"/>
        <source>Reopened timelapse recording</source>
        <translation>다시 연 타임랩스 기록</translation>
    </message>
    <message>
        <location filename="../ui/timelapse_frame_view.py" line="113"/>
        <source>Reopened recording — this is not your current document</source>
        <translation>다시 연 기록 — 현재 문서가 아닙니다</translation>
    </message>
</context>
<context>
    <name>Timeline_Grid_View</name>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="553"/>
        <source>Toggle Cel Visibility</source>
        <extracomment>Emitted with the frame index a selection (of any kind) settled on (REQ-P5-UI-023). Pushes no command. Emitted with the ``layer_id`` a cell/row-header selection settled on (REQ-P5-UI-023). Pushes no command. Emitted with the frame index the cursor is scrubbing over during a body drag away from any occupied cell (REQ-P5-UI-025). Pushes no command. Emitted when a Ctrl+right-click removal was refused because the target document has only one frame left (D-22). ``Document._ensure_frame_removable`` is the single, unconditional owner of that invariant; this view asks the bound document itself (``len(document.frames)``) rather than keeping a second, independently-maintained notion of &quot;removable&quot; — so the two can never drift apart. Pushes no command; the gesture stays inert.</extracomment>
        <translation>셀 표시 전환</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="589"/>
        <source>Create Cel Here</source>
        <translation>여기에 셀 만들기</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="591"/>
        <source>Create a new drawing on this track in this frame</source>
        <translation>이 프레임의 이 트랙에 새 그림 만들기</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="609"/>
        <source>Create Cel</source>
        <translation>셀 만들기</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="642"/>
        <source>Remove Frame</source>
        <translation>프레임 제거</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="666"/>
        <source>Reorder Frame</source>
        <translation>프레임 순서 변경</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="816"/>
        <source>Copy Cel</source>
        <translation>셀 복사</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="824"/>
        <source>Move Cel</source>
        <translation>셀 이동</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="851"/>
        <source>Timeline grid</source>
        <translation>타임라인 격자</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="854"/>
        <source>Frames as columns, layer tracks as rows; drag a header to reorder, drag a drawing to move it (hold Ctrl to copy), or open the context menu on an empty cell to create a cel there</source>
        <translation>프레임은 열, 레이어 트랙은 행으로 표시됩니다. 머리글을 끌어 순서를 바꾸고, 그림을 끌어 이동하며(Ctrl 키를 누른 채 끌면 복사), 빈 셀의 컨텍스트 메뉴를 열어 해당 위치에 셀을 만들 수 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="859"/>
        <source>Frame headers</source>
        <translation>프레임 머리글</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="860"/>
        <source>Layer track headers</source>
        <translation>레이어 트랙 머리글</translation>
    </message>
</context>
<context>
    <name>Timeline_Panel</name>
    <message>
        <location filename="../ui/timeline_panel.py" line="274"/>
        <source>Frame %1</source>
        <extracomment>Index of the strip surface in the cell-surface QStackedWidget — the default (REQ-P5-UI-020: &quot;the strip is the default&quot;). Not a domain constant (Article II does not reach a fixed widget-stack index); grouped with the other presentation literals this module already carries. Longest edge (px) of a cached per-cell frame thumbnail. Presentation-only sizing (like ``_SWATCH_PX`` in ``main_window``); the resident buffer is never culled — only the small display thumbnail is downscaled (F7). Ceiling for the per-frame duration spin box (ms). A presentation-only cap on how high the editor spins (like ``_THUMBNAIL_EDGE``); it is NOT a domain tuning value — the authoritative bound is the logic ``make_set_frame_duration_command`` positive-int guard, which alone validates. Emitted with the frame index a click/keyboard selected (settled — onion on). Emitted with the frame index the cursor is dragging over (scrub — onion off). Emitted with a ``layer_id`` the grid cell surface&apos;s selection settled on (REQ-P5-UI-023, BF-G1); the strip has no layer axis and never emits this.</extracomment>
        <translation>프레임 %1</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="282"/>
        <source>Frame %1 — %2 ms</source>
        <translation>프레임 %1 — %2 ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="396"/>
        <location filename="../ui/timeline_panel.py" line="515"/>
        <source>Add Frame</source>
        <translation>프레임 추가</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="408"/>
        <location filename="../ui/timeline_panel.py" line="517"/>
        <source>Remove Frame</source>
        <translation>프레임 제거</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="419"/>
        <location filename="../ui/timeline_panel.py" line="519"/>
        <source>Duplicate Frame</source>
        <translation>프레임 복제</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="452"/>
        <source>Reorder Frame</source>
        <translation>프레임 순서 변경</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="468"/>
        <source>Set Frame Duration</source>
        <translation>프레임 지속 시간 설정</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="509"/>
        <source>Timeline panel</source>
        <translation>타임라인 패널</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="510"/>
        <source>Frame actions</source>
        <translation>프레임 작업</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="511"/>
        <source>Frame strip</source>
        <translation>프레임 스트립</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="513"/>
        <source>Frames left-to-right in playback order; drag to reorder</source>
        <translation>프레임이 재생 순서대로 왼쪽에서 오른쪽으로 나열됩니다. 끌어서 순서를 바꿀 수 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="516"/>
        <source>Insert a new frame after the active one</source>
        <translation>활성 프레임 뒤에 새 프레임 삽입</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="518"/>
        <source>Delete the active frame</source>
        <translation>활성 프레임 삭제</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="521"/>
        <source>Insert a copy of the active frame after it</source>
        <translation>활성 프레임의 복사본을 그 뒤에 삽입</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="523"/>
        <source>Grid View</source>
        <translation>격자 보기</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="525"/>
        <source>Show frames and layer tracks as a grid instead of a strip</source>
        <translation>프레임과 레이어 트랙을 스트립 대신 격자로 표시</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="527"/>
        <source>Timeline cell surface</source>
        <translation>타임라인 셀 영역</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="528"/>
        <source>Duration</source>
        <translation>지속 시간</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="530"/>
        <source> ms</source>
        <translation> ms</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="531"/>
        <source>Frame duration</source>
        <translation>프레임 지속 시간</translation>
    </message>
    <message>
        <location filename="../ui/timeline_panel.py" line="533"/>
        <source>Display time of the active frame, in milliseconds</source>
        <translation>활성 프레임의 표시 시간(밀리초)</translation>
    </message>
</context>
<context>
    <name>User_Guide_Dialog</name>
    <message>
        <location filename="../ui/user_guide.py" line="509"/>
        <source>Could not load this topic:

%1</source>
        <extracomment>Qt roles that would resolve an anchor to the network or the local filesystem; the viewer is fully offline (REQ-UG-UI-007), so a click on such a link is a no-op — it is never fetched. The UserRole slot carrying a topic id on a ToC / results item. The in-guide markdown image URL the mark resolves against. The guide pages reference the mark as ``![PixelArt Creator](pac-logo.png)`` under this EXACT string -- it is the contract between the content and this widget&apos;s document-resource registration; do not change it here. A reader callable: a bundle-relative content ref -&gt; the Markdown text. Defaults to the defensive ``data`` reader; injectable so headless tests can substitute a fixture reader without touching the real bundle. A locale provider: returns the active UI locale code (e.g. ``&quot;en&quot;``). Defaults to the guide&apos;s default locale; the main window passes the LanguageManager&apos;s ``current_language`` so content follows the UI language (REQ-UG-UI-011 / CL-3). Qt&apos;s scale for a char format&apos;s font-size adjustment (``+1`` is 1.2 times the base size, ``+2`` 1.5, ``+3`` 2.0); the markdown importer gives a heading the adjustment ``4 - level``. Used to find the size a heading would be drawn at, so it can be rounded to a whole multiple of the pixel font&apos;s em. Emitted when the hidden logo switch is toggled (the new on/off state), so the owner can remember it (``REQ-VI-UI-017``).</extracomment>
        <translation>이 주제를 불러올 수 없습니다:

%1</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="568"/>
        <source>The User Guide content could not be loaded:

%1</source>
        <translation>사용자 가이드 내용을 불러올 수 없습니다:

%1</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="571"/>
        <source>The User Guide content could not be loaded.</source>
        <translation>사용자 가이드 내용을 불러올 수 없습니다.</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="711"/>
        <location filename="../ui/user_guide.py" line="712"/>
        <source>User Guide</source>
        <translation>사용자 가이드</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="713"/>
        <source>Search the guide…</source>
        <translation>가이드 검색…</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="714"/>
        <source>Search the guide</source>
        <translation>가이드 검색</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="715"/>
        <source>Guide contents</source>
        <translation>가이드 목차</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="716"/>
        <source>Search results</source>
        <translation>검색 결과</translation>
    </message>
    <message>
        <location filename="../ui/user_guide.py" line="717"/>
        <source>Guide content</source>
        <translation>가이드 내용</translation>
    </message>
</context>
<context>
    <name>Vanishing_Point_Dialog</name>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="156"/>
        <source>1-point</source>
        <translation>1점</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="157"/>
        <source>2-point</source>
        <translation>2점</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="158"/>
        <source>3-point</source>
        <translation>3점</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="162"/>
        <source>Configure Perspective</source>
        <translation>원근 설정</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="163"/>
        <source>Vanishing points</source>
        <translation>소실점</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="164"/>
        <source>Horizon Y</source>
        <translation>수평선 Y</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="165"/>
        <source>Vanishing-point mode</source>
        <translation>소실점 모드</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="166"/>
        <source>Horizon Y position</source>
        <translation>수평선 Y 위치</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="170"/>
        <source>Vanishing point {n}</source>
        <translation>소실점 {n}</translation>
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
        <translation>소실점 {n} X</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="178"/>
        <source>Vanishing point {n} Y</source>
        <translation>소실점 {n} Y</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="182"/>
        <source>OK</source>
        <translation>확인</translation>
    </message>
    <message>
        <location filename="../ui/vanishing_point_dialog.py" line="185"/>
        <source>Cancel</source>
        <translation>취소</translation>
    </message>
</context>
<context>
    <name>Version_History_Browser</name>
    <message>
        <location filename="../ui/version_history_browser.py" line="169"/>
        <source>Select a version to restore.</source>
        <extracomment>Column order of the version tree (presentation-only layout, not a domain value). QSS role-selector property (never a hard-coded colour): the status label carries the computed :class:`SyncState` as a dynamic property so BOTH themes can style it by role (``QLabel[syncState=&quot;diverged&quot;]`` etc.) — see D-13.</extracomment>
        <translation>복원할 버전을 선택하세요.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/version_history_browser.py" line="174"/>
        <source>Version %1 — %n bytes (created marker %3).</source>
        <translation>
            <numerusform>버전 %1 — %n바이트 (생성 마커 %3).</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="185"/>
        <source>Up to date with the cloud.</source>
        <translation>클라우드와 동기화되어 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="187"/>
        <source>Local changes have not been saved to the cloud yet.</source>
        <translation>로컬 변경 사항이 아직 클라우드에 저장되지 않았습니다.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="189"/>
        <source>A newer version exists in the cloud.</source>
        <translation>클라우드에 더 새로운 버전이 있습니다.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="190"/>
        <source>Local and cloud history have diverged.</source>
        <translation>로컬과 클라우드의 버전 내역이 갈라졌습니다.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="195"/>
        <source>Cloud Version History</source>
        <translation>클라우드 버전 내역</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="198"/>
        <source>Prior cloud saves, oldest first. Restoring opens the chosen version in a new tab — your current work is not overwritten.</source>
        <translation>이전 클라우드 저장본이 오래된 순서로 나열됩니다. 복원하면 선택한 버전이 새 탭에서 열리며 현재 작업은 덮어쓰이지 않습니다.</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="203"/>
        <source>Cloud sync status</source>
        <translation>클라우드 동기화 상태</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="206"/>
        <source>Version</source>
        <translation>버전</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="207"/>
        <source>Marker</source>
        <translation>마커</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="208"/>
        <source>Size (bytes)</source>
        <translation>크기(바이트)</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="209"/>
        <source>Pinned</source>
        <translation>고정됨</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="210"/>
        <source>Parent</source>
        <translation>상위</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="213"/>
        <source>Yes</source>
        <translation>예</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="214"/>
        <source>No</source>
        <translation>아니요</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="222"/>
        <source>Restore</source>
        <translation>복원</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="223"/>
        <source>Cloud version list</source>
        <translation>클라우드 버전 목록</translation>
    </message>
    <message>
        <location filename="../ui/version_history_browser.py" line="224"/>
        <source>Restore selected version</source>
        <translation>선택한 버전 복원</translation>
    </message>
</context>
<context>
    <name>_Node_Row</name>
    <message>
        <location filename="../ui/layer_panel.py" line="180"/>
        <source>Ref</source>
        <extracomment>A node address in the frame tree — the logic index path used by the document layer ops (top-level index, then indices descending through nested groups). A fully-shown mask (opaque alpha everywhere ⇒ no modulation, LOGIC-012).</extracomment>
        <translation>참조</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="182"/>
        <source>Mask</source>
        <translation>마스크</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="184"/>
        <source>Smart</source>
        <translation>스마트</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="196"/>
        <source>Toggle Visibility</source>
        <translation>표시 전환</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="205"/>
        <source>Toggle Lock</source>
        <translation>잠금 전환</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="217"/>
        <source>Set Blend Mode</source>
        <translation>혼합 모드 설정</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="251"/>
        <source>Set Opacity</source>
        <translation>불투명도 설정</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="257"/>
        <source>V</source>
        <translation>V</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="258"/>
        <source>Toggle layer visibility</source>
        <translation>레이어 표시 전환</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="259"/>
        <source>Visibility</source>
        <translation>표시</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="260"/>
        <source>L</source>
        <translation>L</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="261"/>
        <source>Lock layer against painting</source>
        <translation>레이어를 잠가 그리기 방지</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="262"/>
        <source>Lock</source>
        <translation>잠금</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="263"/>
        <source>Layer name</source>
        <translation>레이어 이름</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="264"/>
        <source>Layer flags</source>
        <translation>레이어 플래그</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="265"/>
        <source>Layer opacity</source>
        <translation>레이어 불투명도</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="266"/>
        <source>Opacity</source>
        <translation>불투명도</translation>
    </message>
    <message>
        <location filename="../ui/layer_panel.py" line="267"/>
        <location filename="../ui/layer_panel.py" line="268"/>
        <source>Blend mode</source>
        <translation>혼합 모드</translation>
    </message>
</context>
<context>
    <name>_Project_Prefs_Menu</name>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="72"/>
        <source>Ask me every time</source>
        <extracomment>A domain wider than this renders as a nested exclusive submenu rather than a single checkable action (plan §3.4) — a plain boolean-shaped preference (ask / suppressed) keeps the shipped single-checkbox rendering. Menu-rendering strings share one translation context with the class below so :func:`value_label_for` — a free function, exported for a future renderer (phase-6&apos;s settings dialog) — is caught by the same ``tr()`` extraction pass as the class&apos;s own strings.</extracomment>
        <translation>매번 묻기</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="75"/>
        <source>Always pick up the library change</source>
        <translation>항상 라이브러리 변경 내용 반영</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="78"/>
        <source>Always keep the referenced version</source>
        <translation>항상 참조된 버전 유지</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="84"/>
        <source>Set to: %1</source>
        <translation>설정값: %1</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="219"/>
        <source>Confirm before overwriting a cel</source>
        <extracomment>The provider the caller supplies: returns the active document, or ``None`` when no document is open.</extracomment>
        <translation>셀을 덮어쓰기 전에 확인</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="221"/>
        <source>When a referenced library asset changes</source>
        <translation>참조 중인 라이브러리 에셋이 변경될 때</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="227"/>
        <source>Confirm: %1</source>
        <translation>확인: %1</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="230"/>
        <location filename="../ui/project_prefs_actions.py" line="231"/>
        <source>Project confirmations</source>
        <translation>프로젝트 확인 창</translation>
    </message>
    <message>
        <location filename="../ui/project_prefs_actions.py" line="236"/>
        <source>Restore this confirmation so it asks again</source>
        <translation>이 확인 창을 복원하여 다시 묻도록 설정</translation>
    </message>
</context>
<context>
    <name>_Tile_Pixel_Editor</name>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="113"/>
        <location filename="../ui/tileset_editor_panel.py" line="157"/>
        <source>Tile pixel editor</source>
        <extracomment>Thumbnail edge (px) for a tile swatch in the grid list (presentation-only, not a domain tuning value — cf. Palette_Panel&apos;s swatch size). On-screen pixel size of one tile pixel in the tile editor dialog.</extracomment>
        <translation>타일 픽셀 편집기</translation>
    </message>
    <message>
        <location filename="../ui/tileset_editor_panel.py" line="115"/>
        <location filename="../ui/tileset_editor_panel.py" line="159"/>
        <source>Left-click to paint, right-click to erase</source>
        <translation>왼쪽 버튼으로 그리기, 오른쪽 버튼으로 지우기</translation>
    </message>
</context>
<context>
    <name>_Track_Table_Model</name>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="239"/>
        <source>Frame %1</source>
        <extracomment>Longest edge (px) of a cached per-cell thumbnail. Mirrors ``timeline_panel._THUMBNAIL_EDGE`` exactly (visual consistency between the two cell surfaces the toggle swaps between); a presentation-only sizing literal, not a domain tuning value (Article II does not reach it, like its strip twin). Custom data roles carried on every cell, alongside the standard Qt roles.</extracomment>
        <translation>프레임 %1</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="256"/>
        <source>%1, %2</source>
        <translation>%1, %2</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="261"/>
        <source>%1, %2 — empty</source>
        <translation>%1, %2 — 비어 있음</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="268"/>
        <source>%1, track %2</source>
        <translation>%1, 트랙 %2</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="273"/>
        <source>%1, track %2, empty</source>
        <translation>%1, 트랙 %2, 비어 있음</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="278"/>
        <source>Occupied cell</source>
        <translation>사용 중인 셀</translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="278"/>
        <source>Empty cell</source>
        <translation>빈 셀</translation>
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
            <numerusform>프레임 %1, %n밀리초</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/timeline_grid_view.py" line="341"/>
        <source>Track %1</source>
        <translation>트랙 %1</translation>
    </message>
</context>
<context>
    <name>_WheelPad</name>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="309"/>
        <source>Colour wheel</source>
        <extracomment>Hue at the top of the circle, in degrees (achromatic fallback keeps this hue). Number of conical-gradient stops sweeping the hue circle (six primaries + wrap). Edge of a harmony/preview swatch button, px (presentation-only sizing). Minimum wheel diameter, px (presentation-only sizing). Marker radius drawn at the current hue/saturation, px. Keyboard nudge steps for the wheel (hue degrees / saturation fraction). Single left click — paint this swatch&apos;s colour, leave the wheel alone. Double left click / Space / Return — adopt this swatch&apos;s colour into the wheel, paint nothing. Emitted with ``(hue_degrees, saturation)`` when the user picks on the wheel.</extracomment>
        <translation>색상환</translation>
    </message>
    <message>
        <location filename="../ui/colour_wheel_widget.py" line="312"/>
        <source>Hue and saturation wheel; use the arrow keys or the numeric fields to pick a colour without a mouse</source>
        <translation>색조와 채도 색상환입니다. 마우스 없이 색상을 선택하려면 화살표 키 또는 숫자 입력란을 사용하세요.</translation>
    </message>
</context>
<context>
    <name>export</name>
    <message>
        <location filename="../ui/export_actions.py" line="98"/>
        <location filename="../ui/export_actions.py" line="109"/>
        <source>Export</source>
        <extracomment>The source document that was submitted for export (never the exported file&apos;s own bytes — REQ-P11-UI-014). The export settings as used for this run (JSON-scalar values only — bounded by ``logic.constants.MAX_METADATA_BYTES`` at ingress).</extracomment>
        <translation>내보내기</translation>
    </message>
    <message>
        <location filename="../ui/export_actions.py" line="99"/>
        <source>Open a document before exporting.</source>
        <translation>내보내기 전에 문서를 여세요.</translation>
    </message>
    <message>
        <location filename="../ui/export_actions.py" line="110"/>
        <source>Choose a destination path before exporting.</source>
        <translation>내보내기 전에 대상 경로를 선택하세요.</translation>
    </message>
</context>
<context>
    <name>theme</name>
    <message>
        <location filename="../ui/theme.py" line="161"/>
        <source>unknown style: %1</source>
        <extracomment>%1 is the internal style name that could not be found.</extracomment>
        <translation>알 수 없는 스타일: %1</translation>
    </message>
    <message>
        <location filename="../ui/theme.py" line="166"/>
        <source>unknown theme: %1</source>
        <translation>알 수 없는 테마: %1</translation>
    </message>
</context>
<context>
    <name>tilemap_io</name>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="39"/>
        <source>Export Tiled Map</source>
        <extracomment>Tiled JSON file filter (format identifier, not a translated string).</extracomment>
        <translation>Tiled 맵 내보내기</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="50"/>
        <source>Export failed</source>
        <translation>내보내기 실패</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="52"/>
        <source>Could not export the map: %1</source>
        <translation>맵을 내보낼 수 없습니다: %1</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="74"/>
        <source>Import Tiled Map</source>
        <translation>Tiled 맵 가져오기</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="85"/>
        <source>Import failed</source>
        <translation>가져오기 실패</translation>
    </message>
    <message>
        <location filename="../ui/tilemap_io_actions.py" line="87"/>
        <source>Could not import the map: %1</source>
        <translation>맵을 가져올 수 없습니다: %1</translation>
    </message>
</context>
<context>
    <name>tool_icons</name>
    <message>
        <location filename="../ui/tool_icons.py" line="129"/>
        <source>unknown tool glyph id: %1</source>
        <extracomment>The importable package the glyph bundle is shipped inside (package data), matching ``data/guide_content.py``&apos;s ``BUNDLE_PACKAGE`` convention. Package-data subdirectory holding the eleven glyphs, relative to :data:`_ICON_PACKAGE` (``pixelart_creator/icons/tools/``). SVG file extension for a glyph resource. Square render size, in device-independent pixels, for the rasterised glyph and its tinted pixmap. One named constant, referenced everywhere a size is needed in this module (S12) — this module owns no other size. The theme role whose colour tints every glyph (`ui/theme.py`&apos;s role palette; `text` exists in both themes, QT-D1). The eleven shipped `tool_id`s, one per authored glyph stem (`pixelart_creator/icons/tools/&lt;id&gt;.svg`) — the exact `tool_id` class attributes carried by `ui/tools/*.py` (pencil, eraser, fill, line, picker, rectangle, ellipse, select_rect, select_lasso, select_wand, dither). Kept as a literal tuple here (not imported from each tool class) so this module has no dependency on the tool-strategy classes themselves — only on the glyph *ids* they happen to share.</extracomment>
        <translation>알 수 없는 도구 글리프 ID: %1</translation>
    </message>
    <message>
        <location filename="../ui/tool_icons.py" line="136"/>
        <source>missing tool glyph asset for: %1</source>
        <translation>도구 글리프 에셋 없음: %1</translation>
    </message>
    <message>
        <location filename="../ui/tool_icons.py" line="153"/>
        <source>unknown theme: %1</source>
        <translation>알 수 없는 테마: %1</translation>
    </message>
</context>
<context>
    <name>tools</name>
    <message>
        <location filename="../ui/tools/dither_tool.py" line="65"/>
        <source>Dither</source>
        <extracomment>The two dither modes accepted by ``logic.dither.make_dither_command``.</extracomment>
        <translation>디더링</translation>
    </message>
    <message>
        <location filename="../ui/tools/ellipse_tool.py" line="29"/>
        <source>Ellipse</source>
        <translation>타원</translation>
    </message>
    <message>
        <location filename="../ui/tools/eraser.py" line="25"/>
        <source>Eraser</source>
        <extracomment>Indexed buffers erase to palette index 0 (the buffer&apos;s own default value).</extracomment>
        <translation>지우개</translation>
    </message>
    <message>
        <location filename="../ui/tools/fill.py" line="23"/>
        <source>Fill</source>
        <translation>채우기</translation>
    </message>
    <message>
        <location filename="../ui/tools/lasso_tool.py" line="30"/>
        <source>Lasso Select</source>
        <translation>올가미 선택</translation>
    </message>
    <message>
        <location filename="../ui/tools/line.py" line="29"/>
        <source>Line</source>
        <translation>선</translation>
    </message>
    <message>
        <location filename="../ui/tools/magic_wand_tool.py" line="36"/>
        <source>Magic Wand</source>
        <extracomment>A wand click always (re)selects; it never starts a floating move. Colour tolerance; default exact match (CL-1). Set by the shell control.</extracomment>
        <translation>마술봉</translation>
    </message>
    <message>
        <location filename="../ui/tools/pencil.py" line="49"/>
        <source>Pencil</source>
        <translation>연필</translation>
    </message>
    <message>
        <location filename="../ui/tools/rect_select_tool.py" line="23"/>
        <source>Rectangle Select</source>
        <translation>사각형 선택</translation>
    </message>
    <message>
        <location filename="../ui/tools/rectangle_tool.py" line="29"/>
        <source>Rectangle</source>
        <translation>사각형</translation>
    </message>
</context>
<context>
    <name>widget</name>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="62"/>
        <source>Loop</source>
        <translation>반복</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="63"/>
        <source>Once</source>
        <translation>한 번</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="64"/>
        <source>Ping-Pong</source>
        <translation>핑퐁</translation>
    </message>
    <message>
        <location filename="../ui/frame_tags_panel.py" line="65"/>
        <source>Reverse</source>
        <translation>역방향</translation>
    </message>
</context>
</TS>
