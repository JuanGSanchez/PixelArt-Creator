"""PixelArt Creator — unified pixel-art platform (roadmap Phases 1-4).

Three-layer architecture (S11): ui/ (PySide6) - logic/ (pure Python, zero Qt) -
data/ (I/O, zero Qt). The only Qt-dependent file outside ui/ is ui/commands.py.
"""

__version__ = "0.1.0"
