"""Entry point for the desktop GUI build of Left4Translate.

The packaged windowed ``.exe`` targets this module via PyInstaller. The
command-line app remains ``src/main.py`` and is built from ``Left4Translate.spec``.
"""

from __future__ import annotations

import sys

from gui.app import run


if __name__ == "__main__":
    sys.exit(run())
