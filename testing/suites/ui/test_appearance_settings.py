"""Guard tests: the UI suite never reads or writes the real ``QSettings`` store.

Covers T048 / REQ-VI-UI-002 (NFR-7), ADR-0070 section 8 and ADR-0072 (the scaling
preference is read before ``QApplication`` exists). The product module that will
own the appearance keys (``ui/appearance_settings.py``, T052) does not exist yet,
so these tests exercise the EXACT constructor it is specified to use --
``QSettings(QSettings.defaultFormat(), UserScope, org, app)`` -- directly.

What is proved, and how each proof is controlled:

* **Positive control** -- a key written through the production constructor lands
  in a file under the per-test temporary root (and reads back).
* **Negative control** -- the real store (the registry on Windows, a plist on
  macOS, ``~/.config`` on Linux) is identical before and after, measured by a
  separate, un-redirected process that only READS it. That reader is itself
  controlled: pointed at a store the test controls, it sees a known key and sees
  a later write (``test_snapshot_reader_*``), so "unchanged" cannot mean "blind".
* **Escape control** -- ``QSettings(org, app)`` (two arguments) is native format
  and is NOT moved by ``setDefaultFormat`` / ``setPath`` on Windows and macOS
  (T040 item 10, plan R-19). The test records which side of the root it lands on.
* **Before ``QApplication``** -- a fresh subprocess redirects, writes and reads
  with no application object, then builds one and reads the value again; a second
  subprocess reads it before ITS application exists.
* **The guard fails when the redirect is missing** -- run with no redirect, and
  with a redirect to the wrong place, ``assert_settings_isolated`` must raise.

Every writing test calls :func:`assert_settings_isolated` FIRST, which only reads
``fileName()``, so with the isolation fixture disabled these tests fail before
anything is written. Nothing here touches a real ``.pixproj`` / theme / catalogue,
and the only stores written are inside ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pixelart_creator.ui.app import APPLICATION_NAME, ORGANIZATION_NAME
from testing.suites.ui.conftest import (
    assert_settings_isolated,
    redirect_settings_store,
    settings_location_is_under,
    settings_store_scope,
)

#: The product repository root (``testing/suites/ui/<this file>`` -> four levels).
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: A key in the ``appearance`` group (ADR-0070 item 7) used as the probe.
_PROBE_KEY = "appearance/pixel_perfect"

# --------------------------------------------------------------------------- #
# Subprocess scripts. ``-c`` text, run with the repository root on PYTHONPATH.  #
# --------------------------------------------------------------------------- #

#: Read-only snapshot of one store: file name, format, every key/value, file stat.
#: argv: org app [redirect_dir]. With ``redirect_dir`` it first points the Ini
#: search path there (used ONLY to control the reader itself); without it the
#: store is the one a user's installed application would use.
_SNAPSHOT_SCRIPT = """
import json, os, sys
from PySide6.QtCore import QSettings
org, app = sys.argv[1], sys.argv[2]
if len(sys.argv) > 3:
    for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
        QSettings.setPath(QSettings.Format.IniFormat, scope, sys.argv[3])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
s = QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, org, app)
name = s.fileName()
stat = None
if os.path.isfile(name):
    st = os.stat(name)
    stat = [st.st_size, st.st_mtime_ns]
print(json.dumps({
    "file": name,
    "format": s.format().name,
    "keys": {k: repr(s.value(k)) for k in sorted(s.allKeys())},
    "stat": stat,
}))
"""

#: The production access pattern, BEFORE ``QApplication`` exists. argv: root mode.
#: ``write`` redirects (the conftest's own helper), writes the probe key and then
#: builds an application and reads it again; ``read`` redirects and only reads.
_BEFORE_APP_SCRIPT = """
import json, sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QSettings
from pixelart_creator.ui.app import APPLICATION_NAME, ORGANIZATION_NAME
from testing.suites.ui.conftest import (
    assert_settings_isolated, redirect_settings_store,
)
root, mode, key = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
out = {"app_at_start": QCoreApplication.instance() is not None}
redirect_settings_store(root)
assert_settings_isolated(root)

def production_settings():
    return QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope,
                     ORGANIZATION_NAME, APPLICATION_NAME)

s = production_settings()
out["present_before"] = s.contains(key)
out["value_before"] = s.value(key, True, type=bool)
if mode == "write":
    s.setValue(key, False)
    s.sync()
    out["status"] = s.status().name
    out["writable"] = s.isWritable()
out["file"] = s.fileName()
out["app_before_construct"] = QCoreApplication.instance() is not None
from PySide6.QtWidgets import QApplication
app = QApplication([])
again = production_settings()
out["value_after_app"] = again.value(key, True, type=bool)
out["file_after_app"] = again.fileName()
print(json.dumps(out))
"""

#: The guard run where the redirect is absent or wrong. argv: root redirect_dir|-.
_UNISOLATED_SCRIPT = """
import sys
from pathlib import Path
from testing.suites.ui.conftest import assert_settings_isolated
root = Path(sys.argv[1])
if sys.argv[2] != "-":
    from PySide6.QtCore import QSettings
    for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
        QSettings.setPath(QSettings.Format.IniFormat, scope, sys.argv[2])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    from pixelart_creator.ui.app import APPLICATION_NAME, ORGANIZATION_NAME
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setApplicationName(APPLICATION_NAME)
assert_settings_isolated(root)
print("GUARD-PASSED")
"""


def _run_python(script: str, *args: str) -> subprocess.CompletedProcess:
    """Run ``script`` in a fresh interpreter rooted at THIS checkout.

    ``PYTHONPATH`` leads with the repository root so the child imports this
    worktree's ``pixelart_creator`` and not a sibling's editable install; the
    platform is forced offscreen. Never ``-I``: that would ignore ``PYTHONPATH``.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_REPO_ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-B", "-c", script, *args],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _json_run(script: str, *args: str) -> dict:
    """Run a script that prints one JSON object and return it (fail loud otherwise)."""
    done = _run_python(script, *args)
    assert done.returncode == 0, (
        f"subprocess exit {done.returncode}\nstdout: {done.stdout}\n"
        f"stderr: {done.stderr}"
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def _real_store_snapshot() -> dict:
    """Read-only snapshot of the store the installed application would use."""
    return _json_run(_SNAPSHOT_SCRIPT, ORGANIZATION_NAME, APPLICATION_NAME)


def _production_settings() -> QSettings:
    """The exact constructor ``ui/appearance_settings.py`` is specified to use."""
    return QSettings(
        QSettings.defaultFormat(),
        QSettings.Scope.UserScope,
        ORGANIZATION_NAME,
        APPLICATION_NAME,
    )


# --------------------------------------------------------------------------- #
# The redirect is in force                                                      #
# --------------------------------------------------------------------------- #


def test_req_vi_ui_002_redirect_was_applied_before_any_qapplication(
    _settings_store_session,
):
    """REQ-VI-UI-002: the redirect ran before the process' QApplication existed."""
    assert _settings_store_session.app_existed_at_redirect is False


def test_req_vi_ui_002_production_constructors_resolve_inside_the_temp_root(
    tmp_path,
):
    """REQ-VI-UI-002: both default-format constructors point under ``tmp_path``.

    Requests no suite fixture on purpose: with the isolation fixture disabled the
    expected root is simply never in force and this fails (read-only, no write).
    """
    root = tmp_path / "qsettings"
    assert_settings_isolated(root)
    assert settings_location_is_under(_production_settings().fileName(), tmp_path)
    assert QSettings().fileName() == _production_settings().fileName()
    assert _production_settings().format() == QSettings.Format.IniFormat


def test_req_vi_ui_002_guard_rejects_a_location_outside_the_root(tmp_path):
    """REQ-VI-UI-002: the in-process guard raises for a root that is not in force."""
    elsewhere = tmp_path / "somewhere-else"
    with pytest.raises(AssertionError, match="NOT isolated"):
        assert_settings_isolated(elsewhere)


# --------------------------------------------------------------------------- #
# Positive control: a write lands in the temporary location                     #
# --------------------------------------------------------------------------- #


def test_req_vi_ui_002_positive_control_write_lands_in_the_temp_location(tmp_path):
    """REQ-VI-UI-002: a key written through the production constructor is under tmp."""
    root = tmp_path / "qsettings"
    assert_settings_isolated(root)  # read-only; fails before any write if not isolated

    settings = _production_settings()
    assert not settings.contains(_PROBE_KEY), "the per-test store must start empty"
    settings.setValue(_PROBE_KEY, False)
    settings.sync()
    assert settings.status() == QSettings.Status.NoError

    ini = Path(settings.fileName())
    assert ini.is_file(), f"nothing was written to {ini}"
    assert settings_location_is_under(str(ini), root)
    # The value is really in the file, and a brand-new object (a fresh parse) agrees.
    assert "pixel_perfect" in ini.read_text(encoding="utf-8")
    assert _production_settings().value(_PROBE_KEY, True, type=bool) is False
    # The name-less constructor shares the file, so the product's `QSettings()`
    # users (the provider config dialog) are inside the same isolation.
    assert QSettings().value(_PROBE_KEY, True, type=bool) is False


# --------------------------------------------------------------------------- #
# Negative control: the real store is untouched                                 #
# --------------------------------------------------------------------------- #


def test_snapshot_reader_sees_a_known_key_and_a_later_write(tmp_path):
    """Control of the control: the real-store reader is not blind.

    The reader is pointed at a store this test owns (``redirect_dir``): it must
    return a key written beforehand and must report a later change. Only then does
    "the real store did not change" mean anything.
    """
    control = tmp_path / "reader-control"
    redirect_settings_store(control)  # the autouse fixture re-points it afterwards
    seed = _production_settings()
    seed.setValue("control/known", "seed")
    seed.sync()
    del seed
    before = _json_run(
        _SNAPSHOT_SCRIPT, ORGANIZATION_NAME, APPLICATION_NAME, str(control)
    )
    assert "control/known" in before["keys"]
    assert before["stat"] is not None

    later = _production_settings()
    later.setValue("control/known", "changed")
    later.setValue("control/added", "x")
    later.sync()
    del later
    after = _json_run(
        _SNAPSHOT_SCRIPT, ORGANIZATION_NAME, APPLICATION_NAME, str(control)
    )
    assert after != before
    assert after["keys"]["control/added"] == repr("x")
    assert after["keys"]["control/known"] != before["keys"]["control/known"]


def test_req_vi_ui_002_negative_control_real_store_is_untouched(tmp_path):
    """REQ-VI-UI-002: before/after the real store is identical and has no probe key."""
    root = tmp_path / "qsettings"
    assert_settings_isolated(root)  # no write can happen while this fails

    before = _real_store_snapshot()
    settings = _production_settings()
    settings.setValue(_PROBE_KEY, False)
    settings.setValue("appearance/style", "probe-style")
    settings.sync()
    legacy = QSettings()  # the name-less form
    legacy.setValue("appearance/mode", "probe-mode")
    legacy.sync()
    after = _real_store_snapshot()

    assert after == before, "the real settings store changed during the test"
    assert _PROBE_KEY not in after["keys"]
    assert "appearance/style" not in after["keys"]
    assert "appearance/mode" not in after["keys"]
    # And it really did go to the temp store.
    assert settings_location_is_under(settings.fileName(), root)


def test_req_vi_ui_002_escape_control_two_argument_constructor(tmp_path):
    """REQ-VI-UI-002 / plan R-19: ``QSettings(org, app)`` ignores the redirect.

    Read-only (``fileName`` / ``format`` only; nothing is written). On Windows and
    macOS the two-argument constructor is the registry / ``CFPreferences`` and
    ``setDefaultFormat`` + ``setPath`` do not move it, so it lands OUTSIDE the
    root; on Linux native format is a file and ``setPath`` does move it. The
    product must therefore never use this form for the appearance keys.
    """
    root = tmp_path / "qsettings"
    assert_settings_isolated(root)
    two_arg = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
    assert two_arg.format() == QSettings.Format.NativeFormat
    escaped = not settings_location_is_under(two_arg.fileName(), root)
    if sys.platform in ("win32", "darwin"):
        assert escaped, (
            f"expected the 2-argument constructor to escape the redirect on "
            f"{sys.platform}, but it resolved to {two_arg.fileName()!r}"
        )
    else:
        assert not escaped, (
            "on this platform native format is a file that setPath redirects; it "
            f"resolved to {two_arg.fileName()!r}"
        )


# --------------------------------------------------------------------------- #
# Before QApplication, in a subprocess (ADR-0072's pre-application read)        #
# --------------------------------------------------------------------------- #


def test_req_vi_ui_002_subprocess_writes_and_reads_before_qapplication(tmp_path):
    """REQ-VI-UI-002 / ADR-0072: redirect, write and read with NO application object.

    Process 1 redirects, writes the probe key and reads it with no
    ``QApplication``; it then builds one and reads again. Process 2 (another fresh
    interpreter) reads the value before ITS application exists. The real store is
    snapshotted around both and must not change.
    """
    root = tmp_path / "subprocess-store"
    before = _real_store_snapshot()

    first = _json_run(_BEFORE_APP_SCRIPT, str(root), "write", _PROBE_KEY)
    assert first["app_at_start"] is False
    assert first["app_before_construct"] is False, "QApplication existed too early"
    assert first["present_before"] is False
    assert first["status"] == "NoError" and first["writable"] is True
    assert settings_location_is_under(first["file"], root)
    assert first["value_after_app"] is False, "value lost once QApplication existed"
    assert first["file_after_app"] == first["file"]
    assert Path(first["file"]).is_file()

    second = _json_run(_BEFORE_APP_SCRIPT, str(root), "read", _PROBE_KEY)
    assert second["app_before_construct"] is False
    assert second["present_before"] is True, "second process did not see the value"
    assert second["value_before"] is False

    assert _real_store_snapshot() == before


def test_req_vi_ui_002_guard_fails_when_the_redirect_is_missing(tmp_path):
    """REQ-VI-UI-002: with no redirect, or the wrong one, the guard exits non-zero.

    This is the permanent in-suite form of "shown failing with the fixture
    disabled": the same ``assert_settings_isolated`` the suite relies on, run in a
    fresh interpreter where nothing was redirected (native format) and where the
    redirect points somewhere other than the expected root.
    """
    expected = tmp_path / "expected-root"

    unredirected = _run_python(_UNISOLATED_SCRIPT, str(expected), "-")
    assert unredirected.returncode != 0
    assert "NOT isolated" in unredirected.stderr
    assert "GUARD-PASSED" not in unredirected.stdout

    wrong = tmp_path / "wrong-root"
    misdirected = _run_python(_UNISOLATED_SCRIPT, str(expected), str(wrong))
    assert misdirected.returncode != 0
    assert "NOT isolated" in misdirected.stderr
    assert "outside the isolated root" in misdirected.stderr

    # Positive control for this very test: redirected to the expected root, it passes.
    ok = _run_python(_UNISOLATED_SCRIPT, str(expected), str(expected))
    assert ok.returncode == 0, ok.stderr
    assert "GUARD-PASSED" in ok.stdout


# --------------------------------------------------------------------------- #
# Cleanup per test                                                              #
# --------------------------------------------------------------------------- #


def test_req_vi_ui_002_scope_cleans_up_and_falls_back_to_the_session_root(tmp_path):
    """REQ-VI-UI-002: leaving a scope deletes its directory and re-points elsewhere.

    The fixture is a thin wrapper over :func:`settings_store_scope`; this drives
    it directly so the cleanup is observable inside one test.
    """
    scoped = tmp_path / "scoped"
    fallback = tmp_path / "fallback"
    with settings_store_scope(scoped, fallback) as inner:
        assert_settings_isolated(inner)
        settings = _production_settings()
        settings.setValue(_PROBE_KEY, False)
        settings.sync()
        written = Path(settings.fileName())
        assert written.is_file()
        del settings
    assert not scoped.exists(), "the per-scope settings directory was not removed"
    # Between scopes the search path is the fallback (a temp dir), never the real one.
    assert settings_location_is_under(_production_settings().fileName(), fallback)
    assert fallback.is_dir()
