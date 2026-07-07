"""Shipped GUI entry point — application factory + launcher (REQ-P13-*).

This module is the single, testable seam that turns the documented README
launch snippet into a real, packaged entry point. It is intentionally split so
the GUI can be driven both headlessly (tests) and interactively (a native
installer / ``python -m pixelart_creator`` / a ``pyproject`` gui-script):

* :func:`create_app` get-or-creates the :class:`QApplication`, sets its
  application/organisation identity, constructs :class:`Main_Window`, shows it,
  and returns ``(app, window)`` **without** entering the event loop — the
  headless-testable seam.
* :func:`main` wires :func:`create_app` to ``app.exec()`` and returns its exit
  code — the real launcher.

Startup theme/i18n/font-fallback wiring is **not** repeated here: it already
lives inside :meth:`Main_Window.__init__` (``apply_font_fallbacks`` +
``apply_theme`` + ``LanguageManager.install_from_locale``), so a window
constructed via :func:`create_app` paints correctly on first show without this
module duplicating that logic (Article I). Importing this module has **no** side
effects — no :class:`QApplication` is constructed at import time.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional, Tuple

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.main_window import Main_Window

#: Application + organisation identity, used by :class:`QApplication` for
#: ``QStandardPaths`` (autosave/recovery locations), window/task-bar titles, and
#: OS-integration on a packaged build. Defined once here (the startup seam).
APPLICATION_NAME = "PixelArt Creator"
ORGANIZATION_NAME = "PixelArt Creator"


def create_app(argv: Optional[List[str]] = None) -> Tuple[QApplication, Main_Window]:
    """Get-or-create the application and construct the shown main window.

    Reuses an existing :class:`QApplication` when one is already running (so a
    headless test harness that owns the instance is not double-created against),
    otherwise constructs one from ``argv``. Sets the application/organisation
    name, builds :class:`Main_Window` (which applies the theme, font fallbacks,
    and locale itself), shows it, and returns the pair **without** calling
    ``app.exec()`` — leaving the event loop to the caller (:func:`main` or a
    test).

    Args:
        argv: Process arguments handed to a newly created :class:`QApplication`.
            Ignored when an instance already exists. Defaults to ``sys.argv``.

    Returns:
        The running :class:`QApplication` and the shown :class:`Main_Window`.
    """
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv if argv is None else list(argv))
    app.setApplicationName(APPLICATION_NAME)
    app.setOrganizationName(ORGANIZATION_NAME)

    window = Main_Window()
    window.show()
    return app, window


def main(argv: Optional[List[str]] = None) -> int:
    """Launch the GUI and run the event loop, returning the process exit code.

    Honours the ``PIXELART_SMOKE_EXIT_MS`` environment variable: a CI/packaging
    smoke-launch self-exit hook. When it is set to a **positive integer** number
    of *milliseconds*, the app is scheduled to quit that many milliseconds after
    launch (via :meth:`QTimer.singleShot`), so a packaged build can be started,
    confirmed to reach the event loop and paint, then exit ``0`` cleanly without
    blocking forever on ``app.exec()``. Absent, empty, non-integer, or ``<= 0``
    values are ignored — the app runs normally (indefinite). The value is parsed
    defensively (plain :func:`int`, no ``eval``); a bad value never crashes the
    launcher.

    Args:
        argv: Process arguments forwarded to :func:`create_app`. Defaults to
            ``sys.argv``.

    Returns:
        The :class:`QApplication` exit code.
    """
    app, _window = create_app(argv)

    try:
        smoke_exit_ms = int(os.environ.get("PIXELART_SMOKE_EXIT_MS", ""))
    except ValueError:
        smoke_exit_ms = 0
    if smoke_exit_ms > 0:
        QTimer.singleShot(smoke_exit_ms, app.quit)

    return app.exec()
