"""UI/integration test suite (pytest-qt, headless, both themes).

One test per Phase-1 UI acceptance criterion (Gherkin scenario) from
``specs/phase-1-ui-canvas/spec.md`` §11, driven headlessly under
``QT_QPA_PLATFORM=offscreen`` and parametrised over the light and dark themes
(REQ-P1-UI-025). See ``conftest.py`` for the shared fixtures.
"""
