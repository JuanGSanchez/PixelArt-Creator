# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""About dialog (Help > About PixelArt Creator) — REQ-AV-UI-002..011.

``About_Dialog`` is presentation only (S11): it gathers the two facts that
need Qt (the runtime Qt version and the installed PySide6 version, each
through its own seam so a failure degrades to ``None``, REQ-AV-UI-007) and
hands everything to :mod:`pixelart_creator.logic.about_info` for composition.
Every external-URL hand-off goes through the single module-level
:func:`_open_url` seam (ADR-0067 Part 1) — nothing else in this module calls
:class:`~PySide6.QtGui.QDesktopServices`, and the module imports no
``QtNetwork`` and opens no socket (REQ-AV-UI-011). Link colour comes from
:func:`pixelart_creator.ui.theme.link_colour` (the ``text`` role, ADR-0067
Part 2), never a literal. Every user-visible string is wrapped in ``tr()``
and re-set on ``QEvent.LanguageChange`` (F5/F6, REQ-AV-UI-012).
"""

from __future__ import annotations

import html
from typing import Callable, Optional

from PySide6.QtCore import QEvent, Qt, QUrl, qVersion
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic import about_info
from pixelart_creator.ui.app_icon import app_icon
from pixelart_creator.ui.theme import link_colour

#: The dialog's fixed links, in the order shown (REQ-AV-UI-005).
_LINKS = (
    ("aboutRepositoryLink", about_info.REPOSITORY_URL),
    ("aboutDocumentationLink", about_info.DOCUMENTATION_URL),
    ("aboutReleasesLink", about_info.RELEASES_URL),
)


def _qt_version() -> Optional[str]:
    """Return the runtime Qt version, or ``None`` on failure or blank.

    Read here, not in ``logic/`` (plan §3.2/NFR-1: gathering a Qt fact is a
    Qt call). Monkeypatchable seam (plan §3.2, REQ-AV-UI-007).
    """
    try:
        version = qVersion()
        return version if version else None
    except Exception:
        return None


def _pyside_version() -> Optional[str]:
    """Return the installed PySide6 version, or ``None`` on failure or blank.

    Monkeypatchable seam (plan §3.2, REQ-AV-UI-007).
    """
    try:
        import PySide6

        version = PySide6.__version__
        return version if version else None
    except Exception:
        return None


def _safe_fact(read: Callable[[], Optional[str]]) -> Optional[str]:
    """Call the module-level seam ``read`` and degrade to ``None`` on failure.

    The seam is looked up by name at call time (through the caller passing
    the module-global function object), so a test that monkeypatches
    :func:`_qt_version`/:func:`_pyside_version` themselves to raise is still
    guarded here — the fact degrades to ``None`` instead of stopping the
    dialog from opening (REQ-AV-UI-007).
    """
    try:
        return read()
    except Exception:
        return None


def _open_url(url: str) -> None:
    """Open ``url`` in the default browser (ADR-0067 Part 1).

    The ONLY caller of :class:`~PySide6.QtGui.QDesktopServices` in this
    module. Every link hand-off, and nothing else, reaches this function.
    """
    QDesktopServices.openUrl(QUrl(url))


class _Link_Label(QLabel):
    """A rich-text anchor label that also activates from the keyboard.

    ``LinksAccessibleByKeyboard`` alone only makes the anchor Tab-reachable;
    it does not route a real Return/Enter/Space key press to
    :attr:`QLabel.linkActivated`. Left unhandled, that key press instead
    bubbles up, unaccepted, to :class:`About_Dialog`, whose Close button is
    the default button — so the dialog closed instead of activating the
    link (a11y-audit REQ-AV-UI-005 finding, T14). This override accepts the
    three activation keys itself, while the label has focus, and re-emits
    ``linkActivated`` with its own ``url`` dynamic property — the exact
    signal the mouse-click path already emits, so keyboard activation goes
    through the SAME single seam (``About_Dialog._on_link_activated`` ->
    ``_open_url``, ADR-0067 Part 1) and no timing/focus special-casing is
    needed anywhere else in the dialog.
    """

    _ACTIVATION_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        """Activate the link on Return/Enter/Space; delegate every other key."""
        if event.key() in self._ACTIVATION_KEYS:
            self.linkActivated.emit(str(self.property("url")))
            event.accept()
            return
        super().keyPressEvent(event)


class About_Dialog(QDialog):
    """The About dialog: name, version, licence, links, environment, Copy.

    Built fresh on every trigger (``Main_Window._on_about``), so the version,
    the platform facts and the theme are all read at open time
    (SC-AV-UI-004-2). Holds no domain logic (S11): every fact is either a
    constant from :mod:`about_info`, a call-time lookup delegated to it, or a
    Qt fact gathered by the two seams above.
    """

    def __init__(self, theme: str, parent: Optional[QWidget] = None) -> None:
        """Build the dialog for the given ``theme`` name, parented to ``parent``."""
        super().__init__(parent)
        self._theme = theme

        # -- facts, gathered once at open time ---------------------------
        self._version_text = about_info.app_version()
        platform_facts = about_info.read_platform_facts()
        self._environment_facts = about_info.EnvironmentFacts(
            app_name=about_info.APP_NAME,
            app_version=self._version_text,
            os_name=platform_facts.os_name,
            os_version=platform_facts.os_version,
            python_version=platform_facts.python_version,
            qt_version=_safe_fact(_qt_version),
            pyside_version=_safe_fact(_pyside_version),
        )

        # -- icon + name row ----------------------------------------------
        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("aboutIconLabel")
        icon_size = self.style().pixelMetric(QStyle.PixelMetric.PM_MessageBoxIconSize)
        self._icon_label.setPixmap(app_icon().pixmap(icon_size, icon_size))
        self._icon_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._name_label = QLabel(about_info.APP_NAME, self)
        self._name_label.setObjectName("aboutNameLabel")
        self._name_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        header = QHBoxLayout()
        header.addWidget(self._icon_label)
        header.addWidget(self._name_label)
        header.addStretch(1)

        # -- version / licence / links / environment (form rows) ----------
        self._version_caption = QLabel(self)
        self._version_value = QLabel(self._version_text, self)
        self._version_value.setObjectName("aboutVersionValue")
        self._version_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self._licence_caption = QLabel(self)
        self._licence_value = QLabel(about_info.LICENCE_NAME, self)
        self._licence_value.setObjectName("aboutLicenceValue")

        self._link_labels: dict[str, QLabel] = {}
        for object_name, url in _LINKS:
            link = _Link_Label(self)
            link.setObjectName(object_name)
            link.setTextFormat(Qt.TextFormat.RichText)
            link.setTextInteractionFlags(
                Qt.TextInteractionFlag.LinksAccessibleByMouse
                | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
            )
            link.setOpenExternalLinks(False)
            link.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            link.setProperty("url", url)
            link.linkActivated.connect(self._on_link_activated)
            self._link_labels[object_name] = link

        self._environment_caption = QLabel(self)
        self._environment_value = QLabel(self)
        self._environment_value.setObjectName("aboutEnvironmentValue")
        self._environment_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        form = QFormLayout()
        form.addRow(self._version_caption, self._version_value)
        form.addRow(self._licence_caption, self._licence_value)
        for object_name, _url in _LINKS:
            form.addRow(self._link_labels[object_name])
        form.addRow(self._environment_caption, self._environment_value)

        # -- buttons --------------------------------------------------------
        self._copy_button = QPushButton(self)
        self._copy_button.setObjectName("aboutCopyButton")
        self._copy_button.clicked.connect(self._on_copy)

        self._close_button = QPushButton(self)
        self._close_button.setObjectName("aboutCloseButton")
        self._close_button.setDefault(True)
        self._close_button.setAutoDefault(True)
        self._close_button.clicked.connect(self.reject)

        self._button_box = QDialogButtonBox(self)
        self._button_box.addButton(
            self._copy_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        self._button_box.addButton(
            self._close_button, QDialogButtonBox.ButtonRole.RejectRole
        )
        self._button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addLayout(form)
        layout.addWidget(self._button_box)

        # Explicit Tab chain (plan §3.2): the three links, then Copy, Close.
        ordered = [self._link_labels[name] for name, _url in _LINKS] + [
            self._copy_button,
            self._close_button,
        ]
        for earlier, later in zip(ordered, ordered[1:]):
            QWidget.setTabOrder(earlier, later)

        self._retranslate()

    # -- link handling ------------------------------------------------------

    def _on_link_activated(self, url: str) -> None:
        """Hand ``url`` off to the module-level :func:`_open_url` seam.

        Calls the seam by its module-global name at invocation time (not a
        reference captured at connect time), so tests that monkeypatch
        ``pixelart_creator.ui.about_dialog._open_url`` observe the hand-off
        (ADR-0067 Part 1).
        """
        _open_url(url)

    # -- Copy -----------------------------------------------------------

    def _on_copy(self) -> None:
        """Copy the composed one-line environment summary to the clipboard."""
        QGuiApplication.clipboard().setText(self._environment_value.text())

    # -- i18n -----------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("About PixelArt Creator"))
        self.setAccessibleName(self.tr("About PixelArt Creator dialog"))

        self._icon_label.setAccessibleName(self.tr("PixelArt Creator icon"))
        self._name_label.setAccessibleName(self.tr("Application name"))
        self._version_caption.setText(self.tr("Version:"))
        self._version_value.setAccessibleName(self.tr("Application version"))
        self._licence_caption.setText(self.tr("Licence:"))
        self._licence_value.setAccessibleName(self.tr("Licence name"))
        self._environment_caption.setText(self.tr("Environment:"))
        self._environment_value.setAccessibleName(self.tr("Environment summary"))

        colour = link_colour(self._theme).name()
        captions = {
            "aboutRepositoryLink": self.tr("Repository"),
            "aboutDocumentationLink": self.tr("Documentation"),
            "aboutReleasesLink": self.tr("Releases"),
        }
        for object_name, url in _LINKS:
            link = self._link_labels[object_name]
            caption = html.escape(captions[object_name])
            link.setText(
                f'<a href="{url}" style="color:{colour}; '
                f'text-decoration: underline;">{caption}</a>'
            )
            link.setAccessibleName(captions[object_name])

        self._copy_button.setText(self.tr("&Copy"))
        self._copy_button.setAccessibleName(self.tr("Copy environment summary"))
        self._close_button.setText(self.tr("C&lose"))
        self._close_button.setAccessibleName(self.tr("Close the About dialog"))

        self._environment_value.setText(
            about_info.compose_environment_line(
                self._environment_facts, self.tr("unknown")
            )
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on ``QEvent.LanguageChange`` (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
