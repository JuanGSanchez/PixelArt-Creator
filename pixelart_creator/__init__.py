# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""PixelArt Creator — unified pixel-art platform (roadmap Phases 1-14).

Three-layer architecture (S11): ui/ (PySide6) - logic/ (pure Python, zero Qt) -
data/ (I/O, zero Qt). The only Qt-dependent file outside ui/ is ui/commands.py.
"""

__version__ = "0.2.1"
