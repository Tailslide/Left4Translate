"""Shared test setup: make the engine (``src/``) and repo root importable.

The engine uses flat imports (``from translator.translation_service import …``)
with ``src/`` on ``sys.path``, mirroring how ``src/main.py`` and the PyInstaller
bundle resolve modules.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)
