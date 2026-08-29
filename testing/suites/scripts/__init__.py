"""Behavioural contract tests for this repository's own CI gate scripts (AGT-09).

Created by ADR-0047, closing structural-audit finding PA-04 (S1): seven of the
eight gate scripts under ``scripts/`` had no test at all, and a gate that has
never been shown to fail is indistinguishable from one that always passes.
``scripts/*.py`` sits outside the product's own three-layer constitution
(``check_layering.py`` registers ``scripts`` under ``UNGOVERNED_TOPLEVEL`` —
"not shipped, not in the import graph") and outside the container suite's
remit ("product repositories are not units"), so it had no legal test home
until this root was created.

Every module here tests a script's declared CLI **contract** — its
entrypoint, its documented exit-code mapping, and its structured JSON output
— never its private implementation. Each script is invoked either as a real
subprocess (matching its own documented ``ENTRYPOINT``) or via the same
``importlib`` file-load pattern ``testing/suites/deploy/test_run_ci_router.py`` uses
for a ``scripts/`` module with no ``scripts/__init__.py`` to import through.
Fixtures live under ``tmp_path`` and are passed to each script by its own
``--root``/``--xml`` flag; the real repository tree is never the input under
test.

No test in this package carries ``@pytest.mark.integration`` — every script
here runs as an ordinary local subprocess against a temp fixture, so these
tests belong in the default gate alongside the rest of ``testing/suites/``.
"""
