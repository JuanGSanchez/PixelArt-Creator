"""Tests for pixelart_creator.data.llm.token_store (Phase-14, no Qt).

Covers the OS-keyring API-key isolation contract for the assistant providers
(ADR-0040 §5; spec REQ-P14-DATA-003/-006; acceptance SC-D003-1/-2, SC-D006-1,
Article VII §3). The real OS keyring is NEVER touched — every test injects a fake
``keyring`` module or simulates its absence:

* the ``keyring`` import is LAZY — not bound at module load, so 14A-14C + the fake
  adapter import and run without the package (SC-D003-2);
* with ``keyring`` absent, every op raises ``TokenStoreError`` and
  ``is_keyring_available`` returns ``False``;
* the ``pixelart-creator:assistant:{provider}`` keying scheme (DISTINCT from cloud);
* store / load / delete round-trips against an injected fake backend, incl. the
  idempotent-delete branch and backend-error normalisation;
* the key is NEVER returned in / written to any log, stdout, or exception repr;
* a Hypothesis round-trip over generated provider/account/token strings.

Pure ``data`` unit — no Qt, no network, no real key.
"""

from __future__ import annotations

import builtins
import logging
import sys
import types

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data.llm import token_store as ts
from pixelart_creator.data.llm.port import LLMError
from pixelart_creator.data.llm.token_store import (
    SERVICE_NAME_TEMPLATE,
    TokenStoreError,
    delete_token,
    is_keyring_available,
    load_token,
    service_name,
    store_token,
)

# A recognisable secret used to assert it never leaks to a log/stdout/repr.
_SECRET = "sk-SUPER-SECRET-KEY-do-not-log-12345"


# --- lazy-import contract (SC-D003-2) --------------------------------------- #


def test_keyring_import_is_lazy_not_module_level():
    # The module must NOT bind `keyring` at load time; it imports inside the
    # functions so 14A-14C + the fake adapter run without the package installed.
    assert not hasattr(ts, "keyring")


def test_llm_subpackage_import_did_not_pull_in_keyring_at_module_level():
    # Importing data.llm.token_store alone must not force keyring into sys.modules
    # (only the ops do, lazily). If keyring happens to be installed the probe below
    # may load it; this asserts the *module-body* did not.
    src = __import__("inspect").getsource(ts)
    # The only imports of keyring are inside functions (indented), never top-level.
    for line in src.splitlines():
        if line.startswith("import keyring") or line.startswith("from keyring"):
            raise AssertionError("keyring is imported at module top level")


# --- service-name keying scheme (ADR-0040 §5) ------------------------------- #


def test_service_name_scheme_is_assistant_namespaced():
    assert service_name("openai") == "pixelart-creator:assistant:openai"
    assert service_name("openai") == SERVICE_NAME_TEMPLATE.format(provider="openai")
    # DISTINCT from the cloud store namespace (never collides).
    assert "assistant" in service_name("openai")
    assert ":cloud:" not in service_name("openai")


def test_service_name_rejects_empty_provider():
    with pytest.raises(TokenStoreError):
        service_name("")


# --- exception hierarchy ---------------------------------------------------- #


def test_token_store_error_is_llm_error():
    assert issubclass(TokenStoreError, LLMError)
    assert issubclass(TokenStoreError, ValueError)


# --- keyring ABSENT: graceful degradation ----------------------------------- #


@pytest.fixture
def keyring_absent(monkeypatch):
    """Simulate ``keyring`` not being installed for the duration of a test."""
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "keyring":
            raise ImportError("no keyring in this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "keyring", raising=False)
    monkeypatch.setattr(builtins, "__import__", _fake_import)
    return None


def test_is_keyring_available_false_when_absent(keyring_absent):
    assert is_keyring_available() is False


def test_store_load_delete_raise_when_keyring_absent(keyring_absent):
    with pytest.raises(TokenStoreError):
        store_token("openai", "acct", _SECRET)
    with pytest.raises(TokenStoreError):
        load_token("openai", "acct")
    with pytest.raises(TokenStoreError):
        delete_token("openai", "acct")


def test_missing_keyring_error_does_not_leak_a_key(keyring_absent):
    try:
        store_token("openai", "acct", _SECRET)
    except TokenStoreError as exc:
        assert _SECRET not in str(exc)
    else:  # pragma: no cover - store must raise when keyring absent
        raise AssertionError("expected TokenStoreError")


# --- keyring PRESENT: injected fake backend --------------------------------- #


class PasswordDeleteError(Exception):
    """Named exactly as keyring's, so token_store's idempotent branch matches."""


@pytest.fixture
def fake_keyring(monkeypatch):
    """Inject a fake ``keyring`` module (never touches the real OS store)."""
    store: dict = {}

    module = types.ModuleType("keyring")

    def set_password(service, account, token):
        store[(service, account)] = token

    def get_password(service, account):
        return store.get((service, account))

    def delete_password(service, account):
        if (service, account) not in store:
            raise PasswordDeleteError("no such password")
        del store[(service, account)]

    module.set_password = set_password
    module.get_password = get_password
    module.delete_password = delete_password
    monkeypatch.setitem(sys.modules, "keyring", module)
    return store


def test_is_keyring_available_true_when_present(fake_keyring):
    assert is_keyring_available() is True


def test_store_then_load_round_trip(fake_keyring):
    store_token("openai", "acct", _SECRET)
    assert load_token("openai", "acct") == _SECRET
    assert fake_keyring[("pixelart-creator:assistant:openai", "acct")] == _SECRET


def test_load_absent_returns_none(fake_keyring):
    assert load_token("openai", "missing") is None


def test_delete_removes_token(fake_keyring):
    store_token("openai", "acct", _SECRET)
    delete_token("openai", "acct")
    assert load_token("openai", "acct") is None


def test_delete_absent_is_idempotent(fake_keyring):
    # The PasswordDeleteError branch: deleting a missing credential is a no-op.
    delete_token("openai", "never-stored")  # must NOT raise


def test_store_normalises_backend_error(fake_keyring, monkeypatch):
    def _boom(service, account, token):
        raise RuntimeError("backend down")

    monkeypatch.setattr(sys.modules["keyring"], "set_password", _boom)
    with pytest.raises(TokenStoreError):
        store_token("openai", "acct", _SECRET)


def test_load_normalises_backend_error(fake_keyring, monkeypatch):
    def _boom(service, account):
        raise RuntimeError("backend down")

    monkeypatch.setattr(sys.modules["keyring"], "get_password", _boom)
    with pytest.raises(TokenStoreError):
        load_token("openai", "acct")


def test_delete_reraises_non_delete_error(fake_keyring, monkeypatch):
    def _boom(service, account):
        raise RuntimeError("backend down")

    monkeypatch.setattr(sys.modules["keyring"], "delete_password", _boom)
    with pytest.raises(TokenStoreError):
        delete_token("openai", "acct")


# --- input validation ------------------------------------------------------- #


def test_store_rejects_empty_account_or_token(fake_keyring):
    with pytest.raises(TokenStoreError):
        store_token("openai", "", "tok")
    with pytest.raises(TokenStoreError):
        store_token("openai", "acct", "")


# --- the key is NEVER logged / printed / in a repr (Article VII §3) --------- #


def test_key_never_appears_in_logs_stdout_or_repr(fake_keyring, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    store_token("openai", "acct", _SECRET)
    loaded = load_token("openai", "acct")
    delete_token("openai", "acct")

    # Nothing wrote the secret to logs or stdout/stderr.
    assert _SECRET not in caplog.text
    captured = capsys.readouterr()
    assert _SECRET not in captured.out
    assert _SECRET not in captured.err

    # The functions carry no repr that embeds the secret.
    for fn in (store_token, load_token, delete_token, service_name):
        assert _SECRET not in repr(fn)
    # (The value did round-trip through the backend, proving we tested the real path.)
    assert loaded == _SECRET


def test_backend_error_message_does_not_leak_the_key(fake_keyring, monkeypatch):
    # Even when a backend blows up, the normalised TokenStoreError must not embed
    # the secret in its message (our store passes only the backend exc through,
    # and the fake backend never echoes the token).
    def _boom(service, account, token):
        raise RuntimeError("write failed")

    monkeypatch.setattr(sys.modules["keyring"], "set_password", _boom)
    with pytest.raises(TokenStoreError) as ei:
        store_token("openai", "acct", _SECRET)
    assert _SECRET not in str(ei.value)


# --- Hypothesis: round-trip over generated provider/account/token ----------- #

# Non-empty printable strings without the ':' that structures the service name,
# so we exercise a wide input space against the injected fake backend.
_safe_text = st.text(
    alphabet=st.characters(
        min_codepoint=33, max_codepoint=126, blacklist_characters=":"
    ),
    min_size=1,
    max_size=40,
)


@given(provider=_safe_text, account=_safe_text, token=_safe_text)
def test_store_load_round_trip_property(provider, account, token):
    # Fresh injected fake backend per example (no real keyring, no cross-talk).
    store: dict = {}
    module = types.ModuleType("keyring")
    module.set_password = lambda s, a, t: store.__setitem__((s, a), t)
    module.get_password = lambda s, a: store.get((s, a))
    module.delete_password = lambda s, a: store.pop((s, a), None)

    saved = sys.modules.get("keyring")
    sys.modules["keyring"] = module
    try:
        store_token(provider, account, token)
        assert load_token(provider, account) == token
        # Stored under the assistant-namespaced service name.
        assert store[(service_name(provider), account)] == token
    finally:
        if saved is not None:
            sys.modules["keyring"] = saved
        else:
            sys.modules.pop("keyring", None)
