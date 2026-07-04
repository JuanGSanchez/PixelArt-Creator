"""Tests for pixelart_creator.data.cloud.token_store (Phase-10 Slice A, no Qt).

Covers the OS-keyring token-isolation contract (REQ-P10-DATA-008, CL-B3,
Article VII §3):

* the ``keyring`` import is **lazy** — not triggered at module load, so Slice A
  imports and runs without the package;
* with ``keyring`` *absent*, every op raises ``TokenStoreError`` and
  ``is_keyring_available`` returns ``False`` (simulated by patching the import);
* the ``service_name`` keying scheme, and store/load/delete driven against an
  injected fake keyring (never the real OS credential store), including the
  idempotent-delete branch.
"""

from __future__ import annotations

import builtins
import sys
import types

import pytest

from pixelart_creator.data.cloud import token_store as ts
from pixelart_creator.data.cloud.port import CloudError
from pixelart_creator.data.cloud.token_store import (
    SERVICE_NAME_TEMPLATE,
    TokenStoreError,
    delete_token,
    is_keyring_available,
    load_token,
    service_name,
    store_token,
)

# --- lazy-import contract --------------------------------------------------- #


def test_keyring_import_is_lazy_not_module_level():
    # The module must NOT bind `keyring` at load time; it imports inside the
    # functions (so Slice A runs without the package installed).
    assert not hasattr(ts, "keyring")


# --- service-name keying scheme (CL-B3) ------------------------------------- #


def test_service_name_scheme():
    assert service_name("drive") == "pixelart-creator:cloud:drive"
    assert service_name("drive") == SERVICE_NAME_TEMPLATE.format(provider="drive")


def test_service_name_rejects_empty_provider():
    with pytest.raises(TokenStoreError):
        service_name("")


# --- exception hierarchy ---------------------------------------------------- #


def test_token_store_error_is_cloud_error():
    assert issubclass(TokenStoreError, CloudError)
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
        store_token("drive", "acct", "secret")
    with pytest.raises(TokenStoreError):
        load_token("drive", "acct")
    with pytest.raises(TokenStoreError):
        delete_token("drive", "acct")


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
    store_token("drive", "acct", "s3cr3t")
    assert load_token("drive", "acct") == "s3cr3t"
    assert fake_keyring[("pixelart-creator:cloud:drive", "acct")] == "s3cr3t"


def test_load_absent_returns_none(fake_keyring):
    assert load_token("drive", "missing") is None


def test_delete_removes_token(fake_keyring):
    store_token("drive", "acct", "x")
    delete_token("drive", "acct")
    assert load_token("drive", "acct") is None


def test_delete_absent_is_idempotent(fake_keyring):
    # The PasswordDeleteError branch: deleting a missing credential is a no-op.
    # The fake backend raises PasswordDeleteError (matched by class name) which
    # token_store swallows.
    delete_token("drive", "never-stored")  # must NOT raise


def test_store_normalises_backend_error(fake_keyring, monkeypatch):
    def _boom(service, account, token):
        raise RuntimeError("backend down")

    monkeypatch.setattr(sys.modules["keyring"], "set_password", _boom)
    with pytest.raises(TokenStoreError):
        store_token("drive", "acct", "x")


def test_load_normalises_backend_error(fake_keyring, monkeypatch):
    def _boom(service, account):
        raise RuntimeError("backend down")

    monkeypatch.setattr(sys.modules["keyring"], "get_password", _boom)
    with pytest.raises(TokenStoreError):
        load_token("drive", "acct")


def test_delete_reraises_non_delete_error(fake_keyring, monkeypatch):
    def _boom(service, account):
        raise RuntimeError("backend down")

    monkeypatch.setattr(sys.modules["keyring"], "delete_password", _boom)
    with pytest.raises(TokenStoreError):
        delete_token("drive", "acct")


# --- input validation ------------------------------------------------------- #


def test_store_rejects_empty_account_or_token(fake_keyring):
    with pytest.raises(TokenStoreError):
        store_token("drive", "", "tok")
    with pytest.raises(TokenStoreError):
        store_token("drive", "acct", "")
