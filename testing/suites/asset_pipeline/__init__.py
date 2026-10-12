"""Tests of the repository's asset-pipeline scripts (icon deriver, font build
and lint scripts, theme contrast check).

This root is a sibling of ``testing/suites/scripts/`` on purpose: that root
holds the contract tests of the repository's CI gate scripts, while the tests
here belong to the scripts that PRODUCE or MEASURE shipped art and data (the
app-icon family, the Nifen Art font, the theme contrast matrix). Keeping the
two apart lets each root name its own owner without a shared directory.

Like its sibling, every module here runs a script as a real subprocess (the
documented command-line entry point) or reads the committed assets directly;
nothing here mutates a committed file - checks that need a modified tree work
on a copy under ``tmp_path``.
"""
