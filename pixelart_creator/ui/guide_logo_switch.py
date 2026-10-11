# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The hidden switch over the user guide's logo (``REQ-VI-UI-017``).

The logo shown on a guide page is itself a switch: activating it turns the
pixel font on or off for the guide's *page text* (and nothing else). It has no
visible label, so it is an easter egg, but it is a real control: it has an
accessible name, it is reached with Tab, Enter and Space toggle it, and it wears
the same focus ring as every other focusable control (the application's focus
overlay draws it).

:class:`Guide_Logo_Switch_Widget` is a transparent :class:`QAbstractButton` that
is a child of the text browser's viewport. Its geometry is the rectangle of the
logo image fragment in the document layout, re-placed whenever the layout can
have moved: on scroll, resize, re-layout and topic change. It is hidden on a
page that has no logo. When the logo image itself is missing, the markdown
importer still leaves the image fragment (it draws the alternative text), so
the same rectangle is covered and the switch keeps working.

Presentation only (S11): it holds the on/off state of the click and announces
it; the stored preference and the font choice live elsewhere.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QObject, QRect, Qt
from PySide6.QtGui import QKeyEvent, QPaintEvent, QTextCursor, QTextImageFormat
from PySide6.QtWidgets import QAbstractButton, QTextBrowser

__all__ = ["Guide_Logo_Switch_Widget", "logo_rect"]

#: Object name of the switch (a stable handle for tests and accessibility tools).
LOGO_SWITCH_OBJECT_NAME = "GuideLogoSwitch"


def logo_rect(browser: QTextBrowser, logo_name: str) -> Optional[QRect]:
    """Return the logo image's rectangle in viewport coordinates, or ``None``.

    ``logo_name`` is the image name as the page's markdown writes it. The
    rectangle runs from the caret position before the image fragment to the
    caret position after it on the same line; when the image wraps onto another
    line the image's own width (or its line height) is used instead.
    """
    document = browser.document()
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isImageFormat():
                image_format: QTextImageFormat = fragment.charFormat().toImageFormat()
                if image_format.name() == logo_name:
                    start = QTextCursor(document)
                    start.setPosition(fragment.position())
                    end = QTextCursor(document)
                    end.setPosition(fragment.position() + fragment.length())
                    left = browser.cursorRect(start)
                    right = browser.cursorRect(end)
                    same_line = abs(right.top() - left.top()) < left.height()
                    width = right.left() - left.left()
                    if not same_line or width <= 0:
                        width = int(image_format.width()) or left.height()
                    return QRect(left.left(), left.top(), width, left.height())
            iterator += 1
        block = block.next()
    return None


class Guide_Logo_Switch_Widget(QAbstractButton):
    """A transparent, keyboard-reachable button laid over the guide's logo."""

    def __init__(self, browser: QTextBrowser, logo_name: str) -> None:
        """Place the switch on ``browser``'s viewport over the ``logo_name`` image."""
        super().__init__(browser.viewport())
        self._browser = browser
        self._logo_name = logo_name
        self.setObjectName(LOGO_SWITCH_OBJECT_NAME)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._retranslate()
        browser.verticalScrollBar().valueChanged.connect(self.place)
        browser.document().documentLayout().documentSizeChanged.connect(self.place)
        browser.viewport().installEventFilter(self)
        self.hide()

    def place(self, *_args: object) -> None:
        """Cover the logo fragment, or hide the switch when the page has none."""
        rect = logo_rect(self._browser, self._logo_name)
        if rect is None or rect.isEmpty():
            self.hide()
            return
        if self.geometry() != rect:
            self.setGeometry(rect)
        if not self.isVisible():
            self.show()
        self.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Re-place the switch when the viewport is resized; never consume."""
        if watched is self._browser.viewport() and event.type() == QEvent.Type.Resize:
            self.place()
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        """Toggle on Enter as well as Space (a button only takes Space)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        """Paint nothing: the logo underneath is the visible part."""

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Switch the pixel font for the guide's pages"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange; delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
