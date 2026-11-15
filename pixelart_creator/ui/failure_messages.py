# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Failure messages that never show exception text.

An exception's text is written in English by the library that raised it, so
showing it puts an untranslated sentence in front of a user who chose another
language. This module is the one place where an exception becomes a sentence
the user reads: :func:`failure_kind` sorts the exception into one of six kinds
by its classes alone, and :func:`failure_text` returns the translated sentence
for a kind.

The failure is read through the chain of failures that led to it. The data
layer turns an operating-system or network failure into a domain error (a
``ValueError`` subclass) and chains the original with ``raise ... from``; the
class of the outer error alone would then call a missing file an invalid value.
The chain is the outer exception, then each ``__cause__`` (never
``__context__``, which only records that one error happened while another was
handled), and for a ``URLError`` also its ``reason`` when that is an exception.
It is read outermost first, to a fixed depth, and a loop ends it.

The first rule that applies wins, in this order:

1. The first link, outermost first, that is a ``TimeoutError`` -> ``TIMEOUT``,
   a ``ConnectionError`` -> ``CONNECTION``, a ``FileNotFoundError`` ->
   ``NOT_FOUND`` or a ``PermissionError`` -> ``PERMISSION`` decides (the tests
   run in that order on each link).
2. Otherwise, if any link is an ``OSError`` (``URLError``, ``SSLError`` and any
   other ``OSError``) or an ``ImportError`` -> ``GENERIC``: an operating-system,
   network or missing-dependency failure is not an invalid value, and no
   narrower sentence is established.
3. Otherwise, if any link is a ``ValueError``, subclasses included
   (``UnicodeDecodeError``, ``json.JSONDecodeError``) -> ``INVALID_VALUE``.
4. Anything else -> ``GENERIC``.

Each sentence names only what the chain establishes: an ``OSError`` that is
none of the classes in rule 1 does not establish a file cause, so it takes the
generic sentence.

A worker thread emits ``failure_kind(exc).value`` (a ``str``) and never text;
the GUI-thread slot rebuilds the kind with ``FailureKind(value)`` and calls
:func:`failure_text` when it shows the message, so the text follows a live
language switch and no translation runs on a worker thread.

The module imports only the standard library and ``PySide6.QtCore``.
"""

from __future__ import annotations

import enum
import logging

from PySide6.QtCore import QCoreApplication

_LOGGER = logging.getLogger(__name__)


class FailureKind(enum.Enum):
    """The kind of a failure, as far as its exception class establishes it.

    Each value is a plain ``str`` so a worker can emit it on a signal and the
    GUI thread can rebuild the member with ``FailureKind(value)``.
    """

    TIMEOUT = "timeout"
    CONNECTION = "connection"
    NOT_FOUND = "not_found"
    PERMISSION = "permission"
    INVALID_VALUE = "invalid_value"
    GENERIC = "generic"


#: The most links of a chain read; a longer chain is read only this far.
_MAX_CHAIN_LINKS = 16


def _chain(exc: BaseException) -> list[BaseException]:
    """Return ``exc`` and the failures that caused it, outermost first.

    Follows ``__cause__`` and a ``URLError``'s ``reason`` (an exception), stops at
    a repeat and after ``_MAX_CHAIN_LINKS`` links.
    """
    links: list[BaseException] = []
    seen: set[int] = set()
    link: BaseException | None = exc
    while link is not None and id(link) not in seen and len(links) < _MAX_CHAIN_LINKS:
        seen.add(id(link))
        links.append(link)
        reason = getattr(link, "reason", None) if isinstance(link, OSError) else None
        link = link.__cause__
        if link is None and isinstance(reason, BaseException):
            link = reason
    return links


def _os_kind(exc: BaseException) -> FailureKind | None:
    """Return the specific kind ``exc`` itself is, or ``None`` if it is none."""
    if isinstance(exc, TimeoutError):
        return FailureKind.TIMEOUT
    if isinstance(exc, ConnectionError):
        return FailureKind.CONNECTION
    if isinstance(exc, FileNotFoundError):
        return FailureKind.NOT_FOUND
    if isinstance(exc, PermissionError):
        return FailureKind.PERMISSION
    return None


def failure_kind(exc: BaseException) -> FailureKind:
    """Return the kind of ``exc`` from its classes alone (pure, no text read).

    The chain of ``exc`` is read as the module docstring states: the first
    timeout, connection, not-found or permission link decides; else any other
    ``OSError`` or ``ImportError`` link gives ``GENERIC``; else a ``ValueError``
    link gives ``INVALID_VALUE``; else ``GENERIC``.
    """
    links = _chain(exc)
    for link in links:
        kind = _os_kind(link)
        if kind is not None:
            return kind
    if any(isinstance(link, (OSError, ImportError)) for link in links):
        return FailureKind.GENERIC
    if any(isinstance(link, ValueError) for link in links):
        return FailureKind.INVALID_VALUE
    return FailureKind.GENERIC


def log_failure(exc: BaseException) -> None:
    """Log the exception's detail; the interface never shows it.

    Call it from an ``except`` handler, before the kind is read.
    """
    # `.log(logging.WARNING, ...)`: the string audit reads `.warning("...")` as a
    # QMessageBox text (the precedent in `ui/i18n.py`).
    _LOGGER.log(logging.WARNING, "operation failed", exc_info=exc)


def logged_failure_kind(exc: BaseException) -> FailureKind:
    """Return the kind of ``exc`` and log the exception's detail.

    The user sees only the sentence for the kind; the exception itself goes to
    the log, never to the interface. Call it from an ``except`` handler.
    """
    log_failure(exc)
    return failure_kind(exc)


def failure_text(kind: FailureKind) -> str:
    """Return the translated sentence for ``kind`` in the current language."""
    if kind is FailureKind.TIMEOUT:
        return QCoreApplication.translate(
            "Failure_Messages", "The operation timed out."
        )
    if kind is FailureKind.CONNECTION:
        return QCoreApplication.translate("Failure_Messages", "The connection failed.")
    if kind is FailureKind.NOT_FOUND:
        return QCoreApplication.translate(
            "Failure_Messages", "The file or folder could not be found."
        )
    if kind is FailureKind.PERMISSION:
        return QCoreApplication.translate(
            "Failure_Messages", "Access to the file or folder was denied."
        )
    if kind is FailureKind.INVALID_VALUE:
        return QCoreApplication.translate(
            "Failure_Messages", "A value was not valid for this operation."
        )
    return QCoreApplication.translate(
        "Failure_Messages", "The operation could not be completed."
    )
