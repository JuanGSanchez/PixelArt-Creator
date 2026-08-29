"""Package marker restoring the identity chain for testing/.

This file must exist so the ``testing`` package chain is unbroken from
``testing/suites/ui/`` up to the repository root, exactly as it was
before commit a98f61f moved ``tests/`` -> ``testing/suites/``.

Without it, pytest's conftest-plugin loader walks upward from a
conftest.py while ``__init__.py`` files exist, and names the resulting
plugin module relative to the first directory that lacks one. With
``testing/__init__.py`` missing, that walk stopped at ``testing/`` and
pytest registered ``testing/suites/ui/conftest.py`` as the module
``suites.ui.conftest`` -- a DIFFERENT module object than the one named
by an explicit ``from testing.suites.ui.conftest import ...`` inside a
test, which resolves through the implicit namespace package
``testing``. Two module objects meant two distinct copies of any
module-level state (e.g. a shared registry set), so a fixture writing
to one was invisible to a test reading the other.

Deleting this file silently re-splits every explicitly-imported
conftest under ``testing/`` into two modules again. Do not delete it
as an "empty" file -- its only job is to exist.
"""
