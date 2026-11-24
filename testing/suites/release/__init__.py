"""Release-evidence tests: what the branch must still be, measured from git.

Each module here reads the repository's history and its committed files, never the
working tree's uncommitted edits, and each one FAILS - it never skips - when the
history it needs is not there. A clone that cannot answer the question has not
passed it.

The modules are run by their own paths. The folder is a package like every other
root under ``testing/suites/``, so a module imports as
``testing.suites.release.<module>`` and the default collection reaches it.
"""
