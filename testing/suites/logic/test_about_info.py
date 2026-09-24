"""Tests for ``pixelart_creator.logic.about_info`` (Qt-free).

Covers REQ-AV-LOGIC-001 (SC-AV-LOGIC-001-1, -2), the logic half of REQ-AV-UI-001
(``window_title``'s call-time version lookup, C-3) and the logic half of
REQ-AV-UI-007 (``read_platform_facts`` degrading each fact independently, on an
exception or an empty string, per ``platform.version()``/``platform.system()``/
``platform.python_version()``). Binds exactly to the interface contract fixed in
``design-docs/specs/app-version/plan.md`` section 3.2 — module/function names,
dataclass field names, the composed-line layout and slot order below all come
from that contract, not from this test's own invention.

RED-FIRST (NFR-5): ``pixelart_creator/logic/about_info.py`` does
not exist yet at ``a77b5c0``. Every test in this module is expected to fail —
today, with a collection-time ``ModuleNotFoundError`` on the ``import`` below —
until the module is implemented. That is a failure "for the absence of the
feature", not a harness error, and it is the whole point of this file at this
stage of the task.
"""

from __future__ import annotations

import dataclasses
import platform

import pytest
from hypothesis import given
from hypothesis import strategies as st

import pixelart_creator
from pixelart_creator.logic import about_info

# --------------------------------------------------------------------------- #
# constants (plan.md section 3.2) — value elements, never tr()'d               #
# --------------------------------------------------------------------------- #


class TestIdentityConstants:
    """The three addresses and the two identity strings are fixed by spec.md."""

    def test_app_name(self):
        assert about_info.APP_NAME == "PixelArt Creator"

    def test_licence_name(self):
        assert about_info.LICENCE_NAME == "Apache License 2.0"

    def test_repository_url(self):
        assert (
            about_info.REPOSITORY_URL
            == "https://github.com/JuanGSanchez/PixelArt-Creator"
        )

    def test_documentation_url(self):
        assert (
            about_info.DOCUMENTATION_URL
            == "https://juangsanchez.github.io/PixelArt-Creator/"
        )

    def test_releases_url(self):
        assert (
            about_info.RELEASES_URL
            == "https://github.com/JuanGSanchez/PixelArt-Creator/releases"
        )


# --------------------------------------------------------------------------- #
# app_version() — call-time lookup (C-3, NFR-2: never a literal expectation)   #
# --------------------------------------------------------------------------- #


class TestAppVersion:
    def test_returns_the_currently_installed_dunder_version(self, monkeypatch):
        monkeypatch.setattr(pixelart_creator, "__version__", "9.9.9")
        assert about_info.app_version() == "9.9.9"

    def test_is_read_at_call_time_not_bound_once(self, monkeypatch):
        """C-3: a change made *after* about_info is imported must still be seen.

        This is exactly what distinguishes ``about_info.app_version()`` from the
        rejected ``from pixelart_creator import __version__`` idiom (plan.md
        section 2, "Version source" row): that idiom binds at import time and
        would not observe either of the two changes below.
        """
        monkeypatch.setattr(pixelart_creator, "__version__", "1.2.3")
        first = about_info.app_version()
        monkeypatch.setattr(pixelart_creator, "__version__", "4.5.6")
        second = about_info.app_version()
        assert (first, second) == ("1.2.3", "4.5.6")


# --------------------------------------------------------------------------- #
# window_title() — name + version composition (C-2, C-3 at logic level)       #
# --------------------------------------------------------------------------- #


class TestWindowTitle:
    def test_composes_translated_name_and_version_with_one_space(self, monkeypatch):
        monkeypatch.setattr(pixelart_creator, "__version__", "0.3.1")
        assert (
            about_info.window_title("PixelArt Creator") == "PixelArt Creator 0.3.1"
        )

    def test_uses_the_supplied_translated_name_verbatim(self, monkeypatch):
        monkeypatch.setattr(pixelart_creator, "__version__", "0.3.1")
        assert (
            about_info.window_title("Creador de PixelArt")
            == "Creador de PixelArt 0.3.1"
        )

    def test_is_call_time_not_import_time(self, monkeypatch):
        monkeypatch.setattr(pixelart_creator, "__version__", "9.9.9")
        assert about_info.window_title("PixelArt Creator").endswith("9.9.9")
        monkeypatch.setattr(pixelart_creator, "__version__", "8.8.8")
        assert about_info.window_title("PixelArt Creator").endswith("8.8.8")


# --------------------------------------------------------------------------- #
# PlatformFacts — shape (three Optional[str] fields, frozen)                  #
# --------------------------------------------------------------------------- #


class TestPlatformFactsShape:
    def test_is_a_frozen_dataclass_with_the_three_named_fields(self):
        assert dataclasses.is_dataclass(about_info.PlatformFacts)
        field_names = {f.name for f in dataclasses.fields(about_info.PlatformFacts)}
        assert field_names == {"os_name", "os_version", "python_version"}

    def test_is_frozen_against_mutation(self):
        facts = about_info.PlatformFacts(
            os_name="Windows", os_version="10.0.26200", python_version="3.13.1"
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            facts.os_name = "Linux"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# read_platform_facts() — each fact independently None on raise OR "" (REQ-AV-UI-007 logic half) #
# --------------------------------------------------------------------------- #


class TestReadPlatformFacts:
    def test_happy_path_mirrors_the_real_platform_module(self):
        facts = about_info.read_platform_facts()
        assert facts.os_name == platform.system()
        assert facts.os_version == platform.version()
        assert facts.python_version == platform.python_version()

    def test_never_raises(self):
        # Exercised for real, unpatched, on whatever host runs the suite.
        about_info.read_platform_facts()

    def test_os_name_is_none_when_platform_system_raises(self, monkeypatch):
        def _raise():
            raise OSError("simulated platform.system() failure")

        monkeypatch.setattr(platform, "system", _raise)
        assert about_info.read_platform_facts().os_name is None

    def test_os_name_is_none_when_platform_system_is_empty(self, monkeypatch):
        monkeypatch.setattr(platform, "system", lambda: "")
        assert about_info.read_platform_facts().os_name is None

    def test_os_version_is_none_when_platform_version_raises(self, monkeypatch):
        def _raise():
            raise OSError("simulated platform.version() failure")

        monkeypatch.setattr(platform, "version", _raise)
        assert about_info.read_platform_facts().os_version is None

    def test_os_version_is_none_when_platform_version_is_empty(self, monkeypatch):
        monkeypatch.setattr(platform, "version", lambda: "")
        assert about_info.read_platform_facts().os_version is None

    def test_python_version_is_none_when_platform_python_version_raises(
        self, monkeypatch
    ):
        def _raise():
            raise OSError("simulated platform.python_version() failure")

        monkeypatch.setattr(platform, "python_version", _raise)
        assert about_info.read_platform_facts().python_version is None

    def test_python_version_is_none_when_platform_python_version_is_empty(
        self, monkeypatch
    ):
        monkeypatch.setattr(platform, "python_version", lambda: "")
        assert about_info.read_platform_facts().python_version is None

    def test_each_fact_degrades_independently_of_the_others(self, monkeypatch):
        """Only ``platform.version()`` fails; the other two facts stay populated."""

        def _raise():
            raise OSError("simulated platform.version() failure")

        monkeypatch.setattr(platform, "version", _raise)
        facts = about_info.read_platform_facts()
        assert facts.os_version is None
        assert facts.os_name == platform.system()
        assert facts.python_version == platform.python_version()

    def test_every_fact_failing_still_returns_without_raising(self, monkeypatch):
        def _raise():
            raise RuntimeError("simulated total platform failure")

        monkeypatch.setattr(platform, "system", _raise)
        monkeypatch.setattr(platform, "version", _raise)
        monkeypatch.setattr(platform, "python_version", _raise)
        facts = about_info.read_platform_facts()
        assert facts == about_info.PlatformFacts(
            os_name=None, os_version=None, python_version=None
        )


# --------------------------------------------------------------------------- #
# EnvironmentFacts — shape (seven fields, app_name required, rest Optional)    #
# --------------------------------------------------------------------------- #


class TestEnvironmentFactsShape:
    def test_is_a_frozen_dataclass_with_the_seven_named_fields(self):
        assert dataclasses.is_dataclass(about_info.EnvironmentFacts)
        field_names = {
            f.name for f in dataclasses.fields(about_info.EnvironmentFacts)
        }
        assert field_names == {
            "app_name",
            "app_version",
            "os_name",
            "os_version",
            "python_version",
            "qt_version",
            "pyside_version",
        }

    def test_is_frozen_against_mutation(self):
        facts = _known_facts()
        with pytest.raises(dataclasses.FrozenInstanceError):
            facts.app_version = "0.0.0"  # type: ignore[misc]


def _known_facts() -> "about_info.EnvironmentFacts":
    """One EnvironmentFacts instance with every field populated and distinct."""
    return about_info.EnvironmentFacts(
        app_name="PixelArt Creator",
        app_version="0.3.1",
        os_name="Windows",
        os_version="10.0.26200",
        python_version="3.13.1",
        qt_version="6.9.0",
        pyside_version="6.9.0",
    )


# Every field but ``app_name`` is Optional (plan.md 3.2) and therefore a
# candidate for the "missing" side of the Hypothesis property below. Derived
# from the dataclass's own field names — no field name or count is restated
# as an inline literal.
_OPTIONAL_FACT_FIELDS = tuple(
    f.name for f in dataclasses.fields(about_info.EnvironmentFacts) if f.name != "app_name"
)


# --------------------------------------------------------------------------- #
# compose_environment_line() — REQ-AV-LOGIC-001 core                          #
# --------------------------------------------------------------------------- #

_PLACEHOLDER = "unknown"


class TestComposeEnvironmentLine:
    def test_all_known_gives_one_line_in_the_stated_order(self):
        # SC-AV-LOGIC-001-1
        line = about_info.compose_environment_line(_known_facts(), _PLACEHOLDER)
        assert line == (
            "PixelArt Creator 0.3.1; Windows 10.0.26200; "
            "Python 3.13.1; Qt 6.9.0; PySide6 6.9.0"
        )

    def test_result_is_a_single_line(self):
        line = about_info.compose_environment_line(_known_facts(), _PLACEHOLDER)
        assert "\n" not in line
        assert "\r" not in line

    def test_placeholder_appears_only_in_the_missing_slot(self):
        # SC-AV-LOGIC-001-2, one concrete example (qt_version missing)
        facts = dataclasses.replace(_known_facts(), qt_version=None)
        line = about_info.compose_environment_line(facts, _PLACEHOLDER)
        assert line == (
            "PixelArt Creator 0.3.1; Windows 10.0.26200; "
            "Python 3.13.1; Qt unknown; PySide6 6.9.0"
        )

    def test_missing_fact_shown_as_placeholder_when_blank_string_too(self):
        facts = dataclasses.replace(_known_facts(), os_version="")
        line = about_info.compose_environment_line(facts, _PLACEHOLDER)
        assert "unknown" in line

    def test_crlf_inside_a_fact_is_collapsed_no_line_break_survives(self):
        facts = dataclasses.replace(_known_facts(), os_version="10\r\n.0.26200")
        line = about_info.compose_environment_line(facts, _PLACEHOLDER)
        assert "\r" not in line
        assert "\n" not in line

    def test_never_raises_when_every_optional_fact_is_missing(self):
        facts = dataclasses.replace(
            _known_facts(),
            **{name: None for name in _OPTIONAL_FACT_FIELDS},
        )
        line = about_info.compose_environment_line(facts, _PLACEHOLDER)
        assert isinstance(line, str)
        assert "\n" not in line

    def test_uses_the_caller_supplied_placeholder_text(self):
        # CL-AV-6: the placeholder is translated by the caller, not by this fn.
        facts = dataclasses.replace(_known_facts(), python_version=None)
        line = about_info.compose_environment_line(facts, "desconocido")
        assert "desconocido" in line
        assert "unknown" not in line

    @given(missing=st.sets(st.sampled_from(_OPTIONAL_FACT_FIELDS)))
    def test_every_subset_of_missing_facts_shows_the_placeholder_only_there(
        self, missing
    ):
        # SC-AV-LOGIC-001-2, generalised: every subset of the six optional
        # facts may be missing at once, and only those parts show the
        # placeholder, while the rest keep their known value.
        known = _known_facts()
        facts = dataclasses.replace(known, **{name: None for name in missing})
        line = about_info.compose_environment_line(facts, _PLACEHOLDER)

        assert "\n" not in line
        assert "\r" not in line

        for name in _OPTIONAL_FACT_FIELDS:
            if name in missing:
                assert _PLACEHOLDER in line
            else:
                assert str(getattr(known, name)) in line
