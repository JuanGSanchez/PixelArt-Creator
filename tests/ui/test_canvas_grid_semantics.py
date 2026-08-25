"""Canvas ground/border surface-role acceptance tests (REQ-CGS-UI-005, -006).

The canvas gained two theme roles for the surface the document sits on:
``workspace`` (the ground painted behind the document) and ``border`` (the
document-edge outline) — today the canvas has neither, so a rendered view
after a dab shows only the two checker tones and the dab, with the checker
tiling straight past the document edge.

This module covers the ROLE half of REQ-CGS-UI-005/-006: that
:func:`~pixelart_creator.ui.theme.canvas_surface_roles` returns two colours
per theme, each distinct from the theme's own checker tones (and the border
distinct from the workspace too), and that a :class:`CanvasScene` handed the
roles via :meth:`~pixelart_creator.ui.canvas_scene.CanvasScene.set_surface_roles`
reports them back. Nothing paints these roles yet — that is a later task —
so no test here asserts on rendered pixels; every assertion targets the
roles themselves or the scene's stored state.

Every test runs under both light and dark themes via the autouse ``theme``
fixture in ``conftest.py`` (parametrised there; not looped by hand here).
This module is written to be extended by a later task in place, without
restructuring — add further ``test_req_cgs_ui_*`` functions below.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

from pixelart_creator.ui.theme import canvas_roles, canvas_surface_roles

# --------------------------------------------------------------------------- #
# REQ-CGS-UI-005 — canvas_surface_roles(theme) returns (workspace, border),   #
# with the workspace distinct from both checker tones of that theme.          #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_005_surface_roles_returns_two_colours(theme):
    """REQ-CGS-UI-005: canvas_surface_roles(theme) returns (workspace, border)."""
    roles = canvas_surface_roles(theme)
    assert len(roles) == 2
    workspace, border = roles
    assert isinstance(workspace, QColor)
    assert isinstance(border, QColor)


def test_req_cgs_ui_005_workspace_distinct_from_both_checker_tones(theme):
    """REQ-CGS-UI-005: the workspace colour equals neither checker tone.

    A workspace tone equal to a checker tone would make the ground invisible
    against that tile — this is a requirement, not taste, so it is asserted
    against the theme module's own checker values (never a hard-coded hex).
    """
    workspace, _border = canvas_surface_roles(theme)
    checker_light, checker_dark, _grid = canvas_roles(theme)
    assert workspace != checker_light
    assert workspace != checker_dark


# --------------------------------------------------------------------------- #
# REQ-CGS-UI-006 — the border colour equals neither the workspace nor either  #
# checker tone of that theme, and a scene given the roles reports them.       #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_006_border_distinct_from_workspace_and_both_checker_tones(theme):
    """REQ-CGS-UI-006: the border colour equals neither its neighbour colour.

    A border equal to the workspace or to either checker tone makes the
    boundary vanish against one side of itself — the exact class of defect
    this batch exists to fix, one layer down.
    """
    workspace, border = canvas_surface_roles(theme)
    checker_light, checker_dark, _grid = canvas_roles(theme)
    assert border != workspace
    assert border != checker_light
    assert border != checker_dark


def test_req_cgs_ui_006_scene_reports_the_roles_it_was_given(make_scene, theme):
    """REQ-CGS-UI-006: a scene handed the roles via set_surface_roles reports them.

    Asserts on the scene's own stored state, not on rendered pixels — nothing
    paints these roles yet (a later task clips the checker to the canvas rect
    and strokes the border). ``set_surface_roles`` stores no public accessor
    today, so this targets the same ``_workspace_color`` / ``_border_color``
    attributes the method itself sets, which is the only observable surface
    currently exposed for this state.
    """
    scene = make_scene(8, 8)
    workspace, border = canvas_surface_roles(theme)
    scene.set_surface_roles(workspace, border)
    assert scene._workspace_color == workspace
    assert scene._border_color == border
