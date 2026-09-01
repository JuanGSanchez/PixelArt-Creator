# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Package launch hook so ``python -m pixelart_creator`` starts the GUI.

Thin shim only — the real launcher lives in :func:`pixelart_creator.ui.app.main`.
"""

from __future__ import annotations

import sys

from pixelart_creator.ui.app import main

if __name__ == "__main__":
    sys.exit(main())
