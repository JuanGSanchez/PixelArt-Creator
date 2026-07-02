"""PySide6 presentation layer (S11).

Every Qt import in the project lives under this package. UI modules bind to the
Qt-free ``logic/`` + ``data/`` API and add **zero** domain logic (Article I);
the sole Qt-dependent module the constitution permits outside a pure widget is
``ui/commands.py`` (the single ``QUndoCommand`` bridge), which also lives here.
"""
