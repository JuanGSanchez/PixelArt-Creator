"""Rendered keyboard-focus evidence shared by the UI suite (REQ-VI-UI-005, ADR-0069).

Until the pixel-art visual identity the suite proved "focus is visible" by
looking for the substring ``":focus"`` in the application stylesheet. That
proxy is withdrawn (ADR-0069): the stylesheet carries no ``:focus``
rule by design, and a stylesheet focus border on a framed control was measured
to draw **zero** focus-colour pixels, so the substring could be present while
the indicator was invisible. The focus indicator is now an overlay widget
(:class:`~pixelart_creator.ui.pixel_chrome.Focus_Ring_Widget`) painted in the
``focus`` role, so the evidence is a RENDERED check, and it is the same check
in every module that used the proxy:

* grab the control as Qt painted it **without** keyboard focus and count the
  pixels equal to the ``focus`` role colour of the active combination -- this
  must be 0 (the control neither carries the colour of its own nor shows a
  stale ring);
* give it keyboard focus (a Tab reason, as the keyboard would), grab again --
  this must be more than 0;
* assert the number of pixels examined is not zero, so an empty grab cannot
  pass for "no ring" or "ring present";
* clear the focus again and assert the ring is gone (focus-out hides it).

The colour is compared exactly: the art is drawn nearest-neighbour with no
antialiasing, so a ring pixel is the role colour or it is not a ring pixel.
Siblings of the proxy -- the assertions that panels carry no stylesheet of their
own (NFR-5) -- are NOT replaced and stay in the modules that own them.

The helper never edits product state beyond focus: it shows the control's
window, raises the dock or tab page that hides it, and gives focus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional, Set, Tuple

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QStackedWidget,
    QTabWidget,
    QWidget,
)
from pytestqt.exceptions import TimeoutError as QtTimeoutError

from pixelart_creator.ui.pixel_chrome import active_mode, active_style
from pixelart_creator.ui.theme import DEFAULT_STYLE, role_colour

__all__ = [
    "FocusEvidence",
    "colour_mask",
    "count_colour_pixels",
    "distinct_neighbours",
    "image_array",
    "focus_pixel_rgb",
    "grab_image",
    "measure_focus",
    "assert_focus_rendered",
    "reveal",
]

_ACTIVATION_TIMEOUT_MS = 2000

#: A sanity bound: a ring is a band, so it can never be the majority of a
#: control. Guards the test against a control that is simply painted in the
#: focus colour (which would also make "unfocused == 0" fail, but this names it).
_MAX_RING_SHARE = 0.5


@dataclass(frozen=True)
class FocusEvidence:
    """The numbers one focus measurement produced (printed on failure)."""

    mode: str
    style: str
    colour: str
    examined: int
    unfocused_px: int
    focused_px: int
    cleared_px: int
    enabled: bool = True
    took_focus: bool = True

    def describe(self) -> str:
        """Return a one-line account of the measurement."""
        return (
            f"{self.style}/{self.mode} focus {self.colour}: examined "
            f"{self.examined} px; focus-colour px unfocused={self.unfocused_px}, "
            f"focused={self.focused_px}, after focus-out={self.cleared_px}; "
            f"enabled={self.enabled}, took focus={self.took_focus}"
        )


def focus_pixel_rgb(mode: str, style: str = DEFAULT_STYLE) -> int:
    """Return the ``focus`` role of ``mode`` in ``style`` as an opaque ``0xFFRRGGBB``."""
    return QColor(role_colour(mode, "focus", style)).rgb()


def grab_image(widget: QWidget) -> QImage:
    """Return ``widget`` as painted (children and overlays included) as an image."""
    return widget.grab().toImage()


def image_array(image: QImage) -> np.ndarray:
    """Return ``image`` as a copied ``(height, width, 4)`` uint8 RGBA array."""
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    raw = np.frombuffer(rgba.constBits(), dtype=np.uint8, count=rgba.sizeInBytes())
    rows = raw.reshape(rgba.height(), rgba.bytesPerLine())
    return rows[:, : rgba.width() * 4].reshape(rgba.height(), rgba.width(), 4).copy()


def _rgb_triplet(rgb: int) -> Tuple[int, int, int]:
    return ((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)


def colour_mask(image: QImage, rgb: int) -> np.ndarray:
    """Return a boolean mask of the opaque pixels of ``image`` equal to ``rgb``."""
    data = image_array(image)
    red, green, blue = _rgb_triplet(rgb)
    return (
        (data[..., 0] == red)
        & (data[..., 1] == green)
        & (data[..., 2] == blue)
        & (data[..., 3] == 255)
    )


def count_colour_pixels(image: QImage, rgb: int) -> int:
    """Return how many pixels of ``image`` equal the opaque colour ``rgb`` exactly."""
    return int(colour_mask(image, rgb).sum())


def _ancestors(widget: QWidget) -> Iterator[QWidget]:
    parent: Optional[QWidget] = widget.parentWidget()
    while parent is not None:
        yield parent
        parent = parent.parentWidget()


def reveal(qtbot, control: QWidget) -> QWidget:
    """Show ``control``'s window and bring the control on screen; return the window.

    A control may sit in a tabified dock behind another or on an inactive tab
    page; the helper raises exactly those containers (nothing else), shows the
    top-level window, activates it (keyboard focus needs an active window) and
    lets the layout settle.
    """
    window = control.window()
    if not window.isVisible():
        window.show()
        qtbot.waitExposed(window)
    child = control
    page: Optional[QWidget] = None
    for ancestor in _ancestors(control):
        if isinstance(ancestor, QDockWidget):
            ancestor.show()
            ancestor.raise_()
        elif isinstance(ancestor, QTabWidget):
            # a QTabWidget's pages live in its internal stack: ``page`` is the one
            # on the control's path, and selecting it keeps the tab bar in step
            if page is not None and ancestor.indexOf(page) >= 0:
                ancestor.setCurrentWidget(page)
        elif isinstance(ancestor, QStackedWidget):
            if ancestor.indexOf(child) >= 0:
                ancestor.setCurrentWidget(child)
                page = child
        child = ancestor
    window.activateWindow()
    window.raise_()
    try:
        qtbot.waitUntil(window.isActiveWindow, timeout=_ACTIVATION_TIMEOUT_MS)
    except QtTimeoutError:
        # A platform that never activates the window gives the control no FocusIn:
        # the measurement then says so ("did not take keyboard focus"), by name.
        pass
    QApplication.processEvents()
    return window


def _settle() -> None:
    QApplication.processEvents()
    QApplication.processEvents()


def measure_focus(
    qtbot, control: QWidget, mode: Optional[str] = None, style: Optional[str] = None
) -> FocusEvidence:
    """Measure the focus-colour pixels of ``control`` unfocused, focused and cleared.

    Args:
        qtbot: The pytest-qt fixture.
        control: A keyboard-focusable control that carries a pixel frame (a
            push or tool button, a field, a combo or spin box, an item view,
            a slider, a tab bar ...). For a spin or combo box pass the box, not
            its embedded line edit: the ring frames the whole control.
        mode: The mode whose ``focus`` role colour is looked for. Default: the
            mode the overlays are painting in (``pixel_chrome.active_mode()``), i.e.
            the one ``apply_theme`` last applied. Pass it explicitly to assert that
            a combination really is the one on screen: a ``Main_Window`` applies
            Light when it is constructed, whatever the suite's theme fixture said.
        style: The style id (default: the active style).

    Returns:
        The three counts and the number of pixels examined per grab.
    """
    reveal(qtbot, control)
    mode = active_mode() if mode is None else mode
    style = active_style() if style is None else style
    rgb = focus_pixel_rgb(mode, style)
    control.clearFocus()
    _settle()
    before = grab_image(control)
    unfocused = count_colour_pixels(before, rgb)
    control.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    took_focus = control.hasFocus() or any(
        child.hasFocus() for child in control.findChildren(QWidget)
    )
    focused_image = grab_image(control)
    focused = count_colour_pixels(focused_image, rgb)
    control.clearFocus()
    _settle()
    cleared = count_colour_pixels(grab_image(control), rgb)
    examined = before.width() * before.height()
    return FocusEvidence(
        mode=mode,
        style=style,
        colour=f"#{rgb & 0xFFFFFF:06X}",
        examined=min(examined, focused_image.width() * focused_image.height()),
        unfocused_px=unfocused,
        focused_px=focused,
        cleared_px=cleared,
        enabled=control.isEnabled(),
        took_focus=took_focus,
    )


def assert_focus_rendered(
    qtbot, control: QWidget, mode: Optional[str] = None, style: Optional[str] = None
) -> FocusEvidence:
    """Assert a rendered focus ring: absent unfocused, present focused, gone after.

    This is the shared replacement of the ``":focus" in styleSheet()`` proxy
    (ADR-0069). It fails, naming the numbers, when the control shows no ring on
    focus (the case the proxy could not see), when it shows focus colour
    without focus, or when the ring survives focus-out.

    Returns:
        The evidence, for callers that assert more about it.
    """
    evidence = measure_focus(qtbot, control, mode, style)
    where = f"{type(control).__name__} {control.objectName()!r}: {evidence.describe()}"
    assert evidence.examined > 0, f"nothing was rendered to examine -- {where}"
    assert evidence.enabled, (
        f"the control is disabled and cannot take keyboard focus: pass an enabled "
        f"control -- {where}"
    )
    assert evidence.took_focus, f"the control did not take keyboard focus -- {where}"
    assert evidence.unfocused_px == 0, f"focus colour without focus -- {where}"
    assert evidence.focused_px > 0, f"no focus ring is drawn on focus -- {where}"
    assert (
        evidence.focused_px < evidence.examined * _MAX_RING_SHARE
    ), f"the 'ring' is most of the control -- {where}"
    assert evidence.cleared_px == 0, f"the ring survives focus-out -- {where}"
    return evidence


def distinct_neighbours(image: QImage, rgb: int) -> Set[Tuple[int, ...]]:
    """Return the distinct non-focus colours 4-adjacent to a focus pixel.

    These are the colours the focus indicator actually touches on screen
    (``REQ-VI-UI-004``'s third bullet), read from the rendered image.
    """
    mask = colour_mask(image, rgb)
    full = image_array(image)
    data = full[..., :3]
    opaque = full[..., 3] == 255
    touched = np.zeros_like(mask)
    touched[1:, :] |= mask[:-1, :]
    touched[:-1, :] |= mask[1:, :]
    touched[:, 1:] |= mask[:, :-1]
    touched[:, :-1] |= mask[:, 1:]
    touched &= ~mask & opaque
    return {tuple(int(c) for c in px) for px in data[touched]}
