"""A failure is reported in the interface language, without exception text.

REQ-L10N-UI-018: when an operation fails and the interface says so, the message is
built only from catalogue messages and the operation's own data, never from the
text an exception carries. In each language the message is that catalogue's
finished translation with its placeholders filled, and it holds neither the
exception's message nor its type name.

The four channels through which an exception's text could reach a user are each
driven through one real site of the interface, made to fail with a planted
``ValueError`` subclass whose message is ``ZQX exception marker``:

* a message box: ``Asset_Tagging_Panel`` rejecting a tag;
* a translated template: ``User_Guide_Dialog`` failing to load a topic (the
  ``Could not load this topic:`` frame with the sentence in its placeholder);
* a worker signal: ``Cloud_Controller`` relaying a failed cloud operation;
* text stored for later display: ``Dependency_Graph_View`` keeping a cycle report
  and showing it in its notice.

The planted class derives from the class each site catches, so the site's own
handler runs. What a site shows is read from where the user reads it (the box's
text, the guide pane, the controller's ``operationFailed`` message, the notice
label), and exactly one message must have been shown, so a case cannot pass
because nothing was shown.

The oracle is never the code under test. The six sentences are the English source
messages the requirement's plan names for the six kinds of failure; the two
frames are read from the catalogue file (the pair must exist there). For a
language other than English the expected text is read from that language's own
``.ts`` file, finished entries only. Only English is examined for now: the other
seven languages are added to ``LANGUAGES_UNDER_TEST`` as their catalogues carry the
new messages, and every printed line says how many of the eight were examined.

The leak controls plant, at the one seam that turns a failure into text
(``failure_text``), a version that returns what ``str(exc)`` with its type name
would show; each channel must then fail. Both themes, offscreen.
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import xml.etree.ElementTree as ET
import zipfile
from typing import Callable, Dict, Iterator, List, Optional, Tuple, Type

import pytest
from PySide6.QtWidgets import QApplication

import pixelart_creator.logic.export as logic_export
import pixelart_creator.ui.asset_tagging_panel as asset_tagging_panel
import pixelart_creator.ui.assistant_worker as assistant_worker
import pixelart_creator.ui.dependency_graph_view as dependency_graph_view
import pixelart_creator.ui.failure_messages as failure_messages
from pixelart_creator.data.cloud import CloudError, FakeCloudAdapter
from pixelart_creator.data.guide_content import GuideContentError
from pixelart_creator.data.llm.port import LLMError
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_tags import AssetTagError
from pixelart_creator.logic.assistant import AssistantError, Conversation
from pixelart_creator.logic.dependency_graph import DependencyGraphError
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import ExportError, ExportFormat, ExportRequest
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_tagging_panel import Asset_Tagging_Panel
from pixelart_creator.ui.assistant_worker import Assistant_Controller
from pixelart_creator.ui.cloud_actions import Cloud_Session, make_save_job
from pixelart_creator.ui.cloud_worker import Cloud_Controller
from pixelart_creator.ui.dependency_graph_view import Dependency_Graph_View
from pixelart_creator.ui.export_worker import Export_Controller, ExportTarget
from pixelart_creator.ui.failure_messages import (
    FailureKind,
    failure_kind,
    failure_text,
)
from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
from pixelart_creator.ui.user_guide import User_Guide_Dialog

# --------------------------------------------------------------------------- #
# The oracle                                                                  #
# --------------------------------------------------------------------------- #

#: The marker every planted exception carries, and the name of its type.
MARKER = "ZQX exception marker"
PLANTED_TYPE = "ZqxPlantedError"

#: The number of languages the finished product ships (English included).
EXPECTED_LANGUAGE_COUNT = 8

#: The languages examined now. A language joins when its catalogue holds the new
#: messages as finished entries.
LANGUAGES_UNDER_TEST: Tuple[str, ...] = (FALLBACK_LANGUAGE,)

_FAILURE_CONTEXT = "Failure_Messages"

#: The English source message of each kind of failure, as the requirement's plan
#: states them. The member names are the kinds; the values are what a worker emits.
SENTENCES: Dict[str, Tuple[str, str]] = {
    "TIMEOUT": ("timeout", "The operation timed out."),
    "CONNECTION": ("connection", "The connection failed."),
    "NOT_FOUND": ("not_found", "The file or folder could not be found."),
    "PERMISSION": ("permission", "Access to the file or folder was denied."),
    "INVALID_VALUE": ("invalid_value", "A value was not valid for this operation."),
    "GENERIC": ("generic", "The operation could not be completed."),
}

#: The two catalogue messages that frame the sentence, as (context, source).
_GUIDE_FRAME = ("User_Guide_Dialog", "Could not load this topic:\n\n%1")
_CYCLE_FRAME = (
    "Dependency_Graph_View",
    "Dependency cycle detected (graph unchanged): %1",
)

#: The channels, in the order the requirement lists them.
CHANNELS = (
    "message box",
    "translated template",
    "worker signal",
    "stored for later display",
)

#: The site that stands for each channel.
SITES = {
    "message box": "ui/asset_tagging_panel.py, Asset_Tagging_Panel._on_add_tag",
    "translated template": "ui/user_guide.py, User_Guide_Dialog content-load handler",
    "worker signal": "ui/cloud_worker.py, the worker's failure signal and its relay",
    "stored for later display": "ui/dependency_graph_view.py, show_edges and _refresh",
}


def _catalogue_message(code: str, context: str, source: str) -> str:
    """Return the text the catalogue of ``code`` holds for (context, source).

    English has no translation and shows the source, which must nevertheless be a
    message of ``pixelart_en.ts`` for the two frames. Any other language is read
    from its own ``.ts``: exactly one entry, finished, with a text.
    """
    path = _default_translations_dir() / f"pixelart_{code}.ts"
    root = ET.parse(path).getroot()
    found = [
        message
        for scope in root.iter("context")
        if scope.findtext("name") == context
        for message in scope.iter("message")
        if message.findtext("source") == source
    ]
    if code == FALLBACK_LANGUAGE:
        if context != _FAILURE_CONTEXT:
            assert len(found) == 1, f"{path.name}: {len(found)} entries for {source!r}"
        return source
    assert len(found) == 1, f"{path.name}: {len(found)} entries for {source!r}"
    translation = found[0].find("translation")
    assert translation is not None and translation.text, f"{path.name}: no text"
    assert translation.get("type") != "unfinished", f"{path.name}: unfinished"
    return translation.text


def _sentence(code: str, kind: str) -> str:
    """Return the catalogue's text of the sentence for ``kind`` (a member name)."""
    return _catalogue_message(code, _FAILURE_CONTEXT, SENTENCES[kind][1])


def _framed(code: str, frame: Tuple[str, str], kind: str) -> str:
    """Return the frame's catalogue text with the sentence in its placeholder."""
    template = _catalogue_message(code, *frame)
    assert template.count("%1") == 1, f"{frame[0]}: {template!r} has no placeholder"
    return template.replace("%1", _sentence(code, kind))


def _planted(
    base: Type[BaseException], cause: Optional[BaseException] = None
) -> BaseException:
    """Return an exception of a planted subclass of ``base`` carrying the marker.

    With a ``cause`` it is raised ``from`` it, as a domain error wraps the
    operating-system failure it caught.
    """
    assert issubclass(base, ValueError), f"{base.__name__} is not a ValueError"
    planted = type(PLANTED_TYPE, (base,), {})(MARKER)
    if cause is not None:
        planted.__cause__ = cause
    return planted


def assert_clean(shown: List[str], expected: str, base: Type[BaseException]) -> None:
    """Fail unless exactly one message was shown, equal to ``expected``, and clean.

    Clean is: neither the marker, nor the planted type's name, nor the name of the
    class it derives from.
    """
    assert len(shown) == 1, f"{len(shown)} messages were shown, not one: {shown!r}"
    message = shown[0]
    assert message == expected, f"shown {message!r}, the catalogue holds {expected!r}"
    for text in (MARKER, PLANTED_TYPE, base.__name__):
        assert text not in message, f"{text!r} is shown in {message!r}"


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def language(qapp) -> Iterator[Callable[[str], None]]:
    """Install a language through the app's own manager; restore English after."""
    manager = LanguageManager(qapp)

    def install(code: str) -> None:
        assert manager.set_language(code) is True, f"{code!r} did not load"
        assert manager.current_language() == code

    try:
        yield install
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# One driver per channel: make the site fail, return what the user is shown   #
# --------------------------------------------------------------------------- #


def _drive_message_box(
    qtbot,
    monkeypatch,
    boxes: list,
    cause: Optional[BaseException] = None,
) -> Tuple[List[str], Type[BaseException]]:
    """Make the tagging panel reject a tag with a planted error; return the boxes."""
    base = AssetTagError
    failure = _planted(base, cause)

    def raising(descriptor, tag):
        raise failure

    monkeypatch.setattr(asset_tagging_panel, "make_add_tag", raising)
    session = Asset_Library_Session(
        catalog=AssetCatalog(
            descriptors=(
                AssetDescriptor(
                    asset_id="a1",
                    kind=AssetKind.SPRITE,
                    name="Hero",
                    content_hash="hash-a1",
                    tags=frozenset({"hero"}),
                ),
            )
        )
    )
    panel = Asset_Tagging_Panel()
    qtbot.addWidget(panel)
    panel.set_session(session)
    panel.set_asset("a1")
    panel._tag_edit.setText("player")
    panel._on_add_tag()
    assert session.undo_stack().count() == 0, "the failed tag was pushed"
    return [text for (shown, _title, text) in boxes if shown == "warning"], base


def _drive_template(
    qtbot, cause: Optional[BaseException] = None
) -> Tuple[List[str], Type[BaseException]]:
    """Make a guide topic fail to load; return the text the pane shows."""
    base = GuideContentError
    failure = _planted(base, cause)
    asked: List[str] = []

    def raising(ref: str) -> str:
        asked.append(ref)
        raise failure

    dialog = User_Guide_Dialog(None, reader=raising, content_locales=frozenset({"en"}))
    qtbot.addWidget(dialog)
    assert asked, "the failing reader was never asked for a topic"
    return [dialog._content_view.toPlainText()], base


def _drive_worker(
    qtbot, cause: Optional[BaseException] = None
) -> Tuple[List[str], Type[BaseException]]:
    """Make a cloud operation fail on the worker; return the relayed messages."""
    base = CloudError
    failure = _planted(base, cause)

    class _Raising(FakeCloudAdapter):
        def put(self, *args, **kwargs):
            raise failure

    session = Cloud_Session(factory=lambda: _Raising(connected=True))
    session.connect_provider()
    controller = Cloud_Controller()
    shown: List[str] = []
    controller.operationFailed.connect(lambda _kind, message: shown.append(message))
    try:
        document = Document(
            16, 16, palette=Palette([(0, 0, 0, 255), (255, 255, 255, 255)])
        )
        port = session.port()
        assert port is not None, "the planted adapter did not connect"
        with qtbot.waitSignal(controller.operationFinished, timeout=5000):
            controller.submit("save", make_save_job(port, "proj", document))
    finally:
        controller.shutdown()
    return shown, base


def _drive_stored(
    qtbot, monkeypatch, cause: Optional[BaseException] = None
) -> Tuple[List[str], Type[BaseException]]:
    """Make a dependency graph fail to build; return the notice the view shows."""
    base = DependencyGraphError
    failure = _planted(base, cause)

    def raising(*args, **kwargs):
        raise failure

    monkeypatch.setattr(dependency_graph_view, "DependencyGraph", raising)
    view = Dependency_Graph_View()
    qtbot.addWidget(view)
    view.show()
    view.show_edges(())
    QApplication.processEvents()
    assert not view._cycle_label.isHidden(), "the notice is not shown"
    return [view._cycle_label.text()], base


def _frame_for(channel: str):
    """Return the frame a channel composes its message in (``None``: none)."""
    return {
        "message box": None,
        "translated template": _GUIDE_FRAME,
        "worker signal": None,
        "stored for later display": _CYCLE_FRAME,
    }[channel]


def _expected(code: str, channel: str, kind: str) -> str:
    """Return the message a channel must show in ``code`` for a failure of ``kind``."""
    frame = _frame_for(channel)
    return _sentence(code, kind) if frame is None else _framed(code, frame, kind)


def run_channel(
    channel: str,
    qtbot,
    monkeypatch,
    boxes: list,
    cause: Optional[BaseException] = None,
) -> Tuple[List[str], Type[BaseException]]:
    """Drive ``channel`` once with a planted ``ValueError`` subclass.

    With a ``cause`` the planted error is raised ``from`` it.
    """
    if channel == "message box":
        return _drive_message_box(qtbot, monkeypatch, boxes, cause)
    if channel == "translated template":
        return _drive_template(qtbot, cause)
    if channel == "worker signal":
        return _drive_worker(qtbot, cause)
    return _drive_stored(qtbot, monkeypatch, cause)


# --------------------------------------------------------------------------- #
# The channels, one case per language                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("code", LANGUAGES_UNDER_TEST)
def test_a_failure_is_shown_as_the_catalogue_sentence_without_the_exception_text(
    qtbot, monkeypatch, mute_message_boxes, language, code, channel
):
    """REQ-L10N-UI-018: each channel shows the language's sentence, no exception text.

    The site named in ``SITES`` fails with a planted ``ValueError`` subclass whose
    message is the marker. The one message shown equals the catalogue's finished
    text for the sentence of the invalid-value kind (inside the frame, where the
    channel has one) and holds neither the marker, the planted type's name nor the
    name of the class it derives from.
    """
    language(code)
    shown, base = run_channel(channel, qtbot, monkeypatch, mute_message_boxes)
    assert_clean(shown, _expected(code, channel, "INVALID_VALUE"), base)


CAUSE_MARKER = "ZQX cause marker"


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("code", LANGUAGES_UNDER_TEST)
def test_a_wrapped_operating_system_failure_is_shown_as_its_own_sentence(
    qtbot, monkeypatch, mute_message_boxes, language, code, channel
):
    """REQ-L10N-UI-018: a domain error raised from a missing file is not "invalid".

    The same four sites fail with a planted ``ValueError`` subclass raised ``from`` a
    ``FileNotFoundError`` that carries a second marker. An operating-system failure
    is never an invalid value: the one message shown is the sentence for a missing
    file (inside the frame, where the channel has one), and neither marker, nor
    either class name, is in it.
    """
    language(code)
    cause = FileNotFoundError(CAUSE_MARKER)
    shown, base = run_channel(channel, qtbot, monkeypatch, mute_message_boxes, cause)
    assert_clean(shown, _expected(code, channel, "NOT_FOUND"), base)
    assert CAUSE_MARKER not in shown[0], shown
    assert "FileNotFoundError" not in shown[0], shown


@pytest.mark.parametrize("code", LANGUAGES_UNDER_TEST)
def test_the_languages_and_channels_examined_are_printed(
    qtbot, monkeypatch, mute_message_boxes, language, code, capsys
):
    """REQ-L10N-UI-018: the run says how many languages and channels it examined.

    English is examined now, so the line reads one of eight; every channel is driven
    and none may be skipped or examine nothing.
    """
    language(code)
    examined = 0
    for channel in CHANNELS:
        mute_message_boxes.clear()
        shown, base = run_channel(channel, qtbot, monkeypatch, mute_message_boxes)
        assert_clean(shown, _expected(code, channel, "INVALID_VALUE"), base)
        examined += 1
    line = (
        f"languages examined: {len(LANGUAGES_UNDER_TEST)} of {EXPECTED_LANGUAGE_COUNT} "
        f"{list(LANGUAGES_UNDER_TEST)}; channels examined: {examined} "
        f"{list(CHANNELS)}; sites: {json.dumps(SITES)}"
    )
    print(line)
    with capsys.disabled():
        print(f"[failure messages] {line}")
    assert examined == len(CHANNELS) == 4
    assert len(LANGUAGES_UNDER_TEST) >= 1


# --------------------------------------------------------------------------- #
# Controls: a site that shows the exception's text must fail                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("channel", CHANNELS)
def test_a_site_that_shows_the_exception_text_is_caught(
    qtbot, monkeypatch, mute_message_boxes, channel
):
    """Control: with the text seam planted to show ``str(exc)``, each channel fails.

    The planted ``failure_text`` returns what a site showing the exception's text
    with its type name would show (``ZqxPlantedError: ZQX exception marker``); the
    same driver and the same verdict must then reject the channel, because the shown
    text is not the sentence and holds the marker.
    """
    leaked = f"{PLANTED_TYPE}: {MARKER}"
    monkeypatch.setattr(failure_messages, "failure_text", lambda kind: leaked)
    shown, base = run_channel(channel, qtbot, monkeypatch, mute_message_boxes)
    assert any(MARKER in text for text in shown), f"the plant did not reach {channel}"
    with pytest.raises(AssertionError):
        assert_clean(shown, _expected("en", channel, "INVALID_VALUE"), base)


@pytest.mark.parametrize("channel", CHANNELS)
def test_a_sentence_of_the_wrong_kind_is_caught(
    qtbot, monkeypatch, mute_message_boxes, channel
):
    """Control: the verdict compares the sentence, so the generic one fails.

    The same failure is shown with the generic sentence in place of the
    invalid-value one; the verdict must reject it, which also shows the exact
    equality is not satisfied by any sentence.
    """
    monkeypatch.setattr(
        failure_messages,
        "failure_text",
        lambda kind: SENTENCES["GENERIC"][1],
    )
    shown, base = run_channel(channel, qtbot, monkeypatch, mute_message_boxes)
    assert len(shown) == 1
    with pytest.raises(AssertionError):
        assert_clean(shown, _expected("en", channel, "INVALID_VALUE"), base)


def test_the_verdict_accepts_a_clean_message_and_rejects_each_fault():
    """Control: written with literals, so the product plays no part."""
    good = SENTENCES["INVALID_VALUE"][1]
    assert_clean([good], good, ValueError)
    with pytest.raises(AssertionError):
        assert_clean([], good, ValueError)
    with pytest.raises(AssertionError):
        assert_clean([good, good], good, ValueError)
    with pytest.raises(AssertionError):
        assert_clean([f"{good} {MARKER}"], f"{good} {MARKER}", ValueError)
    with pytest.raises(AssertionError):
        assert_clean([f"{PLANTED_TYPE}: {good}"], f"{PLANTED_TYPE}: {good}", ValueError)
    with pytest.raises(AssertionError):
        assert_clean([f"{good} (ValueError)"], f"{good} (ValueError)", ValueError)
    with pytest.raises(AssertionError):
        assert_clean(["another sentence"], good, ValueError)


# --------------------------------------------------------------------------- #
# The six kinds of failure                                                    #
# --------------------------------------------------------------------------- #

_JSON_ERROR = json.JSONDecodeError("Expecting value", "", 0)
_UNICODE_ERROR = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

#: (an exception, the kind it must be given), one row per class the six kinds name,
#: with subclasses of each, and the controls the ordering and the fall-through need.
KIND_CASES: List[Tuple[str, BaseException, str]] = [
    ("TimeoutError", TimeoutError("t"), "TIMEOUT"),
    ("ConnectionError", ConnectionError("c"), "CONNECTION"),
    ("a ConnectionError subclass", ConnectionResetError("c"), "CONNECTION"),
    ("FileNotFoundError", FileNotFoundError("f"), "NOT_FOUND"),
    ("PermissionError", PermissionError("p"), "PERMISSION"),
    ("ValueError", ValueError("v"), "INVALID_VALUE"),
    ("UnicodeDecodeError", _UNICODE_ERROR, "INVALID_VALUE"),
    ("json.JSONDecodeError", _JSON_ERROR, "INVALID_VALUE"),
    ("a planted ValueError subclass", _planted(ValueError), "INVALID_VALUE"),
    ("RuntimeError", RuntimeError("r"), "GENERIC"),
    ("KeyError", KeyError("k"), "GENERIC"),
    # Controls: a TimeoutError is an OSError and must not fall through to the
    # generic sentence; an OSError that is none of the listed classes must.
    ("an OSError that is no listed subclass", OSError("o"), "GENERIC"),
    ("an OSError with a plain errno", OSError(5, "input/output error"), "GENERIC"),
]


@pytest.mark.parametrize(
    "label, exc, kind", KIND_CASES, ids=[case[0] for case in KIND_CASES]
)
def test_failure_kind_gives_each_class_its_kind_and_sentence(
    language, label, exc, kind
):
    """REQ-L10N-UI-018: an exception with no cause has its class decide the kind.

    The kinds and their order are the plan's table: a timeout is never a connection
    failure, a missing file is never generic, a value error with its subclasses is
    the invalid-value kind, and any other exception, any other ``OSError`` included,
    is generic because its class does not establish a file cause. The sentence for
    each kind is the English source message of the table.
    """
    language(FALLBACK_LANGUAGE)
    if label.startswith("an OSError"):
        assert type(exc) is OSError, "the control must be a plain OSError"
    got = failure_kind(exc)
    value, sentence = SENTENCES[kind]
    assert got.value == value, f"{label}: kind {got!r}, expected {kind}"
    assert got is FailureKind(value)
    assert failure_text(got) == sentence


def _wrapped(cause: Optional[BaseException]) -> BaseException:
    """Return a planted domain error (a ``ValueError``) raised ``from`` ``cause``."""
    return _planted(ValueError, cause)


def _from(outer: BaseException, cause: BaseException) -> BaseException:
    """Return ``outer`` raised ``from`` ``cause``."""
    outer.__cause__ = cause
    return outer


def _chain_of(length: int) -> BaseException:
    """Return a chain of ``length`` links of ``RuntimeError`` over a missing file."""
    head: BaseException = FileNotFoundError("deepest")
    for _ in range(length):
        head = _from(RuntimeError("link"), head)
    return head


def _loop() -> BaseException:
    """Return two exceptions that are each other's cause."""
    first, second = RuntimeError("a"), RuntimeError("b")
    first.__cause__, second.__cause__ = second, first
    return first


def _implicit_context_only() -> BaseException:
    """Return a ``ValueError`` raised while a ``FileNotFoundError`` was handled."""
    try:
        try:
            raise FileNotFoundError("handled")
        except FileNotFoundError:
            raise ValueError("raised in the handler")  # noqa: B904 (the point)
    except ValueError as error:
        return error
    raise AssertionError("unreachable")


_URL_TIMEOUT = urllib.error.URLError(TimeoutError("t"))
_URL_REFUSED = urllib.error.URLError(ConnectionRefusedError("c"))
_URL_NO_HOST = urllib.error.URLError(socket.gaierror(-2, "no such host"))
_HTTP_ERROR = urllib.error.HTTPError(
    "http://x", 500, "x", None, None  # type: ignore[arg-type]
)


def _wrapped_runtime(cause: BaseException) -> BaseException:
    """Return a ``RuntimeError`` (not a ``ValueError``) raised ``from`` ``cause``."""
    error = RuntimeError("wrapper")
    error.__cause__ = cause
    return error


#: (a label, an exception, the kind it must be given): a failure is judged by what
#: caused it, not by the domain error that reports it. A missing file, a denied
#: folder, a timeout, a refused connection are those sentences however many domain
#: errors wrap them; any other operating-system, network or missing-dependency
#: cause is generic; an invalid value stays one. The outermost cause that is one of
#: the four named classes decides; only an established cause counts, so a handler's
#: implicit context does not.
CHAIN_CASES: List[Tuple[str, BaseException, str]] = [
    (
        "a domain error from a missing file",
        _wrapped(FileNotFoundError("f")),
        "NOT_FOUND",
    ),
    (
        "a domain error from a denied folder",
        _wrapped(PermissionError("p")),
        "PERMISSION",
    ),
    ("a domain error from a timeout", _wrapped(TimeoutError("t")), "TIMEOUT"),
    (
        "a domain error from a refused connection",
        _wrapped(ConnectionRefusedError("c")),
        "CONNECTION",
    ),
    (
        "a domain error from a URL error that timed out",
        _wrapped(_URL_TIMEOUT),
        "TIMEOUT",
    ),
    (
        "a domain error from a URL error that was refused",
        _wrapped(_URL_REFUSED),
        "CONNECTION",
    ),
    ("a domain error from an unknown host", _wrapped(_URL_NO_HOST), "GENERIC"),
    (
        "a domain error from an HTTP error",
        _wrapped(_HTTP_ERROR),
        "GENERIC",
    ),
    (
        "a domain error from a directory error",
        _wrapped(IsADirectoryError("d")),
        "GENERIC",
    ),
    ("a domain error from a missing dependency", _wrapped(ImportError("i")), "GENERIC"),
    (
        "a domain error from a bad archive",
        _wrapped(zipfile.BadZipFile("z")),
        "INVALID_VALUE",
    ),
    ("a domain error from bad JSON", _wrapped(_JSON_ERROR), "INVALID_VALUE"),
    ("a domain error from bad bytes", _wrapped(_UNICODE_ERROR), "INVALID_VALUE"),
    ("a domain error with no cause", _wrapped(None), "INVALID_VALUE"),
    ("a URL error that timed out, unwrapped", _URL_TIMEOUT, "TIMEOUT"),
    (
        "a certificate error (a value error and an OS error)",
        ssl.SSLCertVerificationError(1, "bad certificate"),
        "GENERIC",
    ),
    (
        "a non-value error from a missing file",
        _wrapped_runtime(FileNotFoundError("f")),
        "NOT_FOUND",
    ),
    (
        "a value error from a value error from a missing file",
        _wrapped(_wrapped(FileNotFoundError("f"))),
        "NOT_FOUND",
    ),
    # Controls on the order and on what counts as a cause.
    (
        "a connection error from a timeout",
        _from(ConnectionError("c"), TimeoutError("t")),
        "CONNECTION",
    ),
    (
        "a timeout from a connection error",
        _from(TimeoutError("t"), ConnectionError("c")),
        "TIMEOUT",
    ),
    (
        "a denied folder from a missing file",
        _from(PermissionError("p"), FileNotFoundError("f")),
        "PERMISSION",
    ),
    (
        "a value error raised while a missing file was handled",
        _implicit_context_only(),
        "INVALID_VALUE",
    ),
]


@pytest.mark.parametrize(
    "label, exc, kind", CHAIN_CASES, ids=[case[0] for case in CHAIN_CASES]
)
def test_failure_kind_reads_what_caused_the_failure(language, label, exc, kind):
    """REQ-L10N-UI-018: the sentence is true of the cause, however it is wrapped.

    Each row is a failure and the kind of sentence it must be given in English.
    An operating-system or network failure that a domain error wraps is never
    reported as an invalid value; a cause that only appears as the context of a
    handler is not a cause; a loop and a long chain end.
    """
    language(FALLBACK_LANGUAGE)
    got = failure_kind(exc)
    value, sentence = SENTENCES[kind]
    assert got.value == value, f"{label}: kind {got!r}, expected {kind}"
    assert failure_text(got) == sentence


def test_a_loop_of_causes_and_a_long_chain_end():
    """REQ-L10N-UI-018: reading the causes always ends, and gives one of the kinds."""
    assert failure_kind(_loop()) is FailureKind.GENERIC
    for length in (3, 40, 1000):
        assert isinstance(failure_kind(_chain_of(length)), FailureKind), length
    assert failure_kind(_chain_of(3)) is FailureKind.NOT_FOUND


def test_there_are_exactly_six_kinds_with_the_documented_values():
    """REQ-L10N-UI-018: six kinds, each a plain string a worker can emit."""
    assert [member.name for member in FailureKind] == list(SENTENCES)
    assert {member.value for member in FailureKind} == {
        value for value, _ in SENTENCES.values()
    }
    assert len(set(sentence for _, sentence in SENTENCES.values())) == 6
    assert KIND_CASES, "no kind case was examined"


# --------------------------------------------------------------------------- #
# Two worker paths that classify the exception a worker carries               #
# --------------------------------------------------------------------------- #

#: Markers in the planted operating-system failure and in the error that wraps it.
OS_MARKER = "ZQX operating-system marker"
WRAPPER_MARKER = "ZQX wrapper marker"

#: (a label, the operating-system failure planted, the kind of its sentence).
OS_FAILURES: List[Tuple[str, Type[OSError], str]] = [
    ("a timeout", TimeoutError, "TIMEOUT"),
    ("a reset connection", ConnectionResetError, "CONNECTION"),
    ("a missing file", FileNotFoundError, "NOT_FOUND"),
    ("a denied folder", PermissionError, "PERMISSION"),
]


def _drive_assistant(
    qtbot, monkeypatch, os_failure: Optional[Type[OSError]]
) -> List[str]:
    """Fail one assistant turn mid-turn; return what the controller says failed.

    The turn fails the way a real one does: the LLM port's own error is raised
    from the operating-system failure, and the turn's loop wraps that as an
    ``AssistantError`` raised from it. With no ``os_failure`` the
    ``AssistantError`` has no cause.
    """

    def failing_turn(*_args, **_kwargs):
        if os_failure is None:
            raise AssistantError(MARKER, applied_commands=())
        try:
            try:
                raise os_failure(OS_MARKER)
            except OSError as os_error:
                raise LLMError(WRAPPER_MARKER) from os_error
        except LLMError as llm_error:
            raise AssistantError(MARKER, applied_commands=()) from llm_error

    monkeypatch.setattr(assistant_worker, "run_turn", failing_turn)
    controller = Assistant_Controller()
    shown: List[str] = []
    controller.failed.connect(shown.append)
    try:
        with qtbot.waitSignal(
            controller.busyChanged,
            timeout=5000,
            check_params_cb=lambda busy: busy is False,
        ):
            controller.submit(
                Document(8, 8), Conversation(), object()  # type: ignore[arg-type]
            )
        QApplication.processEvents()
    finally:
        controller.shutdown()
    return shown


def _drive_export(
    qtbot,
    monkeypatch,
    controller: Export_Controller,
    out_path,
    failure: BaseException,
) -> List[str]:
    """Fail one export target inside the real batch; return what the controller says.

    ``export_document`` is made to raise ``failure``; the real ``run_batch``
    captures it with the exception it carries, and the real worker and
    controller turn it into the message the export dialog shows.
    """

    def raising(document, request):
        raise failure

    monkeypatch.setattr(logic_export, "export_document", raising)
    document = Document(16, 16, palette=Palette([(0, 0, 0, 255), (255, 255, 255, 255)]))
    target = ExportTarget(ExportRequest(ExportFormat.PNG), str(out_path), "target")
    shown: List[str] = []
    controller.targetFailed.connect(lambda _index, message: shown.append(message))
    with qtbot.waitSignal(controller.batchFinished, timeout=5000):
        controller.submit(document, (target,))
    return shown


def _assert_only_the_sentence(
    shown: List[str], expected: str, names: Tuple[str, ...]
) -> None:
    """Fail unless one message was shown, equal to ``expected``, naming no ``names``."""
    assert len(shown) == 1, f"{len(shown)} messages were shown, not one: {shown!r}"
    assert shown[0] == expected, f"shown {shown[0]!r}, the catalogue holds {expected!r}"
    for text in names:
        assert text not in shown[0], f"{text!r} is shown in {shown[0]!r}"


@pytest.mark.parametrize("code", LANGUAGES_UNDER_TEST)
@pytest.mark.parametrize(
    "label, os_failure, kind", OS_FAILURES, ids=[row[0] for row in OS_FAILURES]
)
def test_an_assistant_turn_that_failed_on_an_operating_system_error_says_which(
    qtbot, monkeypatch, language, code, label, os_failure, kind
):
    """REQ-L10N-UI-018: the assistant dock's sentence names what really failed.

    The turn fails with an ``AssistantError`` raised from the LLM port's own error,
    raised from ``os_failure``. The sentence shown is the one for that failure
    (not "a value was not valid", which is what the two ``ValueError`` wrappers
    alone would give), and none of the three markers or class names is in it.
    """
    language(code)
    shown = _drive_assistant(qtbot, monkeypatch, os_failure)
    _assert_only_the_sentence(
        shown,
        _sentence(code, kind),
        (
            MARKER,
            OS_MARKER,
            WRAPPER_MARKER,
            "AssistantError",
            "LLMError",
            os_failure.__name__,
        ),
    )


@pytest.mark.parametrize("code", LANGUAGES_UNDER_TEST)
def test_an_assistant_turn_that_failed_with_no_cause_is_an_invalid_value(
    qtbot, monkeypatch, language, code
):
    """REQ-L10N-UI-018: control: an error with no cause keeps its own kind.

    The same path with no operating-system failure behind the error shows the
    invalid-value sentence, so the cases above differ by the cause and by nothing
    else.
    """
    language(code)
    shown = _drive_assistant(qtbot, monkeypatch, None)
    _assert_only_the_sentence(
        shown, _sentence(code, "INVALID_VALUE"), (MARKER, "AssistantError")
    )


def _export_error_from(os_failure: OSError) -> BaseException:
    """Return the engine's own ``ExportError`` raised ``from`` ``os_failure``."""
    error = ExportError(MARKER)
    error.__cause__ = os_failure
    return error


#: (a label, the failure the engine raises, the kind of the sentence shown): what the
#: export worker carries from the failed target decides the sentence, wrapped or not.
EXPORT_FAILURES: List[Tuple[str, BaseException, str]] = [
    (
        "an engine error from a missing file",
        _export_error_from(FileNotFoundError(OS_MARKER)),
        "NOT_FOUND",
    ),
    (
        "an engine error from a denied folder",
        _export_error_from(PermissionError(OS_MARKER)),
        "PERMISSION",
    ),
    ("an engine error with no cause", ExportError(MARKER), "INVALID_VALUE"),
    ("a denied folder, raw", PermissionError(MARKER), "PERMISSION"),
    ("a timeout, raw", TimeoutError(MARKER), "TIMEOUT"),
    ("a reset connection, raw", ConnectionResetError(MARKER), "CONNECTION"),
    ("a value error, raw", ValueError(MARKER), "INVALID_VALUE"),
    ("an unforeseen error, raw", RuntimeError(MARKER), "GENERIC"),
]


@pytest.mark.parametrize("code", LANGUAGES_UNDER_TEST)
@pytest.mark.parametrize(
    "label, failure, kind", EXPORT_FAILURES, ids=[row[0] for row in EXPORT_FAILURES]
)
def test_an_export_target_that_failed_is_shown_as_the_sentence_of_its_exception(
    qtbot,
    monkeypatch,
    export_controller,
    tmp_path,
    language,
    code,
    label,
    failure,
    kind,
):
    """REQ-L10N-UI-018: a failed export target says what failed, not "generic".

    The engine raises ``failure`` for the target; the batch carries the exception
    and the worker gives its class and cause chain to the classifier. The one
    message the controller reports is the sentence of ``kind``, and neither marker
    nor the exception's class name is in it. The unforeseen error stays the generic
    sentence, so the rows differ by the exception and by nothing else.
    """
    language(code)
    shown = _drive_export(
        qtbot, monkeypatch, export_controller, tmp_path / "a.png", failure
    )
    _assert_only_the_sentence(
        shown,
        _sentence(code, kind),
        (MARKER, OS_MARKER, type(failure).__name__, "ExportError"),
    )


@pytest.mark.parametrize("path", ("assistant", "export"))
def test_a_leak_on_the_assistant_and_export_paths_is_caught(
    qtbot, monkeypatch, export_controller, tmp_path, path
):
    """Control: with the text seam planted to show ``str(exc)``, both paths fail.

    The planted ``failure_text`` returns what a site showing the exception's text
    with its type name would show; the same drivers and the same verdict must then
    reject the message, because it is not the sentence and holds the marker.
    """
    leaked = f"{PLANTED_TYPE}: {MARKER}"
    monkeypatch.setattr(failure_messages, "failure_text", lambda kind: leaked)
    if path == "assistant":
        shown = _drive_assistant(qtbot, monkeypatch, FileNotFoundError)
    else:
        shown = _drive_export(
            qtbot,
            monkeypatch,
            export_controller,
            tmp_path / "a.png",
            ExportError(MARKER),
        )
    assert any(MARKER in text for text in shown), f"the plant did not reach {path}"
    with pytest.raises(AssertionError):
        _assert_only_the_sentence(shown, _sentence("en", "NOT_FOUND"), (MARKER,))
