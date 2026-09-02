"""Asset-library a11y, both themes, i18n (REQ-P11-UI-008/-009/-010).

Every interactive control on the three asset-library panels (library / tagging / search)
exposes a non-empty accessible name, is keyboard-reachable (focus policy other than
``NoFocus``), and the single-selection views make an unambiguous target
(REQ-P11-UI-008); the panels render under both QSS themes with role-based colours and no
inline stylesheet (REQ-P11-UI-009); and their user-visible strings are ``tr()``-wrapped
and retranslate on a ``QEvent.LanguageChange`` (REQ-P11-UI-010). Every test runs under
BOTH themes via the autouse ``theme`` fixture. Findings feed the a11y-audit report.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_library_panel import Asset_Library_Panel
from pixelart_creator.ui.asset_search_panel import Asset_Search_Panel
from pixelart_creator.ui.asset_tagging_panel import Asset_Tagging_Panel


@pytest.fixture
def panels(qtbot):
    """The three bound asset-library panels over one session holding a selected asset."""
    session = Asset_Library_Session(
        catalog=AssetCatalog(
            descriptors=(
                AssetDescriptor(
                    asset_id="a1",
                    kind=AssetKind.SPRITE,
                    name="Hero",
                    content_hash="h1",
                    tags=frozenset({"hero"}),
                ),
            )
        )
    )
    library = Asset_Library_Panel()
    tagging = Asset_Tagging_Panel()
    search = Asset_Search_Panel()
    for widget in (library, tagging, search):
        qtbot.addWidget(widget)
    library.set_session(session)
    tagging.set_session(session)
    tagging.set_asset("a1")
    return library, tagging, search


# -- REQ-P11-UI-008 accessible names ----------------------------------------- #


def test_library_controls_have_accessible_names(panels):
    """Every interactive library control exposes a non-empty a11y name."""
    library, _t, _s = panels
    for widget in (library, library._tree):
        assert widget.accessibleName() != ""


def test_tagging_controls_have_accessible_names(panels):
    """Every interactive tagging control exposes a non-empty a11y name."""
    _l, tagging, _s = panels
    for widget in (
        tagging,
        tagging._tag_list,
        tagging._tag_edit,
        tagging._add_button,
        tagging._remove_button,
    ):
        assert widget.accessibleName() != ""


def test_search_controls_have_accessible_names(panels):
    """Every interactive search/filter control exposes a non-empty a11y name."""
    _l, _t, search = panels
    for widget in (
        search,
        search._name_edit,
        search._tag_edit,
        search._kind_combo,
        search._clear_button,
    ):
        assert widget.accessibleName() != ""


# -- REQ-P11-UI-008 keyboard reachability + focus order ----------------------- #


def test_panels_are_keyboard_reachable(panels):
    """Trees / lists / edits / combos accept keyboard focus (not NoFocus)."""
    library, tagging, search = panels
    for widget in (
        library._tree,
        tagging._tag_list,
        tagging._tag_edit,
        tagging._add_button,
        search._name_edit,
        search._tag_edit,
        search._kind_combo,
    ):
        assert widget.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_selection_views_are_single_selection(panels):
    """Library tree + tag list use single-selection (an unambiguous target)."""
    library, tagging, _s = panels
    assert library._tree.selectionMode() == library._tree.SelectionMode.SingleSelection
    assert (
        tagging._tag_list.selectionMode()
        == tagging._tag_list.SelectionMode.SingleSelection
    )


def test_visible_focus_indicator_is_themed(panels):
    """A visible focus ring is themed once by role (:focus QSS) for the panels."""
    qss = QApplication.instance().styleSheet()
    assert ":focus" in qss


# -- REQ-P11-UI-009 both themes ----------------------------------------------- #


def test_panels_lay_out_under_active_theme_without_inline_colour(panels, theme):
    """Each panel lays out under the active theme with NO per-widget hard-coded colour.

    The autouse ``theme`` fixture runs this under both light and dark; colours come
    from the applied QSS role palette, so the panels carry no inline stylesheet.
    """
    for widget in panels:
        assert widget.sizeHint().isValid()
        assert widget.styleSheet() == ""


# -- REQ-P11-UI-010 i18n retranslate ------------------------------------------ #


def test_panels_retranslate_on_language_change(panels):
    """Each panel re-sets its tr() strings on ``QEvent.LanguageChange`` (F5)."""
    library, tagging, search = panels
    for widget in panels:
        QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))
    # Strings remain populated after the retranslate hook (no crash, no blanking).
    assert library._tree.headerItem().text(0) != ""
    assert tagging._add_button.text() != ""
    assert tagging._remove_button.text() != ""
    assert search._clear_button.text() != ""
    assert search._kind_combo.itemText(0) != ""  # "All kinds"


def test_kind_column_labels_are_translatable(panels):
    """Kind labels route through tr() for every AssetKind (no bare literal)."""
    library, _t, _s = panels
    for kind in AssetKind:
        assert library._kind_text(kind) != ""


def test_tagging_asset_label_updates_on_selection(panels):
    """The tagging header shows a translatable 'Tags for: <name>' when bound."""
    _l, tagging, _s = panels
    assert tagging._asset_label.text() != ""
    assert "Hero" in tagging._asset_label.text()
