"""Tests for pixelart_creator.data.llm.port (Phase-14, no Qt).

Covers the one model-agnostic ``LLMPort`` ABC + its ``LLMError`` family
(ADR-0040 §1/§3; spec REQ-P14-DATA-001/-007; acceptance SC-D001-1 / SC-D007-1):

* the ABC cannot be instantiated directly and ``respond`` is abstract;
* ``is_configured`` defaults to ``False`` (credential-optional posture);
* the ``LLMError`` hierarchy (LLMError <- ValueError; the two subclasses <- LLMError);
* the PROVIDER-AGNOSTIC guarantee — a structural inspection asserting the public
  signatures of ``respond`` / ``is_configured`` carry ONLY the wire-neutral
  ``logic`` value types (no provider SDK / HTTP / urllib / credential type);
* the port module executes nothing (Article VII — no eval/exec/http import);
* ``LLMPort`` structurally satisfies the logic-side ``ChatBackend`` Protocol.

Pure ``data`` unit — no Qt, no network, no key.
"""

from __future__ import annotations

import inspect
import typing

import pytest

from pixelart_creator.data.llm.port import (
    LLMError,
    LLMNotConfiguredError,
    LLMPort,
    LLMResponseError,
)
from pixelart_creator.logic.assistant import (
    AssistantReply,
    ChatBackend,
    Conversation,
    ToolDescriptor,
)

# --- ABC contract ----------------------------------------------------------- #


def test_llmport_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        LLMPort()  # type: ignore[abstract]


def test_respond_is_abstract():
    assert "respond" in LLMPort.__abstractmethods__


def test_is_configured_default_false():
    # A concrete subclass that only implements the abstract verb inherits the
    # provider-agnostic default (credential-optional posture, SC-D006-2).
    class _Bare(LLMPort):
        def respond(self, conversation, tools):  # noqa: ANN001 - test stub
            return AssistantReply.final("ok")

    assert _Bare().is_configured() is False


# --- exception family ------------------------------------------------------- #


def test_llm_error_is_value_error():
    assert issubclass(LLMError, ValueError)


def test_not_configured_and_response_errors_are_llm_errors():
    assert issubclass(LLMNotConfiguredError, LLMError)
    assert issubclass(LLMResponseError, LLMError)


def test_errors_are_raisable_and_catchable_as_base():
    for exc in (LLMNotConfiguredError, LLMResponseError):
        with pytest.raises(LLMError):
            raise exc("boom")


# --- PROVIDER-AGNOSTIC signature inspection (SC-D001-1 / REQ-P14-DATA-007) --- #


def _flatten_types(annotation) -> set:
    """Recursively collect the concrete classes referenced by a type annotation."""
    found: set = set()
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is not None:
        # e.g. Sequence[ToolDescriptor] -> record args, ignore the generic origin.
        for a in args:
            found |= _flatten_types(a)
    elif isinstance(annotation, type):
        found.add(annotation)
    return found


# The ONLY types the model-agnostic port is allowed to speak in its public
# signatures — the wire-neutral logic value types (+ the bool status). No
# provider SDK type, no urllib/HTTP type, no credential/token type.
_ALLOWED_WIRE_TYPES = {Conversation, ToolDescriptor, AssistantReply, bool}


def test_port_signatures_carry_only_wire_neutral_types():
    hints_respond = typing.get_type_hints(LLMPort.respond)
    hints_configured = typing.get_type_hints(LLMPort.is_configured)

    referenced: set = set()
    for hints in (hints_respond, hints_configured):
        for name, annotation in hints.items():
            referenced |= _flatten_types(annotation)

    leaked = referenced - _ALLOWED_WIRE_TYPES
    assert not leaked, f"non-wire-neutral type(s) leaked into the port API: {leaked}"


def test_port_signature_names_no_provider_or_transport_token():
    # Belt-and-braces: the RAW signature/annotation text names no provider,
    # transport, or credential vocabulary.
    src = inspect.getsource(LLMPort.respond) + inspect.getsource(LLMPort.is_configured)
    lowered = src.lower()
    # Inspect only the signature lines (annotations), not the docstrings which
    # legitimately DISCUSS these concepts.
    sig_text = (
        str(inspect.signature(LLMPort.respond)).lower()
        + str(inspect.signature(LLMPort.is_configured)).lower()
    )
    for banned in (
        "openai",
        "anthropic",
        "urllib",
        "http",
        "requests",
        "keyring",
        "token",
        "apikey",
        "api_key",
        "credential",
        "bearer",
    ):
        assert banned not in sig_text, f"{banned!r} appears in a port signature"
    assert "def respond" in lowered  # sanity: we actually inspected the source


# --- Article VII: the port executes nothing --------------------------------- #


def test_port_module_has_no_execution_or_http_import():
    import pixelart_creator.data.llm.port as mod

    src = inspect.getsource(mod)
    for forbidden in (
        "eval(",
        "exec(",
        "compile(",
        "__import__(",
        "import urllib",
        "import requests",
        "import http",
        "os.system",
        "subprocess",
    ):
        assert forbidden not in src, f"unexpected {forbidden!r} in port.py"


# --- ChatBackend structural satisfaction (ADR-0040 §2 bridge) --------------- #


def test_llmport_subclass_structurally_satisfies_chatbackend():
    class _Concrete(LLMPort):
        def respond(self, conversation, tools):  # noqa: ANN001 - test stub
            return AssistantReply.final("ok")

    # runtime_checkable Protocol -> a concrete LLMPort IS a ChatBackend without
    # any logic->data import (the 14C loop stays logic-pure).
    assert isinstance(_Concrete(), ChatBackend)
